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
from backend.runtime.evaluator import (
    EscalationReason,
    OutcomeKind,
    PolicyStatus,
    evaluate,
)

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
# "Zero unexplained rulings" -- the arc's V1 release criterion, as a test.
#
# Every ruling the evaluator can emit must carry a complete, self-consistent
# derivation in its trace. Not "has a trace field" -- the trace must actually
# EXPLAIN this specific outcome: a decisive ruling names a winning policy that
# is present, matched, and whose action it carries; an escalation gives a
# concrete reason substantiated by the trace; and the precedence record agrees
# with the outcome. This is asserted over GENERATED bundles/facts (so it holds
# for inputs no author wrote by hand) and, in test_evaluator/test_seed_*,
# against the real corpora.


def _assert_ruling_is_explained(result) -> None:
    """The completeness contract for a single evaluation. Raises AssertionError
    with a specific message on the first gap, so a Hypothesis counterexample
    points straight at the unexplained ruling.

    The load-bearing distinction: a ruling is DECISIVE (a policy matched and
    its effect governs) exactly when escalation_reason is None -- this includes
    escalate-EFFECT policies like 'enterprise refund -> escalate to AM', which
    are deliberate matched rulings, NOT the evaluator failing to rule. A ruling
    is a SYSTEM ESCALATION (the evaluator couldn't rule) exactly when
    escalation_reason is set. So the discriminator is escalation_reason, never
    the outcome KIND (an escalate-kind outcome can be either)."""
    outcome = result.outcome
    trace = result.trace
    by_id = {pe.policy_id: pe for pe in trace.policies}

    # (1) Every ruling shows its work: every policy in the bundle appears in the
    #     trace with a per-condition breakdown (expected/actual/result).
    for pe in trace.policies:
        for cr in pe.conditions:
            assert cr.result in ("pass", "fail", "missing"), (
                f"{pe.policy_id}: condition result {cr.result!r} is not one of "
                "pass/fail/missing"
            )

    is_system_escalation = outcome.escalation_reason is not None

    if not is_system_escalation:
        # (2) A decisive ruling (approve/deny/route OR an escalate-effect policy)
        #     is explained by a concrete winning policy that matched.
        assert outcome.policy_id is not None, (
            f"decisive outcome {outcome.kind} names no winning policy -- unexplained"
        )
        winner = by_id.get(outcome.policy_id)
        assert winner is not None, (
            f"winning policy {outcome.policy_id!r} is absent from the trace"
        )
        assert winner.status is PolicyStatus.MATCHED, (
            f"winning policy {outcome.policy_id!r} is {winner.status}, not MATCHED"
        )
        assert outcome.action is not None, "decisive outcome carries no action"
        # the precedence record must agree on the winner
        assert trace.precedence.winner == outcome.policy_id, (
            f"precedence winner {trace.precedence.winner!r} disagrees with "
            f"outcome policy {outcome.policy_id!r}"
        )

    else:
        # (3) A system escalation is explained by a concrete, substantiated
        #     reason, and names no winning policy (it IS the no-ruling case).
        assert outcome.kind is OutcomeKind.ESCALATE, (
            f"escalation_reason is set but outcome kind is {outcome.kind}, "
            "not escalate"
        )
        assert outcome.policy_id is None and outcome.action is None, (
            "a system escalation must not also name a winning policy/action"
        )
        reason = outcome.escalation_reason

        if reason is EscalationReason.MISSING_FACTS:
            # some policy that could otherwise govern was blocked by a missing
            # fact -> the trace must record at least one 'missing' condition or a
            # dominance block.
            has_missing = any(
                cr.result == "missing"
                for pe in trace.policies for cr in pe.conditions
            )
            blocked = bool(trace.precedence.dominance_blocked_by)
            assert has_missing or blocked, (
                "escalation reason is missing_facts but the trace shows no missing "
                "condition and no dominance block to substantiate it"
            )
        elif reason is EscalationReason.NO_MATCHING_POLICY:
            matched = [pe for pe in trace.policies if pe.status is PolicyStatus.MATCHED]
            assert not matched, (
                "escalation reason is no_matching_policy but the trace HAS matched "
                f"policies: {[pe.policy_id for pe in matched]}"
            )
        elif reason is EscalationReason.CONFLICT:
            # a genuine tie between equally-ranked matched policies, recorded.
            assert trace.precedence.tie_between, (
                "escalation reason is conflict but precedence records no tie_between"
            )
            assert len(trace.precedence.tie_between) >= 2
        else:  # pragma: no cover - EscalationReason is a closed enum
            raise AssertionError(f"unknown escalation reason {reason!r}")


@given(b=bundles(), f=st.data())
@_SETTINGS
def test_property_zero_unexplained_rulings(b, f):
    """Every generated ruling carries a complete derivation (arc V1 release
    criterion: 'zero unexplained rulings')."""
    facts = f.draw(facts_for())
    _assert_ruling_is_explained(evaluate(facts, b, WORKFLOW))


def test_zero_unexplained_rulings_on_real_corpora():
    """The same completeness contract, against BOTH seeded reference bundles and
    every one of their golden-case fact sets -- real authored policy, not just
    generated shapes."""
    from backend.bundle import seed_higgsfield, seed_rivanly

    for seed in (seed_rivanly, seed_higgsfield):
        bundle = seed.build_bundle()
        for case in seed.build_golden_cases():
            result = evaluate(case.facts, bundle, case.workflow)
            _assert_ruling_is_explained(result)


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
