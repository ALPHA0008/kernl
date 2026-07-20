"""The authored higgsfield reference bundle [synthetic] + golden cases.

Second seeded corpus (2026-07-16, expanded 2026-07-17), built the same way
as seed_rivanly.py: a policy bundle hand-authored from data/sources/
higgsfield/, with evidence spans VERIFIED at build time -- every excerpt
must literally exist in its source file or the builder raises.
source_version is the sha256 of the file bytes.

Scope: three workflows across three source docs --
  * refund   (higgsfield_customer_policy.md section 1): plan-tiered refund
    windows, usage caps, and a fraud-signal screen.
  * bug_triage (higgsfield_eng_runbook.md sections 1 & 3): P0-P3 severity
    routing, with the P1+enterprise AE-notification override.
  * expense  (higgsfield_hr_finance.md section 3.1): the amount-tier
    approval ladder, with the "new SaaS regardless of amount" override.

Still not a claim of FULL coverage of every higgsfield source: the Slack/
ticket JSON exports and finer rules within each doc (deploy windows,
rollback criteria, PIP/termination, vendor payment) are not yet modeled --
the next authoring targets if this corpus needs to grow further, same as any
real tenant's onboarding backlog.

Everything produced here is labeled [synthetic].
"""

from __future__ import annotations

import hashlib
from pathlib import Path

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
from backend.replay.cases import Expected, GoldenCase

COMPANY_ID = "higgsfield"
SOURCES = Path(__file__).resolve().parents[2] / "data" / "sources" / "higgsfield"


def _evidence(source_id: str, excerpt: str) -> Evidence:
    path = SOURCES / source_id
    text = path.read_text(encoding="utf-8")
    start = text.find(excerpt)
    if start < 0:
        raise ValueError(f"excerpt not found in {source_id}: {excerpt[:60]!r}")
    return Evidence(
        source_id=source_id,
        source_version="sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        span_start=start,
        span_end=start + len(excerpt),
        excerpt=excerpt,
    )


def _c(field: str, op: str, value, vtype: str) -> Condition:
    return Condition(field=field, operator=op, value=value, value_type=vtype)


