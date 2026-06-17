"""
eval_harness.py
───────────────
21-scenario + 5 adversarial ground-truth eval against the CURRENT Kernl runtime engine.

Usage (from repo root):
    python -m backend.tests.eval_harness           # standard run
    python -m backend.tests.eval_harness --ablation # ablation test (4 configs)

Outputs:
    - Per-scenario PASS/FAIL with actual vs expected action
    - Accuracy % (exact action match)
    - Retrieval score per scenario (quality proxy)
    - Summary table saved to backend/tests/eval_results_baseline.json
"""

import asyncio
import json
import sys
import os
import datetime
import copy

# ── make repo root importable ──────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv

load_dotenv(override=True)

from backend.runtime.brain_agent import handle_agent_query

COMPANY_ID = "rivanly-inc"

# ──────────────────────────────────────────────────────────────────────────────
# Ground-Truth Scenarios
# Derived directly from the 8 source documents.  Expected actions are the ONLY
# correct answers that the policy documents support.  Any deviation is a FAIL.
# ──────────────────────────────────────────────────────────────────────────────
SCENARIOS = [
    # ── REFUND SOP (notion_refund_sop.md) ─────────────────────────────────────
    {
        "id": "REF-01",
        "source": "notion_refund_sop.md",
        "scenario": "Customer on an annual plan is requesting a refund. They purchased 9 days ago.",
        "context": {"plan_type": "annual", "days_since_purchase": 9},
        "expected_action": "approve",
        "expected_rule_contains": "14 days",
        "rationale": "Annual plan, within 14-day window → full refund, no questions asked.",
    },
    {
        "id": "REF-02",
        "source": "notion_refund_sop.md",
        "scenario": "Customer on an annual plan is requesting a refund. They purchased 20 days ago.",
        "context": {"plan_type": "annual", "days_since_purchase": 20},
        "expected_action": "approve_prorated",
        "expected_rule_contains": "prorated",
        "rationale": "Annual plan, after 14 days → prorated refund for remaining months.",
    },
    {
        "id": "REF-03",
        "source": "notion_refund_sop.md",
        "scenario": "An Enterprise customer is requesting a refund for their annual invoice.",
        "context": {"plan_type": "enterprise", "days_since_purchase": 7},
        "expected_action": "escalate",
        "expected_rule_contains": "Account Manager",
        "rationale": "Enterprise customers must always be escalated to AM within 1 hour — no immediate processing.",
    },
    {
        "id": "REF-04",
        "source": "notion_refund_sop.md",
        "scenario": "A customer purchased a Lifetime Deal and is now requesting a full refund.",
        "context": {"plan_type": "lifetime_deal", "days_since_purchase": 30},
        "expected_action": "deny",
        "expected_rule_contains": "lifetime",
        "rationale": "LTD refunds are denied under all circumstances.",
    },
    {
        "id": "REF-05",
        "source": "notion_refund_sop.md",
        "scenario": "A monthly plan customer who joined 2 months ago is requesting a $650 refund.",
        "context": {"plan_type": "monthly", "tenure_months": 2, "refund_amount": 650},
        "expected_action": "get_founder_approval",
        "expected_rule_contains": "Founder",
        "rationale": "Monthly plan, <3 months tenure, >$500 refund → escalate to Founder. Canonical label: get_founder_approval.",
    },
    {
        "id": "REF-06",
        "source": "notion_refund_sop.md",
        "scenario": "A customer is requesting a refund for a purchase they made 75 days ago.",
        "context": {"plan_type": "annual", "days_since_purchase": 75},
        "expected_action": "deny",
        "expected_rule_contains": "60 days",
        "rationale": "Hard cutoff: no refunds after 60 days for ANY tier.",
    },
    {
        "id": "REF-07",
        "source": "notion_refund_sop.md",
        "scenario": "Annual plan customer requesting a refund for a purchase made exactly 14 days ago.",
        "context": {"plan_type": "annual", "days_since_purchase": 14},
        "expected_action": "approve",
        "expected_rule_contains": "14 days",
        "rationale": "14 days is within the boundary (first 14 days) → full refund.",
    },
    # ── CUSTOMER SUCCESS PLAYBOOK (notion_cs_playbook.md) ─────────────────────
    {
        "id": "CS-01",
        "source": "notion_cs_playbook.md",
        "scenario": "A customer account has shown 4 churn signals in the last 30 days: no logins, 2 support escalations, and a downgrade inquiry.",
        "context": {"churn_signals_count": 4, "timeframe_days": 30},
        "expected_action": "schedule_am_call",
        "expected_rule_contains": "24 hours",
        "rationale": "3 or more churn signals in 30 days → AM call within 24 hours.",
    },
    {
        "id": "CS-02",
        "source": "notion_cs_playbook.md",
        "scenario": "A new Enterprise customer just signed. What does the onboarding process require?",
        "context": {"customer_type": "enterprise", "status": "new"},
        "expected_action": "initiate_enterprise_onboarding",
        "expected_rule_contains": "kickoff call",
        "rationale": "Enterprise onboarding requires kickoff call, custom training, and 30-day check-in.",
    },
    {
        "id": "CS-03",
        "source": "notion_cs_playbook.md",
        "scenario": "An account has shown 2 churn signals this month: no logins and one downgrade inquiry.",
        "context": {"churn_signals_count": 2, "timeframe_days": 28},
        "expected_action": "monitor",
        "expected_rule_contains": "3 or more",
        "rationale": "Only 2 signals, threshold is 3 → no AM call required yet.",
    },
    # ── ENGINEERING RUNBOOK (notion_eng_runbook.md) ───────────────────────────
    {
        "id": "ENG-01",
        "source": "notion_eng_runbook.md",
        "scenario": "An Enterprise customer just reported that their dashboard is completely down — they cannot access any data.",
        "context": {"priority": "P0", "customer_type": "enterprise"},
        "expected_action": "page_on_call",
        "expected_rule_contains": "on-call engineer",
        "rationale": "P0 bug from Enterprise customer → page on-call immediately.",
    },
    {
        "id": "ENG-02",
        "source": "notion_eng_runbook.md",
        "scenario": "An Enterprise customer's SLA has been breached by 2.5 hours. Who do we notify?",
        "context": {"customer_type": "enterprise", "sla_breach_hours": 2.5},
        "expected_action": "notify_am_and_eng_lead",
        "expected_rule_contains": "Account Manager",
        "rationale": "Enterprise SLA breached by 2+ hours → notify AM AND Eng Lead immediately.",
    },
    {
        "id": "ENG-03",
        "source": "notion_eng_runbook.md",
        "scenario": "A customer contacts support during an active platform outage asking for troubleshooting help.",
        "context": {"active_outage": True},
        "expected_action": "send_incident_template",
        "expected_rule_contains": "incident response template",
        "rationale": "During active outage: do not troubleshoot, send incident template and link status page.",
    },
    {
        "id": "ENG-04",
        "source": "notion_eng_runbook.md",
        "scenario": "A P1 bug has been reported. The feature is broken but a workaround exists. How long do we have to resolve it?",
        "context": {"priority": "P1"},
        "expected_action": "resolve_within_4_hours",
        "expected_rule_contains": "4 hours",
        "rationale": "P1 bugs must be resolved within 4 hours per runbook.",
    },
    # ── HR PLAYBOOK (notion_hr_playbook.md) ───────────────────────────────────
    {
        "id": "HR-01",
        "source": "notion_hr_playbook.md",
        "scenario": "An engineering candidate has reached the offer stage. Can the recruiter send the offer letter now?",
        "context": {"role": "engineering", "stage": "offer"},
        "expected_action": "get_founder_approval",
        "expected_rule_contains": "Founder approval",
        "rationale": "Engineering offers require Founder approval before sending the offer letter.",
    },
    {
        "id": "HR-02",
        "source": "notion_hr_playbook.md",
        "scenario": "An employee has missed their KPIs for two consecutive quarters. What happens next?",
        "context": {"missed_kpi_quarters": 2},
        "expected_action": "initiate_pip",
        "expected_rule_contains": "Performance Improvement Plan",
        "rationale": "Two consecutive quarters of missed KPIs → PIP is triggered.",
    },
    # ── PRICING POLICY (notion_pricing_policy.md) ─────────────────────────────
    {
        "id": "PRICE-01",
        "source": "notion_pricing_policy.md",
        "scenario": "A customer is churning and has asked for a discount. Support wants to apply a 10% discount to retain them.",
        "context": {"discount_percent": 10, "reason": "churn_save"},
        "expected_action": "approve",
        "expected_rule_contains": "10%",
        "rationale": "Support and CS can apply up to 10% discount to save churning customers.",
    },
    {
        "id": "PRICE-02",
        "source": "notion_pricing_policy.md",
        "scenario": "A customer is requesting a 35% discount. The support agent wants to approve it.",
        "context": {"discount_percent": 35, "requested_by": "support"},
        "expected_action": "escalate",
        "expected_rule_contains": "Account Executive",
        "rationale": "Discounts >30% must go to an AE. Support cannot approve this.",
    },
    {
        "id": "PRICE-03",
        "source": "notion_pricing_policy.md",
        "scenario": "A pre-seed startup is asking about pricing for an annual plan.",
        "context": {"customer_stage": "pre-seed", "plan": "annual"},
        "expected_action": "approve_20_percent_startup_discount",
        "expected_rule_contains": "20%",
        "rationale": "Pre-seed/seed startups may get up to 20% discount on the annual plan for year 1.",
    },
    # ── SLACK / ZENDESK (contradiction / exception scenarios) ─────────────────
    {
        "id": "SLACK-01",
        "source": "slack_export_support.json",
        "scenario": "A loyal customer who has been with us for 4 years is requesting a refund for a charge 45 days ago due to a billing error.",
        "context": {"tenure_years": 4, "days_since_charge": 45},
        "expected_action": "approve",
        "expected_rule_contains": "loyal",
        "rationale": "Slack establishes precedent: >2 year tenure bypasses strict 30-day rule per team lead.",
    },
    {
        "id": "OPS-01",
        "source": "slack_export_ops.json",
        "scenario": "Finance has received a software vendor invoice for $4,200. Who needs to approve it before payment?",
        "context": {"invoice_amount": 4200, "vendor_type": "software"},
        "expected_action": "route_to_ops_lead",
        "expected_rule_contains": "ops lead",
        "rationale": "Software vendor invoices ≥$3,500 must be routed to ops lead before payment.",
    },
    # ── ADVERSARIAL RETRIEVAL SCENARIOS ───────────────────────────────────────
    # These scenarios are specifically designed to expose retrieval failures.
    # They are NOT optimized for the current skill set — they test general
    # operational retrieval quality (anti-overfitting: Change 9).
    {
        "id": "ENG-ADV-01",
        "source": "notion_eng_runbook.md",
        "scenario": "A minor display bug is affecting less than 5% of users. The UI is partially broken but the core features work fine and there is a simple workaround available.",
        "context": {
            "priority": "P2",
            "affected_users_pct": 4,
            "workaround_available": True,
        },
        "expected_action": "resolve_within_4_hours",
        "expected_rule_contains": "4 hours",
        "rationale": "P2 non-critical bug with workaround → resolve within 4h (P1 rule). Should NOT page on-call (P0 rule). Tests severity confusion.",
    },
    {
        "id": "REF-ADV-01",
        "source": "notion_refund_sop.md",
        "scenario": "An Enterprise account manager is requesting a refund on behalf of their enterprise client for an invoice paid 5 days ago.",
        "context": {
            "plan_type": "enterprise",
            "days_since_purchase": 5,
            "requested_by": "account_manager",
        },
        "expected_action": "escalate",
        "expected_rule_contains": "Account Manager",
        "rationale": "Enterprise refunds ALWAYS escalate to AM — the 14-day standard refund window does not apply. Tests tier overlap: enterprise rule overrides standard rule.",
    },
    {
        "id": "HR-ADV-01",
        "source": "notion_hr_playbook.md",
        "scenario": "A product manager candidate has completed all interview rounds and the team is ready to extend an offer. The offer package includes equity. The recruiter is asking if they can send the offer letter directly.",
        "context": {
            "role": "product_manager",
            "stage": "offer",
            "includes_equity": True,
        },
        "expected_action": "get_founder_approval",
        "expected_rule_contains": "Founder approval",
        "rationale": "All offers with equity require Founder approval — not just engineering. Tests conflicting signals: role=PM (not engineering) vs equity=True (always requires Founder).",
    },
    {
        "id": "CS-ADV-01",
        "source": "notion_cs_playbook.md",
        "scenario": "A customer account has shown exactly 2 churn signals this week: they haven't logged in for 10 days and submitted one support ticket.",
        "context": {"churn_signals_count": 2, "timeframe_days": 7},
        "expected_action": "monitor",
        "expected_rule_contains": "3 or more",
        "rationale": "Exactly 2 signals — one below the 3-signal threshold. Should monitor, NOT schedule AM call. Tests boundary awareness and avoidance of threshold overshoot.",
    },
    {
        "id": "PRICE-ADV-01",
        "source": "notion_pricing_policy.md",
        "scenario": "A Series A startup is requesting a 25% discount on their annual plan. The CS rep wants to approve it.",
        "context": {
            "customer_stage": "series_a",
            "discount_percent": 25,
            "requested_by": "cs_rep",
        },
        "expected_action": "escalate",
        "expected_rule_contains": "Account Executive",
        "rationale": "Startup discount ceiling is 20%. A 25% request exceeds this and must go to AE — the CS rep cannot approve. Tests overlapping discount policies: startup discount (20% ceiling) vs general discount escalation rule (>30% needs AE).",
    },
    # ── DETERMINISM SCENARIOS ─────────────────────────────────────────────────
    {
        "id": "DET-01",
        "source": "notion_eng_runbook.md",
        "scenario": "A P1 bug has been reported. Should we resolve it within 4 hours or notify the AM and Eng Lead?",
        "context": {"priority": "P1"},
        "expected_action": "ambiguous",
        "expected_rule_contains": "",
        "rationale": "Multiple valid actions (P1 escalation — could be notify_am_and_eng_lead OR resolve_within_4_hours).",
    },
    {
        "id": "DET-02",
        "source": "notion_hr_playbook.md",
        "scenario": "We need to escalate the candidate's offer for final sign-off.",
        "context": {"stage": "offer"},
        "expected_action": "ambiguous",
        "expected_rule_contains": "",
        "rationale": "Hierarchy ambiguity (generic escalate vs specific get_founder_approval).",
    },
    {
        "id": "DET-03",
        "source": "notion_cs_playbook.md",
        "scenario": "A customer wrote in. Please handle this appropriately.",
        "context": {"vague": True},
        "expected_action": "ambiguous",
        "expected_rule_contains": "",
        "rationale": "Vague phrasing ('handle this appropriately').",
    },
    {
        "id": "DET-04",
        "source": "notion_refund_sop.md",
        "scenario": "An enterprise customer with 4 churn signals is requesting a refund.",
        "context": {"plan_type": "enterprise", "churn_signals": 4},
        "expected_action": "ambiguous",
        "expected_rule_contains": "",
        "rationale": "Overlapping escalation chains (refund + enterprise + AM call all apply).",
    },
    {
        "id": "DET-05",
        "source": "notion_pricing_policy.md",
        "scenario": "A customer wants exactly a 30% discount on their renewal.",
        "context": {"discount_percent": 30},
        "expected_action": "ambiguous",
        "expected_rule_contains": "",
        "rationale": "Approval boundary (exactly at threshold).",
    },
    {
        "id": "DET-06",
        "source": "notion_cs_playbook.md",
        "scenario": "An enterprise customer has a major billing issue.",
        "context": {"customer_type": "enterprise", "issue": "billing"},
        "expected_action": "ambiguous",
        "expected_rule_contains": "",
        "expected_rule_contains": "",
        "rationale": "Conflicting department signals (billing issue from enterprise customer — CS or Finance?).",
    },
    # ── CONDITION BOUNDARY SCENARIOS (Phase 6) ───────────────────────────────
    {
        "id": "COND-01",
        "source": "notion_refund_sop.md",
        "scenario": "Customer asking for a refund exactly 14 days after purchase.",
        "context": {"days_since_purchase": 14},
        "expected_action": "approve",
        "expected_rule_contains": "14 days",
        "rationale": "Exact boundary value (<= 14). Should approve full refund.",
    },
    {
        "id": "COND-02",
        "source": "notion_refund_sop.md",
        "scenario": "Customer asking for a refund 15 days after purchase.",
        "context": {"days_since_purchase": 15},
        "expected_action": "approve_prorated",
        "expected_rule_contains": "prorated",
        "rationale": "Just over boundary value (15 > 14). Should approve prorated.",
    },
    {
        "id": "COND-03",
        "source": "notion_refund_sop.md",
        "scenario": "Refund request for exactly $500.",
        "context": {"refund_amount": 500},
        "expected_action": "approve",
        "expected_rule_contains": "refund",
        "rationale": "Threshold is > $500 for escalation. $500 exactly should not escalate.",
    },
    {
        "id": "COND-04",
        "source": "notion_refund_sop.md",
        "scenario": "Refund request for $501.",
        "context": {"refund_amount": 501},
        "expected_action": "get_founder_approval",
        "expected_rule_contains": "$500",
        "rationale": "Just over threshold (> $500). Must escalate to founder.",
    },
    {
        "id": "COND-05",
        "source": "notion_pricing_policy.md",
        "scenario": "Discount request for exactly 30%.",
        "context": {"discount_percent": 30},
        "expected_action": "ambiguous",
        "expected_rule_contains": "",
        "rationale": "Boundary case for escalation. Should be ambiguous if exactly at boundary without explicit direction.",
    },
    {
        "id": "COND-06",
        "source": "notion_refund_sop.md",
        "scenario": "Refund request 60 days after purchase.",
        "context": {"days_since_purchase": 60},
        "expected_action": "deny",
        "expected_rule_contains": "60 days",
        "rationale": "Hard cutoff boundary (>= 60 or > 60). Should deny.",
    },
    {
        "id": "COND-07",
        "source": "notion_refund_sop.md",
        "scenario": "Refund request for a lifetime deal.",
        "context": {"plan_type": "lifetime_deal"},
        "expected_action": "deny",
        "expected_rule_contains": "lifetime",
        "rationale": "String equality condition match. Lifetime deals cannot be refunded.",
    },
    {
        "id": "COND-08",
        "source": "notion_cs_playbook.md",
        "scenario": "Enterprise customer with 3 churn signals.",
        "context": {"churn_signals_count": 3, "customer_tier": "enterprise"},
        "expected_action": "schedule_am_call",
        "expected_rule_contains": "AM call",
        "rationale": "Overlapping numeric (>=3) and string (enterprise) conditions.",
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# Canonical Action Labels
# The runtime should ideally output one of these. Strict matching checks for these.
# ──────────────────────────────────────────────────────────────────────────────
CANONICAL_ACTIONS = [
    "approve",
    "approve_prorated",
    "deny",
    "escalate",
    "schedule_am_call",
    "initiate_enterprise_onboarding",
    "monitor",
    "page_on_call",
    "notify_am_and_eng_lead",
    "send_incident_template",
    "resolve_within_4_hours",
    "get_founder_approval",
    "initiate_pip",
    "approve_20_percent_startup_discount",
    "route_to_ops_lead",
]

# Relaxed alias mappings for semantic matching
ACTION_ALIASES = {
    "approve": ["approve", "approved", "full refund", "process refund", "grant"],
    "approve_prorated": ["prorated", "partial refund", "pro-rated", "prorate"],
    "deny": ["deny", "denied", "reject", "decline", "no refund"],
    "escalate": [
        "escalate",
        "escalation",
        "route to",
        "forward to",
        "notify",
        "requires approval",
    ],
    "schedule_am_call": ["schedule", "am call", "account manager call", "24 hours"],
    "initiate_enterprise_onboarding": [
        "kickoff",
        "onboarding",
        "enterprise onboarding",
    ],
    "monitor": [
        "monitor",
        "watch",
        "no action",
        "continue monitoring",
        "do nothing",
        "no intervention",
    ],
    "page_on_call": ["page", "on-call", "paged", "on call engineer"],
    "notify_am_and_eng_lead": [
        "notify",
        "account manager",
        "engineering lead",
        "am and eng",
    ],
    "send_incident_template": ["incident template", "status page", "incident response"],
    "resolve_within_4_hours": ["4 hours", "resolve within", "4-hour"],
    "get_founder_approval": [
        "founder approval",
        "founder",
        "founder sign-off",
        "do not send",
        "get approval",
    ],
    "initiate_pip": ["pip", "performance improvement", "formal review"],
    "approve_20_percent_startup_discount": ["20%", "startup discount", "20 percent"],
    "route_to_ops_lead": ["ops lead", "operations lead", "route to ops"],
}


# ──────────────────────────────────────────────────────────────────────────────
# Evaluation Logic — Dual Metrics
# ──────────────────────────────────────────────────────────────────────────────


def check_action_strict(actual: str, expected: str) -> bool:
    """
    Strict check: the agent's action_type field must exactly match the
    expected canonical label. This measures true runtime determinism.
    """
    if not actual:
        return False
    actual_clean = actual.lower().strip().replace(" ", "_")
    expected_clean = expected.lower().strip()
    return actual_clean == expected_clean


def check_action_relaxed(
    actual: str, expected: str, action_type: str = "", candidates: list = None
) -> bool:
    """
    Relaxed check: the agent's recommended_action semantically matches
    the expected action via substring matching + alias table.
    This measures whether the LLM "understood" the correct action.
    Also provides a soft-pass for 'ambiguous' action_types if the expected action is in candidates.
    """
    if action_type == "ambiguous" and candidates and expected in candidates:
        return True

    if not actual:
        return False
    actual_lower = actual.lower().strip()
    expected_lower = expected.lower().strip()

    # Direct substring match
    if expected_lower in actual_lower or actual_lower in expected_lower:
        return True

    # Alias matching
    for canonical, variants in ACTION_ALIASES.items():
        if expected_lower == canonical or expected_lower in variants:
            for v in variants:
                if v in actual_lower:
                    return True

    return False


def check_rule_contains(actual_rule: str, expected_fragment: str) -> bool:
    """Checks if the retrieved rule text contains the expected key phrase."""
    if not actual_rule or not expected_fragment:
        return False
    return expected_fragment.lower() in actual_rule.lower()


# ──────────────────────────────────────────────────────────────────────────────
# Ablation Configurations (Change 5)
# Run with --ablation flag to compare retrieval component contributions.
#
# Anti-overfitting note (Change 9): these configs test general operational
# relevance improvements — not tuned to specific scenario IDs in this file.
# ──────────────────────────────────────────────────────────────────────────────
ABLATION_CONFIGS = {
    "A_semantic_only": {
        "semantic": 1.00,
        "metadata": 0.00,
        "keyword": 0.00,
        "severity": 0.00,
    },
    "B_semantic_metadata": {
        "semantic": 0.70,
        "metadata": 0.30,
        "keyword": 0.00,
        "severity": 0.00,
    },
    "C_semantic_keywords": {
        "semantic": 0.70,
        "metadata": 0.00,
        "keyword": 0.20,
        "severity": 0.10,
    },
    "D_full_hybrid": {
        "semantic": 0.50,
        "metadata": 0.20,
        "keyword": 0.20,
        "severity": 0.10,
    },
    "E_with_conditions": {
        "semantic": 0.45,
        "metadata": 0.20,
        "keyword": 0.15,
        "severity": 0.10,
        "condition": 0.10,
    },
}


async def run_eval(scenarios=None, label="STANDARD", retrieval_weights=None) -> dict:
    scenarios = scenarios or SCENARIOS
    print("\n" + "=" * 70, flush=True)
    print(f"  KERNL EVAL HARNESS -- {label}", flush=True)
    print(f"  Company: {COMPANY_ID}  |  Scenarios: {len(scenarios)}", flush=True)
    if retrieval_weights:
        print(f"  Retrieval Weights: {retrieval_weights}", flush=True)
    print(f"  Timestamp: {datetime.datetime.now().isoformat()}", flush=True)
    print("=" * 70 + "\n", flush=True)

    results = []
    strict_passed = 0
    relaxed_passed = 0
    rule_hits = 0

    for i, s in enumerate(scenarios):
        scenario_id = s["id"]
        print(
            f"[{i + 1:02d}/{len(scenarios)}] {scenario_id} -- {s['source']}", flush=True
        )

        try:
            response = await handle_agent_query(
                cid=COMPANY_ID,
                scenario=s["scenario"],
                ctx=s["context"],
                with_brain=True,
                rw=retrieval_weights,
            )
        except Exception as e:
            response = {
                "recommended_action": f"EXCEPTION: {e}",
                "action_type": "error",
                "rule_applied": "",
                "evidence": [],
                "skill_matched": "none",
                "confidence": 0.0,
                "retrieval_scores": [],
                "reasoning": str(e),
            }

        actual_action = response.get("recommended_action", "")
        actual_action_type = response.get("action_type", "")
        actual_rule = response.get("rule_applied", "")
        top_retrieval = (
            response.get("retrieval_scores", [0])[0]
            if response.get("retrieval_scores")
            else 0.0
        )

        strict_pass = check_action_strict(actual_action_type, s["expected_action"])

        candidates = response.get("decision_trace", {}).get("candidate_actions", [])
        relaxed_pass = check_action_relaxed(
            actual_action,
            s["expected_action"],
            action_type=actual_action_type,
            candidates=candidates,
        )

        rule_pass = check_rule_contains(actual_rule, s["expected_rule_contains"])

        if strict_pass:
            strict_passed += 1
        if relaxed_pass:
            relaxed_passed += 1
        if rule_pass:
            rule_hits += 1

        strict_label = "STRICT" if strict_pass else "strict_fail"
        relaxed_label = "RELAXED" if relaxed_pass else "relaxed_fail"
        print(
            f"         Strict     : {strict_label}  |  Relaxed: {relaxed_label}",
            flush=True,
        )
        print(f"         Expected   : {s['expected_action']}", flush=True)
        print(f"         action_type: {actual_action_type}", flush=True)
        print(f"         Got (raw)  : {actual_action[:80]}", flush=True)
        print(
            f"         Rule hit   : {'YES' if rule_pass else 'NO '}  | Fragment: '{s['expected_rule_contains']}'",
            flush=True,
        )
        print(
            f"         Retrieval  : {top_retrieval:.3f}  | Confidence: {response.get('confidence', 0)}",
            flush=True,
        )
        print(flush=True)

        # Retrieval trace (new hybrid fields)
        rt = response.get("retrieval_trace", {})

        results.append(
            {
                "id": scenario_id,
                "source": s["source"],
                "scenario": s["scenario"][:80],
                "expected_action": s["expected_action"],
                "actual_action": actual_action,
                "actual_action_type": actual_action_type,
                "strict_pass": strict_pass,
                "relaxed_pass": relaxed_pass,
                "expected_rule_fragment": s["expected_rule_contains"],
                "actual_rule": actual_rule[:120],
                "rule_pass": rule_pass,
                "top_retrieval_score": round(top_retrieval, 4),
                "confidence": response.get("confidence", 0),
                "skill_matched": response.get("skill_matched", ""),
                "reasoning_snippet": response.get("reasoning", "")[:200],
                # Hybrid retrieval signals
                "retrieval_trace": {
                    "top_skill": rt.get("top_skill"),
                    "final_score": rt.get("final_score"),
                    "semantic_confidence": rt.get("components", {}).get(
                        "semantic_confidence"
                    ),
                    "operational_confidence": rt.get("components", {}).get(
                        "operational_confidence"
                    ),
                    "why_matched": rt.get("why_matched"),
                    "runner_up": rt.get("runner_up"),
                    "why_runner_up_lost": rt.get("why_runner_up_lost"),
                },
            }
        )

        # Write partial results after each scenario for live visibility
        partial_out_path = os.path.join(
            os.path.dirname(__file__), "eval_results_partial.json"
        )
        with open(partial_out_path, "w") as pf:
            json.dump(
                {"completed": i + 1, "total": len(scenarios), "results": results},
                pf,
                indent=2,
            )

    # ── Summary ─────────────────────────────────────────────────────────────
    total = len(scenarios)
    strict_accuracy = (strict_passed / total) * 100
    relaxed_accuracy = (relaxed_passed / total) * 100
    rule_accuracy = (rule_hits / total) * 100
    avg_retrieval = sum(r["top_retrieval_score"] for r in results) / total
    avg_op_confidence = (
        sum(
            (r.get("retrieval_trace") or {}).get("operational_confidence") or 0
            for r in results
        )
        / total
    )

    # Condition metrics
    det_scenarios = [r for r in results if r["id"].startswith("DET-")]
    cond_scenarios = [r for r in results if r["id"].startswith("COND-")]
    adv_scenarios = [r for r in results if r["id"].startswith("ADV-")]

    det_count = len(det_scenarios)
    cond_count = len(cond_scenarios)
    adv_count = len(adv_scenarios)

    if cond_scenarios:
        boundary_pass_rate = (
            sum(1 for r in cond_scenarios if r["strict_pass"] or r["relaxed_pass"])
            / len(cond_scenarios)
        ) * 100
    else:
        boundary_pass_rate = 0.0

    condition_accuracy = (
        sum(
            1
            for r in results
            if (r.get("retrieval_trace") or {})
            .get("components", {})
            .get("condition_score", 0)
            > 0
            and (r["strict_pass"] or r["relaxed_pass"])
        )
        / max(
            1,
            sum(
                1
                for r in results
                if (r.get("retrieval_trace") or {})
                .get("components", {})
                .get("condition_score", 0)
                > 0
            ),
        )
        * 100
    )

    print("=" * 70, flush=True)
    print("  RESULTS SUMMARY", flush=True)
    print("=" * 70, flush=True)
    print(f"  Total Scenarios   : {total}", flush=True)
    print(f"  - Determinism     : {det_count}", flush=True)
    print(f"  - Conditions      : {cond_count}", flush=True)
    print(f"  - Adversarial     : {adv_count}", flush=True)
    print("-" * 70, flush=True)
    print(
        f"  Strict Accuracy   : {strict_passed}/{total}  ({strict_accuracy:.1f}%)  <- DETERMINISM METRIC",
        flush=True,
    )
    print(
        f"  Relaxed Accuracy  : {relaxed_passed}/{total}  ({relaxed_accuracy:.1f}%)  <- SEMANTIC METRIC",
        flush=True,
    )
    print(
        f"  Rule Text Hit Rate: {rule_hits}/{total}  ({rule_accuracy:.1f}%)", flush=True
    )
    print(f"  Avg Hybrid Score  : {avg_retrieval:.3f}", flush=True)
    print(f"  Avg Op Confidence : {avg_op_confidence:.3f}", flush=True)
    if cond_scenarios:
        print(
            f"  Boundary Pass Rate: {boundary_pass_rate:.1f}% ({cond_count} scenarios)",
            flush=True,
        )
        print(
            f"  Condition Accuracy: {condition_accuracy:.1f}% (for skills with conditions)",
            flush=True,
        )
    print("=" * 70, flush=True)

    # Category breakdown
    categories = {}
    for r in results:
        src = r["source"]
        if src not in categories:
            categories[src] = {"strict": 0, "relaxed": 0, "total": 0}
        categories[src]["total"] += 1
        if r["strict_pass"]:
            categories[src]["strict"] += 1
        if r["relaxed_pass"]:
            categories[src]["relaxed"] += 1

    print("\n  BREAKDOWN BY SOURCE:", flush=True)
    print(f"    {'Source':<35} {'Strict':>8} {'Relaxed':>8}", flush=True)
    for src, c in sorted(categories.items()):
        print(
            f"    {src:<35} {c['strict']}/{c['total']:>4}    {c['relaxed']}/{c['total']:>4}",
            flush=True,
        )

    # Failures only (relaxed)
    relaxed_failures = [r for r in results if not r["relaxed_pass"]]
    strict_failures = [r for r in results if not r["strict_pass"]]
    if relaxed_failures:
        print(f"\n  RELAXED FAILURES ({len(relaxed_failures)}):", flush=True)
        for f in relaxed_failures:
            print(
                f"    [{f['id']}] expected='{f['expected_action']}'  got='{f['actual_action'][:60]}'",
                flush=True,
            )
    if strict_failures:
        print(f"\n  STRICT FAILURES ({len(strict_failures)}):", flush=True)
        for f in strict_failures:
            print(
                f"    [{f['id']}] expected='{f['expected_action']}'  type='{f['actual_action_type']}'",
                flush=True,
            )

    print(flush=True)

    # ── Save results ─────────────────────────────────────────────────────────
    output = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "company_id": COMPANY_ID,
        "total_scenarios": total,
        "scenario_counts": {
            "determinism": det_count,
            "condition": cond_count,
            "adversarial": adv_count,
        },
        "strict_accuracy_pct": round(strict_accuracy, 1),
        "relaxed_accuracy_pct": round(relaxed_accuracy, 1),
        "rule_hit_rate_pct": round(rule_accuracy, 1),
        "condition_accuracy_pct": round(condition_accuracy, 1),
        "boundary_pass_rate_pct": round(boundary_pass_rate, 1),
        "avg_hybrid_score": round(avg_retrieval, 4),
        "avg_operational_confidence": round(avg_op_confidence, 4),
        "strict_passed": strict_passed,
        "relaxed_passed": relaxed_passed,
        "failed": total - relaxed_passed,
        "results": results,
    }
    return output


async def run_ablation() -> None:
    """
    Ablation test runner (Change 5).
    Runs eval harness under 4 different retrieval weight configurations
    to measure each component's actual contribution to accuracy.

    Anti-overfitting note (Change 9): weights are NOT tuned to maximize score
    on this specific eval set — the goal is to understand signal contribution.
    """
    print("\n" + "#" * 70, flush=True)
    print(
        "  KERNL RETRIEVAL ABLATION TEST (Typed Conditions & Determinism)", flush=True
    )
    print(
        f"  {len(ABLATION_CONFIGS)} configurations × {len(SCENARIOS)} scenarios",
        flush=True,
    )
    print("#" * 70 + "\n", flush=True)

    ablation_results = {}
    for config_name, weights in ABLATION_CONFIGS.items():
        print(f"\n>>> Config: {config_name}  weights={weights}", flush=True)
        result = await run_eval(
            scenarios=SCENARIOS,
            label=config_name,
            retrieval_weights=weights,
        )
        ablation_results[config_name] = {
            "weights": weights,
            "strict_pct": result["strict_accuracy_pct"],
            "relaxed_pct": result["relaxed_accuracy_pct"],
            "avg_hybrid_score": result["avg_hybrid_score"],
            "avg_op_confidence": result["avg_operational_confidence"],
        }

    # ── Ablation summary table ─────────────────────────────────────────────
    print("\n" + "=" * 70, flush=True)
    print("  ABLATION RESULTS SUMMARY", flush=True)
    print("=" * 70, flush=True)
    print(
        f"  {'Config':<30} {'Strict':>8} {'Relaxed':>8} {'Avg Score':>10} {'Avg OpConf':>12}",
        flush=True,
    )
    print("-" * 70, flush=True)
    for cfg, r in ablation_results.items():
        print(
            f"  {cfg:<30} {r['strict_pct']:>7.1f}% {r['relaxed_pct']:>7.1f}% "
            f"{r['avg_hybrid_score']:>10.4f} {r['avg_op_confidence']:>11.4f}",
            flush=True,
        )
    print("=" * 70, flush=True)

    out_path = os.path.join(os.path.dirname(__file__), "eval_ablation_results.json")
    with open(out_path, "w") as f:
        json.dump(
            {
                "run_timestamp": datetime.datetime.now().isoformat(),
                "ablation_configs": ablation_results,
            },
            f,
            indent=2,
        )
    print(f"  Ablation results saved -> {out_path}", flush=True)


async def run_stability_test() -> None:
    """Runs 3 iterations of DET scenarios to measure deterministic stability."""
    print("\n" + "#" * 70, flush=True)
    print("  KERNL RUNTIME STABILITY TEST", flush=True)
    print("  3 runs × 6 DET scenarios", flush=True)
    print("#" * 70 + "\n", flush=True)

    det_scenarios = [s for s in SCENARIOS if s["id"].startswith("DET-")]

    consistent_count = 0

    for i, s in enumerate(det_scenarios):
        print(f"[{i + 1}/{len(det_scenarios)}] {s['id']}", flush=True)
        action_types = []
        for run in range(3):
            try:
                response = await handle_agent_query(
                    company_id=COMPANY_ID,
                    scenario=s["scenario"],
                    context=s["context"],
                    with_brain=True,
                )
            except Exception as e:
                response = {"action_type": "error"}
            action_types.append(response.get("action_type", ""))
            print(f"  Run {run + 1}: {action_types[-1]}", flush=True)

        if len(set(action_types)) == 1:
            consistent_count += 1
            print("  -> CONSISTENT\n", flush=True)
        else:
            print("  -> INCONSISTENT\n", flush=True)

    stability_score = (consistent_count / len(det_scenarios)) * 100
    print("=" * 70, flush=True)
    print(
        f"  STABILITY SCORE: {stability_score:.1f}% ({consistent_count}/{len(det_scenarios)} consistent)",
        flush=True,
    )
    print("=" * 70 + "\n", flush=True)


async def _main():
    if "--stability" in sys.argv:
        await run_stability_test()
    elif "--ablation" in sys.argv:
        await run_ablation()
    else:
        result = await run_eval()
        out_path = os.path.join(os.path.dirname(__file__), "eval_results_baseline.json")
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"  Results saved -> {out_path}", flush=True)
        print(flush=True)
        if result["relaxed_accuracy_pct"] < 90.0:
            print("  WARNING: Relaxed accuracy dropped below 90% baseline!", flush=True)
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_main())
