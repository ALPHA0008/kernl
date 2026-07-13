"""Unit tests: skill -> policy-draft converter + W8 warning surfacing.

Deterministic: no LLM, no DB, no network.
    py -3 backend/tests/test_converter.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.bundle.converter import extraction_warnings, skill_to_draft, skills_to_drafts


def _skill(**kw):
    base = {
        "id": "refund_annual_14",
        "category": "Refunds",
        "rule": "Annual plans refunded within 14 days",
        "rationale": "SOP section 2",
        "evidence": ["If a customer on an annual plan requests a refund within 14 days..."],
        "operational": {
            "department": "support",
            "workflow_type": "refund",
            "action_type": "approve",
        },
        "conditions": [
            {"field": "plan_type", "operator": "==", "value": "annual", "type": "string"},
            {"field": "days_since_purchase", "operator": "<=", "value": 14, "type": "number"},
        ],
    }
    base.update(kw)
    return base


def test_conditions_and_operators_map():
    d = skill_to_draft(_skill(), "acme")
    conds = d.proposed_policy["conditions"]
    assert {c["operator"] for c in conds} == {"eq", "lte"}
    assert d.proposed_policy["workflow"] == "refund"
    assert d.proposed_policy["effect"] == {"kind": "approve", "action": "approve"}


def test_never_publishable_without_real_spans():
    # Even a fully-formed skill cannot publish: legacy evidence has no spans,
    # and the converter must not fabricate citations (rule 2).
    d = skill_to_draft(_skill(), "acme")
    assert d.publishable is False
    assert any("source spans" in i for i in d.issues)
    assert d.proposed_policy["evidence"] == []
    assert d.evidence_texts  # reviewer material preserved


def test_conditionless_skill_flagged():
    d = skill_to_draft(_skill(conditions=[]), "acme")
    assert any("unconditional" in i for i in d.issues)
    assert d.publishable is False


def test_missing_action_type_flagged():
    d = skill_to_draft(_skill(operational={"department": "support"}), "acme")
    assert any("action_type" in i for i in d.issues)
    assert d.proposed_policy["effect"]["action"] == "review_required"


def test_unmappable_operator_flagged_not_crashed():
    bad = _skill(conditions=[{"field": "x", "operator": "~=", "value": 1, "type": "number"}])
    d = skill_to_draft(bad, "acme")
    assert any("unmappable" in i for i in d.issues)


def test_batch_conversion():
    drafts = skills_to_drafts([_skill(), _skill(id="other_rule")], "acme")
    assert len(drafts) == 2
    assert len({d.draft_id for d in drafts}) == 2


def test_w8_warnings_on_empty_extractors():
    state = {
        "extracted_decisions": [],
        "extracted_workflows": [{"x": 1}],
        "final_skills": [],
    }
    warnings = extraction_warnings(state)
    assert any("decision extraction" in w for w in warnings)
    assert not any("workflow extraction" in w for w in warnings)
    assert any("ZERO skills" in w for w in warnings)


def test_w8_silent_on_healthy_run():
    state = {
        "extracted_decisions": [{"d": 1}],
        "extracted_workflows": [{"w": 1}],
        "extracted_exceptions": [{"e": 1}],
        "contradictions": [{"c": 1}],
        "extracted_entities": [{"n": 1}],
        "final_skills": [{"s": 1}],
    }
    assert extraction_warnings(state) == []


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"Results: {len(TESTS) - failed}/{len(TESTS)} passed, {failed} failed")
    sys.exit(1 if failed else 0)
