"""The authored higgsfield reference bundle [synthetic] + golden cases.

Second seeded corpus (2026-07-16), built the same way as seed_rivanly.py: a
policy bundle hand-authored from data/sources/higgsfield/, with evidence
spans VERIFIED at build time -- every excerpt must literally exist in its
source file or the builder raises. source_version is the sha256 of the file
bytes.

Scope: the refund/subscription policy section of
higgsfield_customer_policy.md (section 1) -- the richest, most clearly
typed-condition-shaped ruleset in the higgsfield source set. Deliberately
narrower than rivanly's 9-workflow bundle; this is a real starting corpus
for a second tenant, not a claim of full coverage of every higgsfield
source document. Growing it further (eng_runbook.md, hr_finance.md, the
Slack/ticket JSON exports) is future work, same as any real tenant's
onboarding backlog.

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
    ]
