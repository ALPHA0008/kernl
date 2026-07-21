"""PostgreSQL implementations of the five V1 storage protocols.

These implement EXACTLY the semantics of the in-memory reference stores
(backend/ledger/store.py, backend/bundle/lifecycle.py, backend/escalation/,
backend/replay/) -- the contract is defined by the shared test suites; an
adapter is not done until backend/tests/test_pg_stores.py passes against a
real database.

Design:
  - psycopg 3, plain SQL, explicit transactions. No ORM, no PostgREST.
  - Full pydantic payloads live verbatim in a JSONB column (the source of
    truth for reconstruction and hash verification); indexed scalar columns
    exist for filtering only.
  - Ledger appends serialize per company via pg_advisory_xact_lock, verify
    the chain head, assign seq, and rely on the unique idempotency constraint
    as the atomic guarantee.
  - History mutation is blocked by a database trigger (schema.sql), not by
    convention.
  - One connection per store instance, guarded by a lock, reconnect-on-close.
    Correctness first; pooling is a later, measured optimization.

Connection string: KERNL_DB_URL (postgresql://...). For Supabase this is the
DIRECT connection string (Dashboard -> Settings -> Database), not the API URL.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from typing import Any, Optional

import psycopg
from psycopg import conninfo as _conninfo_mod
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.bundle.lifecycle import BundleRecord, BundleStatus
from backend.bundle.schema import Bundle
from backend.escalation.service import Escalation, EscalationStatus
from backend.ledger.events import ChainConflict, DecisionEvent
from backend.onboarding.drafts import OnboardingDraft
from backend.onboarding.sources import SourceSnapshot
from backend.onboarding.tenants import ApiKeyRecord, Tenant
from backend.replay.cases import GoldenCase
from backend.replay.engine import ReplayRun

# Fail a connection attempt fast instead of letting a request hang, and keep
# idle connections alive through NAT/pooler timeouts.
_CONNECT_DEFAULTS = {
    "connect_timeout": "10",
    "keepalives": "1",
    "keepalives_idle": "30",
    "keepalives_interval": "10",
    "keepalives_count": "5",
}


def _resolve_hostaddr(conninfo: str, *, attempts: int = 5) -> str:
    """Resolve the host to an IP ONCE and pin it via `hostaddr`, so per-request
    DNS never happens (some networks resolve Supabase's pooler intermittently).
    The hostname is kept for TLS SNI / cert validation. Adds sane connect and
    keepalive timeouts. Best-effort: if resolution fails, returns the original
    conninfo unchanged so libpq can try its own resolution."""
    try:
        params = _conninfo_mod.conninfo_to_dict(conninfo)
    except Exception:
        return conninfo
    host = params.get("host")
    if not host or params.get("hostaddr"):
        return conninfo  # nothing to resolve, or already pinned

    port = int(params.get("port") or 5432)
    last_exc: Optional[Exception] = None
    for i in range(attempts):
        try:
            infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
            # prefer IPv4 (this machine has no IPv6 route to Supabase)
            ipv4 = [ai[4][0] for ai in infos if ai[0] == socket.AF_INET]
            addr = ipv4[0] if ipv4 else infos[0][4][0]
            params["hostaddr"] = addr
            for k, v in _CONNECT_DEFAULTS.items():
                params.setdefault(k, v)
            return _conninfo_mod.make_conninfo(**params)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(0.5 * (i + 1))
    raise RuntimeError(
        f"could not resolve database host {host!r} after {attempts} attempts: {last_exc}"
    )


class SharedPgConn:
    """One physical connection + one lock, shared by every store in a container.

    Why one connection, not a pool: the arc (Part 11) makes the ledger
    single-writer-per-org on purpose -- "linearizability trivial", and the
    honest load math (~115 decisions/sec sustained across ALL tenants) never
    justifies more. What DID bite in practice is the opposite failure: eight
    separate _Pg stores each opened their OWN connection, so one container
    held 8 connections against Supabase's session-pooler cap of 15 -- a real
    EMAXCONNSESSION outage under light concurrent load. Collapsing all stores
    onto ONE guarded connection fixes that at the root: a container is now a
    single-connection client, exactly matching the single-writer design, and
    a handful of containers fit comfortably under any pooler cap.

    Every store operation still runs in its own lock-guarded transaction; no
    logical operation spans two stores (verified), so sharing is safe and
    changes no observable semantics -- it only removes redundant sockets."""

    def __init__(self, conninfo: str, schema: str = "public") -> None:
        # Resolve + pin the host address once at construction (with retries),
        # so later reconnects never depend on flaky DNS.
        self._conninfo = _resolve_hostaddr(conninfo)
        self._schema = schema
        self.lock = threading.Lock()
        self._conn: Optional[psycopg.Connection] = None

    def connection(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self._conninfo, row_factory=dict_row)
            with self._conn.cursor() as cur:
                cur.execute(
                    sql.SQL("SET search_path TO {}").format(sql.Identifier(self._schema))
                )
            self._conn.commit()
        return self._conn

    def close(self) -> None:
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
        self._conn = None


class _Pg:
    """Base for the Postgres store adapters. Each holds a reference to a
    SharedPgConn; every public operation runs in its own transaction.

    Backward compatible: constructing a store with a conninfo string still
    works (it builds a private SharedPgConn), so existing tests that create a
    lone store are unaffected. In a real container, pass a single shared
    SharedPgConn to every store (see backend/v1_container.py) so the whole
    process uses ONE database connection."""

    def __init__(
        self,
        conninfo: str | None = None,
        schema: str = "public",
        *,
        shared: Optional[SharedPgConn] = None,
    ) -> None:
        if shared is None:
            if conninfo is None:
                raise ValueError("_Pg needs either a conninfo or a shared connection")
            shared = SharedPgConn(conninfo, schema)
        self._shared = shared

    @property
    def _lock(self) -> threading.Lock:
        return self._shared.lock

    def _connection(self) -> psycopg.Connection:
        return self._shared.connection()

    def _tx(self):
        """Context manager: lock + connection + commit/rollback."""
        outer = self

        class _Tx:
            def __enter__(self):
                outer._lock.acquire()
                self.conn = outer._connection()
                return self.conn

            def __exit__(self, exc_type, exc, tb):
                try:
                    if exc_type is None:
                        self.conn.commit()
                    else:
                        self.conn.rollback()
                finally:
                    outer._lock.release()
                return False

        return _Tx()


def _event_from_row(row: dict[str, Any]) -> DecisionEvent:
    return DecisionEvent.model_validate(row["event_json"])


class PgLedgerStore(_Pg):
    def append(self, event: DecisionEvent) -> tuple[DecisionEvent, bool]:
        if not event.verify():
            raise ValueError("refusing to append an unsealed or tampered event")
        with self._tx() as conn:
            with conn.cursor() as cur:
                # serialize the company stream
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))", (event.company_id,)
                )
                cur.execute(
                    "SELECT event_json FROM decision_events "
                    "WHERE company_id = %s AND idempotency_key = %s",
                    (event.company_id, event.idempotency_key),
                )
                existing = cur.fetchone()
                if existing is not None:
                    return DecisionEvent.model_validate(existing["event_json"]), False
                cur.execute(
                    "SELECT event_hash, seq FROM decision_events "
                    "WHERE company_id = %s ORDER BY seq DESC LIMIT 1",
                    (event.company_id,),
                )
                head = cur.fetchone()
                expected_prev = head["event_hash"] if head else None
                next_seq = (head["seq"] + 1) if head else 0
                if event.prev_event_hash != expected_prev:
                    raise ChainConflict(
                        "chain break: prev_event_hash does not match stream head"
                    )
                cur.execute(
                    "INSERT INTO decision_events (event_id, event_type, company_id,"
                    " workflow, idempotency_key, bundle_hash, outcome_kind,"
                    " linked_event_id, created_at, seq, prev_event_hash, event_hash,"
                    " event_json)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        event.event_id,
                        event.event_type.value,
                        event.company_id,
                        event.workflow,
                        event.idempotency_key,
                        event.bundle_hash,
                        str(event.outcome.get("kind")),
                        event.linked_event_id,
                        event.created_at,
                        next_seq,
                        event.prev_event_hash,
                        event.event_hash,
                        Jsonb(json.loads(event.model_dump_json())),
                    ),
                )
                return event, True

    def get(self, company_id: str, event_id: str) -> Optional[DecisionEvent]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT event_json FROM decision_events "
                "WHERE company_id = %s AND event_id = %s",
                (company_id, event_id),
            )
            row = cur.fetchone()
            return _event_from_row(row) if row else None

    def by_idempotency_key(
        self, company_id: str, idempotency_key: str
    ) -> Optional[DecisionEvent]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT event_json FROM decision_events "
                "WHERE company_id = %s AND idempotency_key = %s",
                (company_id, idempotency_key),
            )
            row = cur.fetchone()
            return _event_from_row(row) if row else None

    def list(
        self,
        company_id: str,
        workflow: Optional[str] = None,
        outcome_kind: Optional[str] = None,
        bundle_hash: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DecisionEvent]:
        q = ["SELECT event_json FROM decision_events WHERE company_id = %s"]
        params: list[Any] = [company_id]
        if workflow is not None:
            q.append("AND workflow = %s")
            params.append(workflow)
        if outcome_kind is not None:
            q.append("AND outcome_kind = %s")
            params.append(outcome_kind)
        if bundle_hash is not None:
            q.append("AND bundle_hash = %s")
            params.append(bundle_hash)
        if since is not None:
            q.append("AND created_at >= %s")
            params.append(since)
        if until is not None:
            q.append("AND created_at <= %s")
            params.append(until)
        q.append("ORDER BY seq DESC LIMIT %s OFFSET %s")
        params.extend([limit, offset])
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(" ".join(q), params)
            return [_event_from_row(r) for r in cur.fetchall()]

    def chain_head(self, company_id: str) -> Optional[str]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT event_hash FROM decision_events "
                "WHERE company_id = %s ORDER BY seq DESC LIMIT 1",
                (company_id,),
            )
            row = cur.fetchone()
            return row["event_hash"] if row else None

    def verify_chain(self, company_id: str) -> bool:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT event_json FROM decision_events "
                "WHERE company_id = %s ORDER BY seq ASC",
                (company_id,),
            )
            prev: Optional[str] = None
            for row in cur.fetchall():
                event = _event_from_row(row)
                if not event.verify() or event.prev_event_hash != prev:
                    return False
                prev = event.event_hash
            return True


class PgBundleStore(_Pg):
    def add(self, record: BundleRecord) -> BundleRecord:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO policy_bundles (record_id, company_id, content_hash,"
                " status, bundle_json, created_at, created_by, published_at,"
                " published_by, replay_run_id, signature, signing_pubkey,"
                " signature_scheme)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    record.record_id,
                    record.company_id,
                    record.content_hash,
                    record.status.value,
                    Jsonb(json.loads(record.bundle.model_dump_json())),
                    record.created_at,
                    record.created_by,
                    record.published_at,
                    record.published_by,
                    record.replay_run_id,
                    record.signature,
                    record.signing_pubkey,
                    record.signature_scheme,
                ),
            )
            return record

    def _from_row(self, row: dict[str, Any]) -> BundleRecord:
        return BundleRecord(
            record_id=str(row["record_id"]),
            company_id=row["company_id"],
            content_hash=row["content_hash"],
            status=BundleStatus(row["status"]),
            bundle=Bundle.model_validate(row["bundle_json"]),
            created_at=row["created_at"].isoformat(),
            created_by=row["created_by"],
            published_at=row["published_at"].isoformat() if row["published_at"] else None,
            published_by=row["published_by"],
            replay_run_id=str(row["replay_run_id"]) if row["replay_run_id"] else None,
            signature=row.get("signature"),
            signing_pubkey=row.get("signing_pubkey"),
            signature_scheme=row.get("signature_scheme"),
        )

    _COLS = ("record_id, company_id, content_hash, status, bundle_json, created_at,"
             " created_by, published_at, published_by, replay_run_id,"
             " signature, signing_pubkey, signature_scheme")

    def get(self, company_id: str, record_id: str) -> Optional[BundleRecord]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._COLS} FROM policy_bundles "
                "WHERE company_id = %s AND record_id = %s",
                (company_id, record_id),
            )
            row = cur.fetchone()
            return self._from_row(row) if row else None

    def by_hash(self, company_id: str, content_hash: str) -> Optional[BundleRecord]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._COLS} FROM policy_bundles "
                "WHERE company_id = %s AND content_hash = %s",
                (company_id, content_hash),
            )
            row = cur.fetchone()
            return self._from_row(row) if row else None

    def active(self, company_id: str) -> Optional[BundleRecord]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._COLS} FROM policy_bundles b "
                "WHERE b.company_id = %s AND b.record_id ="
                " (SELECT record_id FROM active_bundles WHERE company_id = %s)",
                (company_id, company_id),
            )
            row = cur.fetchone()
            return self._from_row(row) if row else None

    def set_active(self, company_id: str, record_id: str) -> BundleRecord:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO active_bundles (company_id, record_id, updated_at)"
                " VALUES (%s, %s, now())"
                " ON CONFLICT (company_id) DO UPDATE"
                " SET record_id = EXCLUDED.record_id, updated_at = now()",
                (company_id, record_id),
            )
        record = self.get(company_id, record_id)
        assert record is not None
        return record

    def update(self, record: BundleRecord) -> BundleRecord:
        # bundle content is immutable; only lifecycle metadata (incl. the
        # signature stamped at publish) may change
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE policy_bundles SET status = %s, published_at = %s,"
                " published_by = %s, replay_run_id = %s, signature = %s,"
                " signing_pubkey = %s, signature_scheme = %s"
                " WHERE company_id = %s AND record_id = %s",
                (
                    record.status.value,
                    record.published_at,
                    record.published_by,
                    record.replay_run_id,
                    record.signature,
                    record.signing_pubkey,
                    record.signature_scheme,
                    record.company_id,
                    record.record_id,
                ),
            )
            return record

    def list(self, company_id: str) -> list[BundleRecord]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._COLS} FROM policy_bundles "
                "WHERE company_id = %s ORDER BY created_at DESC",
                (company_id,),
            )
            return [self._from_row(r) for r in cur.fetchall()]


class PgEscalationStore(_Pg):
    def add(self, esc: Escalation) -> Escalation:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO escalations (escalation_id, company_id, workflow,"
                " decision_event_id, reason, detail_json, status, created_at,"
                " resolution_json)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                " ON CONFLICT (company_id, decision_event_id) DO NOTHING",
                (
                    esc.escalation_id,
                    esc.company_id,
                    esc.workflow,
                    esc.decision_event_id,
                    esc.reason.value,
                    Jsonb(esc.detail),
                    esc.status.value,
                    esc.created_at,
                    None,
                ),
            )
            if cur.rowcount == 0:  # exactly one escalation per decision
                existing = self._by_decision(cur, esc.company_id, esc.decision_event_id)
                assert existing is not None
                return existing
            return esc

    @staticmethod
    def _row_to_esc(row: dict[str, Any]) -> Escalation:
        return Escalation.model_validate(
            {
                "escalation_id": str(row["escalation_id"]),
                "company_id": row["company_id"],
                "workflow": row["workflow"],
                "decision_event_id": str(row["decision_event_id"]),
                "reason": row["reason"],
                "detail": row["detail_json"],
                "status": row["status"],
                "created_at": row["created_at"].isoformat(),
                "resolution": row["resolution_json"],
            }
        )

    _COLS = ("escalation_id, company_id, workflow, decision_event_id, reason,"
             " detail_json, status, created_at, resolution_json")

    def get(self, company_id: str, escalation_id: str) -> Optional[Escalation]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._COLS} FROM escalations "
                "WHERE company_id = %s AND escalation_id = %s",
                (company_id, escalation_id),
            )
            row = cur.fetchone()
            return self._row_to_esc(row) if row else None

    def update(self, esc: Escalation) -> Escalation:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE escalations SET status = %s, resolution_json = %s"
                " WHERE company_id = %s AND escalation_id = %s",
                (
                    esc.status.value,
                    Jsonb(json.loads(esc.resolution.model_dump_json()))
                    if esc.resolution
                    else None,
                    esc.company_id,
                    esc.escalation_id,
                ),
            )
            return esc

    def list(
        self,
        company_id: str,
        status: Optional[EscalationStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Escalation]:
        q = [f"SELECT {self._COLS} FROM escalations WHERE company_id = %s"]
        params: list[Any] = [company_id]
        if status is not None:
            q.append("AND status = %s")
            params.append(status.value)
        q.append("ORDER BY created_at DESC LIMIT %s OFFSET %s")
        params.extend([limit, offset])
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(" ".join(q), params)
            return [self._row_to_esc(r) for r in cur.fetchall()]

    def by_decision(self, company_id: str, decision_event_id: str) -> Optional[Escalation]:
        with self._tx() as conn, conn.cursor() as cur:
            return self._by_decision(cur, company_id, decision_event_id)

    @classmethod
    def _by_decision(cls, cur, company_id: str, decision_event_id: str) -> Optional[Escalation]:
        cur.execute(
            f"SELECT {cls._COLS} FROM escalations "
            "WHERE company_id = %s AND decision_event_id = %s",
            (company_id, decision_event_id),
        )
        row = cur.fetchone()
        return cls._row_to_esc(row) if row else None


class PgCaseStore(_Pg):
    def add(self, case: GoldenCase) -> GoldenCase:
        with self._tx() as conn, conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO golden_cases (case_id, company_id, workflow,"
                    " facts_json, expected_json, provenance, synthetic, notes)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        case.case_id,
                        case.company_id,
                        case.workflow,
                        Jsonb(case.facts),
                        Jsonb(json.loads(case.expected.model_dump_json())),
                        case.provenance,
                        case.synthetic,
                        case.notes,
                    ),
                )
            except psycopg.errors.UniqueViolation as exc:
                raise ValueError(f"duplicate case id {case.case_id!r}") from exc
            return case

    def list(self, company_id: str, workflow: Optional[str] = None) -> list[GoldenCase]:
        q = ["SELECT case_id, company_id, workflow, facts_json, expected_json,"
             " provenance, synthetic, notes FROM golden_cases WHERE company_id = %s"]
        params: list[Any] = [company_id]
        if workflow is not None:
            q.append("AND workflow = %s")
            params.append(workflow)
        q.append("ORDER BY case_id ASC")
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(" ".join(q), params)
            return [
                GoldenCase.model_validate(
                    {
                        "case_id": r["case_id"],
                        "company_id": r["company_id"],
                        "workflow": r["workflow"],
                        "facts": r["facts_json"],
                        "expected": r["expected_json"],
                        "provenance": r["provenance"],
                        "synthetic": r["synthetic"],
                        "notes": r["notes"],
                    }
                )
                for r in cur.fetchall()
            ]


class PgReplayRunStore(_Pg):
    def add(self, run: ReplayRun) -> ReplayRun:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO replay_runs (run_id, company_id, candidate_bundle_hash,"
                " reference_bundle_hash, case_set_hash, created_at, summary_json,"
                " results_json, acknowledged_by, acknowledged_at)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    run.run_id,
                    run.company_id,
                    run.candidate_bundle_hash,
                    run.reference_bundle_hash,
                    run.case_set_hash,
                    run.created_at,
                    Jsonb(json.loads(run.summary.model_dump_json())),
                    Jsonb([json.loads(r.model_dump_json()) for r in run.results]),
                    run.acknowledged_by,
                    run.acknowledged_at,
                ),
            )
            return run

    @staticmethod
    def _from_row(row: dict[str, Any]) -> ReplayRun:
        return ReplayRun.model_validate(
            {
                "run_id": str(row["run_id"]),
                "company_id": row["company_id"],
                "candidate_bundle_hash": row["candidate_bundle_hash"],
                "reference_bundle_hash": row["reference_bundle_hash"],
                "case_set_hash": row["case_set_hash"],
                "created_at": row["created_at"].isoformat(),
                "summary": row["summary_json"],
                "results": row["results_json"],
                "acknowledged_by": row["acknowledged_by"],
                "acknowledged_at": row["acknowledged_at"].isoformat()
                if row["acknowledged_at"]
                else None,
            }
        )

    _COLS = ("run_id, company_id, candidate_bundle_hash, reference_bundle_hash,"
             " case_set_hash, created_at, summary_json, results_json,"
             " acknowledged_by, acknowledged_at")

    def get(self, company_id: str, run_id: str) -> Optional[ReplayRun]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._COLS} FROM replay_runs "
                "WHERE company_id = %s AND run_id = %s",
                (company_id, run_id),
            )
            row = cur.fetchone()
            return self._from_row(row) if row else None

    def update(self, run: ReplayRun) -> ReplayRun:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE replay_runs SET acknowledged_by = %s, acknowledged_at = %s"
                " WHERE company_id = %s AND run_id = %s",
                (run.acknowledged_by, run.acknowledged_at, run.company_id, run.run_id),
            )
            return run

    def latest_acknowledged_for(
        self, company_id: str, candidate_bundle_hash: str
    ) -> Optional[ReplayRun]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._COLS} FROM replay_runs"
                " WHERE company_id = %s AND candidate_bundle_hash = %s"
                " AND acknowledged_by IS NOT NULL"
                " ORDER BY created_at DESC LIMIT 1",
                (company_id, candidate_bundle_hash),
            )
            row = cur.fetchone()
            return self._from_row(row) if row else None

    def list(self, company_id: str, limit: int = 50) -> list[ReplayRun]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._COLS} FROM replay_runs "
                "WHERE company_id = %s ORDER BY created_at DESC LIMIT %s",
                (company_id, limit),
            )
            return [self._from_row(r) for r in cur.fetchall()]


# --------------------------------------------------------------- onboarding


class PgTenantStore(_Pg):
    def add_tenant(self, tenant: Tenant) -> Tenant:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM companies WHERE id = %s", (tenant.company_id,))
            if cur.fetchone() is not None:
                raise ValueError(f"tenant {tenant.company_id!r} already exists")
            cur.execute(
                "INSERT INTO companies (id, name, created_at) VALUES (%s, %s, now())",
                (tenant.company_id, tenant.name),
            )
            cur.execute(
                "SELECT id, name, created_at FROM companies WHERE id = %s",
                (tenant.company_id,),
            )
            r = cur.fetchone()
            return Tenant(
                company_id=r["id"], name=r["name"], created_at=r["created_at"].isoformat()
            )

    def get_tenant(self, company_id: str) -> Optional[Tenant]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, created_at FROM companies WHERE id = %s", (company_id,)
            )
            r = cur.fetchone()
            if r is None:
                return None
            return Tenant(
                company_id=r["id"], name=r["name"], created_at=r["created_at"].isoformat()
            )

    def list_tenants(self) -> list[Tenant]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, name, created_at FROM companies ORDER BY created_at")
            return [
                Tenant(company_id=r["id"], name=r["name"], created_at=r["created_at"].isoformat())
                for r in cur.fetchall()
            ]

    def add_key(self, record: ApiKeyRecord) -> ApiKeyRecord:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO api_keys (key_id, key_hash, company_id, role, created_at)"
                " VALUES (%s, %s, %s, %s, now())",
                (record.key_id, record.key_hash, record.company_id, record.role),
            )
            cur.execute(
                "SELECT key_id, key_hash, company_id, role, created_at, revoked_at"
                " FROM api_keys WHERE key_id = %s",
                (record.key_id,),
            )
            return _key_from_row(cur.fetchone())

    def find_by_hash(self, key_hash: str) -> Optional[ApiKeyRecord]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT key_id, key_hash, company_id, role, created_at, revoked_at"
                " FROM api_keys WHERE key_hash = %s AND revoked_at IS NULL",
                (key_hash,),
            )
            r = cur.fetchone()
            return _key_from_row(r) if r else None

    def list_keys(self, company_id: str) -> list[ApiKeyRecord]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT key_id, key_hash, company_id, role, created_at, revoked_at"
                " FROM api_keys WHERE company_id = %s ORDER BY created_at",
                (company_id,),
            )
            return [_key_from_row(r) for r in cur.fetchall()]

    def get_key(self, company_id: str, key_id: str) -> Optional[ApiKeyRecord]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT key_id, key_hash, company_id, role, created_at, revoked_at"
                " FROM api_keys WHERE company_id = %s AND key_id = %s",
                (company_id, key_id),
            )
            r = cur.fetchone()
            return _key_from_row(r) if r else None

    def revoke_key(self, company_id: str, key_id: str) -> Optional[ApiKeyRecord]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE api_keys SET revoked_at = COALESCE(revoked_at, now())"
                " WHERE company_id = %s AND key_id = %s"
                " RETURNING key_id, key_hash, company_id, role, created_at, revoked_at",
                (company_id, key_id),
            )
            r = cur.fetchone()
            return _key_from_row(r) if r else None

    def delete_tenant(self, company_id: str) -> bool:
        """Purge the tenant and ALL its data across every V1 table, as one
        transaction. The whole-stream removal is sanctioned by the retention
        policy (discard the entire logbook), so the append-only trigger is
        told, for THIS transaction only, that this specific tenant is being
        purged (see forbid_history_mutation in schema.sql). Order respects FKs:
        dependents before the rows they reference; companies last."""
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM companies WHERE id = %s", (company_id,))
            if cur.fetchone() is None:
                return False
            # authorize the ledger purge for this tenant, transaction-scoped
            cur.execute(
                "SELECT set_config('kernl.purging_tenant', %s, true)", (company_id,)
            )
            # dependents first (respect FKs), then the anchors
            cur.execute("DELETE FROM active_bundles WHERE company_id = %s", (company_id,))
            cur.execute("DELETE FROM escalations WHERE company_id = %s", (company_id,))
            cur.execute("DELETE FROM decision_events WHERE company_id = %s", (company_id,))
            cur.execute("DELETE FROM replay_runs WHERE company_id = %s", (company_id,))
            cur.execute("DELETE FROM golden_cases WHERE company_id = %s", (company_id,))
            cur.execute("DELETE FROM policy_bundles WHERE company_id = %s", (company_id,))
            cur.execute("DELETE FROM onboarding_drafts WHERE company_id = %s", (company_id,))
            cur.execute("DELETE FROM source_snapshots WHERE company_id = %s", (company_id,))
            cur.execute("DELETE FROM api_keys WHERE company_id = %s", (company_id,))
            # legacy tables that FK to companies(id) -- clear so the parent delete
            # is not blocked if any residual rows exist
            for legacy in (
                "skills_files", "skills", "source_files", "compile_runs",
                "operational_entities", "relationship_edges",
            ):
                cur.execute(
                    sql.SQL("DELETE FROM {} WHERE company_id = %s").format(
                        sql.Identifier(legacy)
                    ),
                    (company_id,),
                )
            cur.execute("DELETE FROM companies WHERE id = %s", (company_id,))
            return True


def _key_from_row(r: dict[str, Any]) -> ApiKeyRecord:
    return ApiKeyRecord(
        key_id=r["key_id"],
        key_hash=r["key_hash"],
        company_id=r["company_id"],
        role=r["role"],
        created_at=r["created_at"].isoformat() if r["created_at"] else "",
        revoked_at=r["revoked_at"].isoformat() if r["revoked_at"] else None,
    )


class PgSourceStore(_Pg):
    def add(self, snapshot: SourceSnapshot) -> SourceSnapshot:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT source_id FROM source_snapshots"
                " WHERE company_id = %s AND source_id = %s",
                (snapshot.company_id, snapshot.source_id),
            )
            if cur.fetchone() is not None:
                return self.get(snapshot.company_id, snapshot.source_id)  # type: ignore[return-value]
            cur.execute(
                "INSERT INTO source_snapshots (source_id, company_id, filename,"
                " content_hash, content, byte_length, created_at)"
                " VALUES (%s, %s, %s, %s, %s, %s, now())",
                (
                    snapshot.source_id,
                    snapshot.company_id,
                    snapshot.filename,
                    snapshot.content_hash,
                    snapshot.content,
                    snapshot.byte_length,
                ),
            )
        return self.get(snapshot.company_id, snapshot.source_id)  # type: ignore[return-value]

    def get(self, company_id: str, source_id: str) -> Optional[SourceSnapshot]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM source_snapshots WHERE company_id = %s AND source_id = %s",
                (company_id, source_id),
            )
            r = cur.fetchone()
            return _snapshot_from_row(r) if r else None

    def list(self, company_id: str) -> list[SourceSnapshot]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM source_snapshots WHERE company_id = %s"
                " ORDER BY created_at DESC",
                (company_id,),
            )
            return [_snapshot_from_row(r) for r in cur.fetchall()]


def _snapshot_from_row(r: dict[str, Any]) -> SourceSnapshot:
    return SourceSnapshot(
        source_id=r["source_id"],
        company_id=r["company_id"],
        filename=r["filename"],
        content_hash=r["content_hash"],
        content=r["content"],
        byte_length=r["byte_length"],
        created_at=r["created_at"].isoformat() if r["created_at"] else "",
    )


class PgDraftStore(_Pg):
    def upsert(self, draft: OnboardingDraft) -> OnboardingDraft:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO onboarding_drafts (draft_id, company_id, proposed_json,"
                " evidence_json, origin, source_skill_id, status, publishable,"
                " issues_json, created_at, updated_at)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                " COALESCE(%s::timestamptz, now()), now())"
                " ON CONFLICT (company_id, draft_id) DO UPDATE SET"
                " proposed_json = EXCLUDED.proposed_json,"
                " evidence_json = EXCLUDED.evidence_json,"
                " origin = EXCLUDED.origin,"
                " source_skill_id = EXCLUDED.source_skill_id,"
                " status = EXCLUDED.status,"
                " publishable = EXCLUDED.publishable,"
                " issues_json = EXCLUDED.issues_json,"
                " updated_at = now()",
                (
                    draft.draft_id,
                    draft.company_id,
                    Jsonb(draft.proposed_json),
                    Jsonb(list(draft.evidence_json)),
                    draft.origin,
                    draft.source_skill_id,
                    draft.status,
                    draft.publishable,
                    Jsonb(list(draft.issues_json)),
                    draft.created_at or None,
                ),
            )
        return self.get(draft.company_id, draft.draft_id)  # type: ignore[return-value]

    def get(self, company_id: str, draft_id: str) -> Optional[OnboardingDraft]:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM onboarding_drafts WHERE company_id = %s AND draft_id = %s",
                (company_id, draft_id),
            )
            r = cur.fetchone()
            return _draft_from_row(r) if r else None

    def list(self, company_id: str, status: Optional[str] = None) -> list[OnboardingDraft]:
        with self._tx() as conn, conn.cursor() as cur:
            if status is None:
                cur.execute(
                    "SELECT * FROM onboarding_drafts WHERE company_id = %s"
                    " ORDER BY updated_at DESC",
                    (company_id,),
                )
            else:
                cur.execute(
                    "SELECT * FROM onboarding_drafts WHERE company_id = %s AND status = %s"
                    " ORDER BY updated_at DESC",
                    (company_id, status),
                )
            return [_draft_from_row(r) for r in cur.fetchall()]

    def delete(self, company_id: str, draft_id: str) -> None:
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM onboarding_drafts WHERE company_id = %s AND draft_id = %s",
                (company_id, draft_id),
            )


def _draft_from_row(r: dict[str, Any]) -> OnboardingDraft:
    return OnboardingDraft(
        draft_id=r["draft_id"],
        company_id=r["company_id"],
        proposed_json=r["proposed_json"],
        evidence_json=tuple(r["evidence_json"] or ()),
        origin=r["origin"],
        source_skill_id=r["source_skill_id"],
        status=r["status"],
        publishable=r["publishable"],
        issues_json=tuple(r["issues_json"] or ()),
        created_at=r["created_at"].isoformat() if r["created_at"] else "",
        updated_at=r["updated_at"].isoformat() if r["updated_at"] else "",
    )
