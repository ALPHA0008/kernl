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
import threading
from typing import Any, Optional

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.bundle.lifecycle import BundleRecord, BundleStatus
from backend.bundle.schema import Bundle
from backend.escalation.service import Escalation, EscalationStatus
from backend.ledger.events import DecisionEvent
from backend.replay.cases import GoldenCase
from backend.replay.engine import ReplayRun


class _Pg:
    """Shared connection handling: one guarded connection, reconnect on loss,
    every public operation runs in its own transaction."""

    def __init__(self, conninfo: str, schema: str = "public") -> None:
        self._conninfo = conninfo
        self._schema = schema
        self._lock = threading.Lock()
        self._conn: Optional[psycopg.Connection] = None

    def _connection(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self._conninfo, row_factory=dict_row)
            with self._conn.cursor() as cur:
                cur.execute(
                    sql.SQL("SET search_path TO {}").format(sql.Identifier(self._schema))
                )
            self._conn.commit()
        return self._conn

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
                    raise ValueError(
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
                " published_by, replay_run_id)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
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
        )

    _COLS = ("record_id, company_id, content_hash, status, bundle_json, created_at,"
             " created_by, published_at, published_by, replay_run_id")

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
        # bundle content is immutable; only lifecycle metadata may change
        with self._tx() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE policy_bundles SET status = %s, published_at = %s,"
                " published_by = %s, replay_run_id = %s"
                " WHERE company_id = %s AND record_id = %s",
                (
                    record.status.value,
                    record.published_at,
                    record.published_by,
                    record.replay_run_id,
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
