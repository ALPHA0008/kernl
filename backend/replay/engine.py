"""Replay execution: pure evaluation of a case set against a candidate bundle,
scored two ways:

  golden mode -- candidate outcome vs each case's EXPECTED outcome
  diff mode   -- candidate outcome vs a REFERENCE bundle's outcome (flips)

Replay is LLM-free and deterministic by construction (it calls the pure
evaluator). A persisted ReplayRun pins candidate hash, reference hash and
case-set hash so a publish gate can demand "a replay for exactly this draft".
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Optional, Protocol

from pydantic import BaseModel, ConfigDict

from backend.bundle.canonical import bundle_content_hash
from backend.bundle.schema import Bundle
from backend.replay.cases import GoldenCase, case_set_hash
from backend.runtime.evaluator import InvalidFactsError, evaluate


class CaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    workflow: str
    candidate_kind: Optional[str] = None
    candidate_action: Optional[str] = None
    candidate_policy_id: Optional[str] = None
    expected_kind: Optional[str] = None
    expected_action: Optional[str] = None
    reference_kind: Optional[str] = None
    reference_action: Optional[str] = None
    golden_pass: Optional[bool] = None  # None when not scored against expected
    flipped: Optional[bool] = None  # None when no reference bundle
    error: Optional[str] = None  # evaluation error (workflow/type mismatch)


class ReplaySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    total: int
    golden_passed: int
    golden_failed: int
    flips: int
    new_escalations: int
    errors: int


class ReplayRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    company_id: str
    candidate_bundle_hash: str
    reference_bundle_hash: Optional[str]
    case_set_hash: str
    created_at: str
    summary: ReplaySummary
    results: tuple[CaseResult, ...]
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None


class ReplayRunStore(Protocol):
    def add(self, run: ReplayRun) -> ReplayRun: ...
    def get(self, company_id: str, run_id: str) -> Optional[ReplayRun]: ...
    def update(self, run: ReplayRun) -> ReplayRun: ...
    def latest_acknowledged_for(
        self, company_id: str, candidate_bundle_hash: str
    ) -> Optional[ReplayRun]: ...
    def list(self, company_id: str, limit: int = 50) -> list[ReplayRun]: ...


class InMemoryReplayRunStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[tuple[str, str], ReplayRun] = {}

    def add(self, run: ReplayRun) -> ReplayRun:
        with self._lock:
            self._rows[(run.company_id, run.run_id)] = run
            return run

    def get(self, company_id: str, run_id: str) -> Optional[ReplayRun]:
        return self._rows.get((company_id, run_id))

    def update(self, run: ReplayRun) -> ReplayRun:
        with self._lock:
            self._rows[(run.company_id, run.run_id)] = run
            return run

    def latest_acknowledged_for(
        self, company_id: str, candidate_bundle_hash: str
    ) -> Optional[ReplayRun]:
        rows = [
            r for (cid, _), r in self._rows.items()
            if cid == company_id
            and r.candidate_bundle_hash == candidate_bundle_hash
            and r.acknowledged_by is not None
        ]
        rows.sort(key=lambda r: r.created_at, reverse=True)
        return rows[0] if rows else None

    def list(self, company_id: str, limit: int = 50) -> list[ReplayRun]:
        rows = [r for (cid, _), r in self._rows.items() if cid == company_id]
        rows.sort(key=lambda r: r.created_at, reverse=True)
        return rows[:limit]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _outcome_of(bundle: Bundle, case: GoldenCase):
    try:
        result = evaluate(case.facts, bundle, case.workflow)
        return result.outcome, None
    except (KeyError, InvalidFactsError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


class ReplayEngine:
    def __init__(self, run_store: ReplayRunStore) -> None:
        self._runs = run_store

    def run(
        self,
        *,
        company_id: str,
        cases: list[GoldenCase],
        candidate: Bundle,
        reference: Optional[Bundle] = None,
    ) -> ReplayRun:
        if not cases:
            raise ValueError("replay requires a non-empty case set")
        results: list[CaseResult] = []
        golden_passed = golden_failed = flips = new_escalations = errors = 0

        for case in cases:
            cand_outcome, err = _outcome_of(candidate, case)
            ref_outcome = None
            if reference is not None and err is None:
                ref_outcome, ref_err = _outcome_of(reference, case)
                if ref_err is not None:
                    ref_outcome = None

            if err is not None:
                errors += 1
                results.append(
                    CaseResult(case_id=case.case_id, workflow=case.workflow, error=err)
                )
                continue

            assert cand_outcome is not None
            golden_pass: Optional[bool] = None
            if case.expected is not None:
                golden_pass = cand_outcome.kind.value == case.expected.kind and (
                    case.expected.action is None
                    or cand_outcome.action == case.expected.action
                ) and (
                    case.expected.escalation_reason is None
                    or (
                        cand_outcome.escalation_reason is not None
                        and cand_outcome.escalation_reason.value
                        == case.expected.escalation_reason
                    )
                )
                golden_passed += 1 if golden_pass else 0
                golden_failed += 0 if golden_pass else 1

            flipped: Optional[bool] = None
            if ref_outcome is not None:
                flipped = (
                    cand_outcome.kind != ref_outcome.kind
                    or cand_outcome.action != ref_outcome.action
                )
                if flipped:
                    flips += 1
                    if cand_outcome.kind.value == "escalate" and ref_outcome.kind.value != "escalate":
                        new_escalations += 1

            results.append(
                CaseResult(
                    case_id=case.case_id,
                    workflow=case.workflow,
                    candidate_kind=cand_outcome.kind.value,
                    candidate_action=cand_outcome.action,
                    candidate_policy_id=cand_outcome.policy_id,
                    expected_kind=case.expected.kind if case.expected else None,
                    expected_action=case.expected.action if case.expected else None,
                    reference_kind=ref_outcome.kind.value if ref_outcome else None,
                    reference_action=ref_outcome.action if ref_outcome else None,
                    golden_pass=golden_pass,
                    flipped=flipped,
                )
            )

        run = ReplayRun(
            run_id=str(uuid.uuid4()),
            company_id=company_id,
            candidate_bundle_hash=bundle_content_hash(candidate),
            reference_bundle_hash=bundle_content_hash(reference) if reference else None,
            case_set_hash=case_set_hash(cases),
            created_at=_now_iso(),
            summary=ReplaySummary(
                total=len(cases),
                golden_passed=golden_passed,
                golden_failed=golden_failed,
                flips=flips,
                new_escalations=new_escalations,
                errors=errors,
            ),
            results=tuple(results),
        )
        return self._runs.add(run)

    def acknowledge(self, company_id: str, run_id: str, by: str) -> ReplayRun:
        run = self._runs.get(company_id, run_id)
        if run is None:
            raise KeyError(f"unknown replay run {run_id!r}")
        return self._runs.update(
            run.model_copy(update={"acknowledged_by": by, "acknowledged_at": _now_iso()})
        )
