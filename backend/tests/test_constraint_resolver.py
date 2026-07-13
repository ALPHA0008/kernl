"""
Unit tests for constraint_resolver and guardrails.
No LLM calls. Pure deterministic tests.
"""

import sys
import os
import json
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.runtime.constraint_resolver import (
    resolve,
    compute_entropy,
    ConstraintResult,
    ResolvedAction,
    DEFAULT_THRESHOLDS,
)

AMBIGUITY_ENTROPY_THRESHOLD = DEFAULT_THRESHOLDS["ambiguity_entropy"]
from backend.runtime.guardrails import guardrail_check

import backend.runtime.constraint_resolver as _cr

# The production default is GRAPH_AUTHORITY_ENABLED = False (W1: graph is not
# decision authority). These unit tests exercise the graph-resolution
# MECHANISM, so they enable it explicitly. test_graph_authority_default_off
# guards the production default.
_PRODUCTION_GRAPH_DEFAULT = _cr.GRAPH_AUTHORITY_ENABLED
_cr.GRAPH_AUTHORITY_ENABLED = True


def test_graph_authority_default_off():
    assert _PRODUCTION_GRAPH_DEFAULT is False, (
        "W1: the graph decision path must ship disabled; enabling it requires "
        "an evidence-citing decision record"
    )


def _make_graph_policy(
    policy_id: str,
    rule_text: str,
    effect: str = "approve",
    category: str = "Refunds",
    priority: int = 0,
    authority: str = None,
    confidence: float = 0.7,
    conditions: list = None,
    evidence: list = None,
) -> dict:
    return {
        "id": policy_id,
        "rule_text": rule_text,
        "category": category,
        "effect": effect,
        "priority": priority,
        "authority": authority,
        "confidence": confidence,
        "conditions": conditions or [],
        "evidence": evidence or [],
    }


def _make_graph_result(
    success: bool = True,
    policies: list = None,
    graph_confidence: float = 0.7,
    reasoning_steps: list = None,
) -> dict:
    condition_results = []
    for p in policies or []:
        condition_results.append(
            {
                "all_met": True,
                "matched_count": len(p.get("conditions", [])),
                "total_evaluated": len(p.get("conditions", [])),
                "details": [],
            }
        )
    return {
        "success": success,
        "policies": policies or [],
        "condition_results": condition_results,
        "graph_confidence": graph_confidence,
        "reasoning_steps": reasoning_steps or ["Graph resolved via unit test"],
    }


def _make_skill_action(
    action: str,
    retrieval_score: float = 0.6,
    action_confidence: float = 0.7,
    specificity: int = 2,
    category: str = "general",
    fallback_used: bool = False,
) -> dict:
    return {
        "action": action,
        "retrieval_score": retrieval_score,
        "source_skill": "test_skill",
        "action_confidence": action_confidence,
        "specificity": specificity,
        "category": category,
        "fallback_used": fallback_used,
    }


