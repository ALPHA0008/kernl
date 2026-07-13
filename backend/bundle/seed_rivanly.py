"""The authored rivanly-inc reference bundle [synthetic] + migrated golden cases.

This is the V1 seed: a policy bundle hand-authored from the eight synthetic
source documents (the Policy-Owner authoring path), with evidence spans that
are VERIFIED at build time -- every excerpt must literally exist in its source
file or the builder raises. source_version is the sha256 of the file bytes.

Golden-case migration notes (from the legacy 40-scenario eval harness):
  - The legacy harness matched LLM free text; V1 replay matches canonical
    outcomes exactly. Expectations were re-derived from the source docs.
  - Legacy "ambiguous" maps to escalate (missing_facts / no_matching_policy /
    conflict) -- ambiguity is crisp under exhaustive evaluation.
  - Cases that relied on the legacy missing-field-is-neutral bug were given
    complete facts (noted per case). Where the docs are genuinely silent, the
    expected outcome is escalate(no_matching_policy) -- documented gaps.
  - COND-06 boundary corrected: the SOP says "after 60 days" => deny at 61,
    prorate at exactly 60. The legacy expectation (deny at 60) contradicted
    the SOP text.
  - DET-01 dropped: identical facts to ENG-04 with a different expected
    outcome is impossible under determinism (it tested prose sensitivity).
    Replaced by an empty-facts case.

Everything produced here is labeled [synthetic].
"""

from __future__ import annotations

import hashlib
from pathlib import Path

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
from backend.replay.cases import Expected, GoldenCase

