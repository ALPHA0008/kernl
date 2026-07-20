"""V1 service container: wires stores + services and owns the seed bootstrap.

The in-memory stores are the tested reference implementations of the storage
protocols (see backend/tests/*). Production persistence swaps Supabase-backed
implementations of the same protocols into this container -- an infrastructure
change that touches no API or service code (tables: backend/schema.sql).

Seed bootstrap (KERNL_SEED_RIVANLY=1): registers the authored rivanly-inc
reference bundle [synthetic] and its golden cases, then walks it through the
REAL publish gate -- draft -> replay vs golden set -> acknowledge -> publish.
No backdoor: if the seed ever fails its own golden set, the process refuses
to serve it.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

from backend.bundle.lifecycle import BundleLifecycle, BundleStore, InMemoryBundleStore
from backend.escalation.service import (
    Escalation,
    EscalationService,
    EscalationStore,
    InMemoryEscalationStore,
    Resolution,
)
from backend.ledger.events import DecisionEvent
from backend.ledger.service import DecisionService
from backend.ledger.store import InMemoryLedgerStore, LedgerStore
from backend.onboarding.drafts import DraftStore, InMemoryDraftStore
from backend.onboarding.service import OnboardingService
from backend.onboarding.sources import InMemorySourceStore, SourceStore
from backend.onboarding.tenants import (
    InMemoryTenantStore,
    TenantService,
    TenantStore,
)
from backend.replay.cases import CaseStore, Expected, GoldenCase, InMemoryCaseStore
from backend.replay.engine import InMemoryReplayRunStore, ReplayEngine, ReplayRunStore

SEED_ENV = "KERNL_SEED_RIVANLY"
SEED_HIGGSFIELD_ENV = "KERNL_SEED_HIGGSFIELD"


class Container:
    def __init__(
        self,
        ledger: Optional[LedgerStore] = None,
        bundles: Optional[BundleStore] = None,
        escalation_store: Optional[EscalationStore] = None,
        cases: Optional[CaseStore] = None,
        replay_runs: Optional[ReplayRunStore] = None,
        tenants: Optional[TenantStore] = None,
        sources: Optional[SourceStore] = None,
        drafts: Optional[DraftStore] = None,
    ) -> None:
        self.ledger: LedgerStore = ledger or InMemoryLedgerStore()
        self.bundles: BundleStore = bundles or InMemoryBundleStore()
        self.escalation_store: EscalationStore = escalation_store or InMemoryEscalationStore()
        self.cases: CaseStore = cases or InMemoryCaseStore()
        self.replay_runs: ReplayRunStore = replay_runs or InMemoryReplayRunStore()
        self.tenant_store: TenantStore = tenants or InMemoryTenantStore()
        self.source_store: SourceStore = sources or InMemorySourceStore()
        self.draft_store: DraftStore = drafts or InMemoryDraftStore()

        self.decisions = DecisionService(self.ledger)
        self.replay = ReplayEngine(self.replay_runs)
        self.lifecycle = BundleLifecycle(self.bundles, self.replay_runs)
        self.escalations = EscalationService(
            self.escalation_store, self.decisions, self._promote_golden
        )
        self.tenants = TenantService(self.tenant_store)
        self.onboarding = OnboardingService(
            self.tenants, self.source_store, self.draft_store
        )

    # promoted adjudications become golden cases with full provenance
    def _promote_golden(self, event: DecisionEvent, resolution: Resolution) -> None:
        self.cases.add(
            GoldenCase(
                case_id=f"adj-{event.event_id[:8]}",
                company_id=event.company_id,
                workflow=event.workflow,
                facts=event.facts,
                expected=Expected(
                    kind=resolution.outcome_kind, action=resolution.chosen_action
                ),
                provenance=f"adjudication:{resolution.adjudication_event_id}",
                synthetic=False,
            )
        )

    def escalations_by_decision(self, company_id: str, decision_event_id: str) -> Optional[Escalation]:
        return self.escalation_store.by_decision(company_id, decision_event_id)

    def delete_tenant(self, company_id: str) -> bool:
        """Purge a tenant and all its data. Returns False if the tenant is
        unknown. Whole-tenant removal is sanctioned by the retention policy
        (discard the entire logbook, not tear out a page) -- see
        docs/RETENTION_POLICY.md and the append-only trigger in schema.sql.

        Postgres: PgTenantStore.delete_tenant cascades every table in one
        transaction (authoritative). In-memory: the tenant store drops the
        tenant + keys; the other volatile reference stores are best-effort
        purged where they expose a purge hook. In-memory state is dev/test
        only and does not survive a restart, so residual per-tenant rows
        there are not a durability concern."""
        if self.tenant_store.get_tenant(company_id) is None:
            return False
        # Best-effort purge of any reference store that offers a hook (the Pg
        # tenant store already cascaded these; in-memory stores may not).
        for store in (
            self.ledger, self.bundles, self.escalation_store, self.cases,
            self.replay_runs, self.source_store, self.draft_store,
        ):
            purge = getattr(store, "purge_company", None)
            if callable(purge):
                purge(company_id)
        return self.tenant_store.delete_tenant(company_id)

    def seed_rivanly(self) -> None:
        """Idempotent: registers + publishes the reference bundle through the
        real replay gate. Raises if the seed fails its own golden set."""
        from backend.bundle.seed_rivanly import COMPANY_ID, build_bundle, build_golden_cases

        self._seed_reference_bundle(COMPANY_ID, build_bundle, build_golden_cases)

    def seed_higgsfield(self) -> None:
        """Idempotent: registers + publishes the second reference bundle
        [synthetic] the same way seed_rivanly does. Raises if the seed fails
        its own golden set."""
        from backend.bundle.seed_higgsfield import COMPANY_ID, build_bundle, build_golden_cases

        self._seed_reference_bundle(COMPANY_ID, build_bundle, build_golden_cases)

    def _seed_reference_bundle(self, company_id, build_bundle, build_golden_cases) -> None:
        """Case-seeding and bundle-publishing are deliberately decoupled: new
        golden cases (grown, e.g., by re-running this codebase's own seed
        module after adding cases) are additive corpus data, not history --
        adding one after the bundle is already published doesn't touch the
        immutable bundle at all, so it's always safe to attempt. Publishing
        is still idempotent-by-early-return: never re-publish an already
        active bundle."""
        for case in build_golden_cases():
            try:
                self.cases.add(case)
            except ValueError:
                pass  # already seeded
        if self.lifecycle.active_bundle(company_id) is not None:
            return
        bundle = build_bundle()
        draft = self.lifecycle.save_draft(company_id, bundle, created_by="seed")
        run = self.replay.run(
            company_id=company_id, cases=self.cases.list(company_id), candidate=bundle
        )
        if run.summary.golden_failed or run.summary.errors:
            raise RuntimeError(
                f"seed bundle for {company_id!r} fails its own golden set "
                f"({run.summary.golden_failed} failed, {run.summary.errors} errors) "
                "-- refusing to publish"
            )
        self.replay.acknowledge(company_id, run.run_id, by="seed")
        self.lifecycle.publish(company_id, draft.record_id, published_by="seed")


_container: Optional[Container] = None
_lock = threading.Lock()


def _build_container() -> Container:
    """Store selection is env-driven:
    KERNL_DB_URL set   -> Postgres adapters (production persistence)
    KERNL_DB_URL unset -> in-memory reference stores (dev/tests; volatile)
    """
    from pathlib import Path

    from dotenv import load_dotenv

    # explicit repo-root .env (backend/.env would shadow it in the walk-up)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    db_url = os.environ.get("KERNL_DB_URL") or os.environ.get("SUPABASE_DB_URL")
    if db_url:
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

        schema = os.environ.get("KERNL_DB_SCHEMA", "public")
        # ONE connection for the whole container -- all eight stores share it.
        # This is the arc's single-writer-per-cell design made literal at the
        # socket level, and it fixes the real EMAXCONNSESSION failure that
        # eight-connections-per-container hit against Supabase's pooler cap.
        shared = SharedPgConn(db_url, schema)
        return Container(
            ledger=PgLedgerStore(shared=shared),
            bundles=PgBundleStore(shared=shared),
            escalation_store=PgEscalationStore(shared=shared),
            cases=PgCaseStore(shared=shared),
            replay_runs=PgReplayRunStore(shared=shared),
            tenants=PgTenantStore(shared=shared),
            sources=PgSourceStore(shared=shared),
            drafts=PgDraftStore(shared=shared),
        )
    return Container()


def get_container() -> Container:
    global _container
    if _container is None:
        with _lock:
            if _container is None:
                c = _build_container()
                if os.environ.get(SEED_ENV, "1") == "1":
                    c.seed_rivanly()
                if os.environ.get(SEED_HIGGSFIELD_ENV, "1") == "1":
                    c.seed_higgsfield()
                _container = c
    return _container


def reset_container() -> None:
    """Test hook: drop the singleton so the next request rebuilds it."""
    global _container
    with _lock:
        _container = None
