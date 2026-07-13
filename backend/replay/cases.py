"""Golden cases: the versioned corpus of (facts -> expected outcome) records
that gates every publish. Cases only grow; expectations change only with a
documented revision note."""

from __future__ import annotations

import threading
from typing import Any, Optional, Protocol

from pydantic import BaseModel, ConfigDict

from backend.bundle.canonical import content_hash


class Expected(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str  # OutcomeKind value
    action: Optional[str] = None
    escalation_reason: Optional[str] = None


class GoldenCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    company_id: str
    workflow: str
    facts: dict[str, Any]
    expected: Expected
    provenance: str  # source doc / adjudication event id / migration note
    synthetic: bool = True  # [synthetic] until real-tenant cases exist
    notes: str = ""


def case_set_hash(cases: list[GoldenCase]) -> str:
    body = sorted((c.model_dump(mode="json") for c in cases), key=lambda c: c["case_id"])
    return content_hash(body)


class CaseStore(Protocol):
    def add(self, case: GoldenCase) -> GoldenCase: ...
    def list(self, company_id: str, workflow: Optional[str] = None) -> list[GoldenCase]: ...


class InMemoryCaseStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[tuple[str, str], GoldenCase] = {}

    def add(self, case: GoldenCase) -> GoldenCase:
        with self._lock:
            key = (case.company_id, case.case_id)
            if key in self._rows:
                raise ValueError(f"duplicate case id {case.case_id!r}")
            self._rows[key] = case
            return case

    def list(self, company_id: str, workflow: Optional[str] = None) -> list[GoldenCase]:
        rows = [
            c for (cid, _), c in sorted(self._rows.items())
            if cid == company_id and (workflow is None or c.workflow == workflow)
        ]
        return rows