COMPANY_ID = "rivanly-inc"
SOURCES = Path(__file__).resolve().parents[2] / "data" / "sources" / "rivanly-inc"


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
    workflows = (
        WorkflowSpec(
            name="refund",
            description="Refund eligibility and routing (Support).",
            facts=(
                FactSpec(name="plan_type", value_type="string",
                         description="annual | monthly | enterprise | lifetime_deal"),
                FactSpec(name="days_since_purchase", value_type="number"),
                FactSpec(name="refund_amount", value_type="number",
                         description="requested refund in USD"),
                FactSpec(name="tenure_months", value_type="number"),
                FactSpec(name="tenure_years", value_type="number"),
            ),
        ),
        WorkflowSpec(
            name="discount",
            description="Discount approval chain (Revenue).",
            facts=(
                FactSpec(name="discount_percent", value_type="number", default=0,
                         description="requested discount; 0 when no specific percent"),
                FactSpec(name="customer_stage", value_type="string"),
                FactSpec(name="plan", value_type="string"),
            ),
        ),
        WorkflowSpec(
            name="bug_triage",
            description="Bug priority handling (Engineering).",
            facts=(
                FactSpec(name="priority", value_type="string", description="p0 | p1 | p2"),
                FactSpec(name="customer_type", value_type="string"),
                FactSpec(name="active_outage", value_type="boolean", default=False),
                FactSpec(name="affected_users_pct", value_type="number"),
                FactSpec(name="workaround_available", value_type="boolean"),
            ),
        ),
        WorkflowSpec(
            name="sla",
            description="SLA breach handling (Engineering).",
            facts=(
                FactSpec(name="customer_type", value_type="string"),
                FactSpec(name="sla_breach_hours", value_type="number"),
            ),
        ),
        WorkflowSpec(
            name="churn",
            description="Churn-risk intervention (Customer Success).",
            facts=(
                FactSpec(name="churn_signals_count", value_type="number",
                         description="signals observed within the past 30 days"),
            ),
        ),
        WorkflowSpec(
            name="onboarding",
            description="New-customer onboarding (Customer Success).",
            facts=(
                FactSpec(name="customer_type", value_type="string"),
                FactSpec(name="status", value_type="string"),
            ),
        ),
        WorkflowSpec(
            name="hiring",
            description="Hiring approvals (HR).",
            facts=(
                FactSpec(name="role", value_type="string"),
                FactSpec(name="stage", value_type="string"),
            ),
        ),
        WorkflowSpec(
            name="performance",
            description="Performance management (HR).",
            facts=(FactSpec(name="missed_kpi_quarters", value_type="number"),),
        ),
        WorkflowSpec(
            name="vendor",
            description="Vendor invoice routing (Finance/Ops).",
            facts=(
                FactSpec(name="invoice_amount", value_type="number"),
                FactSpec(name="vendor_type", value_type="string"),
            ),
        ),
    )

    refund_sop = "notion_refund_sop.md"
    pricing = "notion_pricing_policy.md"
    runbook = "notion_eng_runbook.md"
    hr = "notion_hr_playbook.md"
    cs = "notion_cs_playbook.md"
    slack_support = "slack_export_support.json"
    slack_ops = "slack_export_ops.json"

    policies = (
        # ---- refund ---------------------------------------------------------
        Policy(
            id="refund.deny_after_60_days",
            workflow="refund",
            effect=Effect(kind=OutcomeKind.DENY, action="deny_refund"),
            priority=100,
            conditions=(_c("days_since_purchase", "gt", 60, "number"),),
            overrides=("refund.annual_full_14d", "refund.annual_prorate",
                       "refund.loyalty_precedent", "refund.monthly_new_large_founder"),
            evidence=(_evidence(refund_sop,
                "We offer absolutely no refunds after 60 days of purchase for any customer tier."),),
            rationale="Absolute cutoff; the SOP marks it CRITICAL and tier-independent.",
        ),
        Policy(
            id="refund.enterprise_escalate",
            workflow="refund",
            effect=Effect(kind=OutcomeKind.ESCALATE, action="escalate_to_account_manager"),
            priority=90,
            conditions=(_c("plan_type", "eq", "enterprise", "string"),),
            evidence=(_evidence(refund_sop,
                "If any Enterprise customer requests a refund of any amount, DO NOT process it immediately. You must escalate to the Account Manager (AM) within 1 hour."),),
            rationale="Enterprise refunds are never processed directly.",
        ),
        Policy(
            id="refund.lifetime_deal_deny",
            workflow="refund",
            effect=Effect(kind=OutcomeKind.DENY, action="deny_refund_ltd_terms"),
            priority=110,  # categorical: outranks even the 60-day rule (both deny)
            conditions=(_c("plan_type", "eq", "lifetime_deal", "string"),),
            evidence=(_evidence(refund_sop,
                "Under no circumstances do we process refunds for lifetime deal accounts. Deny the request citing LTD terms."),),
            rationale="LTD accounts are categorically non-refundable.",
        ),
        Policy(
            id="refund.monthly_new_large_founder",
            workflow="refund",
            effect=Effect(kind=OutcomeKind.ESCALATE, action="get_founder_approval"),
            priority=80,
            conditions=(
                _c("plan_type", "eq", "monthly", "string"),
                _c("tenure_months", "lt", 3, "number"),
                _c("refund_amount", "gt", 500, "number"),
            ),
            evidence=(_evidence(refund_sop,
                "If a customer on a monthly plan with a tenure of less than 3 months requests a refund over $500, escalate to the Founder."),),
            rationale="Large refunds from new monthly customers need founder sign-off.",
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
            evidence=(_evidence(refund_sop,
                "If a customer on an annual plan requests a refund within the first 14 days of purchase, approve a full refund immediately. No questions asked."),),
            rationale="14-day no-questions window for annual plans.",
        ),
        Policy(
            id="refund.annual_prorate",
            workflow="refund",
            effect=Effect(kind=OutcomeKind.APPROVE, action="approve_prorated_refund"),
            priority=60,
            conditions=(
                _c("plan_type", "eq", "annual", "string"),
                _c("days_since_purchase", "gt", 14, "number"),
            ),
            evidence=(_evidence(refund_sop,
                "If a customer on an annual plan requests a refund after 14 days, approve a prorated refund for the remaining unused months."),),
            rationale="Prorated refund after the 14-day window (until the 60-day cutoff).",
        ),
        Policy(
            id="refund.loyalty_precedent",
            workflow="refund",
            effect=Effect(kind=OutcomeKind.APPROVE, action="approve_full_refund"),
            priority=55,
            conditions=(_c("tenure_years", "gt", 2, "number"),),
            overrides=("refund.annual_prorate",),
            evidence=(_evidence(slack_support,
                "For loyal customers over 2 years tenure, we can bypass the 30-day rule. Go ahead and approve the refund for Acme Corp."),),
            rationale="Tribal-knowledge precedent from Slack: loyal customers (>2y) get "
                      "full refunds past the standard window. Does NOT bypass the 60-day "
                      "cutoff (deny_after_60_days overrides this policy). Note: the Slack "
                      "thread cites a 30-day rule that contradicts the SOP's 60 -- the "
                      "override edge encodes the reviewer's resolution.",
        ),
        # ---- discount -------------------------------------------------------
        Policy(
            id="discount.large_escalate_ae",
            workflow="discount",
            effect=Effect(kind=OutcomeKind.ESCALATE, action="escalate_to_account_executive"),
            priority=90,
            conditions=(_c("discount_percent", "gt", 30, "number"),),
            evidence=(_evidence(pricing,
                "If a customer requests a discount greater than 30%, it must be escalated to an Account Executive (AE) for approval. Support cannot approve this."),),
            rationale="Support cannot approve >30% discounts.",
        ),
        Policy(
            id="discount.standard_10",
            workflow="discount",
            effect=Effect(kind=OutcomeKind.APPROVE, action="approve_discount"),
            priority=70,
            conditions=(_c("discount_percent", "lte", 10, "number"),),
            evidence=(_evidence(pricing,
                "Support and CS can apply up to a 10% discount to save a churning customer."),),
            rationale="Standard retention discount authority.",
        ),
        Policy(
            id="discount.startup_20_annual",
            workflow="discount",
            effect=Effect(kind=OutcomeKind.APPROVE, action="approve_20_percent_startup_discount"),
            priority=60,
            conditions=(
                _c("customer_stage", "in", ["pre-seed", "seed"], "string"),
                _c("plan", "eq", "annual", "string"),
                _c("discount_percent", "lte", 20, "number"),
            ),
            evidence=(_evidence(pricing,
                "If a customer identifies as an early-stage startup (pre-seed or seed), you may approve up to a 20% discount on the Annual plan for the first year."),),
            rationale="Startup program: up to 20% on annual, first year.",
        ),
        # ---- bug_triage -----------------------------------------------------
        Policy(
            id="triage.outage_incident_template",
            workflow="bug_triage",
            effect=Effect(kind=OutcomeKind.ROUTE, action="send_incident_template"),
            priority=95,
            conditions=(_c("active_outage", "eq", True, "boolean"),),
            evidence=(_evidence(runbook,
                "If a customer contacts support during an active platform outage, do not troubleshoot. Send the standard incident response template and link to the status page."),),
            rationale="During outages, incident comms replace triage.",
        ),
        Policy(
            id="triage.p0_enterprise_page",
            workflow="bug_triage",
            effect=Effect(kind=OutcomeKind.ROUTE, action="page_on_call"),
            priority=90,
            conditions=(
                _c("priority", "eq", "p0", "string"),
                _c("customer_type", "eq", "enterprise", "string"),
            ),
            evidence=(_evidence(runbook,
                "If a P0 bug is reported by an Enterprise customer, page the on-call engineer immediately."),),
            rationale="P0 + Enterprise pages on-call.",
        ),
        Policy(
            id="triage.p1_resolve_4h",
            workflow="bug_triage",
            effect=Effect(kind=OutcomeKind.ROUTE, action="resolve_within_4_hours"),
            priority=80,
            conditions=(_c("priority", "eq", "p1", "string"),),
            evidence=(_evidence(runbook, "P1 bugs must be resolved within 4 hours."),),
            rationale="P1 SLA.",
        ),
        Policy(
            id="triage.p2_backlog",
            workflow="bug_triage",
            effect=Effect(kind=OutcomeKind.ROUTE, action="add_to_backlog"),
            priority=70,
            conditions=(_c("priority", "eq", "p2", "string"),),
            evidence=(_evidence(runbook,
                "**P2 (Medium/Low):** UI glitches, minor inconveniences. Add to the backlog."),),
            rationale="P2 goes to backlog.",
        ),
        # ---- sla ------------------------------------------------------------
        Policy(
            id="sla.enterprise_2h_notify_am_eng",
            workflow="sla",
            effect=Effect(kind=OutcomeKind.ROUTE, action="notify_am_and_eng_lead"),
            priority=80,
            conditions=(
                _c("customer_type", "eq", "enterprise", "string"),
                _c("sla_breach_hours", "gte", 2, "number"),
            ),
            evidence=(_evidence(runbook,
                "If an Enterprise plan customer SLA is breached by 2 hours or more, you must notify both the Account Manager and the Engineering Lead immediately."),),
            rationale="Enterprise escalation path for >=2h breaches.",
        ),
        Policy(
            id="sla.standard_1h_notify_support_lead",
            workflow="sla",
            effect=Effect(kind=OutcomeKind.ROUTE, action="notify_support_lead"),
            priority=70,
            conditions=(_c("sla_breach_hours", "gt", 1, "number"),),
            evidence=(_evidence(runbook,
                "If a customer SLA is breached by more than 1 hour, notify the support lead."),),
            rationale="Standard breach notification.",
        ),
        # ---- churn ----------------------------------------------------------
        Policy(
            id="churn.am_call_3_signals",
            workflow="churn",
            effect=Effect(kind=OutcomeKind.ROUTE, action="schedule_am_call"),
            priority=80,
            conditions=(_c("churn_signals_count", "gte", 3, "number"),),
            evidence=(_evidence(cs,
                "If a customer exhibits 3 or more churn signals (e.g., no logins, support ticket escalations, downgrade inquiries) within a 30-day timeframe, you must schedule an AM call within 24 hours."),),
            rationale="Three signals in 30 days triggers intervention.",
        ),
        Policy(
            id="churn.below_threshold_monitor",
            workflow="churn",
            effect=Effect(kind=OutcomeKind.ROUTE, action="monitor"),
            priority=70,
            conditions=(_c("churn_signals_count", "lt", 3, "number"),),
            evidence=(_evidence(cs,
                "It is critical to identify and intervene when accounts show signs of churning."),),
            rationale="Authored: below the intervention threshold, keep monitoring. "
                      "(Reviewer judgment grounded in the playbook's intent.)",
        ),
        # ---- onboarding -----------------------------------------------------
        Policy(
            id="onboarding.enterprise_kickoff",
            workflow="onboarding",
            effect=Effect(kind=OutcomeKind.ROUTE, action="initiate_enterprise_onboarding"),
            priority=80,
            conditions=(
                _c("customer_type", "eq", "enterprise", "string"),
                _c("status", "eq", "new", "string"),
            ),
            evidence=(_evidence(cs,
                "For all new Enterprise customers, the onboarding process must include a dedicated kickoff call, a customized training session, and a 30-day check-in."),),
            rationale="Enterprise onboarding is mandatory and structured.",
        ),
        # ---- hiring ---------------------------------------------------------
        Policy(
            id="hiring.eng_offer_founder_approval",
            workflow="hiring",
            effect=Effect(kind=OutcomeKind.ESCALATE, action="get_founder_approval"),
            priority=80,
            conditions=(
                _c("role", "eq", "engineering", "string"),
                _c("stage", "eq", "offer", "string"),
            ),
            evidence=(_evidence(hr,
                "For any engineering candidate at the offer stage, you must get Founder approval before sending the final offer letter."),),
            rationale="Founder gate on engineering offers.",
        ),
        # ---- performance ----------------------------------------------------
        Policy(
            id="performance.pip_two_quarters",
            workflow="performance",
            effect=Effect(kind=OutcomeKind.ROUTE, action="initiate_pip"),
            priority=80,
            conditions=(_c("missed_kpi_quarters", "gte", 2, "number"),),
            evidence=(_evidence(hr,
                "A Performance Improvement Plan (PIP) is triggered if an employee misses their core KPIs for two consecutive quarters."),),
            rationale="PIP trigger per HR playbook.",
        ),
        # ---- vendor ---------------------------------------------------------
        Policy(
            id="vendor.software_3500_route_ops",
            workflow="vendor",
            effect=Effect(kind=OutcomeKind.ROUTE, action="route_to_ops_lead"),
            priority=80,
            conditions=(
                _c("vendor_type", "eq", "software", "string"),
                _c("invoice_amount", "gte", 3500, "number"),
            ),
            evidence=(_evidence(slack_ops,
                "Any software vendor invoice of $3,500 or more needs to be routed to the ops lead for approval before finance pays it."),),
            rationale="Tribal-knowledge precedent from ops Slack.",
        ),
    )
    return Bundle(company_id=COMPANY_ID, workflows=workflows, policies=policies)


