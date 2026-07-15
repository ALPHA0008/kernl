"""Onboarding service: the docs -> cited dashboard flow, orchestrated.

Ties together tenants, source snapshots, and groundable drafts, and assembles
accepted drafts into a real Bundle -- which then goes through the EXISTING
publish path (replay gate -> ledger). Nothing here bypasses a single V1
guarantee: every published policy is a validated Policy with grounded,
byte-verified evidence.

The bundle assembler infers each workflow's fact schema from the union of the
conditions across its accepted policies (the Bundle integrity check requires
every condition field to be a declared, correctly-typed fact).
"""

from __future__ import annotations

from typing import Any, Optional

from backend.bundle.schema import (
    Bundle,
    FactSpec,
    Policy,
    WorkflowSpec,
)
from backend.onboarding.drafts import (
    DraftStore,
    OnboardingDraft,
    build_draft,
    evaluate_draft,
)
from backend.onboarding.sources import GroundingError, SourceStore, ground_evidence
from backend.onboarding.tenants import TenantService


class AssembleError(ValueError):
    """Accepted drafts cannot be assembled into a valid bundle."""


class OnboardingService:
    def __init__(
        self,
        tenants: TenantService,
        sources: SourceStore,
        drafts: DraftStore,
    ) -> None:
        self.tenants = tenants
        self.sources = sources
        self.drafts = drafts

    # ---------------------------------------------------------------- drafts

    def save_draft(
        self,
        company_id: str,
        proposed: dict[str, Any],
        *,
        origin: str = "authored",
        source_skill_id: Optional[str] = None,
        draft_id: Optional[str] = None,
    ) -> OnboardingDraft:
        """Create or replace a draft's proposed policy, preserving any evidence
        already grounded on it. Re-evaluates publishability."""
        existing = self.drafts.get(company_id, draft_id) if draft_id else None
        evidence = existing.evidence_json if existing else ()
        draft = build_draft(
            company_id,
            proposed,
            origin=origin,
            source_skill_id=source_skill_id or (existing.source_skill_id if existing else None),
            evidence=evidence,
            draft_id=draft_id,
        )
        if existing:
            draft = draft.model_copy(update={"created_at": existing.created_at})
        return self.drafts.upsert(draft)

    def ground_span(
        self,
        company_id: str,
        draft_id: str,
        source_id: str,
        span_start: int,
        span_end: int,
        excerpt: str,
    ) -> OnboardingDraft:
        """Verify a selected source span and attach it as evidence to the draft.
        Raises GroundingError if the span does not match the source bytes."""
        draft = self.drafts.get(company_id, draft_id)
        if draft is None:
            raise KeyError(f"unknown draft {draft_id!r}")
        snapshot = self.sources.get(company_id, source_id)
        if snapshot is None:
            raise KeyError(f"unknown source {source_id!r}")
        evidence = ground_evidence(snapshot, span_start, span_end, excerpt)
        ev_json = draft.evidence_json + (evidence.model_dump(mode="json"),)
        publishable, issues = evaluate_draft(draft.proposed_json, ev_json)
        updated = draft.model_copy(
            update={
                "evidence_json": ev_json,
                "publishable": publishable,
                "issues_json": issues,
                "updated_at": _now(),
            }
        )
        return self.drafts.upsert(updated)

    def remove_evidence(self, company_id: str, draft_id: str, index: int) -> OnboardingDraft:
        draft = self.drafts.get(company_id, draft_id)
        if draft is None:
            raise KeyError(f"unknown draft {draft_id!r}")
        if index < 0 or index >= len(draft.evidence_json):
            raise ValueError("evidence index out of range")
        ev_json = draft.evidence_json[:index] + draft.evidence_json[index + 1 :]
        publishable, issues = evaluate_draft(draft.proposed_json, ev_json)
        return self.drafts.upsert(
            draft.model_copy(
                update={
                    "evidence_json": ev_json,
                    "publishable": publishable,
                    "issues_json": issues,
                    "updated_at": _now(),
                }
            )
        )

    def set_status(self, company_id: str, draft_id: str, status: str) -> OnboardingDraft:
        draft = self.drafts.get(company_id, draft_id)
        if draft is None:
            raise KeyError(f"unknown draft {draft_id!r}")
        if status == "accepted" and not draft.publishable:
            raise ValueError(
                "cannot accept a draft that is not publishable: "
                + "; ".join(draft.issues_json)
            )
        return self.drafts.upsert(
            draft.model_copy(update={"status": status, "updated_at": _now()})
        )

    # -------------------------------------------------------------- assemble

    def assemble_bundle(self, company_id: str) -> Bundle:
        """Assemble all ACCEPTED drafts into a validated Bundle. Infers each
        workflow's fact schema from the conditions of its policies."""
        accepted = self.drafts.list(company_id, status="accepted")
        if not accepted:
            raise AssembleError("no accepted drafts to assemble")

        policies: list[Policy] = []
        for d in accepted:
            candidate = {**d.proposed_json, "evidence": list(d.evidence_json)}
            try:
                policies.append(Policy.model_validate(candidate))
            except Exception as exc:  # noqa: BLE001
                raise AssembleError(
                    f"accepted draft {d.draft_id!r} is not a valid policy: {exc}"
                ) from exc

        workflows = _infer_workflows(policies)
        try:
            return Bundle(
                company_id=company_id,
                workflows=tuple(workflows),
                policies=tuple(policies),
            )
        except Exception as exc:  # noqa: BLE001
            raise AssembleError(f"assembled bundle failed integrity: {exc}") from exc


def _infer_workflows(policies: list[Policy]) -> list[WorkflowSpec]:
    """Derive a WorkflowSpec per workflow: every condition field becomes a
    declared fact with the type used in the condition. Type conflicts across
    policies in the same workflow are a hard error (the bundle would reject it
    anyway, but here we give a clearer message)."""
    facts_by_wf: dict[str, dict[str, str]] = {}
    for p in policies:
        wf_facts = facts_by_wf.setdefault(p.workflow, {})
        for c in p.conditions:
            prior = wf_facts.get(c.field)
            if prior is not None and prior != c.value_type:
                raise AssembleError(
                    f"workflow {p.workflow!r}: fact {c.field!r} used as both "
                    f"{prior!r} and {c.value_type!r}"
                )
            wf_facts[c.field] = c.value_type
    return [
        WorkflowSpec(
            name=wf,
            facts=tuple(
                FactSpec(name=name, value_type=vt) for name, vt in sorted(fields.items())
            ),
        )
        for wf, fields in sorted(facts_by_wf.items())
    ]


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