def _make_authority_rules() -> dict:
    return {
        "founder": {
            "can_approve": [
                "approve",
                "approve_prorated",
                "deny",
                "get_founder_approval",
                "escalate",
            ],
            "up_to_amount": None,
            "source": "test",
        },
        "support_agent": {
            "can_approve": ["approve", "approve_prorated", "deny"],
            "up_to_amount": 500.0,
            "source": "test",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Compute Entropy
# ═══════════════════════════════════════════════════════════════════════════════


def test_entropy_empty_list():
    assert compute_entropy([]) == 1.0


def test_entropy_single_action():
    actions = [ResolvedAction(action_type="approve", category="test", confidence=0.9)]
    assert compute_entropy(actions) == 0.0


def test_entropy_two_equal():
    actions = [
        ResolvedAction(action_type="approve", category="test", confidence=0.5),
        ResolvedAction(action_type="deny", category="test", confidence=0.5),
    ]
    e = compute_entropy(actions)
    assert e == 1.0, f"Expected 1.0 for equal confidences, got {e}"


def test_entropy_two_unequal():
    actions = [
        ResolvedAction(action_type="approve", category="test", confidence=0.9),
        ResolvedAction(action_type="deny", category="test", confidence=0.1),
    ]
    e = compute_entropy(actions)
    assert e < 0.75, f"Expected low entropy for clear winner, got {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# Graph-based Resolution
# ═══════════════════════════════════════════════════════════════════════════════


def test_graph_resolve_clear_winner():
    result = resolve(
        graph_result=_make_graph_result(
            policies=[
                _make_graph_policy(
                    "refund_annual",
                    "Full refund within 14 days for annual plans",
                    effect="approve",
                ),
            ],
            graph_confidence=0.8,
        ),
        skill_admissible=[],
        context={"plan_type": "annual", "days_since_purchase": 9},
        query_signals={},
    )
    assert result.resolution_source == "graph"
    assert result.primary_action is not None
    assert result.primary_action.action_type == "approve"
    assert not result.is_ambiguous


def test_graph_resolve_no_policies():
    result = resolve(
        graph_result=_make_graph_result(
            success=False, policies=[], graph_confidence=0.0
        ),
        skill_admissible=[
            _make_skill_action("approve", retrieval_score=0.6),
        ],
        context={},
        query_signals={},
    )
    assert result.resolution_source == "skill"
    assert result.primary_action is not None


def test_graph_resolve_ambiguous():
    result = resolve(
        graph_result=_make_graph_result(
            policies=[
                _make_graph_policy(
                    "policy_a",
                    "Approve all",
                    effect="approve",
                    priority=0,
                    confidence=0.5,
                ),
                _make_graph_policy(
                    "policy_b", "Deny all", effect="deny", priority=0, confidence=0.5
                ),
            ],
            graph_confidence=0.7,
        ),
        skill_admissible=[],
        context={},
        query_signals={},
    )
    assert result.primary_action is None
    assert result.is_ambiguous
    assert len(result.all_admissible_actions) == 2


def test_graph_resolve_escalation():
    result = resolve(
        graph_result=_make_graph_result(
            policies=[
                _make_graph_policy(
                    "refund_over_500",
                    "Refunds over $500 need Founder approval",
                    effect="get_founder_approval",
                    priority=2,
                    confidence=0.9,
                ),
            ],
            graph_confidence=0.8,
        ),
        skill_admissible=[],
        context={"refund_amount": 700},
        query_signals={},
    )
    assert result.resolution_source == "graph"
    assert result.primary_action is not None
    assert result.primary_action.action_type == "get_founder_approval"


def test_graph_resolve_empty_graph_and_empty_skills():
    result = resolve(
        graph_result=_make_graph_result(
            success=False, policies=[], graph_confidence=0.0
        ),
        skill_admissible=[],
        context={},
        query_signals={},
    )
    assert result.primary_action is None
    assert result.is_ambiguous
    assert len(result.all_admissible_actions) == 0
    assert result.entropy == 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# Skill-based Fallback
# ═══════════════════════════════════════════════════════════════════════════════


def test_skill_fallback_single():
    result = resolve(
        graph_result=_make_graph_result(
            success=False, policies=[], graph_confidence=0.0
        ),
        skill_admissible=[
            _make_skill_action("approve", retrieval_score=0.8, specificity=3),
        ],
        context={},
        query_signals={},
    )
    assert result.resolution_source == "skill"
    assert result.primary_action is not None
    assert result.primary_action.action_type == "approve"


def test_skill_fallback_ambiguous():
    result = resolve(
        graph_result=_make_graph_result(
            success=False, policies=[], graph_confidence=0.0
        ),
        skill_admissible=[
            _make_skill_action("approve", retrieval_score=0.4),
            _make_skill_action("deny", retrieval_score=0.4),
        ],
        context={},
        query_signals={},
    )
    assert result.is_ambiguous
    assert result.primary_action is None


def test_skill_fallback_multiple_but_clear():
    result = resolve(
        graph_result=_make_graph_result(
            success=False, policies=[], graph_confidence=0.0
        ),
        skill_admissible=[
            _make_skill_action("approve", retrieval_score=0.9),
            _make_skill_action("deny", retrieval_score=0.2),
            _make_skill_action("escalate", retrieval_score=0.15),
        ],
        context={},
        query_signals={},
    )
    assert result.primary_action is not None
    assert result.primary_action.action_type == "approve"
    assert not result.is_ambiguous


# ═══════════════════════════════════════════════════════════════════════════════
# Authority Rules
# ═══════════════════════════════════════════════════════════════════════════════


def test_authority_support_agent_within_limit():
    result = resolve(
        graph_result=_make_graph_result(
            policies=[
                _make_graph_policy(
                    "refund", "Approve refund under $500", effect="approve"
                ),
            ],
            graph_confidence=0.8,
        ),
        skill_admissible=[],
        context={"refund_amount": 300, "requested_by": "support_agent"},
        query_signals={},
        authority_rules=_make_authority_rules(),
        requester_role="support_agent",
    )
    assert result.primary_action is not None
    assert result.primary_action.action_type == "approve"
    assert not result.primary_action.requires_approval


def test_authority_support_agent_over_limit():
    result = resolve(
        graph_result=_make_graph_result(
            policies=[
                _make_graph_policy(
                    "refund", "Approve refund under $700", effect="approve"
                ),
            ],
            graph_confidence=0.8,
        ),
        skill_admissible=[],
        context={"refund_amount": 600, "requested_by": "support_agent"},
        query_signals={},
        authority_rules=_make_authority_rules(),
        requester_role="support_agent",
    )
    assert result.primary_action is not None
    assert result.primary_action.requires_approval
    assert result.escalation_required


def test_authority_founder_no_limit():
    result = resolve(
        graph_result=_make_graph_result(
            policies=[
                _make_graph_policy("refund", "Approve any refund", effect="approve"),
            ],
            graph_confidence=0.8,
        ),
        skill_admissible=[],
        context={"refund_amount": 100000, "requested_by": "founder"},
        query_signals={},
        authority_rules=_make_authority_rules(),
        requester_role="founder",
    )
    assert result.primary_action is not None
    assert not result.primary_action.requires_approval
    assert not result.escalation_required


# ═══════════════════════════════════════════════════════════════════════════════
# Guardrails
# ═══════════════════════════════════════════════════════════════════════════════


def _make_resolver_result(
    primary_action_type: str = "approve",
    entropy: float = 0.0,
    escalation: bool = False,
    confidence: float = 0.85,
) -> ConstraintResult:
    primary = None
    if primary_action_type:
        primary = ResolvedAction(
            action_type=primary_action_type,
            category="test",
            confidence=confidence,
            requires_approval=escalation,
            escalation_target="founder" if escalation else None,
            policy_applied="Test policy",
            evidence=["source: test"],
            source="graph",
        )
    return ConstraintResult(
        primary_action=primary,
        all_admissible_actions=[primary] if primary else [],
        is_ambiguous=primary is None,
        entropy=entropy,
        escalation_required=escalation,
        escalation_target="founder" if escalation else None,
        resolution_source="graph" if primary else "skill",
        reasoning_steps=["Resolver decided via test"],
    )


def test_guardrail_llm_agrees():
    resolver = _make_resolver_result("approve")
    llm = {"action_type": "approve", "recommended_action": "ok", "rule_applied": "rule"}
    result = guardrail_check(llm, resolver)
    assert result["_guardrail_fired"] is False
    assert result["action_type"] == "approve"


def test_guardrail_llm_disagrees():
    resolver = _make_resolver_result("approve")
    llm = {
        "action_type": "deny",
        "recommended_action": "I think deny",
        "rule_applied": "rule",
    }
    result = guardrail_check(llm, resolver)
    assert result["_guardrail_fired"] is True
    assert result["action_type"] == "approve"
    assert "diverged" in result["_guardrail_reason"]


def test_guardrail_llm_empty_action():
    resolver = _make_resolver_result("approve")
    llm = {"action_type": "", "recommended_action": "idk", "rule_applied": ""}
    result = guardrail_check(llm, resolver)
    assert result["_guardrail_fired"] is True
    assert result["action_type"] == "approve"


def test_guardrail_resolver_ambiguous():
    resolver = _make_resolver_result(primary_action_type=None, entropy=0.85)
    llm = {"action_type": "approve", "recommended_action": "approve it"}
    result = guardrail_check(llm, resolver)
    assert result["action_type"] == "ambiguous"
    assert result["_guardrail_fired"] is True


def test_guardrail_llm_not_dict():
    resolver = _make_resolver_result("approve")
    result = guardrail_check("not a dict", resolver)
    assert result["_guardrail_fired"] is True
    assert result["action_type"] == "approve"


def test_guardrail_fills_evidence():
    resolver = _make_resolver_result("approve")
    llm = {
        "action_type": "approve",
        "rule_applied": "LLM rule",
        "evidence": ["LLM evidence"],
    }
    result = guardrail_check(llm, resolver)
    assert result["action_type"] == "approve"
    assert result["_guardrail_fired"] is False
    assert result["rule_applied"] == "LLM rule"


def test_guardrail_escalation():
    resolver = _make_resolver_result("approve", escalation=True)
    llm = {"action_type": "deny", "recommended_action": "deny it"}
    result = guardrail_check(llm, resolver)
    assert result["_guardrail_fired"] is True
    assert result["action_type"] == "approve"


# ═══════════════════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


def test_null_authority_rules():
    result = resolve(
        graph_result=_make_graph_result(
            policies=[_make_graph_policy("p1", "Rule", effect="approve")],
            graph_confidence=0.8,
        ),
        skill_admissible=[],
        context={},
        query_signals={},
        authority_rules=None,
        requester_role=None,
    )
    assert result.primary_action is not None
    assert result.primary_action.action_type == "approve"


def test_precedence_higher_priority_wins():
    result = resolve(
        graph_result=_make_graph_result(
            policies=[
                _make_graph_policy(
                    "low_prio",
                    "Low priority rule",
                    effect="deny",
                    priority=1,
                    confidence=0.5,
                ),
                _make_graph_policy(
                    "high_prio",
                    "High priority rule",
                    effect="approve",
                    priority=10,
                    confidence=0.9,
                ),
            ],
            graph_confidence=0.8,
        ),
        skill_admissible=[],
        context={},
        query_signals={},
    )
    assert result.primary_action is not None
    assert result.primary_action.action_type == "approve"


def test_constraint_result_to_dict():
    resolver = _make_resolver_result("approve", entropy=0.3)
    d = resolver.to_dict()
    assert d["primary_action"]["action_type"] == "approve"
    assert d["entropy"] == 0.3
    assert d["resolution_source"] == "graph"
    assert d["is_ambiguous"] is False


def test_constraint_result_ambiguous_to_dict():
    resolver = _make_resolver_result(primary_action_type=None, entropy=0.9)
    d = resolver.to_dict()
    assert d["primary_action"] is None
    assert d["is_ambiguous"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# Run all
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        ("graph_authority_default_off", test_graph_authority_default_off),
        ("entropy_empty_list", test_entropy_empty_list),
        ("entropy_single_action", test_entropy_single_action),
        ("entropy_two_equal", test_entropy_two_equal),
        ("entropy_two_unequal", test_entropy_two_unequal),
        ("graph_resolve_clear_winner", test_graph_resolve_clear_winner),
        ("graph_resolve_no_policies", test_graph_resolve_no_policies),
        ("graph_resolve_ambiguous", test_graph_resolve_ambiguous),
        ("graph_resolve_escalation", test_graph_resolve_escalation),
        (
            "graph_resolve_empty_graph_and_empty_skills",
            test_graph_resolve_empty_graph_and_empty_skills,
        ),
        ("skill_fallback_single", test_skill_fallback_single),
        ("skill_fallback_ambiguous", test_skill_fallback_ambiguous),
        ("skill_fallback_multiple_but_clear", test_skill_fallback_multiple_but_clear),
        (
            "authority_support_agent_within_limit",
            test_authority_support_agent_within_limit,
        ),
        ("authority_support_agent_over_limit", test_authority_support_agent_over_limit),
        ("authority_founder_no_limit", test_authority_founder_no_limit),
        ("guardrail_llm_agrees", test_guardrail_llm_agrees),
        ("guardrail_llm_disagrees", test_guardrail_llm_disagrees),
        ("guardrail_llm_empty_action", test_guardrail_llm_empty_action),
        ("guardrail_resolver_ambiguous", test_guardrail_resolver_ambiguous),
        ("guardrail_llm_not_dict", test_guardrail_llm_not_dict),
        ("guardrail_fills_evidence", test_guardrail_fills_evidence),
        ("guardrail_escalation", test_guardrail_escalation),
        ("null_authority_rules", test_null_authority_rules),
        ("precedence_higher_priority_wins", test_precedence_higher_priority_wins),
        ("constraint_result_to_dict", test_constraint_result_to_dict),
        (
            "constraint_result_ambiguous_to_dict",
            test_constraint_result_ambiguous_to_dict,
        ),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1
            import traceback

            traceback.print_exc()

    total = passed + failed
    print(f"\n{'=' * 50}")
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)
    sys.exit(0)
