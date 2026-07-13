"""The V1 deterministic evaluator -- a pure function from (facts, bundle,
workflow) to (decision, trace).

PURITY CONTRACT (constitutional -- CLAUDE.md rule 1):
  - No LLM calls. No DB. No network. No clock. No randomness. No environment.
  - Same inputs => byte-identical output, across runs and processes.
  - The ONLY inputs are the arguments. decision ids and timestamps are
    assigned by the service layer (backend/ledger), never here.

SEMANTICS (docs/V1_EXECUTION_PLAN.md step 2; defeasible reading per
docs/Kernel_arc.md Part 2):
  Every policy in the workflow evaluates to exactly one of:
    matched         -- all conditions pass on present facts
    failed          -- at least one condition definitively fails
    undeterminable  -- no condition fails, but >=1 condition field is absent

  Winner selection among matched policies:
    1. overrides edges (a matched policy eliminates matched policies it overrides)
    2. specificity   (more conditions wins)
    3. priority      (higher wins)
    4. still tied    -> escalate(conflict)

  Dominance rule (defeasible): the winner stands unless some UNDETERMINABLE
  policy has strictly higher priority -- an unproven exception with authored
  precedence over the winner blocks the decision and escalates for the
  missing facts. An unproven exception WITHOUT higher priority does not block
  the general rule (exceptions must be proven to defeat it).

  No matched policy:
    - undeterminable policies exist -> escalate(missing_facts, their fields)
    - otherwise                     -> escalate(no_matching_policy)

  Strictness: a condition on an absent fact NEVER silently passes. (This
  deliberately replaces the legacy condition_eval.py missing-is-neutral
  behavior, which was a correctness hazard.)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict

from backend.bundle.schema import Bundle, Condition, FactSpec, OutcomeKind, Policy, Scalar

EVALUATOR_VERSION = "kernl-evaluator/1.0.0"
TRACE_VERSION = "1"


class InvalidFactsError(ValueError):
    """A supplied fact has the wrong type for its workflow declaration.
    This is a malformed request (HTTP 400), not an escalation."""


class EscalationReason(str, Enum):
    MISSING_FACTS = "missing_facts"
    NO_MATCHING_POLICY = "no_matching_policy"
    CONFLICT = "conflict"


class PolicyStatus(str, Enum):
    MATCHED = "matched"
    FAILED = "failed"
    UNDETERMINABLE = "undeterminable"


class ConditionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    operator: str
    expected: Union[Scalar, list[Scalar]]
    actual: Optional[Scalar] = None
    result: str  # "pass" | "fail" | "missing"


class PolicyEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_id: str
    priority: int
    specificity: int
    status: PolicyStatus
    conditions: tuple[ConditionResult, ...]
    missing_fields: tuple[str, ...] = ()


class Elimination(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_id: str
    eliminated_by: str
    rule: str  # "overrides" | "specificity" | "priority"


class PrecedenceTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    applied_rules: tuple[str, ...] = ()
    winner: Optional[str] = None
    eliminated: tuple[Elimination, ...] = ()
    tie_between: tuple[str, ...] = ()
    dominance_blocked_by: tuple[str, ...] = ()  # undeterminable ids that blocked


class Outcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: OutcomeKind
    action: Optional[str] = None
    policy_id: Optional[str] = None
    approval_required: bool = False
    approver_role: Optional[str] = None
    escalation_reason: Optional[EscalationReason] = None
    missing_facts: tuple[str, ...] = ()
    conflict_between: tuple[str, ...] = ()


class Trace(BaseModel):
    model_config = ConfigDict(frozen=True)

    trace_version: str = TRACE_VERSION
    evaluator_version: str = EVALUATOR_VERSION
    workflow: str
    facts_supplied: dict[str, Any]
    facts_effective: dict[str, Any]  # after defaults; what conditions saw
    facts_ignored: tuple[str, ...] = ()  # supplied but not declared
    defaults_applied: tuple[str, ...] = ()
    policies: tuple[PolicyEvaluation, ...]
    precedence: PrecedenceTrace
    outcome: Outcome


class EvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    outcome: Outcome
    trace: Trace


# ---------------------------------------------------------------------------
# Fact validation


def _check_type(name: str, value: Any, spec: FactSpec) -> Scalar:
    t = spec.value_type
    if t == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidFactsError(f"fact {name!r} must be a number, got {value!r}")
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value
    if t == "string":
        if not isinstance(value, str):
            raise InvalidFactsError(f"fact {name!r} must be a string, got {value!r}")
        return value
    if t == "boolean":
        if not isinstance(value, bool):
            raise InvalidFactsError(f"fact {name!r} must be a boolean, got {value!r}")
        return value
    raise InvalidFactsError(f"fact {name!r}: unknown declared type {t!r}")


def _validate_facts(
    facts: dict[str, Any], fact_map: dict[str, FactSpec]
) -> tuple[dict[str, Scalar], tuple[str, ...], tuple[str, ...]]:
    effective: dict[str, Scalar] = {}
    ignored: list[str] = []
    defaults: list[str] = []
    for name, value in facts.items():
        spec = fact_map.get(name)
        if spec is None:
            ignored.append(name)
            continue
        effective[name] = _check_type(name, value, spec)
    for name, spec in fact_map.items():
        if name not in effective and spec.default is not None:
            effective[name] = spec.default
            defaults.append(name)
    return effective, tuple(sorted(ignored)), tuple(sorted(defaults))


# ---------------------------------------------------------------------------
# Condition evaluation (strict)


def _norm_str(v: Scalar) -> str:
    return str(v).strip().lower()


def _compare(cond: Condition, actual: Scalar) -> bool:
    op = cond.operator
    if cond.value_type == "number":
        a = float(actual)  # type: ignore[arg-type]
        e = cond.value
        if op == "gt":
            return a > float(e)  # type: ignore[arg-type]
        if op == "gte":
            return a >= float(e)  # type: ignore[arg-type]
        if op == "lt":
            return a < float(e)  # type: ignore[arg-type]
        if op == "lte":
            return a <= float(e)  # type: ignore[arg-type]
        if op == "eq":
            return a == float(e)  # type: ignore[arg-type]
        if op == "neq":
            return a != float(e)  # type: ignore[arg-type]
    elif cond.value_type == "string":
        a = _norm_str(actual)
        if op == "eq":
            return a == _norm_str(cond.value)  # type: ignore[arg-type]
        if op == "neq":
            return a != _norm_str(cond.value)  # type: ignore[arg-type]
        if op == "in":
            return a in [_norm_str(v) for v in cond.value]  # type: ignore[union-attr]
        if op == "not_in":
            return a not in [_norm_str(v) for v in cond.value]  # type: ignore[union-attr]
    elif cond.value_type == "boolean":
        if op == "eq":
            return bool(actual) is bool(cond.value)
    raise AssertionError(f"unreachable: operator {op!r} for {cond.value_type!r}")


def _evaluate_policy(policy: Policy, facts: dict[str, Scalar]) -> PolicyEvaluation:
    results: list[ConditionResult] = []
    missing: list[str] = []
    any_fail = False
    for cond in policy.conditions:
        if cond.field not in facts:
            results.append(
                ConditionResult(
                    field=cond.field,
                    operator=cond.operator,
                    expected=cond.value,
                    actual=None,
                    result="missing",
                )
            )
            missing.append(cond.field)
            continue
        actual = facts[cond.field]
        passed = _compare(cond, actual)
        any_fail = any_fail or not passed
        results.append(
            ConditionResult(
                field=cond.field,
                operator=cond.operator,
                expected=cond.value,
                actual=actual,
                result="pass" if passed else "fail",
            )
        )
    if any_fail:
        status = PolicyStatus.FAILED
    elif missing:
        status = PolicyStatus.UNDETERMINABLE
    else:
        status = PolicyStatus.MATCHED
    return PolicyEvaluation(
        policy_id=policy.id,
        priority=policy.priority,
        specificity=policy.specificity,
        status=status,
        conditions=tuple(results),
        missing_fields=tuple(sorted(set(missing))),
    )


# ---------------------------------------------------------------------------
# Winner selection + dominance


def _select_winner(
    matched: list[Policy],
) -> tuple[Optional[Policy], tuple[str, ...], list[Elimination], tuple[str, ...]]:
    """Returns (winner, applied_rules, eliminations, tie_between)."""
    if not matched:
        return None, (), [], ()
    rules: list[str] = []
    elims: list[Elimination] = []
    survivors = list(matched)

    matched_ids = {p.id for p in survivors}
    overridden: dict[str, str] = {}
    for p in survivors:
        for target in p.overrides:
            if target in matched_ids:
                overridden[target] = p.id
    if overridden:
        rules.append("overrides")
        elims.extend(
            Elimination(policy_id=t, eliminated_by=by, rule="overrides")
            for t, by in sorted(overridden.items())
        )
        survivors = [p for p in survivors if p.id not in overridden]

    if len(survivors) > 1:
        top_spec = max(p.specificity for p in survivors)
        losers = [p for p in survivors if p.specificity < top_spec]
        if losers:
            rules.append("specificity")
            keeper = next(p for p in survivors if p.specificity == top_spec)
            elims.extend(
                Elimination(policy_id=p.id, eliminated_by=keeper.id, rule="specificity")
                for p in sorted(losers, key=lambda p: p.id)
            )
            survivors = [p for p in survivors if p.specificity == top_spec]

    if len(survivors) > 1:
        top_prio = max(p.priority for p in survivors)
        losers = [p for p in survivors if p.priority < top_prio]
        if losers:
            rules.append("priority")
            keeper = next(p for p in survivors if p.priority == top_prio)
            elims.extend(
                Elimination(policy_id=p.id, eliminated_by=keeper.id, rule="priority")
                for p in sorted(losers, key=lambda p: p.id)
            )
            survivors = [p for p in survivors if p.priority == top_prio]

    if len(survivors) > 1:
        return None, tuple(rules), elims, tuple(sorted(p.id for p in survivors))
    if len(survivors) == 1 and not rules:
        rules.append("single_match")
    return survivors[0], tuple(rules), elims, ()


def evaluate(facts: dict[str, Any], bundle: Bundle, workflow: str) -> EvaluationResult:
    """The pure decision function. Raises KeyError for an unknown workflow and
    InvalidFactsError for wrongly-typed facts; both are request errors, not
    decisions. Every other path returns a decision with a complete trace."""

    wf = bundle.workflow(workflow)  # KeyError -> API 400
    fact_map = wf.fact_map()
    effective, ignored, defaults = _validate_facts(facts, fact_map)

    policies = bundle.policies_for(workflow)
    evaluations = tuple(_evaluate_policy(p, effective) for p in policies)
    by_id = {p.id: p for p in policies}

    matched = [by_id[e.policy_id] for e in evaluations if e.status is PolicyStatus.MATCHED]
    undeterminable = [e for e in evaluations if e.status is PolicyStatus.UNDETERMINABLE]

    winner, rules, elims, tie = _select_winner(matched)

    def _trace(outcome: Outcome, precedence: PrecedenceTrace) -> EvaluationResult:
        return EvaluationResult(
            outcome=outcome,
            trace=Trace(
                workflow=workflow,
                facts_supplied=dict(facts),
                facts_effective=dict(effective),
                facts_ignored=ignored,
                defaults_applied=defaults,
                policies=evaluations,
                precedence=precedence,
                outcome=outcome,
            ),
        )

    if tie:
        outcome = Outcome(
            kind=OutcomeKind.ESCALATE,
            escalation_reason=EscalationReason.CONFLICT,
            conflict_between=tie,
        )
        return _trace(
            outcome,
            PrecedenceTrace(applied_rules=rules, eliminated=tuple(elims), tie_between=tie),
        )

    if winner is None:
        if undeterminable:
            fields = tuple(
                sorted({f for e in undeterminable for f in e.missing_fields})
            )
            outcome = Outcome(
                kind=OutcomeKind.ESCALATE,
                escalation_reason=EscalationReason.MISSING_FACTS,
                missing_facts=fields,
            )
        else:
            outcome = Outcome(
                kind=OutcomeKind.ESCALATE,
                escalation_reason=EscalationReason.NO_MATCHING_POLICY,
            )
        return _trace(outcome, PrecedenceTrace(applied_rules=rules, eliminated=tuple(elims)))

    # Dominance: an unproven (undeterminable) policy with strictly higher
    # priority than the winner blocks the decision.
    blockers = [e for e in undeterminable if e.priority > winner.priority]
    if blockers:
        fields = tuple(sorted({f for e in blockers for f in e.missing_fields}))
        blocker_ids = tuple(sorted(e.policy_id for e in blockers))
        outcome = Outcome(
            kind=OutcomeKind.ESCALATE,
            escalation_reason=EscalationReason.MISSING_FACTS,
            missing_facts=fields,
        )
        return _trace(
            outcome,
            PrecedenceTrace(
                applied_rules=rules + ("dominance",),
                winner=None,
                eliminated=tuple(elims),
                dominance_blocked_by=blocker_ids,
            ),
        )

    outcome = Outcome(
        kind=winner.effect.kind,
        action=winner.effect.action,
        policy_id=winner.id,
        approval_required=winner.authority.approval_required,
        approver_role=winner.authority.approver_role,
    )
    return _trace(
        outcome,
        PrecedenceTrace(applied_rules=rules, winner=winner.id, eliminated=tuple(elims)),
    )
