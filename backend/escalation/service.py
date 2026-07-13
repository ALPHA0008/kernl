"""Escalation lifecycle.

An escalation is opened when a ledgered decision either (a) escalated
(evaluator- or policy-directed) or (b) carries approval_required. Resolving it
records an ADJUDICATION event on the ledger (the write-ahead rule applies:
resolution status flips only after the adjudication event is committed) and
optionally promotes the resolved case into the golden set.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional, Protocol

from pydantic import BaseModel, ConfigDict

from backend.ledger.events import Actor, DecisionEvent
from backend.ledger.service import DecisionService


class EscalationStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class EscalationReasonKind(str, Enum):
    MISSING_FACTS = "missing_facts"
    NO_MATCHING_POLICY = "no_matching_policy"
    CONFLICT = "conflict"
    POLICY_DIRECTED = "policy_directed"  # a policy's effect is escalate
    AUTHORITY_REQUIRED = "authority_required"  # approval_required on the winner


class Resolution(BaseModel):
    model_config = ConfigDict(frozen=True)

    chosen_action: str
    outcome_kind: str
    rationale: str
    resolver: Actor
    adjudication_event_id: str
    resolved_at: str
    promoted_to_golden: bool = False


class Escalation(BaseModel):
    model_config = ConfigDict(frozen=True)

    escalation_id: str
    company_id: str
    workflow: str
    decision_event_id: str
    reason: EscalationReasonKind
    detail: dict  # missing fact names / conflicting policy ids / approver role
    status: EscalationStatus = EscalationStatus.OPEN
    created_at: str = ""
    resolution: Optional[Resolution] = None


class EscalationStore(Protocol):
    def add(self, esc: Escalation) -> Escalation: ...
    def get(self, company_id: str, escalation_id: str) -> Optional[Escalation]: ...
    def update(self, esc: Escalation) -> Escalation: ...
    def list(
        self, company_id: str, status: Optional[EscalationStatus] = None,
        limit: int = 100, offset: int = 0,
    ) -> list[Escalation]: ...
    def by_decision(self, company_id: str, decision_event_id: str) -> Optional[Escalation]: ...


class InMemoryEscalationStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[tuple[str, str], Escalation] = {}
        self._by_decision: dict[tuple[str, str], str] = {}

    def add(self, esc: Escalation) -> Escalation:
        with self._lock:
            dkey = (esc.company_id, esc.decision_event_id)
            if dkey in self._by_decision:  # exactly one escalation per decision
                return self._rows[(esc.company_id, self._by_decision[dkey])]
            self._rows[(esc.company_id, esc.escalation_id)] = esc
            self._by_decision[dkey] = esc.escalation_id
            return esc

    def get(self, company_id: str, escalation_id: str) -> Optional[Escalation]:
        return self._rows.get((company_id, escalation_id))

    def update(self, esc: Escalation) -> Escalation:
        with self._lock:
            self._rows[(esc.company_id, esc.escalation_id)] = esc
            return esc

    def list(self, company_id, status=None, limit=100, offset=0):  # noqa: ANN001
        rows = [
            e for (cid, _), e in self._rows.items()
            if cid == company_id and (status is None or e.status is status)
        ]
        rows.sort(key=lambda e: e.created_at, reverse=True)
        return rows[offset : offset + limit]

    def by_decision(self, company_id: str, decision_event_id: str) -> Optional[Escalation]:
        eid = self._by_decision.get((company_id, decision_event_id))
        return self._rows.get((company_id, eid)) if eid else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class AlreadyResolvedError(RuntimeError):
    pass


class EscalationService:
    def __init__(
        self,
        store: EscalationStore,
        decisions: DecisionService,
        promote_golden: Optional[Callable[[DecisionEvent, Resolution], None]] = None,
    ) -> None:
        self._store = store
        self._decisions = decisions
        self._promote_golden = promote_golden

    def open_for(self, event: DecisionEvent) -> Optional[Escalation]:
        """Open an escalation for a ledgered decision if it needs one.
        Returns None when the decision needs no human attention."""
        outcome = event.outcome
        reason: Optional[EscalationReasonKind] = None
        detail: dict = {}

        if outcome.get("kind") == "escalate":
            r = outcome.get("escalation_reason")
            if r == "missing_facts":
                reason = EscalationReasonKind.MISSING_FACTS
                detail = {"missing_facts": outcome.get("missing_facts", [])}
            elif r == "conflict":
                reason = EscalationReasonKind.CONFLICT
                detail = {"conflict_between": outcome.get("conflict_between", [])}
            elif r == "no_matching_policy":
                reason = EscalationReasonKind.NO_MATCHING_POLICY
            else:
                reason = EscalationReasonKind.POLICY_DIRECTED
                detail = {"action": outcome.get("action"), "policy_id": outcome.get("policy_id")}
        elif outcome.get("approval_required"):
            reason = EscalationReasonKind.AUTHORITY_REQUIRED
            detail = {
                "approver_role": outcome.get("approver_role"),
                "action": outcome.get("action"),
                "policy_id": outcome.get("policy_id"),
            }

        if reason is None:
            return None
        esc = Escalation(
            escalation_id=str(uuid.uuid4()),
            company_id=event.company_id,
            workflow=event.workflow,
            decision_event_id=event.event_id,
            reason=reason,
            detail=detail,
            created_at=_now_iso(),
        )
        return self._store.add(esc)

    def resolve(
        self,
        *,
        company_id: str,
        escalation_id: str,
        resolver: Actor,
        chosen_action: str,
        outcome_kind: str,
        rationale: str,
        promote_to_golden: bool = False,
    ) -> Escalation:
        esc = self._store.get(company_id, escalation_id)
        if esc is None:
            raise KeyError(f"unknown escalation {escalation_id!r}")
        if esc.status is EscalationStatus.RESOLVED:
            raise AlreadyResolvedError(escalation_id)

        # Write-ahead: the adjudication event commits BEFORE status flips.
        original = self._decisions_store_get(company_id, esc.decision_event_id)
        adjudication, _ = self._decisions.record_adjudication(
            company_id=company_id,
            original_event=original,
            actor=resolver,
            chosen_action=chosen_action,
            outcome_kind=outcome_kind,
            rationale=rationale,
            idempotency_key=f"adjudication:{escalation_id}",
        )
        resolution = Resolution(
            chosen_action=chosen_action,
            outcome_kind=outcome_kind,
            rationale=rationale,
            resolver=resolver,
            adjudication_event_id=adjudication.event_id,
            resolved_at=_now_iso(),
            promoted_to_golden=promote_to_golden,
        )
        if promote_to_golden and self._promote_golden is not None:
            self._promote_golden(original, resolution)
        return self._store.update(
            esc.model_copy(update={"status": EscalationStatus.RESOLVED, "resolution": resolution})
        )

    def _decisions_store_get(self, company_id: str, event_id: str) -> DecisionEvent:
        event = self._decisions._store.get(company_id, event_id)  # noqa: SLF001
        if event is None:
            raise KeyError(f"decision event {event_id!r} not found")
        return event
