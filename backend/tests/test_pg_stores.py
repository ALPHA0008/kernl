"""Contract tests: the Postgres adapters must satisfy the exact semantics the
in-memory reference stores define -- run against a REAL database.

Behavior:
  - Requires KERNL_DB_URL (or SUPABASE_DB_URL) in the environment or .env.
    Without it the suite SKIPS (exit 0) with a clear message -- it never fakes
    a pass.
  - Fully isolated: creates a throwaway schema (kernl_test_<hex>), applies
    backend/schema.sql inside it, runs, then DROPs the schema -- the real
    database keeps no residue and reruns are safe.

    py -3 backend/tests/test_pg_stores.py
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

# explicit repo-root .env (backend/.env would shadow it in the walk-up)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DB_URL = os.environ.get("KERNL_DB_URL") or os.environ.get("SUPABASE_DB_URL")

if not DB_URL:
    print(
        "SKIPPED: no KERNL_DB_URL / SUPABASE_DB_URL configured. "
        "Add the direct Postgres connection string to .env to run the "
        "adapter contract suite. (This is a skip, not a pass: the Postgres "
        "adapters are NOT verified until this suite runs green.)"
    )
    sys.exit(0)

import psycopg
from psycopg import sql

from backend.apply_schema import apply as apply_schema
from backend.bundle.canonical import bundle_content_hash
from backend.bundle.lifecycle import BundleLifecycle, PublishGateError
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
from backend.escalation.service import EscalationService, EscalationStatus
from backend.ledger.events import Actor
from backend.ledger.service import DecisionService
from backend.replay.cases import Expected, GoldenCase
from backend.replay.engine import ReplayEngine
from backend.onboarding.drafts import build_draft
from backend.onboarding.service import OnboardingService
from backend.onboarding.sources import make_snapshot
from backend.onboarding.tenants import Tenant, TenantService
from backend.stores_pg import (
    PgBundleStore,
    PgCaseStore,
    PgDraftStore,
    PgEscalationStore,
    PgLedgerStore,
    PgReplayRunStore,
    PgSourceStore,
    PgTenantStore,
    SharedPgConn,
)

SCHEMA = f"kernl_test_{uuid.uuid4().hex[:10]}"


def _bundle(days: int = 14) -> Bundle:
    wf = WorkflowSpec(
        name="refund",
        facts=(
            FactSpec(name="plan_type", value_type="string"),
            FactSpec(name="days_since_purchase", value_type="number"),
        ),
    )
    pol = Policy(
        id="refund.annual_14d",
        workflow="refund",
        effect=Effect(kind=OutcomeKind.APPROVE, action="approve_full_refund"),
        priority=70,
        conditions=(
            Condition(field="plan_type", operator="eq", value="annual", value_type="string"),
            Condition(field="days_since_purchase", operator="lte", value=days,
                      value_type="number"),
        ),
        evidence=(
            Evidence(source_id="doc.md", source_version="sha256:x", span_start=0,
                     span_end=5, excerpt="rule"),
        ),
    )
    return Bundle(company_id="pg-test", workflows=(wf,), policies=(pol,))


AGENT = Actor(type="agent", id="bot", api_key_id="k1")
HUMAN = Actor(type="human", id="jane")


class Stack:
    def __init__(self) -> None:
        self.ledger = PgLedgerStore(DB_URL, schema=SCHEMA)
        self.bundles = PgBundleStore(DB_URL, schema=SCHEMA)
        self.escalation_store = PgEscalationStore(DB_URL, schema=SCHEMA)
        self.cases = PgCaseStore(DB_URL, schema=SCHEMA)
        self.replay_runs = PgReplayRunStore(DB_URL, schema=SCHEMA)
        self.decisions = DecisionService(self.ledger)
        self.replay = ReplayEngine(self.replay_runs)
        self.lifecycle = BundleLifecycle(self.bundles, self.replay_runs)
        self.escalations = EscalationService(
            self.escalation_store, self.decisions, self._promote
        )
        self.promoted: list[GoldenCase] = []

    def _promote(self, event, resolution):  # noqa: ANN001
        case = GoldenCase(
            case_id=f"adj-{event.event_id[:8]}",
            company_id=event.company_id,
            workflow=event.workflow,
            facts=event.facts,
            expected=Expected(kind=resolution.outcome_kind, action=resolution.chosen_action),
            provenance=f"adjudication:{resolution.adjudication_event_id}",
            synthetic=False,
        )
        self.cases.add(case)
        self.promoted.append(case)


S: Stack  # initialized in main after schema setup
CID = "pg-test"


def test_ledger_append_idempotency_chain():
    b = _bundle()
    h = bundle_content_hash(b)
    e1, c1 = S.decisions.decide(company_id=CID, workflow="refund",
                                facts={"plan_type": "annual", "days_since_purchase": 9},
                                actor=AGENT, idempotency_key="k1", bundle=b, bundle_hash=h)
    e2, c2 = S.decisions.decide(company_id=CID, workflow="refund",
                                facts={"plan_type": "annual", "days_since_purchase": 99},
                                actor=AGENT, idempotency_key="k1", bundle=b, bundle_hash=h)
    assert c1 is True and c2 is False and e2.event_id == e1.event_id
    assert e2.outcome == e1.outcome  # original preserved verbatim
    e3, _ = S.decisions.decide(company_id=CID, workflow="refund",
                               facts={"plan_type": "annual", "days_since_purchase": 9},
                               actor=AGENT, idempotency_key="k2", bundle=b, bundle_hash=h)
    assert e3.prev_event_hash == e1.event_hash
    assert S.ledger.verify_chain(CID) is True
    # round-trip hash integrity: reconstructed event re-verifies
    fetched = S.ledger.get(CID, e1.event_id)
    assert fetched is not None and fetched.verify()


def test_history_mutation_blocked_by_database():
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(SCHEMA)))
            try:
                cur.execute("UPDATE decision_events SET outcome_kind = 'deny'")
                assert False, "UPDATE on decision_events must be blocked by trigger"
            except psycopg.errors.RaiseException as exc:
                assert "append-only" in str(exc)
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(SCHEMA)))
            try:
                cur.execute("DELETE FROM decision_events")
                assert False, "DELETE on decision_events must be blocked by trigger"
            except psycopg.errors.RaiseException:
                pass
        conn.rollback()


def test_ledger_list_filters():
    rows = S.ledger.list(CID, outcome_kind="approve")
    assert rows and all(r.outcome["kind"] == "approve" for r in rows)
    assert S.ledger.list("other-co") == []
    assert S.ledger.chain_head("other-co") is None


def test_lifecycle_publish_gate_and_rollback():
    b1, b2 = _bundle(days=14), _bundle(days=7)
    S.cases.add(GoldenCase(
        case_id="g1", company_id=CID, workflow="refund",
        facts={"plan_type": "annual", "days_since_purchase": 5},
        expected=Expected(kind="approve", action="approve_full_refund"),
        provenance="test",
    ))
    d1 = S.lifecycle.save_draft(CID, b1, created_by="jane")
    d1_dup = S.lifecycle.save_draft(CID, _bundle(days=14), created_by="jane")
    assert d1_dup.record_id == d1.record_id  # content-addressed dedup via unique index
    try:
        S.lifecycle.publish(CID, d1.record_id, published_by="jane")
        assert False, "publish without acknowledged replay must be blocked"
    except PublishGateError:
        pass
    run = S.replay.run(company_id=CID, cases=S.cases.list(CID), candidate=b1)
    S.replay.acknowledge(CID, run.run_id, by="jane")
    p1 = S.lifecycle.publish(CID, d1.record_id, published_by="jane")
    assert S.lifecycle.active_bundle(CID).record_id == p1.record_id

    d2 = S.lifecycle.save_draft(CID, b2, created_by="jane")
    run2 = S.replay.run(company_id=CID, cases=S.cases.list(CID), candidate=b2,
                        reference=b1)
    assert run2.summary.flips >= 0  # persisted run reconstructs
    S.replay.acknowledge(CID, run2.run_id, by="jane")
    S.lifecycle.publish(CID, d2.record_id, published_by="jane")
    assert S.lifecycle.active_bundle(CID).content_hash == bundle_content_hash(b2)
    S.lifecycle.activate(CID, d1.record_id)  # rollback = pointer move
    assert S.lifecycle.active_bundle(CID).content_hash == bundle_content_hash(b1)


def test_escalation_resolution_and_promotion():
    active = S.lifecycle.active_bundle(CID)
    event, _ = S.decisions.decide(company_id=CID, workflow="refund",
                                  facts={"days_since_purchase": 9},
                                  actor=AGENT, idempotency_key="esc-1",
                                  bundle=active.bundle, bundle_hash=active.content_hash)
    assert event.outcome["kind"] == "escalate"
    esc = S.escalations.open_for(event)
    assert esc is not None
    dup = S.escalations.open_for(event)  # one escalation per decision
    assert dup.escalation_id == esc.escalation_id
    resolved = S.escalations.resolve(
        company_id=CID, escalation_id=esc.escalation_id, resolver=HUMAN,
        chosen_action="approve_full_refund", outcome_kind="approve",
        rationale="verified in billing", promote_to_golden=True,
    )
    assert resolved.status is EscalationStatus.RESOLVED
    fetched = S.escalation_store.get(CID, esc.escalation_id)
    assert fetched.resolution is not None
    assert fetched.resolution.rationale == "verified in billing"
    assert len(S.promoted) == 1 and S.promoted[0].synthetic is False
    assert any(c.case_id == S.promoted[0].case_id for c in S.cases.list(CID))
    assert S.ledger.verify_chain(CID) is True


def test_case_duplicate_rejected():
    case = GoldenCase(case_id="dup-x", company_id=CID, workflow="refund",
                      facts={}, expected=Expected(kind="escalate"), provenance="t")
    S.cases.add(case)
    try:
        S.cases.add(case)
        assert False, "duplicate case id must raise"
    except ValueError:
        pass


def test_persistence_across_reconnect():
    """The point of the whole exercise: a NEW connection sees everything."""
    fresh = Stack()
    assert fresh.lifecycle.active_bundle(CID) is not None
    assert fresh.ledger.verify_chain(CID) is True
    assert len(fresh.ledger.list(CID)) >= 4
    assert fresh.cases.list(CID)


def test_onboarding_stores_full_flow():
    """Onboarding adapters satisfy the same contract: provision a tenant, issue
    + resolve a hashed key, snapshot a source, author + ground + accept a draft,
    and see it all survive a fresh connection."""
    tenants = TenantService(PgTenantStore(DB_URL, schema=SCHEMA))
    sources = PgSourceStore(DB_URL, schema=SCHEMA)
    drafts = PgDraftStore(DB_URL, schema=SCHEMA)
    svc = OnboardingService(tenants, sources, drafts)

    tenant, key = tenants.provision("pg-onboard-co", "PG Onboard Co")
    assert tenant.company_id == "pg-onboard-co" and key.startswith("kk_")
    # hashed key resolves; duplicate tenant rejected
    assert tenants.resolve(key).role == "owner"
    try:
        tenants.provision("pg-onboard-co", "dup")
        assert False, "duplicate tenant must raise"
    except ValueError:
        pass

    source_text = "Annual plans refunded within 14 days receive a full refund."
    snap = sources.add(make_snapshot("pg-onboard-co", "refund.md", source_text))
    assert sources.get("pg-onboard-co", snap.source_id).content == source_text

    proposed = {
        "id": "refund.annual_14d", "workflow": "refund",
        "effect": {"kind": "approve", "action": "approve_full_refund"},
        "priority": 70,
        "conditions": [{"field": "days_since_purchase", "operator": "lte",
                        "value": 14, "value_type": "number"}],
        "authority": {"approval_required": False}, "overrides": [],
        "unconditional_ack": False, "rationale": "x",
    }
    d = svc.save_draft("pg-onboard-co", proposed)
    assert d.publishable is False
    start = source_text.index("Annual")
    end = source_text.index("full refund.") + len("full refund.")
    d = svc.ground_span("pg-onboard-co", d.draft_id, snap.source_id, start, end,
                        source_text[start:end])
    assert d.publishable is True
    svc.set_status("pg-onboard-co", d.draft_id, "accepted")

    # fresh connections see the persisted state, and a bundle assembles
    fresh = OnboardingService(
        TenantService(PgTenantStore(DB_URL, schema=SCHEMA)),
        PgSourceStore(DB_URL, schema=SCHEMA),
        PgDraftStore(DB_URL, schema=SCHEMA),
    )
    accepted = fresh.drafts.list("pg-onboard-co", status="accepted")
    assert len(accepted) == 1 and accepted[0].evidence_json
    bundle = fresh.assemble_bundle("pg-onboard-co")
    assert len(bundle.policies) == 1


def test_all_stores_share_one_connection():
    """The production wiring: eight stores over ONE SharedPgConn use exactly
    one physical connection, not eight. This is what fixes the real
    EMAXCONNSESSION failure -- a container is a single-connection client, in
    line with the arc's single-writer-per-cell design. Verified by identity
    (one holder, one lock, one live psycopg connection object) AND by
    behavior (writes through one store are visible through another on the
    same shared connection)."""
    shared = SharedPgConn(DB_URL, schema=SCHEMA)
    ledger = PgLedgerStore(shared=shared)
    bundles = PgBundleStore(shared=shared)
    cases = PgCaseStore(shared=shared)
    tenants = PgTenantStore(shared=shared)

    # identity: every store points at the same holder + lock
    assert ledger._shared is bundles._shared is cases._shared is tenants._shared
    assert ledger._lock is tenants._lock

    # one physical connection object, opened once and reused by all stores
    conn_via_ledger = ledger._connection()
    conn_via_bundles = bundles._connection()
    assert conn_via_ledger is conn_via_bundles
    assert not conn_via_ledger.closed

    # behavior: a write via one store is visible via another store on the
    # same shared connection (provisioning goes through TenantService, which
    # wraps `tenants`; a second store on the same holder reads it back)
    TenantService(tenants).provision("pg-shared-co", "PG Shared Co")
    fetched = PgTenantStore(shared=shared).get_tenant("pg-shared-co")
    assert fetched is not None and fetched.company_id == "pg-shared-co"

    shared.close()
    assert conn_via_ledger.closed


def test_delete_tenant_purges_all_data_and_is_isolated():
    """Whole-tenant purge (retention policy: discard the entire logbook) works
    against the live DB -- including deleting decision_events, which the
    append-only trigger normally blocks. Critically: purging tenant A must NOT
    touch tenant B's ledger, and the trigger must still block an ordinary
    (non-purge) delete afterward. This is the constitutional line: whole-stream
    removal is allowed; editing or partially deleting a live stream is not."""
    victim = "pg-purge-victim"
    bystander = CID  # the main test tenant, with real ledger history

    # give the victim its own tenant row + a real ledger event
    tsvc = TenantService(PgTenantStore(DB_URL, schema=SCHEMA))
    tsvc.provision(victim, "Purge Victim")
    b = _bundle()
    h = bundle_content_hash(b)
    S.decisions.decide(company_id=victim, workflow="refund",
                       facts={"plan_type": "annual", "days_since_purchase": 9},
                       actor=AGENT, idempotency_key="purge-k1", bundle=b, bundle_hash=h)
    assert len(S.ledger.list(victim)) == 1
    bystander_events_before = len(S.ledger.list(bystander))
    assert bystander_events_before >= 1  # the bystander has real history to protect

    # purge the victim
    deleted = PgTenantStore(DB_URL, schema=SCHEMA).delete_tenant(victim)
    assert deleted is True

    # victim is gone across the board
    assert PgTenantStore(DB_URL, schema=SCHEMA).get_tenant(victim) is None
    assert S.ledger.list(victim) == []

    # bystander is fully intact -- purge was isolated to the victim's stream
    assert len(S.ledger.list(bystander)) == bystander_events_before
    assert S.ledger.verify_chain(bystander) is True

    # deleting an unknown tenant is a clean False, not an error
    assert PgTenantStore(DB_URL, schema=SCHEMA).delete_tenant(victim) is False

    # and the trigger STILL blocks an ordinary delete (purge flag not set)
    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(SCHEMA)))
        try:
            cur.execute("DELETE FROM decision_events WHERE company_id = %s", (bystander,))
            assert False, "ordinary DELETE must still be blocked by the trigger"
        except psycopg.errors.RaiseException:
            pass
        conn.rollback()


TESTS = [
    test_ledger_append_idempotency_chain,
    test_history_mutation_blocked_by_database,
    test_ledger_list_filters,
    test_lifecycle_publish_gate_and_rollback,
    test_escalation_resolution_and_promotion,
    test_case_duplicate_rejected,
    test_persistence_across_reconnect,
    test_onboarding_stores_full_flow,
    test_all_stores_share_one_connection,
    test_delete_tenant_purges_all_data_and_is_isolated,
]


def main() -> int:
    global S
    print(f"schema: {SCHEMA}")
    apply_schema(DB_URL, SCHEMA)
    S = Stack()
    failed = 0
    try:
        for fn in TESTS:
            try:
                fn()
                print(f"PASS {fn.__name__}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    finally:
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(SCHEMA))
                )
            conn.commit()
        print(f"schema {SCHEMA} dropped (no residue)")
    print(f"Results: {len(TESTS) - failed}/{len(TESTS)} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
