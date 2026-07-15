"""Onboarding drafts: editable, groundable proposed policies.

A draft holds a full Policy-shaped JSON that a reviewer edits freely, plus the
list of VERIFIED evidence spans they have grounded so far. A draft is
`publishable` only when it validates as a real Policy AND carries at least one
grounded citation -- the same bar seed_rivanly.py meets. `issues` explains what
still blocks it, so the reviewer always knows why.

Origin is 'authored' (human wrote it) or 'extracted' (LLM proposed it); either
way the evidence must be human-grounded before publish. The LLM never disposes.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from backend.bundle.schema import Evidence, Policy


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OnboardingDraft(BaseModel):
    model_config = ConfigDict(frozen=True)

    draft_id: str
    company_id: str
    proposed_json: dict[str, Any]  # Policy-shaped, editable, possibly incomplete
    evidence_json: tuple[dict[str, Any], ...] = ()  # grounded verified spans
    origin: str = "authored"  # "authored" | "extracted"
    source_skill_id: Optional[str] = None
    status: str = "draft"  # "draft" | "accepted" | "rejected"
    publishable: bool = False
    issues_json: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""


def new_draft_id() -> str:
    return "od_" + secrets.token_hex(8)


def evaluate_draft(
    proposed: dict[str, Any], evidence: tuple[dict[str, Any], ...]
) -> tuple[bool, tuple[str, ...]]:
    """Return (publishable, issues). Publishable iff the proposed policy plus its
    grounded evidence validate as a real Policy with at least one citation."""
    issues: list[str] = []
    if not evidence:
        issues.append("no grounded evidence yet -- select the source text that "
                      "justifies this policy")
    candidate = {**proposed, "evidence": list(evidence)}
    try:
        Policy.model_validate(candidate)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            issues.append(f"{loc}: {err['msg']}")
    return (not issues, tuple(issues))


def build_draft(
    company_id: str,
    proposed: dict[str, Any],
    *,
    origin: str = "authored",
    source_skill_id: Optional[str] = None,
    evidence: tuple[dict[str, Any], ...] = (),
    draft_id: Optional[str] = None,
) -> OnboardingDraft:
    publishable, issues = evaluate_draft(proposed, evidence)
    now = _now()
    return OnboardingDraft(
        draft_id=draft_id or new_draft_id(),
        company_id=company_id,
        proposed_json=proposed,
        evidence_json=evidence,
        origin=origin,
        source_skill_id=source_skill_id,
        status="draft",
        publishable=publishable,
        issues_json=issues,
        created_at=now,
        updated_at=now,
    )


class DraftStore(Protocol):
    def upsert(self, draft: OnboardingDraft) -> OnboardingDraft: ...
    def get(self, company_id: str, draft_id: str) -> Optional[OnboardingDraft]: ...
    def list(self, company_id: str, status: Optional[str] = None) -> list[OnboardingDraft]: ...
    def delete(self, company_id: str, draft_id: str) -> None: ...


class InMemoryDraftStore:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], OnboardingDraft] = {}

    def upsert(self, draft: OnboardingDraft) -> OnboardingDraft:
        self._rows[(draft.company_id, draft.draft_id)] = draft
        return draft

    def get(self, company_id: str, draft_id: str) -> Optional[OnboardingDraft]:
        return self._rows.get((company_id, draft_id))

    def list(self, company_id: str, status: Optional[str] = None) -> list[OnboardingDraft]:
        rows = [
            d
            for (cid, _), d in self._rows.items()
            if cid == company_id and (status is None or d.status == status)
        ]
        return sorted(rows, key=lambda d: d.updated_at, reverse=True)

    def delete(self, company_id: str, draft_id: str) -> None:
        self._rows.pop((company_id, draft_id), None)
