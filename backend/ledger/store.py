"""Ledger storage protocol + implementations.

The protocol is intentionally tiny: append-or-return-existing, point reads,
filtered listing, and chain head. All implementations MUST provide atomic
idempotency (the same (company_id, idempotency_key) never yields two events).

InMemoryLedgerStore  -- tests and single-process development. Thread-safe.
SupabaseLedgerStore  -- production (backend/schema.sql: decision_events).
"""

from __future__ import annotations

import threading
from typing import Iterable, Optional, Protocol

from backend.ledger.events import ChainConflict, DecisionEvent


class LedgerStore(Protocol):
    def append(self, event: DecisionEvent) -> tuple[DecisionEvent, bool]:
        """Append a sealed event. Returns (stored_event, created). If an event
        with the same (company_id, idempotency_key) exists, returns it with
        created=False and stores nothing."""
        ...

    def get(self, company_id: str, event_id: str) -> Optional[DecisionEvent]: ...

    def by_idempotency_key(
        self, company_id: str, idempotency_key: str
    ) -> Optional[DecisionEvent]: ...

    def list(
        self,
        company_id: str,
        workflow: Optional[str] = None,
        outcome_kind: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DecisionEvent]: ...

    def chain_head(self, company_id: str) -> Optional[str]:
        """event_hash of the most recent event in the company stream."""
        ...

    def verify_chain(self, company_id: str) -> bool: ...


class InMemoryLedgerStore:
    """Reference implementation. Semantics here are the contract the
    production store must match (test_ledger.py runs against this)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: dict[str, list[DecisionEvent]] = {}
        self._by_key: dict[tuple[str, str], DecisionEvent] = {}
        self._by_id: dict[tuple[str, str], DecisionEvent] = {}

    def append(self, event: DecisionEvent) -> tuple[DecisionEvent, bool]:
        if not event.verify():
            raise ValueError("refusing to append an unsealed or tampered event")
        key = (event.company_id, event.idempotency_key)
        with self._lock:
            existing = self._by_key.get(key)
            if existing is not None:
                return existing, False
            stream = self._events.setdefault(event.company_id, [])
            expected_prev = stream[-1].event_hash if stream else None
            if event.prev_event_hash != expected_prev:
                raise ChainConflict(
                    "chain break: prev_event_hash does not match stream head"
                )
            stream.append(event)
            self._by_key[key] = event
            self._by_id[(event.company_id, event.event_id)] = event
            return event, True

    def get(self, company_id: str, event_id: str) -> Optional[DecisionEvent]:
        return self._by_id.get((company_id, event_id))

    def by_idempotency_key(
        self, company_id: str, idempotency_key: str
    ) -> Optional[DecisionEvent]:
        return self._by_key.get((company_id, idempotency_key))

    def list(
        self,
        company_id: str,
        workflow: Optional[str] = None,
        outcome_kind: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DecisionEvent]:
        stream: Iterable[DecisionEvent] = self._events.get(company_id, [])
        rows = [
            e
            for e in stream
            if (workflow is None or e.workflow == workflow)
            and (outcome_kind is None or e.outcome.get("kind") == outcome_kind)
        ]
        rows.reverse()  # newest first
        return rows[offset : offset + limit]

    def chain_head(self, company_id: str) -> Optional[str]:
        with self._lock:
            stream = self._events.get(company_id, [])
            return stream[-1].event_hash if stream else None

    def verify_chain(self, company_id: str) -> bool:
        stream = self._events.get(company_id, [])
        prev: Optional[str] = None
        for event in stream:
            if not event.verify():
                return False
            if event.prev_event_hash != prev:
                return False
            prev = event.event_hash
        return True
