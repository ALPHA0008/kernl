"""Unit tests: escalation workflow, replay engine, bundle lifecycle,
and the full V1 loop (scenario -> evaluation -> trace -> ledger -> replay
-> escalation -> adjudication -> golden promotion).

Deterministic: no LLM, no DB, no network. Run directly or via pytest:
    py -3 backend/tests/test_escalation_replay_lifecycle.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.bundle.canonical import bundle_content_hash
from backend.bundle.lifecycle import (
    BundleLifecycle,
    BundleStatus,
    InMemoryBundleStore,
    PublishGateError,
)
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
from backend.escalation.service import (
    AlreadyResolvedError,
    EscalationReasonKind,
    EscalationService,
    EscalationStatus,
    InMemoryEscalationStore,
)
from backend.ledger.events import Actor
from backend.ledger.service import DecisionService
from backend.ledger.store import InMemoryLedgerStore
from backend.replay.cases import Expected, GoldenCase, InMemoryCaseStore
from backend.replay.engine import InMemoryReplayRunStore, ReplayEngine


def _ev():
    return Evidence(source_id="doc.md", source_version="sha256:x",
                    span_start=0, span_end=5, excerpt="rule")


def _wf():
    return WorkflowSpec(
        name="refund",
        facts=(
            FactSpec(name="plan_type", value_type="string"),
            FactSpec(name="days_since_purchase", value_type="number"),
        ),
    )


def _pol(pid="refund.annual_14d", days=14, authority=None):
    return Policy(
        id=pid, workflow="refund",
        effect=Effect(kind=OutcomeKind.APPROVE, action="approve_full_refund"),
        priority=70,
        conditions=(
            Condition(field="plan_type", operator="eq", value="annual", value_type="string"),
            Condition(field="days_since_purchase", operator="lte", value=days, value_type="number"),
        ),
        authority=authority or Authority(),
        evidence=(_ev(),),
    )


def _bundle(days=14, authority=None):
    return Bundle(company_id="acme", workflows=(_wf(),),
                  policies=(_pol(days=days, authority=authority),))


HUMAN = Actor(type="human", id="jane")
AGENT = Actor(type="agent", id="bot")


def _stack():
    ledger = InMemoryLedgerStore()
    decisions = DecisionService(ledger)
    cases = InMemoryCaseStore()
    promoted = []

    def promote(event, resolution):  # noqa: ANN001
        case = GoldenCase(
            case_id=f"adj-{event.event_id[:8]}",
            company_id=event.company_id,
            workflow=event.workflow,
            facts=event.facts,
            expected=Expected(kind=resolution.outcome_kind, action=resolution.chosen_action),
            provenance=f"adjudication:{resolution.adjudication_event_id}",
            synthetic=False,
        )
        cases.add(case)
        promoted.append(case)

    escalations = EscalationService(InMemoryEscalationStore(), decisions, promote)
    return ledger, decisions, escalations, cases, promoted


# --- escalation --------------------------------------------------------------


def test_no_escalation_for_clean_decision():
    _, decisions, escalations, _, _ = _stack()
    b = _bundle()
    event, _ = decisions.decide(
        company_id="acme", workflow="refund",
        facts={"plan_type": "annual", "days_since_purchase": 9},
        actor=AGENT, idempotency_key="k1",
        bundle=b, bundle_hash=bundle_content_hash(b),
    )
    assert escalations.open_for(event) is None


def test_missing_facts_opens_escalation_with_detail():
    _, decisions, escalations, _, _ = _stack()
    b = _bundle()
    event, _ = decisions.decide(
        company_id="acme", workflow="refund", facts={"days_since_purchase": 9},
        actor=AGENT, idempotency_key="k1",
        bundle=b, bundle_hash=bundle_content_hash(b),
    )
    esc = escalations.open_for(event)
    assert esc is not None
    assert esc.reason is EscalationReasonKind.MISSING_FACTS
    assert "plan_type" in esc.detail["missing_facts"]


def test_approval_required_opens_authority_escalation():
    _, decisions, escalations, _, _ = _stack()
    gated = _bundle(authority=Authority(approval_required=True, approver_role="founder"))
    event, _ = decisions.decide(
        company_id="acme", workflow="refund",
        facts={"plan_type": "annual", "days_since_purchase": 9},
        actor=AGENT, idempotency_key="k1",
        bundle=gated, bundle_hash=bundle_content_hash(gated),
    )
    esc = escalations.open_for(event)
    assert esc is not None
    assert esc.reason is EscalationReasonKind.AUTHORITY_REQUIRED
    assert esc.detail["approver_role"] == "founder"


def test_resolution_is_ledgered_and_idempotent_guarded():
    ledger, decisions, escalations, _, _ = _stack()
    b = _bundle()
    event, _ = decisions.decide(
        company_id="acme", workflow="refund", facts={"days_since_purchase": 9},
        actor=AGENT, idempotency_key="k1",
        bundle=b, bundle_hash=bundle_content_hash(b),
    )
    esc = escalations.open_for(event)
    resolved = escalations.resolve(
        company_id="acme", escalation_id=esc.escalation_id, resolver=HUMAN,
        chosen_action="approve_full_refund", outcome_kind="approve",
        rationale="Billing system confirms annual plan.",
    )
    assert resolved.status is EscalationStatus.RESOLVED
    adj = ledger.get("acme", resolved.resolution.adjudication_event_id)
    assert adj is not None and adj.linked_event_id == event.event_id
    assert ledger.verify_chain("acme")
    try:
        escalations.resolve(
            company_id="acme", escalation_id=esc.escalation_id, resolver=HUMAN,
            chosen_action="deny_refund", outcome_kind="deny", rationale="second try",
        )
        assert False, "double resolution must be rejected"
    except AlreadyResolvedError:
        pass


def test_promotion_creates_golden_case_with_provenance():
    _, decisions, escalations, cases, promoted = _stack()
    b = _bundle()
    event, _ = decisions.decide(
        company_id="acme", workflow="refund", facts={"days_since_purchase": 9},
        actor=AGENT, idempotency_key="k1",
        bundle=b, bundle_hash=bundle_content_hash(b),
    )
    esc = escalations.open_for(event)
    escalations.resolve(
        company_id="acme", escalation_id=esc.escalation_id, resolver=HUMAN,
        chosen_action="approve_full_refund", outcome_kind="approve",
        rationale="verified", promote_to_golden=True,
    )
    assert len(promoted) == 1
    assert promoted[0].synthetic is False
    assert promoted[0].provenance.startswith("adjudication:")
    assert cases.list("acme")[0].case_id == promoted[0].case_id


# --- replay ------------------------------------------------------------------


def _golden(case_id, facts, kind, action=None, reason=None):
    return GoldenCase(
        case_id=case_id, company_id="acme", workflow="refund", facts=facts,
        expected=Expected(kind=kind, action=action, escalation_reason=reason),
        provenance="test",
    )


def test_replay_golden_pass_and_fail():
    engine = ReplayEngine(InMemoryReplayRunStore())
    b = _bundle()
    run = engine.run(
        company_id="acme",
        cases=[
            _golden("g1", {"plan_type": "annual", "days_since_purchase": 9},
                    "approve", "approve_full_refund"),
            _golden("g2", {"plan_type": "annual", "days_since_purchase": 20},
                    "approve", "approve_full_refund"),  # 20 > 14 -> escalate, so FAIL
        ],
        candidate=b,
    )
    assert run.summary.golden_passed == 1
    assert run.summary.golden_failed == 1
    assert run.candidate_bundle_hash == bundle_content_hash(b)


def test_replay_detects_flips_and_new_escalations():
    engine = ReplayEngine(InMemoryReplayRunStore())
    reference = _bundle(days=14)
    candidate = _bundle(days=7)  # tightened window
    run = engine.run(
        company_id="acme",
        cases=[
            _golden("g1", {"plan_type": "annual", "days_since_purchase": 9},
                    "approve", "approve_full_refund"),
            _golden("g2", {"plan_type": "annual", "days_since_purchase": 5},
                    "approve", "approve_full_refund"),
        ],
        candidate=candidate,
        reference=reference,
    )
    # day-9 case: reference approves, candidate escalates (no match) -> flip + new escalation
    assert run.summary.flips == 1
    assert run.summary.new_escalations == 1
    flipped = next(r for r in run.results if r.case_id == "g1")
    assert flipped.flipped is True and flipped.candidate_kind == "escalate"


def test_replay_identical_bundles_zero_flips():
    engine = ReplayEngine(InMemoryReplayRunStore())
    b = _bundle()
    run = engine.run(
        company_id="acme",
        cases=[_golden("g1", {"plan_type": "annual", "days_since_purchase": 9},
                       "approve", "approve_full_refund")],
        candidate=b, reference=_bundle(),
    )
    assert run.summary.flips == 0


def test_replay_expected_escalation_reason_scored():
    engine = ReplayEngine(InMemoryReplayRunStore())
    run = ReplayEngine(InMemoryReplayRunStore()).run(
        company_id="acme",
        cases=[_golden("g1", {"days_since_purchase": 9}, "escalate",
                       reason="missing_facts")],
        candidate=_bundle(),
    )
    assert run.summary.golden_passed == 1


# --- lifecycle + publish gate -------------------------------------------------


def test_publish_blocked_without_acknowledged_replay():
    runs = InMemoryReplayRunStore()
    lc = BundleLifecycle(InMemoryBundleStore(), runs)
    draft = lc.save_draft("acme", _bundle(), created_by="jane")
    assert draft.status is BundleStatus.DRAFT
    try:
        lc.publish("acme", draft.record_id, published_by="jane")
        assert False, "publish without replay must be blocked"
    except PublishGateError:
        pass


def test_publish_flows_through_replay_gate():
    runs = InMemoryReplayRunStore()
    engine = ReplayEngine(runs)
    lc = BundleLifecycle(InMemoryBundleStore(), runs)
    b = _bundle()
    draft = lc.save_draft("acme", b, created_by="jane")
    run = engine.run(
        company_id="acme",
        cases=[_golden("g1", {"plan_type": "annual", "days_since_purchase": 9},
                       "approve", "approve_full_refund")],
        candidate=b,
    )
    engine.acknowledge("acme", run.run_id, by="jane")
    published = lc.publish("acme", draft.record_id, published_by="jane")
    assert published.status is BundleStatus.PUBLISHED
    assert published.replay_run_id == run.run_id
    assert lc.active_bundle("acme").record_id == published.record_id


def test_rollback_is_pointer_move_to_previously_published():
    runs = InMemoryReplayRunStore()
    engine = ReplayEngine(runs)
    lc = BundleLifecycle(InMemoryBundleStore(), runs)
    cases = [_golden("g1", {"plan_type": "annual", "days_since_purchase": 5},
                     "approve", "approve_full_refund")]

    v1, v2 = _bundle(days=14), _bundle(days=7)
    d1 = lc.save_draft("acme", v1, created_by="jane")
    r1 = engine.run(company_id="acme", cases=cases, candidate=v1)
    engine.acknowledge("acme", r1.run_id, by="jane")
    lc.publish("acme", d1.record_id, published_by="jane")

    d2 = lc.save_draft("acme", v2, created_by="jane")
    r2 = engine.run(company_id="acme", cases=cases, candidate=v2)
    engine.acknowledge("acme", r2.run_id, by="jane")
    lc.publish("acme", d2.record_id, published_by="jane")
    assert lc.active_bundle("acme").content_hash == bundle_content_hash(v2)

    lc.activate("acme", d1.record_id)  # rollback
    assert lc.active_bundle("acme").content_hash == bundle_content_hash(v1)
    # a never-published draft cannot be activated
    d3 = lc.save_draft("acme", _bundle(days=30), created_by="jane")
    try:
        lc.activate("acme", d3.record_id)
        assert False, "activating an unpublished draft must fail"
    except PublishGateError:
        pass


def test_identical_content_publish_is_noop_and_dedup():
    runs = InMemoryReplayRunStore()
    engine = ReplayEngine(runs)
    lc = BundleLifecycle(InMemoryBundleStore(), runs)
    b = _bundle()
    d1 = lc.save_draft("acme", b, created_by="jane")
    d1_again = lc.save_draft("acme", _bundle(), created_by="jane")
    assert d1.record_id == d1_again.record_id  # content-addressed dedup
    run = engine.run(
        company_id="acme",
        cases=[_golden("g1", {"plan_type": "annual", "days_since_purchase": 9},
                       "approve", "approve_full_refund")],
        candidate=b,
    )
    engine.acknowledge("acme", run.run_id, by="jane")
    p1 = lc.publish("acme", d1.record_id, published_by="jane")
    p2 = lc.publish("acme", d1.record_id, published_by="jane")
    assert p1.record_id == p2.record_id


# --- the full V1 loop ---------------------------------------------------------


def test_full_v1_loop():
    """Scenario -> Evaluation -> Trace -> Ledger -> Replay -> Escalation ->
    Adjudication -> Golden promotion -> tightened bundle blocked by gate."""
    ledger = InMemoryLedgerStore()
    decisions = DecisionService(ledger)
    case_store = InMemoryCaseStore()

    def promote(event, resolution):  # noqa: ANN001
        case_store.add(GoldenCase(
            case_id=f"adj-{event.event_id[:8]}", company_id=event.company_id,
            workflow=event.workflow, facts=event.facts,
            expected=Expected(kind=resolution.outcome_kind, action=resolution.chosen_action),
            provenance=f"adjudication:{resolution.adjudication_event_id}", synthetic=False,
        ))

    escalations = EscalationService(InMemoryEscalationStore(), decisions, promote)
    runs = InMemoryReplayRunStore()
    engine = ReplayEngine(runs)
    lc = BundleLifecycle(InMemoryBundleStore(), runs)

    # 1. author + gate + publish v1
    b = _bundle()
    case_store.add(_golden("g1", {"plan_type": "annual", "days_since_purchase": 9},
                           "approve", "approve_full_refund"))
    draft = lc.save_draft("acme", b, created_by="jane")
    run = engine.run(company_id="acme", cases=case_store.list("acme"), candidate=b)
    assert run.summary.golden_failed == 0
    engine.acknowledge("acme", run.run_id, by="jane")
    published = lc.publish("acme", draft.record_id, published_by="jane")

    # 2. an agent asks a decision (clean path): evaluated, traced, ledgered
    ok_event, _ = decisions.decide(
        company_id="acme", workflow="refund",
        facts={"plan_type": "annual", "days_since_purchase": 9},
        actor=AGENT, idempotency_key="t1",
        bundle=published.bundle, bundle_hash=published.content_hash,
    )
    assert ok_event.outcome["kind"] == "approve"
    assert ok_event.trace["precedence"]["winner"] == "refund.annual_14d"
    assert escalations.open_for(ok_event) is None

    # 3. an incomplete scenario escalates and is adjudicated + promoted
    esc_event, _ = decisions.decide(
        company_id="acme", workflow="refund", facts={"days_since_purchase": 9},
        actor=AGENT, idempotency_key="t2",
        bundle=published.bundle, bundle_hash=published.content_hash,
    )
    esc = escalations.open_for(esc_event)
    escalations.resolve(
        company_id="acme", escalation_id=esc.escalation_id, resolver=HUMAN,
        chosen_action="approve_full_refund", outcome_kind="approve",
        rationale="Verified plan in billing.", promote_to_golden=True,
    )
    assert len(case_store.list("acme")) == 2
    assert ledger.verify_chain("acme")

    # 4. a tightened draft (7-day window) fails the grown golden set on replay
    tight = _bundle(days=7)
    tight_draft = lc.save_draft("acme", tight, created_by="jane")
    tight_run = engine.run(company_id="acme", cases=case_store.list("acme"),
                           candidate=tight, reference=published.bundle)
    assert tight_run.summary.golden_failed >= 1  # day-9 approvals now fail
    assert tight_run.summary.flips >= 1
    # gate still enforces acknowledgment (a human must own the blast radius)
    try:
        lc.publish("acme", tight_draft.record_id, published_by="jane")
        assert False
    except PublishGateError:
        pass


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