def build_bundle() -> Bundle:
    policy_doc = "higgsfield_customer_policy.md"
    runbook = "higgsfield_eng_runbook.md"
    hr_finance = "higgsfield_hr_finance.md"

    workflows = (
        WorkflowSpec(
            name="refund",
            description="Subscription refund eligibility and routing (Customer Success).",
            facts=(
                FactSpec(name="plan_type", value_type="string",
                         description="annual | monthly | enterprise | api"),
                FactSpec(name="days_since_purchase", value_type="number",
                         description="applies to annual and api plans"),
                FactSpec(name="hours_since_purchase", value_type="number",
                         description="applies to monthly plans (48h window, not days)"),
                FactSpec(name="credit_usage_percent", value_type="number", default=0,
                         description="pct of annual credit allocation consumed"),
                FactSpec(name="account_age_days", value_type="number", default=9999,
                         description="for fraud-signal screening; unknown -> assume "
                                      "an established, non-suspicious account"),
                FactSpec(name="refund_amount", value_type="number", default=0,
                         description="requested refund in USD; unknown -> assume no "
                                      "monetary amount is in question"),
            ),
        ),
        WorkflowSpec(
            name="bug_triage",
            description="Incident/bug severity routing (Engineering).",
            facts=(
                FactSpec(name="severity", value_type="string",
                         description="p0 | p1 | p2 | p3"),
                FactSpec(name="customer_type", value_type="string", default="standard",
                         description="enterprise | standard"),
            ),
        ),
        WorkflowSpec(
            name="expense",
            description="Expense approval authority ladder (Finance).",
            facts=(
                FactSpec(name="amount", value_type="number",
                         description="expense amount in USD"),
                FactSpec(name="is_new_saas", value_type="boolean", default=False,
                         description="a new recurring SaaS subscription (special-cased "
                                      "by the policy regardless of amount)"),
            ),
        ),
    )

    policies = (
        Policy(
            id="refund.fraud_new_account_large",
            workflow="refund",
            effect=Effect(kind=OutcomeKind.ESCALATE, action="escalate_to_fraud_review"),
            priority=100,
            conditions=(
                _c("account_age_days", "lt", 7, "number"),
                _c("refund_amount", "gt", 200, "number"),
            ),
            evidence=(_evidence(policy_doc,
                "Account was created less than 7 days ago and the refund amount exceeds $200"),),
            rationale="Fraud-signal screen outranks ordinary approval paths -- a new "
                      "account requesting a refund over $200 must be reviewed before "
                      "any plan-specific rule grants it, regardless of plan type.",
        ),
        Policy(
            id="refund.enterprise_escalate_ae",
            workflow="refund",
            effect=Effect(kind=OutcomeKind.ESCALATE, action="escalate_to_account_executive"),
            priority=90,
            conditions=(_c("plan_type", "eq", "enterprise", "string"),),
            evidence=(_evidence(policy_doc,
                "All enterprise refund requests must be escalated to AE within 2 hours regardless of amount"),),
            rationale="Enterprise refunds are never processed directly, at any amount.",
        ),
        Policy(
            id="refund.annual_full_14d",
            workflow="refund",
            effect=Effect(kind=OutcomeKind.APPROVE, action="approve_full_refund"),
            priority=70,
            conditions=(
                _c("plan_type", "eq", "annual", "string"),
                _c("days_since_purchase", "lte", 14, "number"),
            ),
            evidence=(_evidence(policy_doc,
                "Full refund within 14 days of initial purchase, no questions asked"),),
            rationale="Unconditional full refund inside the 14-day window.",
        ),
        Policy(
            id="refund.annual_prorated_low_usage",
            workflow="refund",
            effect=Effect(kind=OutcomeKind.APPROVE, action="approve_prorated_refund"),
            priority=70,
            conditions=(
                _c("plan_type", "eq", "annual", "string"),
                _c("days_since_purchase", "gt", 14, "number"),
                _c("credit_usage_percent", "lte", 20, "number"),
            ),
            evidence=(_evidence(policy_doc,
                "After 14 days: prorated refund based on unused credits"),),
            rationale="Past the free window, prorated refund is available while usage "
                      "stays under the 20% cap (see the sibling low/high-usage split).",
        ),
        Policy(
            id="refund.annual_high_usage_extension",
            workflow="refund",
            effect=Effect(kind=OutcomeKind.DENY, action="deny_refund_offer_extension"),
            priority=70,
            conditions=(
                _c("plan_type", "eq", "annual", "string"),
                _c("days_since_purchase", "gt", 14, "number"),
                _c("credit_usage_percent", "gt", 20, "number"),
            ),
            evidence=(_evidence(policy_doc,
                "If usage exceeds 20%, no refund is issued"),),
            rationale="Above the 20% usage cap, no refund -- the doc directs a "
                      "2-month extension offer instead.",
        ),
        Policy(
            id="refund.monthly_48h_window",
            workflow="refund",
            effect=Effect(kind=OutcomeKind.APPROVE, action="approve_full_refund"),
            priority=70,
            conditions=(
                _c("plan_type", "eq", "monthly", "string"),
                _c("hours_since_purchase", "lte", 48, "number"),
            ),
            evidence=(_evidence(policy_doc,
                "Refund only within 48 hours of billing cycle start"),),
            rationale="Monthly plans use an hours-based window, not days -- distinct "
                      "from the annual plan's 14-day window.",
        ),
        Policy(
            id="refund.monthly_after_48h_credit",
            workflow="refund",
            effect=Effect(kind=OutcomeKind.APPROVE, action="issue_account_credit_50_percent"),
            priority=70,
            conditions=(
                _c("plan_type", "eq", "monthly", "string"),
                _c("hours_since_purchase", "gt", 48, "number"),
            ),
            evidence=(_evidence(policy_doc,
                "After 48 hours: no monetary refund"),),
            rationale="Past the 48h window: no cash refund, but the doc still directs "
                      "an account-credit remedy, not an outright denial.",
        ),
        Policy(
            id="refund.api_unused_prepaid_30d",
            workflow="refund",
            effect=Effect(kind=OutcomeKind.APPROVE, action="approve_full_refund"),
            priority=70,
            conditions=(
                _c("plan_type", "eq", "api", "string"),
                _c("days_since_purchase", "lte", 30, "number"),
            ),
            evidence=(_evidence(policy_doc,
                "Unused prepaid API credits: refundable within 30 days of purchase"),),
            rationale="Unused prepaid API credits are refundable inside 30 days; "
                      "consumed credits are never refundable (a separate, absolute "
                      "rule the current bundle does not yet model -- see module "
                      "docstring on scope).",
        ),
        # ---- bug_triage (from higgsfield_eng_runbook.md) --------------------
        Policy(
            id="triage.p0_page_on_call",
            workflow="bug_triage",
            effect=Effect(kind=OutcomeKind.ROUTE, action="page_on_call"),
            priority=100,
            conditions=(_c("severity", "eq", "p0", "string"),),
            evidence=(_evidence(runbook,
                "On-call engineer MUST post in #incidents within 5 minutes of alert. "
                "If no post in 5 minutes, Engineering Lead gets automatically paged by "
                "PagerDuty."),),
            rationale="P0 is the always-page path; the runbook mandates on-call "
                      "engagement within 5 minutes.",
        ),
        Policy(
            id="triage.p1_enterprise_notify_ae",
            workflow="bug_triage",
            effect=Effect(kind=OutcomeKind.ROUTE, action="notify_ae_and_on_call"),
            priority=90,
            conditions=(
                _c("severity", "eq", "p1", "string"),
                _c("customer_type", "eq", "enterprise", "string"),
            ),
            evidence=(_evidence(runbook,
                "When a P1 affects a named enterprise customer, the AE for that "
                "customer must be notified within 15 minutes"),),
            rationale="P1 + enterprise adds the AE-notification obligation on top of "
                      "ordinary P1 handling.",
        ),
        Policy(
            id="triage.p1_standard_assign_on_call",
            workflow="bug_triage",
            effect=Effect(kind=OutcomeKind.ROUTE, action="assign_to_on_call"),
            priority=70,
            conditions=(_c("severity", "eq", "p1", "string"),),
            evidence=(_evidence(runbook,
                "P0 and P1 bugs: assigned to on-call engineer immediately, regardless "
                "of their sprint commitments"),),
            rationale="Baseline P1 handling; the enterprise rule (higher specificity + "
                      "priority) overrides this when the customer is enterprise.",
        ),
        Policy(
            id="triage.p2_next_standup",
            workflow="bug_triage",
            effect=Effect(kind=OutcomeKind.ROUTE, action="triage_next_standup"),
            priority=60,
            conditions=(_c("severity", "eq", "p2", "string"),),
            evidence=(_evidence(runbook,
                "P2 bugs: triaged in next daily standup, assigned to appropriate team"),),
            rationale="P2 is not an interrupt; it enters the daily standup queue.",
        ),
        Policy(
            id="triage.p3_backlog",
            workflow="bug_triage",
            effect=Effect(kind=OutcomeKind.ROUTE, action="add_to_backlog"),
            priority=50,
            conditions=(_c("severity", "eq", "p3", "string"),),
            evidence=(_evidence(runbook,
                "P3 bugs: added to backlog, reviewed in sprint planning"),),
            rationale="P3 is backlog work reviewed at sprint planning.",
        ),
        # ---- expense (from higgsfield_hr_finance.md) -----------------------
        Policy(
            id="expense.new_saas_cfo",
            workflow="expense",
            effect=Effect(kind=OutcomeKind.ESCALATE, action="require_cfo_approval"),
            priority=100,
            conditions=(_c("is_new_saas", "eq", True, "boolean"),),
            evidence=(_evidence(hr_finance,
                "Any new recurring SaaS expense (regardless of amount) requires CFO "
                "approval"),),
            rationale="New SaaS is CFO-gated regardless of amount -- outranks the "
                      "amount-tier ladder below.",
        ),
        Policy(
            id="expense.manager_under_500",
            workflow="expense",
            effect=Effect(kind=OutcomeKind.APPROVE, action="approve_by_manager"),
            priority=70,
            conditions=(_c("amount", "lt", 500, "number"),),
            evidence=(_evidence(hr_finance, "| Under $500 | Direct manager |"),),
            rationale="Under $500: direct manager authority (the ladder's lowest rung).",
        ),
        Policy(
            id="expense.dept_head_500_to_2500",
            workflow="expense",
            effect=Effect(kind=OutcomeKind.ROUTE, action="route_to_department_head"),
            priority=70,
            conditions=(
                _c("amount", "gte", 500, "number"),
                _c("amount", "lte", 2500, "number"),
            ),
            evidence=(_evidence(hr_finance, "| $500 – $2,500 | Department Head |"),),
            rationale="$500–$2,500 inclusive: department head.",
        ),
        Policy(
            id="expense.cfo_2500_to_10000",
            workflow="expense",
            effect=Effect(kind=OutcomeKind.ESCALATE, action="require_cfo_approval"),
            priority=70,
            conditions=(
                _c("amount", "gt", 2500, "number"),
                _c("amount", "lte", 10000, "number"),
            ),
            evidence=(_evidence(hr_finance, "| $2,500 – $10,000 | CFO |"),),
            rationale="Above $2,500 through $10,000: CFO. (The doc's tiers overlap at "
                      "the $2,500 boundary; resolved here as <=2500 dept-head, >2500 "
                      "CFO, so every amount maps to exactly one rung.)",
        ),
        Policy(
            id="expense.cfo_ceo_above_10000",
            workflow="expense",
            effect=Effect(kind=OutcomeKind.ESCALATE, action="require_cfo_and_ceo_approval"),
            priority=80,
            conditions=(_c("amount", "gt", 10000, "number"),),
            evidence=(_evidence(hr_finance, "| Above $10,000 | CFO + CEO |"),),
            rationale="Above $10,000: joint CFO + CEO. Slightly higher priority so the "
                      "top rung is unambiguous at the boundary.",
        ),
    )

    return Bundle(company_id=COMPANY_ID, workflows=workflows, policies=policies)


