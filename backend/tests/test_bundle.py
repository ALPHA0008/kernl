"""Unit tests: Policy IR schema validation + canonical hashing.

Deterministic: no LLM, no DB, no network. Run directly or via pytest:
    py -3 backend/tests/test_bundle.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pydantic import ValidationError

from backend.bundle.canonical import bundle_content_hash, canonical_json, content_hash
from backend.bundle.schema import (
    Authority,
    Bundle,
    Condition,
    Effect,
    Evidence,
    FactSpec,
    OutcomeKind,
    Policy,
    WorkflowSpec,
)


def _ev() -> Evidence:
    return Evidence(
        source_id="notion_refund_sop.md",
        source_version="sha256:test",
        span_start=0,
        span_end=10,
        excerpt="test span",
    )


def _wf(name: str = "refund", facts: tuple[FactSpec, ...] | None = None) -> WorkflowSpec:
    if facts is None:
        facts = (
            FactSpec(name="plan_type", value_type="string"),
            FactSpec(name="days_since_purchase", value_type="number"),
        )
    return WorkflowSpec(name=name, facts=facts)


def _policy(pid: str = "refund.test", **kw) -> Policy:
    defaults = dict(
        id=pid,
        workflow="refund",
        effect=Effect(kind=OutcomeKind.APPROVE, action="approve"),
        priority=50,
        conditions=(
            Condition(field="plan_type", operator="eq", value="annual", value_type="string"),
        ),
        evidence=(_ev(),),
    )
    defaults.update(kw)
    return Policy(**defaults)


# --- schema validation -------------------------------------------------------


def test_operator_whitelist_enforced():
    try:
        Condition(field="x", operator="gt", value="a", value_type="string")
        assert False, "gt must be rejected for string"
    except ValidationError:
        pass


def test_list_value_requires_list_operator():
    try:
        Condition(field="x", operator="eq", value=["a", "b"], value_type="string")
        assert False, "eq must reject list value"
    except ValidationError:
        pass
    Condition(field="x", operator="in", value=["a", "b"], value_type="string")  # ok


def test_number_condition_rejects_non_numeric():
    try:
        Condition(field="x", operator="gt", value="14", value_type="number")
        assert False, "string value must be rejected for number type"
    except ValidationError:
        pass


def test_no_evidence_no_publish():
    try:
        _policy(evidence=())
        assert False, "policy without evidence must be rejected"
    except ValidationError:
        pass


def test_unconditional_requires_ack():
    try:
        _policy(conditions=())
        assert False, "0 conditions without ack must be rejected"
    except ValidationError:
        pass
    p = _policy(conditions=(), unconditional_ack=True)
    assert p.specificity == 0


def test_approval_requires_role():
    try:
        Authority(approval_required=True)
        assert False, "approval without role must be rejected"
    except ValidationError:
        pass


def test_bundle_rejects_condition_on_undeclared_fact():
    bad = _policy(
        conditions=(
            Condition(field="unknown_field", operator="eq", value="x", value_type="string"),
        )
    )
    try:
        Bundle(company_id="c", workflows=(_wf(),), policies=(bad,))
        assert False, "condition on undeclared fact must be rejected"
    except ValidationError:
        pass


def test_bundle_rejects_condition_type_mismatch():
    bad = _policy(
        conditions=(
            Condition(field="days_since_purchase", operator="eq", value="x", value_type="string"),
        )
    )
    try:
        Bundle(company_id="c", workflows=(_wf(),), policies=(bad,))
        assert False, "condition type mismatch with fact declaration must be rejected"
    except ValidationError:
        pass


def test_bundle_rejects_override_cycle():
    a = _policy("refund.a", overrides=("refund.b",))
    b = _policy("refund.b", overrides=("refund.a",))
    try:
        Bundle(company_id="c", workflows=(_wf(),), policies=(a, b))
        assert False, "override cycle must be rejected"
    except ValidationError:
        pass


def test_bundle_rejects_cross_workflow_override():
    wf2 = _wf("discount", facts=(FactSpec(name="discount_percent", value_type="number"),))
    a = _policy("refund.a")
    b = _policy(
        "discount.b",
        workflow="discount",
        overrides=("refund.a",),
        conditions=(
            Condition(field="discount_percent", operator="lte", value=10, value_type="number"),
        ),
    )
    try:
        Bundle(company_id="c", workflows=(_wf(), wf2), policies=(a, b))
        assert False, "cross-workflow override must be rejected"
    except ValidationError:
        pass


def test_bundle_rejects_duplicate_policy_ids():
    try:
        Bundle(company_id="c", workflows=(_wf(),), policies=(_policy(), _policy()))
        assert False, "duplicate policy ids must be rejected"
    except ValidationError:
        pass


def test_fact_default_must_match_type():
    try:
        FactSpec(name="active_outage", value_type="boolean", default="no")
        assert False, "string default on boolean fact must be rejected"
    except ValidationError:
        pass
    FactSpec(name="active_outage", value_type="boolean", default=False)  # ok


# --- canonical hashing -------------------------------------------------------


def test_canonical_json_is_key_order_independent():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_canonical_float_handling():
    assert canonical_json({"x": 2.0}) == canonical_json({"x": 2})
    assert canonical_json({"x": 2.5}) == '{"x":2.5}'
    for bad in (float("nan"), float("inf"), float("-inf")):
        try:
            canonical_json({"x": bad})
            assert False, "non-finite float must be rejected"
        except ValueError:
            pass


def test_content_hash_stable_and_prefixed():
    h1 = content_hash({"a": 1})
    h2 = content_hash({"a": 1})
    assert h1 == h2
    assert h1.startswith("sha256:") and len(h1) == len("sha256:") + 64


def test_bundle_hash_independent_of_policy_order_and_company():
    a, b = _policy("refund.a"), _policy("refund.b", priority=60)
    b1 = Bundle(company_id="acme", workflows=(_wf(),), policies=(a, b))
    b2 = Bundle(company_id="other", workflows=(_wf(),), policies=(b, a))
    assert bundle_content_hash(b1) == bundle_content_hash(b2)


def test_bundle_hash_changes_on_content_change():
    a = _policy("refund.a")
    base = Bundle(company_id="c", workflows=(_wf(),), policies=(a,))
    changed = Bundle(
        company_id="c", workflows=(_wf(),), policies=(_policy("refund.a", priority=51),)
    )
    assert bundle_content_hash(base) != bundle_content_hash(changed)


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