def _case(cid, wf, facts, kind, action=None, reason=None, notes="", provenance="") -> GoldenCase:
    return GoldenCase(
        case_id=cid, company_id=COMPANY_ID, workflow=wf, facts=facts,
        expected=Expected(kind=kind, action=action, escalation_reason=reason),
        provenance=provenance or "migrated from legacy eval_harness scenario",
        synthetic=True, notes=notes,
    )


def build_golden_cases() -> list[GoldenCase]:
    return [
        # ---- refund (REF + COND + SLACK families) ---------------------------
        _case("REF-01", "refund", {"plan_type": "annual", "days_since_purchase": 9},
              "approve", "approve_full_refund"),
        _case("REF-02", "refund", {"plan_type": "annual", "days_since_purchase": 20},
              "approve", "approve_prorated_refund"),
        _case("REF-03", "refund", {"plan_type": "enterprise", "days_since_purchase": 7},
              "escalate", "escalate_to_account_manager"),
        _case("REF-04", "refund", {"plan_type": "lifetime_deal", "days_since_purchase": 30},
              "deny", "deny_refund_ltd_terms"),
        _case("REF-05", "refund",
              {"plan_type": "monthly", "tenure_months": 2, "refund_amount": 650,
               "days_since_purchase": 10},
              "escalate", "get_founder_approval",
              notes="REVISED: days_since_purchase added -- without it the 60-day "
                    "deny rule dominates (correctly) and blocks the founder path"),
        _case("REF-06", "refund", {"plan_type": "annual", "days_since_purchase": 75},
              "deny", "deny_refund",
              notes="deny_after_60 overrides prorate via explicit edge"),
        _case("REF-07", "refund", {"plan_type": "annual", "days_since_purchase": 14},
              "approve", "approve_full_refund", notes="boundary: 14 is inclusive"),
        _case("REF-ADV-01", "refund",
              {"plan_type": "enterprise", "days_since_purchase": 5,
               "requested_by": "account_manager"},
              "escalate", "escalate_to_account_manager",
              notes="requested_by is undeclared -> ignored fact; enterprise rule fires"),
        _case("SLACK-01", "refund",
              {"plan_type": "annual", "days_since_purchase": 45, "tenure_years": 4},
              "approve", "approve_full_refund",
              notes="REVISED: legacy used days_since_charge; unified to "
                    "days_since_purchase and plan_type added. Loyalty precedent "
                    "overrides prorate."),
        _case("COND-01", "refund", {"plan_type": "annual", "days_since_purchase": 14},
              "approve", "approve_full_refund",
              notes="REVISED: plan_type added (legacy relied on missing-is-neutral)"),
        _case("COND-02", "refund", {"plan_type": "annual", "days_since_purchase": 15},
              "approve", "approve_prorated_refund",
              notes="REVISED: plan_type added; boundary 15 > 14"),
        _case("COND-03", "refund",
              {"plan_type": "monthly", "tenure_months": 2, "refund_amount": 500,
               "days_since_purchase": 10, "tenure_years": 0},
              "escalate", reason="no_matching_policy",
              notes="REVISED: at exactly $500 the founder rule does not fire and the "
                    "SOP is silent on ordinary monthly refunds -- a documented gap"),
        _case("COND-04", "refund",
              {"plan_type": "monthly", "tenure_months": 2, "refund_amount": 501,
               "days_since_purchase": 10},
              "escalate", "get_founder_approval",
              notes="REVISED: full facts; boundary 501 > 500"),
        _case("COND-06", "refund", {"plan_type": "annual", "days_since_purchase": 60},
              "approve", "approve_prorated_refund",
              notes="CORRECTED: SOP says 'after 60 days' => 60 exactly still prorates. "
                    "Legacy expectation (deny at 60) contradicted the SOP text."),
        _case("COND-06B", "refund", {"plan_type": "annual", "days_since_purchase": 61},
              "deny", "deny_refund", notes="NEW: true >60 boundary"),
        _case("COND-07", "refund", {"plan_type": "lifetime_deal"},
              "deny", "deny_refund_ltd_terms"),
        _case("DET-03", "refund", {"vague": True},
              "escalate", reason="missing_facts",
              notes="REVISED: unrecognized fact only -> every policy undeterminable"),
        _case("DET-04", "refund", {"plan_type": "enterprise"},
              "escalate", reason="missing_facts",
              notes="REVISED: enterprise WITHOUT purchase age is blocked by dominance "
                    "-- the 60-day deny rule (priority 100) could govern and outranks "
                    "the enterprise AM-escalation (90). This case tests the dominance "
                    "rule. With days supplied, see REF-03."),
        # ---- discount (PRICE + DET-05) --------------------------------------
        _case("PRICE-01", "discount", {"discount_percent": 10},
              "approve", "approve_discount", notes="boundary: 10 inclusive"),
        _case("PRICE-02", "discount", {"discount_percent": 35},
              "escalate", "escalate_to_account_executive"),
        _case("PRICE-03", "discount", {"customer_stage": "pre-seed", "plan": "annual"},
              "approve", "approve_20_percent_startup_discount",
              notes="discount_percent defaults to 0; specificity beats standard_10"),
        _case("PRICE-ADV-01", "discount",
              {"customer_stage": "series_a", "discount_percent": 25},
              "escalate", reason="no_matching_policy",
              notes="REVISED: series_a is not startup-eligible and 25% is in the "
                    "documented 10-30 gap"),
        _case("PRICE-GAP", "discount", {"discount_percent": 25},
              "escalate", reason="no_matching_policy",
              notes="NEW: the 10-30% non-startup gap the pricing doc never covers"),
        _case("DET-05", "discount", {"discount_percent": 30},
              "escalate", reason="no_matching_policy",
              notes="REVISED (was COND-05 too): 30 is neither <=10 nor >30 nor "
                    "startup-eligible -- a real boundary gap in the pricing doc"),
        # ---- bug_triage (ENG + DET) ------------------------------------------
        _case("ENG-01", "bug_triage", {"priority": "P0", "customer_type": "enterprise"},
              "route", "page_on_call"),
        _case("ENG-03", "bug_triage", {"active_outage": True},
              "route", "send_incident_template",
              notes="outage outranks undeterminable P-policies by priority"),
        _case("ENG-04", "bug_triage", {"priority": "P1"},
              "route", "resolve_within_4_hours"),
        _case("ENG-ADV-01", "bug_triage",
              {"priority": "P2", "affected_users_pct": 4, "workaround_available": True},
              "route", "add_to_backlog",
              notes="REVISED: doc-grounded P2 action is backlog; legacy expected the "
                    "P1 action, which the runbook does not support"),
        _case("ENG-P0-UNKNOWN", "bug_triage", {"priority": "P0"},
              "escalate", reason="missing_facts",
              notes="NEW: P0 without customer_type cannot resolve the enterprise rule"),
        _case("DET-01", "bug_triage", {},
              "escalate", reason="missing_facts",
              notes="REPLACED: legacy DET-01 duplicated ENG-04 facts with a different "
                    "expectation -- impossible under determinism. Now: empty facts."),
        _case("DET-06", "bug_triage", {"customer_type": "enterprise"},
              "escalate", reason="missing_facts",
              notes="REVISED: no priority supplied -> escalate listing priority"),
        # ---- sla (ENG-02) ----------------------------------------------------
        _case("ENG-02", "sla", {"customer_type": "enterprise", "sla_breach_hours": 2.5},
              "route", "notify_am_and_eng_lead",
              notes="specificity: enterprise rule beats standard when both match"),
        _case("SLA-STD", "sla", {"customer_type": "smb", "sla_breach_hours": 1.5},
              "route", "notify_support_lead", notes="NEW: standard path coverage"),
        _case("SLA-UNKNOWN-TIER", "sla", {"sla_breach_hours": 3},
              "escalate", reason="missing_facts",
              notes="NEW: >=2h breach with unknown tier is blocked by dominance -- "
                    "the enterprise rule could apply and outranks standard"),
        # ---- churn (CS + COND-08) --------------------------------------------
        _case("CS-01", "churn", {"churn_signals_count": 4},
              "route", "schedule_am_call",
              notes="REVISED: timeframe_days folded into the fact definition"),
        _case("CS-03", "churn", {"churn_signals_count": 2}, "route", "monitor"),
        _case("CS-ADV-01", "churn", {"churn_signals_count": 2}, "route", "monitor",
              notes="REVISED: 2 signals in any window below 3 -> monitor"),
        _case("COND-08", "churn", {"churn_signals_count": 3},
              "route", "schedule_am_call", notes="boundary: 3 inclusive"),
        # ---- onboarding (CS-02) ----------------------------------------------
        _case("CS-02", "onboarding", {"customer_type": "enterprise", "status": "new"},
              "route", "initiate_enterprise_onboarding"),
        # ---- hiring (HR-01, HR-ADV-01, DET-02) --------------------------------
        _case("HR-01", "hiring", {"role": "engineering", "stage": "offer"},
              "escalate", "get_founder_approval"),
        _case("HR-ADV-01", "hiring",
              {"role": "product_manager", "stage": "offer", "includes_equity": True},
              "escalate", reason="no_matching_policy",
              notes="REVISED: the playbook gates ENGINEERING offers only; PM offers "
                    "are a documented gap (legacy expected founder approval without "
                    "doc support)"),
        _case("DET-02", "hiring", {"stage": "offer"},
              "escalate", reason="missing_facts",
              notes="REVISED: role unknown -> founder-gate rule undeterminable"),
        # ---- performance (HR-02) ----------------------------------------------
        _case("HR-02", "performance", {"missed_kpi_quarters": 2},
              "route", "initiate_pip", notes="boundary: 2 inclusive"),
        # ---- vendor (OPS-01) ---------------------------------------------------
        _case("OPS-01", "vendor", {"invoice_amount": 4200, "vendor_type": "software"},
              "route", "route_to_ops_lead"),
        _case("OPS-SMALL", "vendor", {"invoice_amount": 900, "vendor_type": "software"},
              "escalate", reason="no_matching_policy",
              notes="NEW: sub-$3,500 invoices are not covered by the Slack precedent"),
    ]
