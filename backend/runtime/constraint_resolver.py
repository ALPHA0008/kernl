"""
Constraint resolver — the core policy engine that makes Phase 4 real.

Deterministically resolves admissible actions from:
  - Applicable policies (from graph retrieval, already condition-filtered)
  - Typed conditions evaluated against context
  - Precedence hierarchy (authority, specificity, priority)
  - Authority rules (who can do what)
  - Skill-derived admissible actions (fallback when graph is weak)

This module NEVER calls an LLM. It is deterministic.
The LLM's job is to verbalize what this module decides — not to decide itself.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from backend.runtime.condition_eval import evaluate_conditions
from backend.runtime.precedence import (
    resolve_conflicts as resolve_precedence,
    get_authority_level,
    merge_with_metadata as merge_authority_levels,
)

DEFAULT_THRESHOLDS = {
    "ambiguity_entropy": 0.75,
    "min_confidence_for_auto_action": 0.40,
    "graph_fallback_threshold": 0.5,
    "score_differential_threshold": 0.10,
}


def _get_thresholds(metadata: dict = None) -> dict:
    th = dict(DEFAULT_THRESHOLDS)
    if metadata and isinstance(metadata, dict):
        meta_th = metadata.get("thresholds", {})
        if isinstance(meta_th, dict):
            for k in th:
                v = meta_th.get(k)
                if v is not None and isinstance(v, (int, float)):
                    th[k] = v
    return th


@dataclass
class ResolvedAction:
    action_type: str
    category: str
    confidence: float
    requires_approval: bool = False
    escalation_target: Optional[str] = None
    policy_applied: str = ""
    evidence: List[str] = field(default_factory=list)
    condition_trace: List[dict] = field(default_factory=list)
    precedence_trace: List[str] = field(default_factory=list)
    source: str = "skill"

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type,
            "category": self.category,
            "confidence": round(self.confidence, 4),
            "requires_approval": self.requires_approval,
            "escalation_target": self.escalation_target,
            "policy_applied": self.policy_applied,
            "evidence": self.evidence[:3],
            "condition_trace": self.condition_trace,
            "precedence_trace": self.precedence_trace[:3],
            "source": self.source,
        }


@dataclass
class ConstraintResult:
    primary_action: Optional[ResolvedAction]
    all_admissible_actions: List[ResolvedAction]
    is_ambiguous: bool
    entropy: float
    escalation_required: bool
    escalation_target: Optional[str]
    resolution_source: str
    reasoning_steps: List[str]

    def to_dict(self) -> dict:
        return {
            "primary_action": self.primary_action.to_dict()
            if self.primary_action
            else None,
            "all_admissible_actions": [
                a.to_dict() for a in self.all_admissible_actions
            ],
            "is_ambiguous": self.is_ambiguous,
            "entropy": round(self.entropy, 4),
            "escalation_required": self.escalation_required,
            "escalation_target": self.escalation_target,
            "resolution_source": self.resolution_source,
            "reasoning_steps": self.reasoning_steps,
        }


def compute_entropy(actions: List[ResolvedAction]) -> float:
    if not actions:
        return 1.0
    scores = [a.confidence for a in actions]
    total = sum(scores)
    if total <= 0:
        return 1.0
    probs = [s / total for s in scores]
    entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    max_entropy = math.log2(len(probs)) if len(probs) > 1 else 1.0
    return entropy / max_entropy if max_entropy > 0 else 1.0


def _build_resolved_action(
    action_type: str,
    category: str,
    confidence: float,
    policy: dict = None,
    condition_trace: list = None,
    precedence_trace: list = None,
    source: str = "skill",
) -> ResolvedAction:
    return ResolvedAction(
        action_type=action_type,
        category=category or "general",
        confidence=confidence,
        requires_approval=policy.get("requires_approval", False) if policy else False,
        escalation_target=policy.get("escalation_target") if policy else None,
        policy_applied=(policy.get("rule_text") or policy.get("rule") or "")
        if policy
        else "",
        evidence=policy.get("evidence", []) if policy else [],
        condition_trace=condition_trace or [],
        precedence_trace=precedence_trace or [],
        source=source,
    )


def _apply_authority_rules(
    resolved_actions: List[ResolvedAction],
    requester_role: Optional[str],
    authority_rules: dict,
    context: dict,
) -> List[ResolvedAction]:
    if not requester_role or not authority_rules:
        return resolved_actions

    requester_level = get_authority_level(requester_role)
    rule = authority_rules.get(requester_role)
    if not rule:
        return resolved_actions

    can_approve = rule.get("can_approve", [])
    up_to_amount = rule.get("up_to_amount")

    for action in resolved_actions:
        action_type = action.action_type
        if action_type not in can_approve:
            action.requires_approval = True
            action.precedence_trace.append(
                f"Requester ({requester_role}) cannot approve '{action_type}'; escalation needed"
            )
            action.escalation_target = _find_escalation_target(
                action_type, authority_rules
            )
            continue

        if up_to_amount is not None and action_type in ("approve", "approve_prorated"):
            refund_amount = context.get("refund_amount", 0)
            if isinstance(refund_amount, (int, float)) and refund_amount > up_to_amount:
                action.requires_approval = True
                action.precedence_trace.append(
                    f"Amount ${refund_amount} exceeds ${up_to_amount} limit for {requester_role}"
                )
                action.escalation_target = _find_escalation_target(
                    action_type, authority_rules
                )

    return resolved_actions


def _find_escalation_target(action_type: str, authority_rules: dict) -> Optional[str]:
    for role, rule in sorted(
        authority_rules.items(),
        key=lambda x: get_authority_level(x[0]),
        reverse=True,
    ):
        if action_type in rule.get("can_approve", []):
            return role
    return None


def _resolve_via_graph(
    graph_result: dict,
    context: dict,
    precedence_edges: list,
    authority_rules: dict,
    requester_role: Optional[str],
    thresholds: dict,
    metadata: dict = None,
) -> ConstraintResult:
    steps = []
    ambiguity_th = thresholds["ambiguity_entropy"]

    policies = graph_result.get("policies", [])
    graph_confidence = graph_result.get("graph_confidence", 0.0)
    steps.append(
        f"Graph provided {len(policies)} policies at confidence {graph_confidence:.2f}"
    )

    condition_results = graph_result.get("condition_results", [])
    for i, (policy, cond_result) in enumerate(zip(policies, condition_results)):
        steps.append(
            f"Policy #{i + 1}: '{policy.get('rule_text', policy.get('rule', ''))[:80]}' — "
            f"conditions: {cond_result.get('matched_count', 0)}/{cond_result.get('total_evaluated', 0)} matched"
        )

    if not policies:
        return None

    auth_levels = None
    if metadata:
        ma = metadata.get("authority_levels", {})
        if ma:
            auth_levels = merge_authority_levels(ma)

    precedence_edges = precedence_edges or []
    scored = resolve_precedence(policies, precedence_edges, context, auth_levels)

    resolved_actions = []
    for s in scored:
        policy = s["policy"]
        effect = policy.get("effect", "ambiguous")
        priority_score = s["effective_priority"]
        confidence = min(priority_score / 10.0, 0.95)

        cond_detail = None
        for cr in condition_results:
            if cr.get("details"):
                cond_detail = cr["details"]
                break

        action = _build_resolved_action(
            action_type=effect,
            category=policy.get("category", "general"),
            confidence=confidence,
            policy=policy,
            condition_trace=cond_detail or [],
            precedence_trace=s.get("reasons", []),
            source="graph",
        )
        resolved_actions.append(action)

    resolved_actions = _apply_authority_rules(
        resolved_actions, requester_role, authority_rules, context
    )

    entropy = compute_entropy(resolved_actions)
    steps.append(f"Graph resolution: entropy={entropy:.3f}")

    is_ambiguous = entropy > ambiguity_th
    primary = resolved_actions[0] if resolved_actions and not is_ambiguous else None

    escalation_required = any(a.requires_approval for a in resolved_actions)
    escalation_target = None
    if escalation_required:
        for a in resolved_actions:
            if a.requires_approval and a.escalation_target:
                escalation_target = a.escalation_target
                break

    return ConstraintResult(
        primary_action=primary,
        all_admissible_actions=resolved_actions,
        is_ambiguous=is_ambiguous,
        entropy=entropy,
        escalation_required=escalation_required,
        escalation_target=escalation_target,
        resolution_source="graph",
        reasoning_steps=steps,
    )


def _compute_condition_adjustment(skill_candidate: dict, context: dict) -> tuple:
    context_values = {}
    for k, v in (context or {}).items():
        k_lower = str(k).lower().strip()
        try:
            context_values[k_lower] = float(v)
        except (ValueError, TypeError):
            if isinstance(v, str):
                context_values[k_lower] = v.lower().strip()
            else:
                context_values[k_lower] = v

    conditions = skill_candidate.get("conditions", [])
    if not conditions:
        return 1.0, ["No conditions to evaluate"]

    matched = 0
    evaluated = 0
    trace = []

    for cond in conditions:
        field = cond.get("field")
        operator = cond.get("operator")
        value = cond.get("value")
        cond_type = cond.get("type", "string")

        ctx_val = context_values.get(field)
        if ctx_val is None:
            trace.append(f"{field}: not in context (neutral)")
            continue

        evaluated += 1
        is_match = False
        try:
            if cond_type == "number":
                if operator == "<=":
                    is_match = ctx_val <= value
                elif operator == ">=":
                    is_match = ctx_val >= value
                elif operator == ">":
                    is_match = ctx_val > value
                    if not is_match and ctx_val == value:
                        is_match = True
                elif operator == "<":
                    is_match = ctx_val < value
                    if not is_match and ctx_val == value:
                        is_match = True
                elif operator == "==":
                    is_match = ctx_val == value
                elif operator == "!=":
                    is_match = ctx_val != value
            elif cond_type == "string":
                if operator == "==":
                    is_match = str(ctx_val) == str(value).lower()
                elif operator == "!=":
                    is_match = str(ctx_val) != str(value).lower()
                elif operator == "in" and isinstance(value, list):
                    is_match = str(ctx_val) in [str(v).lower() for v in value]
                elif operator == "not_in" and isinstance(value, list):
                    is_match = str(ctx_val) not in [str(v).lower() for v in value]
        except (TypeError, ValueError):
            pass

        if is_match:
            matched += 1
            trace.append(f"{field} {operator} {value} (matched ctx={ctx_val})")
        else:
            trace.append(f"{field} {operator} {value} (FAILED ctx={ctx_val})")

    if evaluated == 0:
        return 1.0, trace + [
            "No evaluable conditions (all fields missing from context)"
        ]

    condition_score = matched / evaluated
    multiplier = 0.5 + 0.5 * condition_score
    trace.append(
        f"Condition adjustment: {multiplier:.3f} ({matched}/{evaluated} matched, score={condition_score:.2f})"
    )
    return multiplier, trace


def _detect_ambiguity_signals(query_signals: dict, metadata: dict = None) -> list:
    signals = []
    raw_text = (query_signals or {}).get("raw_text", "")
    if not raw_text:
        return signals
    text_lower = raw_text.lower()

    if " or " in text_lower:
        signals.append("or_choice")

    vague_phrases = [
        "handle this appropriately",
        "handle appropriately",
        "what to do",
        "what should",
        "please handle",
        "you decide",
        "what's the right",
        "not sure",
        "best way",
        "appropriate",
    ]
    if any(p in text_lower for p in vague_phrases):
        signals.append("vague_phrasing")

    if "escalate" in text_lower:
        signals.append("escalation_wording")

    if "%" in text_lower or "percent" in text_lower:
        if "exactly" in text_lower:
            signals.append("exact_percent_boundary")

    valid_sets = (metadata or {}).get("valid_sets", {})
    domain_keywords = list(valid_sets.get("departments", []))
    domain_keywords += list(valid_sets.get("workflow_types", []))
    if not domain_keywords:
        domain_keywords = [
            "enterprise",
            "churn",
            "refund",
            "discount",
            "outage",
            "hiring",
        ]

    domain_matches = sum(
        1
        for kw in domain_keywords
        if kw.replace("_", " ") in text_lower or kw in text_lower
    )
    if domain_matches >= min(3, max(1, len(domain_keywords) // 2)):
        signals.append("multi_domain_overlap")

    return signals


def _resolve_via_skills(
    skill_admissible: list,
    context: dict,
    authority_rules: dict,
    requester_role: Optional[str],
    query_signals: dict = None,
    thresholds: dict = None,
    metadata: dict = None,
) -> ConstraintResult:
    if thresholds is None:
        thresholds = _get_thresholds()
    ambiguity_th = thresholds["ambiguity_entropy"]
    score_diff_th = thresholds["score_differential_threshold"]

    steps = []
    steps.append(
        f"Falling back to skill-derived admissible actions ({len(skill_admissible)} candidates)"
    )

    if not skill_admissible:
        return ConstraintResult(
            primary_action=None,
            all_admissible_actions=[],
            is_ambiguous=True,
            entropy=1.0,
            escalation_required=False,
            escalation_target=None,
            resolution_source="skill",
            reasoning_steps=steps + ["No admissible actions from skills either"],
        )

    resolved_actions = []
    for cand in skill_admissible:
        base_confidence = cand.get("retrieval_score", 0.5) * cand.get(
            "action_confidence", 0.5
        )

        cond_adjustment, cond_trace = _compute_condition_adjustment(cand, context)
        adjusted_confidence = base_confidence * cond_adjustment

        action = _build_resolved_action(
            action_type=cand["action"],
            category=cand.get("category", "general"),
            confidence=adjusted_confidence,
            source="skill_fallback" if cand.get("fallback_used") else "skill",
        )
        action.condition_trace = cond_trace
        resolved_actions.append(action)
        steps.append(
            f"  Candidate '{cand['action']}': base={base_confidence:.3f}, "
            f"cond_adj={cond_adjustment:.3f}, adjusted={adjusted_confidence:.3f}"
        )

    resolved_actions.sort(key=lambda a: a.confidence, reverse=True)

    resolved_actions = _apply_authority_rules(
        resolved_actions, requester_role, authority_rules, context
    )

    entropy = compute_entropy(resolved_actions)

    score_diff = 0.0
    if len(resolved_actions) >= 2:
        score_diff = (
            resolved_actions[0].confidence - resolved_actions[1].confidence
        ) / max(resolved_actions[0].confidence, 0.001)

    det_signals = _detect_ambiguity_signals(query_signals or {}, metadata)
    det_ambiguous = bool(det_signals) and score_diff < 0.50

    is_ambiguous = (
        (entropy > ambiguity_th) and (score_diff < score_diff_th) or det_ambiguous
    )

    steps.append(
        f"Skill resolution: entropy={entropy:.3f}, score_diff={score_diff:.3f}, "
        f"ambiguous={is_ambiguous}, det_signals={det_signals}"
    )

    primary = resolved_actions[0] if resolved_actions and not is_ambiguous else None

    escalation_required = any(a.requires_approval for a in resolved_actions)
    escalation_target = None
    if escalation_required:
        for a in resolved_actions:
            if a.requires_approval and a.escalation_target:
                escalation_target = a.escalation_target
                break

    return ConstraintResult(
        primary_action=primary,
        all_admissible_actions=resolved_actions,
        is_ambiguous=is_ambiguous,
        entropy=entropy,
        escalation_required=escalation_required,
        escalation_target=escalation_target,
        resolution_source="skill",
        reasoning_steps=steps,
    )


def resolve(
    graph_result: dict,
    skill_admissible: list,
    context: dict,
    query_signals: dict,
    authority_rules: dict = None,
    requester_role: str = None,
    metadata: dict = None,
) -> ConstraintResult:
    thresholds = _get_thresholds(metadata)

    precedence_edges = (
        graph_result.get("precedence_edges", [])
        if isinstance(graph_result, dict)
        else []
    )
    authority_rules = authority_rules or {}
    context = context or {}

    graph_fallback_th = thresholds["graph_fallback_threshold"]
    graph_success = (
        isinstance(graph_result, dict)
        and graph_result.get("success", False)
        and graph_result.get("graph_confidence", 0.0) >= graph_fallback_th
    )

    if graph_success:
        result = _resolve_via_graph(
            graph_result,
            context,
            precedence_edges,
            authority_rules,
            requester_role,
            thresholds,
            metadata,
        )
        if result is not None:
            return result

    return _resolve_via_skills(
        skill_admissible,
        context,
        authority_rules,
        requester_role,
        query_signals,
        thresholds,
        metadata,
    )
