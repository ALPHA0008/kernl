"""Unit tests: structural bundle diff (backend/bundle/diff.py).

Deterministic: no LLM, no DB, no network. Run directly or via pytest:
    py -3 backend/tests/test_bundle_diff.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.bundle.canonical import bundle_content_hash
from backend.bundle.diff import diff_bundles
from backend.bundle.schema import (
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


def _wf(name: str = "refund") -> WorkflowSpec:
    return WorkflowSpec(
        name=name,
        facts=(
            FactSpec(name="plan_type", value_type="string"),
            FactSpec(name="days_since_purchase", value_type="number"),
        ),
    )


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


def _bundle(*policies: Policy, company_id: str = "c") -> Bundle:
    return Bundle(company_id=company_id, workflows=(_wf(),), policies=policies)


# --- diff_bundles -------------------------------------------------------


def test_no_baseline_reports_every_policy_as_added():
    after = _bundle(_policy("refund.a"), _policy("refund.b"))
    d = diff_bundles(None, after)
    assert d.from_hash is None
    assert {c.policy_id for c in d.added} == {"refund.a", "refund.b"}
    assert not d.removed and not d.modified
    assert d.unchanged_count == 0


def test_identical_bundles_produce_empty_diff():
    a = _bundle(_policy("refund.a"))
    b = _bundle(_policy("refund.a"))
    d = diff_bundles(a, b)
    assert d.is_empty
    assert d.unchanged_count == 1
    assert d.from_hash == bundle_content_hash(a)
    assert d.to_hash == bundle_content_hash(b)


def test_added_policy_detected():
    before = _bundle(_policy("refund.a"))
    after = _bundle(_policy("refund.a"), _policy("refund.b"))
    d = diff_bundles(before, after)
    assert [c.policy_id for c in d.added] == ["refund.b"]
    assert not d.removed and not d.modified
    assert d.unchanged_count == 1


def test_removed_policy_detected():
    before = _bundle(_policy("refund.a"), _policy("refund.b"))
    after = _bundle(_policy("refund.a"))
    d = diff_bundles(before, after)
    assert [c.policy_id for c in d.removed] == ["refund.b"]
    assert not d.added and not d.modified


def test_modified_policy_reports_changed_fields():
    before = _bundle(_policy("refund.a", priority=50))
    after = _bundle(_policy("refund.a", priority=90))
    d = diff_bundles(before, after)
    assert len(d.modified) == 1
    change = d.modified[0]
    assert change.policy_id == "refund.a"
    assert change.changed_fields == ("priority",)
    assert change.before.priority == 50
    assert change.after.priority == 90


def test_modified_detects_multiple_changed_fields():
    before = _policy("refund.a", priority=50, rationale="old")
    after = _policy("refund.a", priority=90, rationale="new")
    d = diff_bundles(_bundle(before), _bundle(after))
    assert set(d.modified[0].changed_fields) == {"priority", "rationale"}


def test_diffing_bundle_against_itself_is_empty():
    b = _bundle(_policy("refund.a"), _policy("refund.b"))
    d = diff_bundles(b, b)
    assert d.is_empty
    assert d.unchanged_count == 2


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
