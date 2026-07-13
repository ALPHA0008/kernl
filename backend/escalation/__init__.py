"""Escalation Workflow: where ambiguity becomes work, and adjudication
becomes ledgered precedent (V1 scope: docs/V1_EXECUTION_PLAN.md step 4)."""

from backend.escalation.service import (
    Escalation,
    EscalationService,
    EscalationStatus,
    InMemoryEscalationStore,
)

__all__ = [
    "Escalation",
    "EscalationService",
    "EscalationStatus",
    "InMemoryEscalationStore",
]
