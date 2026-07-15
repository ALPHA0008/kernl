"""DecisionService: the write-ahead orchestration around the pure evaluator.

Flow (constitutional, CLAUDE.md rule 4):
    evaluate (pure) -> seal event -> append to ledger -> THEN return.
A response the caller sees always corresponds to a committed ledger row.
Ledger unavailability aborts the decision with LedgerUnavailableError
(API layer maps to HTTP 503); no fallback, no fixture, no best-effort.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.bundle.schema import Bundle
from backend.ledger.events import Actor, ChainConflict, DecisionEvent, EventType
from backend.ledger.store import LedgerStore
from backend.runtime.evaluator import EvaluationResult, evaluate

_MAX_CHAIN_CONFLICT_RETRIES = 8


class LedgerUnavailableError(RuntimeError):
    """The ledger cannot be written; the decision is aborted."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class DecisionService:
    def __init__(self, store: LedgerStore) -> None:
        self._store = store

    def decide(
        self,
        *,
        company_id: str,
        workflow: str,
        facts: dict[str, Any],
        actor: Actor,
        idempotency_key: str,
        bundle: Bundle,
        bundle_hash: str,
    ) -> tuple[DecisionEvent, bool]:
        """Evaluate and record. Returns (event, created). If the idempotency
        key was already used, the ORIGINAL event is returned unchanged and
        no evaluation side effects occur (created=False)."""
        existing = self._safe(lambda: self._store.by_idempotency_key(company_id, idempotency_key))
        if existing is not None:
            return existing, False

        result: EvaluationResult = evaluate(facts, bundle, workflow)
        return self._append_sealed(
            lambda: self._seal(
                event_type=EventType.DECISION,
                company_id=company_id,
                workflow=workflow,
                actor=actor,
                idempotency_key=idempotency_key,
                facts=facts,
                result=result,
                bundle_hash=bundle_hash,
                linked_event_id=None,
            )
        )

    def record_adjudication(
        self,
        *,
        company_id: str,
        original_event: DecisionEvent,
        actor: Actor,
        chosen_action: str,
        outcome_kind: str,
        rationale: str,
        idempotency_key: str,
    ) -> tuple[DecisionEvent, bool]:
        """A human ruling on an escalated decision, recorded as its own
        ledgered event linked to the original."""
        if not rationale.strip():
            raise ValueError("adjudication requires a non-empty rationale")
        outcome = {
            "kind": outcome_kind,
            "action": chosen_action,
            "policy_id": None,
            "adjudicated": True,
            "rationale": rationale,
        }
        trace = {
            "trace_version": "1",
            "kind": "adjudication",
            "original_event_id": original_event.event_id,
            "original_outcome": original_event.outcome,
        }
        return self._append_sealed(
            lambda: self._seal_raw(
                event_type=EventType.ADJUDICATION,
                company_id=company_id,
                workflow=original_event.workflow,
                actor=actor,
                idempotency_key=idempotency_key,
                facts=original_event.facts,
                outcome=outcome,
                trace=trace,
                bundle_hash=original_event.bundle_hash,
                linked_event_id=original_event.event_id,
            )
        )

    # -- internals ----------------------------------------------------------

    def _seal(
        self,
        *,
        event_type: EventType,
        company_id: str,
        workflow: str,
        actor: Actor,
        idempotency_key: str,
        facts: dict[str, Any],
        result: EvaluationResult,
        bundle_hash: str,
        linked_event_id: Optional[str],
    ) -> DecisionEvent:
        return self._seal_raw(
            event_type=event_type,
            company_id=company_id,
            workflow=workflow,
            actor=actor,
            idempotency_key=idempotency_key,
            facts=facts,
            outcome=result.outcome.model_dump(mode="json"),
            trace=result.trace.model_dump(mode="json"),
            bundle_hash=bundle_hash,
            linked_event_id=linked_event_id,
        )

    def _seal_raw(
        self,
        *,
        event_type: EventType,
        company_id: str,
        workflow: str,
        actor: Actor,
        idempotency_key: str,
        facts: dict[str, Any],
        outcome: dict[str, Any],
        trace: dict[str, Any],
        bundle_hash: str,
        linked_event_id: Optional[str],
    ) -> DecisionEvent:
        prev = self._safe(lambda: self._store.chain_head(company_id))
        return DecisionEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            company_id=company_id,
            workflow=workflow,
            actor=actor,
            idempotency_key=idempotency_key,
            facts=facts,
            outcome=outcome,
            trace=trace,
            bundle_hash=bundle_hash,
            linked_event_id=linked_event_id,
            created_at=_now_iso(),
            prev_event_hash=prev,
        ).sealed()

    def _append_sealed(self, seal_fn) -> tuple[DecisionEvent, bool]:
        """seal_fn produces a freshly-sealed event (reads the current chain
        head). A ChainConflict means a concurrent writer for the same
        company won the race to the previous head -- re-seal against the
        new head and retry. This keeps sealing (which reads chain_head)
        and appending (which locks + validates it) correct under
        concurrency without holding a lock across the evaluate+seal step."""
        last_exc: Optional[ChainConflict] = None
        for _ in range(_MAX_CHAIN_CONFLICT_RETRIES):
            event = seal_fn()
            try:
                return self._store.append(event)
            except ChainConflict as exc:
                last_exc = exc
                continue
            except ValueError:
                raise
            except Exception as exc:  # storage failure -> abort, never fallback
                raise LedgerUnavailableError(str(exc)) from exc
        raise LedgerUnavailableError(
            f"ledger append lost the race to a concurrent writer "
            f"{_MAX_CHAIN_CONFLICT_RETRIES} times in a row: {last_exc}"
        )

    def _safe(self, fn):
        try:
            return fn()
        except Exception as exc:
            raise LedgerUnavailableError(str(exc)) from exc
