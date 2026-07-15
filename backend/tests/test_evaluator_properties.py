"""Property-based + metamorphic tests for the pure evaluator (Tier-1 hardening,
per docs/V1_EXECUTION_PLAN.md Step 2 DoD and the user's explicit request to
keep this in mind while building on top of the 45 hand-picked golden cases).

These don't replace the golden-case suite (test_evaluator.py) -- they attack a
different failure mode: the golden cases prove specific scenarios stay correct
under change; these prove the evaluator's CONSTITUTIONAL INVARIANTS hold for
GENERATED inputs the authors never thought to write by hand.

Two families:

  PROPERTY tests assert something true of every single evaluation:
    - determinism, the strictness rule (never silently pass on a missing
      fact), escalation/winner mutual exclusivity, the dominance rule, the
      overrides rule, and the declared-fields invariant.

  METAMORPHIC tests assert a relationship between two evaluations that differ
  by one controlled mutation:
    - adding an irrelevant fact must not change the outcome
    - deleting a fact the current winner depends on must dethrone it
    - raising the current winner's priority can never make it lose
    - a new matched policy that overrides the winner must dethrone it

Deterministic and LLM/DB/network-free (Hypothesis explores the input space
in-process against the pure evaluate() function only).
    py -3 backend/tests/test_evaluator_properties.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

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
from backend.runtime.evaluator import PolicyStatus, evaluate

WORKFLOW = "wf"
_DUMMY_EVIDENCE = (
    Evidence(source_id="doc.md", source_version="sha256:x", span_start=0, span_end=4, excerpt="rule"),
)

# A small, fixed field pool -- randomness lives in which fields are USED and
# with what values, not in a churning schema. That keeps generated failures
# interpretable while still covering the interesting state space.
FIELDS: dict[str, tuple[str, tuple]] = {
    "plan_type": ("string", ("annual", "monthly", "enterprise")),
    "days": ("number", (0, 7, 14, 30, 60, 90)),
    "amount": ("number", (0, 100, 500, 5000)),
    "flag": ("boolean", (True, False)),
}
FIELD_NAMES = tuple(FIELDS.keys())

_OPS_BY_TYPE = {
    "string": ("eq", "neq"),
    "number": ("eq", "neq", "gt", "gte", "lt", "lte"),
    "boolean": ("eq",),
}


def _fact_specs() -> tuple[FactSpec, ...]:
    return tuple(FactSpec(name=n, value_type=t) for n, (t, _) in FIELDS.items())


@st.composite
def _condition(draw, field: str) -> Condition:
    vtype, domain = FIELDS[field]
    op = draw(st.sampled_from(_OPS_BY_TYPE[vtype]))
    value = draw(st.sampled_from(domain))
    return Condition(field=field, operator=op, value=value, value_type=vtype)


@st.composite
def _policy(draw, index: int, earlier_ids: tuple[str, ...]) -> Policy:
    pid = f"p{index}"
    cond_fields = draw(
        st.lists(st.sampled_from(FIELD_NAMES), min_size=0, max_size=len(FIELD_NAMES), unique=True)
    )
    conditions = tuple(draw(_condition(f)) for f in cond_fields)
    overrides = tuple(draw(st.lists(st.sampled_from(earlier_ids) if earlier_ids else st.nothing(),
                                     min_size=0, max_size=len(earlier_ids), unique=True)))
    kind = draw(st.sampled_from(list(OutcomeKind)))
    priority = draw(st.integers(min_value=0, max_value=1000))
    return Policy(
        id=pid,
        workflow=WORKFLOW,
        effect=Effect(kind=kind, action=f"action_{pid}"),
        priority=priority,
        conditions=conditions,
        authority=Authority(),
        evidence=_DUMMY_EVIDENCE,
        overrides=overrides,
        unconditional_ack=(len(conditions) == 0),
        rationale="generated",
    )


@st.composite
def bundles(draw, min_policies: int = 1, max_policies: int = 5) -> Bundle:
    n = draw(st.integers(min_value=min_policies, max_value=max_policies))
    policies: list[Policy] = []
    for i in range(n):
        earlier = tuple(p.id for p in policies)
        policies.append(draw(_policy(i, earlier)))
    wf = WorkflowSpec(name=WORKFLOW, facts=_fact_specs())
    return Bundle(company_id="prop-test", workflows=(wf,), policies=tuple(policies))


@st.composite
def facts_for(draw) -> dict:
    present = draw(st.lists(st.sampled_from(FIELD_NAMES), min_size=0, max_size=len(FIELD_NAMES), unique=True))
    out = {}
    for f in present:
        _, domain = FIELDS[f]
        out[f] = draw(st.sampled_from(domain))
    return out


_SETTINGS = settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])


# ---------------------------------------------------------------------------
# PROPERTY tests: invariants of a single evaluation


@given(b=bundles(), f=st.data())
@_SETTINGS
def test_property_determinism(b, f):
    facts = f.draw(facts_for())
    r1 = evaluate(facts, b, WORKFLOW)
    r2 = evaluate(facts, b, WORKFLOW)
    assert r1.outcome.model_dump() == r2.outcome.model_dump()
    assert r1.trace.model_dump() == r2.trace.model_dump()


@given(b=bundles(), f=st.data())
@_SETTINGS
def test_property_strictness_never_silently_passes_missing_fact(b, f):
    """The constitutional rule: a condition on an absent fact is 'missing',
    never 'pass'. This is the exact bug class the evaluator replaced."""
    facts = f.draw(facts_for())
    result = evaluate(facts, b, WORKFLOW)
    for pe in result.trace.policies:
        for cr in pe.conditions:
            if cr.field not in facts:
                assert cr.result == "missing", (
                    f"condition on absent field {cr.field!r} resolved to "
                    f"{cr.result!r}, not 'missing' -- silent pass/fail on missing data"
                )
                assert cr.actual is None


@given(b=bundles(), f=st.data())
@_SETTINGS
def test_property_escalation_and_winner_are_mutually_exclusive(b, f):
    facts = f.draw(facts_for())
    outcome = evaluate(facts, b, WORKFLOW).outcome
    if outcome.escalation_reason is not None:
        assert outcome.policy_id is None
        assert outcome.action is None
    if outcome.policy_id is not None:
        assert outcome.escalation_reason is None


@given(b=bundles(), f=st.data())
@_SETTINGS
def test_property_dominance_rule_never_violated(b, f):
    """If a policy won, no UNDETERMINABLE policy may have strictly higher
    priority than it -- that must have blocked the decision instead."""
    facts = f.draw(facts_for())
    result = evaluate(facts, b, WORKFLOW)
    winner_id = result.trace.precedence.winner
    if winner_id is None:
        return
    winner_eval = next(pe for pe in result.trace.policies if pe.policy_id == winner_id)
    for pe in result.trace.policies:
        if pe.status is PolicyStatus.UNDETERMINABLE:
            assert pe.priority <= winner_eval.priority, (
                f"undeterminable policy {pe.policy_id} (priority {pe.priority}) "
                f"outranks winner {winner_id} (priority {winner_eval.priority}) "
                "but was not blocked by the dominance rule"
            )


@given(b=bundles(), f=st.data())
@_SETTINGS
def test_property_overridden_policy_never_wins(b, f):
    facts = f.draw(facts_for())
    result = evaluate(facts, b, WORKFLOW)
    overridden_ids = {e.policy_id for e in result.trace.precedence.eliminated if e.rule == "overrides"}
    if result.trace.precedence.winner is not None:
        assert result.trace.precedence.winner not in overridden_ids


@given(b=bundles(), f=st.data())
@_SETTINGS
def test_property_effective_facts_are_declared_fields_only(b, f):
    facts = f.draw(facts_for())
    result = evaluate(facts, b, WORKFLOW)
    declared = set(FIELD_NAMES)
    assert set(result.trace.facts_effective.keys()) <= declared
    assert set(result.trace.facts_ignored) <= set(facts.keys())


# ---------------------------------------------------------------------------
# METAMORPHIC tests: relate two evaluations under a controlled mutation


@given(b=bundles(), f=st.data())
@_SETTINGS
def test_metamorphic_irrelevant_extra_field_does_not_change_outcome(b, f):
    """A fact for a field NOT declared by the workflow can never influence any
    condition (it always lands in facts_ignored) -- the outcome must be
    byte-identical with or without it."""
    facts = f.draw(facts_for())
    baseline = evaluate(facts, b, WORKFLOW)

    mutated = dict(facts)
    mutated["__irrelevant_undeclared_field__"] = "noise"
    mutated_result = evaluate(mutated, b, WORKFLOW)

    assert baseline.outcome.model_dump() == mutated_result.outcome.model_dump()


@given(b=bundles(min_policies=1, max_policies=5), f=st.data())
@_SETTINGS
def test_metamorphic_removing_winners_required_fact_dethrones_it(b, f):
    """If a decision has a winner whose conditions reference at least one
    field, deleting that field from facts must produce a DIFFERENT winner (or
    an escalation) -- the same policy can never keep winning once one of its
    own matched conditions can no longer be verified."""
    facts = f.draw(facts_for())
    baseline = evaluate(facts, b, WORKFLOW)
    winner_id = baseline.trace.precedence.winner
    if winner_id is None:
        return
    winner_policy = next(p for p in b.policies if p.id == winner_id)
    fields_used = {c.field for c in winner_policy.conditions if c.field in facts}
    if not fields_used:
        return  # winner had no facts-backed conditions to remove

    field_to_remove = sorted(fields_used)[0]
    mutated = {k: v for k, v in facts.items() if k != field_to_remove}
    mutated_result = evaluate(mutated, b, WORKFLOW)

    assert mutated_result.trace.precedence.winner != winner_id, (
        f"policy {winner_id} still won after removing {field_to_remove!r}, "
        "one of its own matched-condition fields"
    )


@given(b=bundles(), f=st.data())
@_SETTINGS
def test_metamorphic_raising_winners_priority_cannot_dethrone_it(b, f):
    """Priority only breaks ties among survivors of overrides+specificity.
    Strictly raising the CURRENT winner's priority (bundle content otherwise
    identical) can never cause a different policy to win instead."""
    facts = f.draw(facts_for())
    baseline = evaluate(facts, b, WORKFLOW)
    winner_id = baseline.trace.precedence.winner
    if winner_id is None:
        return

    boosted_policies = tuple(
        p.model_copy(update={"priority": 1000}) if p.id == winner_id else p for p in b.policies
    )
    boosted_bundle = b.model_copy(update={"policies": boosted_policies})
    boosted_result = evaluate(facts, boosted_bundle, WORKFLOW)

    assert boosted_result.trace.precedence.winner == winner_id, (
        f"raising winner {winner_id}'s priority to 1000 changed the winner to "
        f"{boosted_result.trace.precedence.winner!r}"
    )


@given(b=bundles(min_policies=1, max_policies=4), f=st.data())
@_SETTINGS
def test_metamorphic_new_overriding_policy_dethrones_the_winner(b, f):
    """A new policy that overrides EVERY currently-matched policy becomes the
    sole survivor of the overrides elimination step, and must win outright --
    regardless of specificity/priority, since no other matched policy remains
    to contest those later tiebreak rounds.

    (A challenger that overrides only the previous winner is NOT guaranteed to
    win: if other matched-but-lower-ranked policies survive alongside it, they
    can still beat it on specificity. That was this test's first draft, and
    the property-based run correctly caught the flawed assumption -- overrides
    eliminates only its named targets, it doesn't crown the overrider.)"""
    facts = f.draw(facts_for())
    baseline = evaluate(facts, b, WORKFLOW)
    matched_ids = tuple(sorted(
        pe.policy_id for pe in baseline.trace.policies if pe.status is PolicyStatus.MATCHED
    ))
    if not matched_ids:
        return

    challenger = Policy(
        id="wf.challenger",
        workflow=WORKFLOW,
        effect=Effect(kind=OutcomeKind.DENY, action="challenger_action"),
        priority=1000,
        conditions=(),
        authority=Authority(),
        evidence=_DUMMY_EVIDENCE,
        overrides=matched_ids,  # eliminates every current contender
        unconditional_ack=True,
        rationale="generated challenger",
    )
    mutated_bundle = b.model_copy(update={"policies": b.policies + (challenger,)})
    mutated_result = evaluate(facts, mutated_bundle, WORKFLOW)

    assert mutated_result.trace.precedence.winner == "wf.challenger", (
        f"challenger overriding ALL matched policies {matched_ids} did not win; "
        f"got {mutated_result.trace.precedence.winner!r}"
    )


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"Results: {len(TESTS) - failed}/{len(TESTS)} passed, {failed} failed")
    sys.exit(1 if failed else 0)
