"""Ledger event model. Events are immutable and hash-chained per company.

`event_hash` = sha256 over the canonical form of the event WITHOUT the hash
itself; `prev_event_hash` links each event to its predecessor in the same
company stream, making silent history edits detectable.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from backend.bundle.canonical import content_hash


class EventType(str, Enum):
    DECISION = "decision"
    ADJUDICATION = "adjudication"


class Actor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: str  # "human" | "agent" | "service"
    id: str
    api_key_id: Optional[str] = None


class DecisionEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str  # uuid4, assigned by the service
    event_type: EventType
    company_id: str
    workflow: str
    actor: Actor
    idempotency_key: str
    facts: dict[str, Any]
    outcome: dict[str, Any]  # Outcome.model_dump(mode="json")
    trace: dict[str, Any]  # Trace.model_dump(mode="json")
    bundle_hash: str
    linked_event_id: Optional[str] = None  # adjudication -> original decision
    created_at: str  # ISO-8601 UTC, assigned by the service
    prev_event_hash: Optional[str] = None
    event_hash: str = ""

    def compute_hash(self) -> str:
        body = self.model_dump(mode="json")
        body.pop("event_hash")
        return content_hash(body)

    def sealed(self) -> "DecisionEvent":
        return self.model_copy(update={"event_hash": self.compute_hash()})

    def verify(self) -> bool:
        return bool(self.event_hash) and self.event_hash == self.compute_hash()