def _case(cid, wf, facts, kind, action=None, reason=None, notes="", provenance="") -> GoldenCase:
    return GoldenCase(
        case_id=cid, company_id=COMPANY_ID, workflow=wf, facts=facts,
        expected=Expected(kind=kind, action=action, escalation_reason=reason),
        provenance=provenance or "authored from higgsfield_customer_policy.md section 1",
        synthetic=True, notes=notes,
    )


def build_golden_cases() -> list[GoldenCase]:
    return [
        _case("HF-REF-01", "refund",
              {"plan_type": "annual", "days_since_purchase": 9},
              "approve", "approve_full_refund"),
        _case("HF-REF-02", "refund",
              {"plan_type": "annual", "days_since_purchase": 14},
              "approve", "approve_full_refund", notes="boundary: 14 inclusive"),
        _case("HF-REF-03", "refund",
              {"plan_type": "annual", "days_since_purchase": 15,
               "credit_usage_percent": 10},
              "approve", "approve_prorated_refund", notes="boundary: 15 > 14"),
        _case("HF-REF-04", "refund",
              {"plan_type": "annual", "days_since_purchase": 20,
               "credit_usage_percent": 20},
              "approve", "approve_prorated_refund", notes="boundary: 20 inclusive (lte)"),
        _case("HF-REF-05", "refund",
              {"plan_type": "annual", "days_since_purchase": 20,
               "credit_usage_percent": 21},
              "deny", "deny_refund_offer_extension", notes="boundary: 21 > 20"),
        _case("HF-REF-06", "refund",
              {"plan_type": "monthly", "hours_since_purchase": 48},
              "approve", "approve_full_refund", notes="boundary: 48 inclusive (lte)"),
        _case("HF-REF-07", "refund",
              {"plan_type": "monthly", "hours_since_purchase": 49},
              "approve", "issue_account_credit_50_percent", notes="boundary: 49 > 48"),
        _case("HF-REF-08", "refund",
              {"plan_type": "enterprise", "days_since_purchase": 1,
               "refund_amount": 50000},
              "escalate", "escalate_to_account_executive",
              notes="enterprise escalates regardless of amount -- no monetary "
                    "condition on the policy at all"),
        _case("HF-REF-09", "refund",
              {"plan_type": "api", "days_since_purchase": 15},
              "approve", "approve_full_refund"),
        _case("HF-REF-10", "refund",
              {"plan_type": "api", "days_since_purchase": 31},
              "escalate", reason="no_matching_policy",
              notes="past the 30-day unused-prepaid window; the current bundle does "
                    "not model the consumed-vs-unused distinction for this case (see "
                    "module docstring) -- a documented gap, not a wrong answer"),
        _case("HF-REF-11", "refund",
              {"plan_type": "annual", "days_since_purchase": 3,
               "account_age_days": 2, "refund_amount": 500},
              "escalate", "escalate_to_fraud_review",
              notes="fraud screen (2 conditions, priority 100) outranks the annual "
                    "14-day approval (2 conditions, priority 70) on priority once "
                    "specificity ties"),
        _case("HF-REF-12", "refund",
              {"plan_type": "annual", "days_since_purchase": 3,
               "account_age_days": 30, "refund_amount": 500},
              "approve", "approve_full_refund",
              notes="same refund amount as HF-REF-11, but account_age_days=30 means "
                    "the fraud condition (age < 7) cleanly fails -- isolates the "
                    "fraud gate from the amount alone"),
        _case("HF-REF-13", "refund",
              {"plan_type": "annual", "days_since_purchase": 3,
               "account_age_days": 2, "refund_amount": 150},
              "approve", "approve_full_refund",
              notes="new account but refund_amount=150 is under the $200 fraud "
                    "threshold -- fraud condition cleanly fails, ordinary approval fires"),
        _case("HF-REF-14", "refund",
              {"plan_type": "monthly", "hours_since_purchase": 10,
               "account_age_days": 3, "refund_amount": 250},
              "escalate", "escalate_to_fraud_review",
              notes="fraud screen applies across plan types -- monthly is not "
                    "exempt just because it has its own window rule"),
        _case("HF-REF-15", "refund",
              {"plan_type": "lifetime_deal", "days_since_purchase": 5},
              "escalate", reason="no_matching_policy",
              notes="lifetime_deal is not a plan type this bundle's scope covers "
                    "(section 1 of the source doc is silent on it) -- documented gap"),
        # ---- bug_triage (from higgsfield_eng_runbook.md) --------------------
        _case("HF-BUG-01", "bug_triage", {"severity": "p0"},
              "route", "page_on_call", provenance="authored from higgsfield_eng_runbook.md"),
        _case("HF-BUG-02", "bug_triage",
              {"severity": "p1", "customer_type": "enterprise"},
              "route", "notify_ae_and_on_call",
              notes="p1 + enterprise: specificity (2 conds) + priority beats the "
                    "standard p1 rule",
              provenance="authored from higgsfield_eng_runbook.md"),
        _case("HF-BUG-03", "bug_triage",
              {"severity": "p1", "customer_type": "standard"},
              "route", "assign_to_on_call",
              notes="p1 standard: the enterprise rule's customer_type condition fails "
                    "cleanly, baseline p1 handling fires",
              provenance="authored from higgsfield_eng_runbook.md"),
        _case("HF-BUG-04", "bug_triage", {"severity": "p2"},
              "route", "triage_next_standup",
              provenance="authored from higgsfield_eng_runbook.md"),
        _case("HF-BUG-05", "bug_triage", {"severity": "p3"},
              "route", "add_to_backlog",
              provenance="authored from higgsfield_eng_runbook.md"),
        _case("HF-BUG-06", "bug_triage", {"severity": "p5"},
              "escalate", reason="no_matching_policy",
              notes="unknown severity -> no matching rung; a clean gap, not a guess",
              provenance="authored from higgsfield_eng_runbook.md"),
        # ---- expense (from higgsfield_hr_finance.md) -----------------------
        _case("HF-EXP-01", "expense", {"amount": 300},
              "approve", "approve_by_manager",
              provenance="authored from higgsfield_hr_finance.md"),
        _case("HF-EXP-02", "expense", {"amount": 500},
              "route", "route_to_department_head", notes="boundary: 500 -> dept head (gte)",
              provenance="authored from higgsfield_hr_finance.md"),
        _case("HF-EXP-03", "expense", {"amount": 2500},
              "route", "route_to_department_head", notes="boundary: 2500 inclusive dept head",
              provenance="authored from higgsfield_hr_finance.md"),
        _case("HF-EXP-04", "expense", {"amount": 2501},
              "escalate", "require_cfo_approval", notes="boundary: 2501 -> CFO",
              provenance="authored from higgsfield_hr_finance.md"),
        _case("HF-EXP-05", "expense", {"amount": 10000},
              "escalate", "require_cfo_approval", notes="boundary: 10000 inclusive CFO",
              provenance="authored from higgsfield_hr_finance.md"),
        _case("HF-EXP-06", "expense", {"amount": 10001},
              "escalate", "require_cfo_and_ceo_approval", notes="boundary: 10001 -> CFO+CEO",
              provenance="authored from higgsfield_hr_finance.md"),
        _case("HF-EXP-07", "expense", {"amount": 50, "is_new_saas": True},
              "escalate", "require_cfo_approval",
              notes="new SaaS (priority 100) overrides the amount ladder even at $50 -- "
                    "'regardless of amount'",
              provenance="authored from higgsfield_hr_finance.md"),
    ]
