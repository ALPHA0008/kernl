"""LLM extraction as a draft PROPOSER (never a disposer).

Given an uploaded source snapshot, ask the LLM to propose candidate policies as
structured Policy-shaped JSON. Each proposal becomes an onboarding draft with
origin='extracted' and NO evidence -- a human must still ground every citation
against the source bytes before it can publish (CLAUDE.md rule 2). The LLM only
saves the reviewer from typing the skeleton; it never grants authority.

Degrades cleanly: if the LLM infra is unreachable, ExtractionUnavailable is
raised and the caller surfaces a 503 -- the author-directly path is unaffected.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from backend.onboarding.drafts import OnboardingDraft, build_draft
from backend.onboarding.sources import SourceSnapshot

# The extraction proposer calls the LLM gateway directly over HTTP (httpx only).
# It deliberately does NOT import backend.core.llm, which drags numpy/torch into
# the path -- onboarding must stay light and keep the heavy ML stack out of the
# V1 request path (the same posture that keeps LLMs off the decision path).
_GATEWAY_URL = os.getenv("VLLM_BASE_URL", "http://172.20.7.22:9000")
_GATEWAY_KEY = os.getenv("VLLM_API_KEY", "")

_SYSTEM_PROMPT = """You extract OPERATIONAL DECISION POLICIES from a company's \
policy document. Return a JSON array; each element is one policy with this exact \
shape:

{
  "id": "<workflow>.<short_snake_name>",
  "workflow": "<snake_case workflow, e.g. refund, discount, escalation>",
  "effect": {"kind": "approve|deny|route|escalate", "action": "<snake_case action>"},
  "priority": <integer 0-1000, higher = stronger>,
  "conditions": [
    {"field": "<snake_case fact>", "operator": "eq|neq|gt|gte|lt|lte|in|not_in",
     "value": <string|number|boolean>, "value_type": "string|number|boolean"}
  ],
  "rationale": "<one sentence, paraphrase of the source rule>"
}

Rules:
- Only extract rules that are ACTIONABLE decisions (approve/deny/route/escalate).
- Use the operators literally as listed; map "<=" to "lte", ">=" to "gte", etc.
- Every condition field must be snake_case and typed correctly.
- Do NOT invent evidence, citations, or quotes. Do NOT include an "evidence" key.
- If unsure about a value, still propose the policy; a human will review it.
- Return ONLY the JSON array, no prose.
"""


class ExtractionUnavailable(RuntimeError):
    """The LLM extraction backend could not be reached or returned nothing."""


def _strip_fences(raw: str) -> str:
    """Remove ```json ... ``` fences an LLM may wrap the array in."""
    m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    return (m.group(1) if m else raw).strip()


async def _gateway_json_array(system_prompt: str, user_content: str) -> list:
    """One HTTP call to the LLM gateway; parse a JSON array from the response.
    httpx only -- no numpy/torch. Raises on any transport or parse failure."""
    import httpx

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{_GATEWAY_URL}/generate",
            headers={"x-api-key": _GATEWAY_KEY, "x-user-name": "kernl-onboarding"},
            json={
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ]
            },
        )
        resp.raise_for_status()
        text = resp.json()["response"]
    parsed = json.loads(_strip_fences(text))
    if isinstance(parsed, dict):
        for key in ("policies", "skills", "items", "results", "data"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
        return [parsed]
    return parsed if isinstance(parsed, list) else []


async def propose_drafts_from_source(snapshot: SourceSnapshot) -> list[OnboardingDraft]:
    """Run one LLM extraction pass over the snapshot and return ungrounded
    onboarding drafts (origin='extracted'). Raises ExtractionUnavailable if the
    LLM call fails."""
    try:
        proposals = await _gateway_json_array(_SYSTEM_PROMPT, snapshot.content)
    except Exception as exc:  # noqa: BLE001
        raise ExtractionUnavailable(
            f"extraction backend unavailable: {exc}"
        ) from exc

    if not isinstance(proposals, list) or not proposals:
        raise ExtractionUnavailable(
            "extraction returned no candidate policies -- verify the source and "
            "the LLM gateway, or author policies directly"
        )

    drafts: list[OnboardingDraft] = []
    for i, raw in enumerate(proposals):
        if not isinstance(raw, dict):
            continue
        proposed = _normalize(raw, i)
        drafts.append(
            build_draft(
                snapshot.company_id,
                proposed,
                origin="extracted",
                source_skill_id=f"{snapshot.source_id}:{proposed.get('id', i)}",
                evidence=(),  # ungrounded: the reviewer must cite the source
            )
        )
    if not drafts:
        raise ExtractionUnavailable("no well-formed policies could be parsed")
    return drafts


def _normalize(raw: dict[str, Any], index: int) -> dict[str, Any]:
    """Coerce an LLM proposal into a Policy-shaped dict. Missing pieces stay
    missing -- evaluate_draft will report them as issues for the reviewer; we do
    NOT fabricate anything to force validity."""
    effect = raw.get("effect") or {}
    return {
        "id": str(raw.get("id") or f"proposed.rule_{index}"),
        "workflow": str(raw.get("workflow") or "general"),
        "effect": {
            "kind": str(effect.get("kind") or "route"),
            "action": str(effect.get("action") or "review_required"),
        },
        "priority": int(raw.get("priority") or 50),
        "conditions": [
            {
                "field": str(c.get("field", "")),
                "operator": str(c.get("operator", "")),
                "value": c.get("value"),
                "value_type": str(c.get("value_type") or "string"),
            }
            for c in (raw.get("conditions") or [])
            if isinstance(c, dict)
        ],
        "authority": {"approval_required": False},
        "evidence": [],
        "overrides": [],
        "unconditional_ack": False,
        "rationale": str(raw.get("rationale") or ""),
    }
