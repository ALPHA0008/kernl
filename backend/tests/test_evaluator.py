"""Unit tests: the V1 pure evaluator -- semantics, determinism, boundaries.

Deterministic: no LLM, no DB, no network. Run directly or via pytest:
    py -3 backend/tests/test_evaluator.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
from backend.runtime.evaluator import (
    EscalationReason,
    InvalidFactsError,
    PolicyStatus,
    evaluate,
)


def _ev() -> Evidence:
    return Evidence(
        source_id="doc.md", source_version="sha256:x", span_start=0, span_end=5, excerpt="rule"
    )


def _c(field, op, value, vtype) -> Condition:
    return Condition(field=field, operator=op, value=value, value_type=vtype)


def _p(pid, effect_kind, action, conds, priority=50, overrides=(), authority=None) -> Policy:
    return Policy(
        id=pid,
        workflow="refund",
        effect=Effect(kind=effect_kind, action=action),
        priority=priority,
        conditions=tuple(conds),
        overrides=tuple(overrides),
        authority=authority or Authority(),
        evidence=(_ev(),),
    )


def _refund_bundle(policies) -> Bundle:
    wf = WorkflowSpec(
        name="refund",
        facts=(
            FactSpec(name="plan_type", value_type="string"),
            FactSpec(name="days_since_purchase", value_type="number"),
            FactSpec(name="refund_amount", value_type="number"),
            FactSpec(name="tenure_months", value_type="number"),
            FactSpec(name="tenure_years", value_type="number"),
        ),
    )
    return Bundle(company_id="test", workflows=(wf,), policies=tuple(policies))


ANNUAL_14D = _p(
    "refund.annual_14d",
    OutcomeKind.APPROVE,
    "approve_full_refund",
    [
        _c("plan_type", "eq", "annual", "string"),
        _c("days_since_purchase", "lte", 14, "number"),
    ],
    priority=70,
)
PRORATE = _p(
    "refund.annual_prorate",
    OutcomeKind.APPROVE,
    "approve_prorated_refund",
    [
        _c("plan_type", "eq", "annual", "string"),
        _c("days_since_purchase", "gt", 14, "number"),
    ],
    priority=60,
)
DENY_60 = _p(
    "refund.deny_after_60",
    OutcomeKind.DENY,
    "deny_refund",
    [_c("days_since_purchase", "gt", 60, "number")],
    priority=100,
    overrides=("refund.annual_prorate", "refund.annual_14d", "refund.loyalty"),
)
ENTERPRISE = _p(
    "refund.enterprise_escalate",
    OutcomeKind.ESCALATE,
    "escalate_to_account_manager",
    [_c("plan_type", "eq", "enterprise", "string")],
    priority=90,
)
LOYALTY = _p(
    "refund.loyalty",
    OutcomeKind.APPROVE,
    "approve_full_refund",
    [
        _c("tenure_years", "gte", 3, "number"),
        _c("days_since_purchase", "lte", 60, "number"),
    ],
    priority=55,
    overrides=("refund.annual_prorate",),
)

ALL = [ANNUAL_14D, PRORATE, DENY_60, ENTERPRISE, LOYALTY]


# --- happy paths & boundaries ------------------------------------------------


def test_simple_match():
    r = evaluate({"plan_type": "annual", "days_since_purchase": 9}, _refund_bundle(ALL), "refund")
    assert r.outcome.kind is OutcomeKind.APPROVE
    assert r.outcome.policy_id == "refund.annual_14d"


def test_boundary_lte_inclusive():
    r = evaluate({"plan_type": "annual", "days_since_purchase": 14}, _refund_bundle(ALL), "refund")
    assert r.outcome.policy_id == "refund.annual_14d"


def test_boundary_gt_exclusive():
    r = evaluate({"plan_type": "annual", "days_since_purchase": 15}, _refund_bundle(ALL), "refund")
    assert r.outcome.policy_id == "refund.annual_prorate"


def test_boundary_60_exact_is_not_after_60():
    r = evaluate({"plan_type": "annual", "days_since_purchase": 60}, _refund_bundle(ALL), "refund")
    assert r.outcome.policy_id == "refund.annual_prorate"


def test_deny_after_60_wins_by_override():
    r = evaluate({"plan_type": "annual", "days_since_purchase": 75}, _refund_bundle(ALL), "refund")
    assert r.outcome.kind is OutcomeKind.DENY
    assert r.outcome.policy_id == "refund.deny_after_60"
    assert any(e.rule == "overrides" for e in r.trace.precedence.eliminated)


def test_string_compare_case_insensitive():
    r = evaluate({"plan_type": "ANNUAL ", "days_since_purchase": 9}, _refund_bundle(ALL), "refund")
    assert r.outcome.policy_id == "refund.annual_14d"


def test_escalate_effect_propagates():
    r = evaluate({"plan_type": "enterprise", "days_since_purchase": 7}, _refund_bundle(ALL), "refund")
    assert r.outcome.kind is OutcomeKind.ESCALATE
    assert r.outcome.action == "escalate_to_account_manager"
    assert r.outcome.policy_id == "refund.enterprise_escalate"
    assert r.outcome.escalation_reason is None  # policy-directed, not evaluator-forced


# --- overrides vs priority (defeasible semantics) ----------------------------


def test_loyalty_overrides_prorate_when_both_match():
    facts = {"plan_type": "annual", "days_since_purchase": 45, "tenure_years": 4}
    r = evaluate(facts, _refund_bundle(ALL), "refund")
    assert r.outcome.policy_id == "refund.loyalty"
    assert r.outcome.action == "approve_full_refund"


def test_unproven_lower_priority_exception_does_not_block():
    # tenure_years absent -> loyalty undeterminable (prio 55 < prorate 60):
    # the general rule stands (defeasible: exceptions must be proven).
    facts = {"plan_type": "annual", "days_since_purchase": 45}
    r = evaluate(facts, _refund_bundle(ALL), "refund")
    assert r.outcome.policy_id == "refund.annual_prorate"
    loyalty_eval = next(p for p in r.trace.policies if p.policy_id == "refund.loyalty")
    assert loyalty_eval.status is PolicyStatus.UNDETERMINABLE


def test_unproven_higher_priority_policy_blocks_via_dominance():
    high_unknown = _p(
        "refund.vip_hold",
        OutcomeKind.ESCALATE,
        "escalate_to_founder",
        [_c("refund_amount", "gt", 10000, "number")],
        priority=99,
    )
    facts = {"plan_type": "annual", "days_since_purchase": 9}  # refund_amount absent
    r = evaluate(facts, _refund_bundle(ALL + [high_unknown]), "refund")
    assert r.outcome.kind is OutcomeKind.ESCALATE
    assert r.outcome.escalation_reason is EscalationReason.MISSING_FACTS
    assert r.outcome.missing_facts == ("refund_amount",)
    assert "dominance" in r.trace.precedence.applied_rules
    assert r.trace.precedence.dominance_blocked_by == ("refund.vip_hold",)


# --- escalation paths --------------------------------------------------------


def test_missing_facts_escalates_when_nothing_matches():
    r = evaluate({"days_since_purchase": 20}, _refund_bundle(ALL), "refund")
    assert r.outcome.kind is OutcomeKind.ESCALATE
    assert r.outcome.escalation_reason is EscalationReason.MISSING_FACTS
    assert "plan_type" in r.outcome.missing_facts


def test_no_matching_policy_escalates():
    facts = {"plan_type": "monthly", "days_since_purchase": 20, "tenure_years": 1,
             "refund_amount": 50, "tenure_months": 12}
    r = evaluate(facts, _refund_bundle(ALL), "refund")
    assert r.outcome.kind is OutcomeKind.ESCALATE
    assert r.outcome.escalation_reason is EscalationReason.NO_MATCHING_POLICY


def test_conflict_tie_escalates():
    a = _p("refund.tie_a", OutcomeKind.APPROVE, "approve_full_refund",
           [_c("plan_type", "eq", "annual", "string")], priority=50)
    b = _p("refund.tie_b", OutcomeKind.DENY, "deny_refund",
           [_c("plan_type", "eq", "annual", "string")], priority=50)
    r = evaluate({"plan_type": "annual"}, _refund_bundle([a, b]), "refund")
    assert r.outcome.kind is OutcomeKind.ESCALATE
    assert r.outcome.escalation_reason is EscalationReason.CONFLICT
    assert r.outcome.conflict_between == ("refund.tie_a", "refund.tie_b")


def test_specificity_beats_priority_order():
    general = _p("refund.general", OutcomeKind.DENY, "deny_refund",
                 [_c("plan_type", "eq", "annual", "string")], priority=90)
    specific = _p("refund.specific", OutcomeKind.APPROVE, "approve_full_refund",
                  [_c("plan_type", "eq", "annual", "string"),
                   _c("days_since_purchase", "lte", 14, "number")], priority=10)
    r = evaluate({"plan_type": "annual", "days_since_purchase": 5},
                 _refund_bundle([general, specific]), "refund")
    assert r.outcome.policy_id == "refund.specific"
    assert "specificity" in r.trace.precedence.applied_rules


# --- strictness & validation -------------------------------------------------


def test_missing_field_never_silently_passes():
    # Regression guard against the legacy condition_eval missing-is-neutral bug.
    loyalty_standalone = LOYALTY.model_copy(update={"overrides": ()})
    only_loyalty = _refund_bundle([loyalty_standalone])
    r = evaluate({"days_since_purchase": 10}, only_loyalty, "refund")
    assert r.outcome.kind is OutcomeKind.ESCALATE
    assert r.outcome.escalation_reason is EscalationReason.MISSING_FACTS


def test_wrong_fact_type_is_request_error():
    try:
        evaluate({"plan_type": "annual", "days_since_purchase": "nine"},
                 _refund_bundle(ALL), "refund")
        assert False, "typed fact mismatch must raise InvalidFactsError"
    except InvalidFactsError:
        pass


def test_unknown_workflow_raises_keyerror():
    try:
        evaluate({}, _refund_bundle(ALL), "nope")
        assert False, "unknown workflow must raise"
    except KeyError:
        pass


def test_unknown_facts_ignored_but_recorded():
    r = evaluate({"plan_type": "annual", "days_since_purchase": 9, "mood": "great"},
                 _refund_bundle(ALL), "refund")
    assert r.outcome.policy_id == "refund.annual_14d"
    assert r.trace.facts_ignored == ("mood",)


def test_fact_default_applied_and_recorded():
    wf = WorkflowSpec(
        name="bug_triage",
        facts=(
            FactSpec(name="priority", value_type="string"),
            FactSpec(name="active_outage", value_type="boolean", default=False),
        ),
    )
    outage = Policy(
        id="triage.outage", workflow="bug_triage",
        effect=Effect(kind=OutcomeKind.ROUTE, action="send_incident_template"),
        priority=95,
        conditions=(_c("active_outage", "eq", True, "boolean"),),
        evidence=(_ev(),),
    )
    p1 = Policy(
        id="triage.p1", workflow="bug_triage",
        effect=Effect(kind=OutcomeKind.ROUTE, action="resolve_within_4_hours"),
        priority=80,
        conditions=(_c("priority", "eq", "p1", "string"),),
        evidence=(_ev(),),
    )
    b = Bundle(company_id="t", workflows=(wf,), policies=(outage, p1))
    r = evaluate({"priority": "P1"}, b, "bug_triage")
    assert r.outcome.action == "resolve_within_4_hours"
    assert r.trace.defaults_applied == ("active_outage",)
    outage_eval = next(p for p in r.trace.policies if p.policy_id == "triage.outage")
    assert outage_eval.status is PolicyStatus.FAILED  # default false -> definitive fail


def test_approval_required_propagates():
    gated = _p("refund.big", OutcomeKind.APPROVE, "approve_full_refund",
               [_c("refund_amount", "gt", 1000, "number")], priority=80,
               authority=Authority(approval_required=True, approver_role="founder"))
    r = evaluate({"plan_type": "monthly", "days_since_purchase": 5, "refund_amount": 2000,
                  "tenure_months": 1, "tenure_years": 0},
                 _refund_bundle([gated]), "refund")
    assert r.outcome.approval_required is True
    assert r.outcome.approver_role == "founder"


# --- determinism -------------------------------------------------------------


def test_bit_exact_determinism_100_runs():
    facts = {"plan_type": "annual", "days_since_purchase": 45, "tenure_years": 4}
    bundle = _refund_bundle(ALL)
    first = evaluate(facts, bundle, "refund").model_dump_json()
    for _ in range(99):
        assert evaluate(facts, bundle, "refund").model_dump_json() == first


def test_trace_records_every_policy():
    r = evaluate({"plan_type": "annual", "days_since_purchase": 9}, _refund_bundle(ALL), "refund")
    assert {p.policy_id for p in r.trace.policies} == {p.id for p in ALL}
    for pe in r.trace.policies:
        assert len(pe.conditions) >= 1


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
