"""Skill -> policy-draft converter: the bridge from the legacy extraction
pipeline to the V1 Policy IR.

Constitutional posture (CLAUDE.md rule 2): extraction PROPOSES, it never
disposes. A converted draft is publishable only if it fully validates as a
Policy -- including real evidence spans. The converter NEVER fabricates
citations, conditions, or acknowledgements to force validity; whatever is
missing becomes an explicit issue for a human reviewer.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, ValidationError

from backend.bundle.schema import Policy

# legacy condition_eval operators -> Policy IR operators
_OPERATOR_MAP = {
    ">": "gt",
    ">=": "gte",
    "<": "lt",
    "<=": "lte",
    "==": "eq",
    "!=": "neq",
    "in": "in",
    "not_in": "not_in",
}

_KIND_MAP = {"approve": "approve", "deny": "deny", "escalate": "escalate"}


def _snake(value: str, fallback: str) -> str:
    s = re.sub(r"[^a-z0-9_]+", "_", str(value).strip().lower()).strip("_")
    return s if re.match(r"^[a-z][a-z0-9_]*$", s or "") else fallback


class PolicyDraft(BaseModel):
    """A proposed policy awaiting review. Loose by design: it holds whatever
    extraction produced plus the exact list of reasons it cannot publish yet."""

    model_config = ConfigDict(frozen=True)

    draft_id: str
    company_id: str
    source_skill_id: str
    proposed_policy: dict[str, Any]  # Policy-shaped JSON, possibly incomplete
    issues: tuple[str, ...]  # empty <=> publishable
    publishable: bool
    evidence_texts: tuple[str, ...] = ()  # reviewer material; NOT citations


def skill_to_draft(skill: dict[str, Any], company_id: str) -> PolicyDraft:
    issues: list[str] = []
    skill_id = str(skill.get("id") or "unknown")
    operational = skill.get("operational") or {}

    workflow = _snake(
        operational.get("workflow_type") or operational.get("department") or "",
        "general",
    )
    action_raw = str(operational.get("action_type") or "").strip()
    if not action_raw:
        issues.append("no action_type extracted; reviewer must assign an effect")
    kind = _KIND_MAP.get(action_raw.lower(), "route")
    action = _snake(action_raw, "review_required")

    conditions: list[dict[str, Any]] = []
    for cond in skill.get("conditions") or []:
        op = _OPERATOR_MAP.get(str(cond.get("operator")))
        if op is None:
            issues.append(f"unmappable condition operator {cond.get('operator')!r}")
            continue
        conditions.append(
            {
                "field": _snake(str(cond.get("field", "")), "unknown_field"),
                "operator": op,
                "value": cond.get("value"),
                "value_type": cond.get("type", "string"),
            }
        )
    if not conditions:
        issues.append(
            "no typed conditions survived extraction; unconditional publication "
            "requires explicit reviewer sign-off (unconditional_ack)"
        )

    # Evidence honesty: legacy skills carry quoted text but NO source spans or
    # source versions. We surface the text for the reviewer and refuse to
    # fabricate citations (rule 2: no uncited norm).
    evidence_texts = tuple(
        str(e) for e in (skill.get("evidence") or []) if str(e).strip()
    )
    issues.append(
        "evidence lacks verified source spans; re-link against a source "
        "snapshot during review"
    )

    proposed = {
        "id": f"{workflow}.{_snake(skill_id, 'draft')}",
        "workflow": workflow,
        "effect": {"kind": kind, "action": action},
        "priority": 50,
        "conditions": conditions,
        "authority": {"approval_required": False},
        "evidence": [],  # intentionally empty until review re-links spans
        "overrides": [],
        "unconditional_ack": False,
        "rationale": str(skill.get("rationale") or ""),
    }

    publishable = False
    try:
        Policy.model_validate(proposed)
        publishable = not issues
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            msg = f"schema: {loc}: {err['msg']}"
            if msg not in issues:
                issues.append(msg)

    return PolicyDraft(
        draft_id=f"draft_{_snake(skill_id, 'x')}",
        company_id=company_id,
        source_skill_id=skill_id,
        proposed_policy=proposed,
        issues=tuple(issues),
        publishable=publishable,
        evidence_texts=evidence_texts,
    )


def skills_to_drafts(
    skills: list[dict[str, Any]], company_id: str
) -> list[PolicyDraft]:
    return [skill_to_draft(s, company_id) for s in skills]


def extraction_warnings(state: dict[str, Any]) -> list[str]:
    """W8 surfacing: silent-empty extraction becomes a visible warning on the
    compile run instead of a quiet success."""
    warnings: list[str] = []
    checks = {
        "extracted_decisions": "decision extraction",
        "extracted_workflows": "workflow extraction",
        "extracted_exceptions": "exception extraction",
        "contradictions": "contradiction detection",
        "extracted_entities": "entity extraction",
    }
    for key, label in checks.items():
        if key in state and not state.get(key):
            warnings.append(
                f"W8: {label} returned zero items -- possible silent LLM/parse "
                "failure; verify sources and gateway before trusting this run"
            )
    if not state.get("final_skills"):
        warnings.append(
            "W8: compile produced ZERO skills -- treat this run as failed "
            "regardless of its status"
        )
    return warnings
