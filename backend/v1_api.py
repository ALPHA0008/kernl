"""Kernl V1 API -- the Decision Ledger surface.

Endpoints (all under /v1, all tenant-scoped by API key):
    POST /v1/decisions/evaluate        evaluate facts -> ledgered decision
    GET  /v1/decisions/{event_id}      full trace (the receipt)
    GET  /v1/ledger                    append-only event browser
    GET  /v1/ledger/verify             hash-chain verification
    GET  /v1/bundles                   bundle registry
    GET  /v1/bundles/active            the live bundle
    POST /v1/bundles/drafts            register a draft bundle
    POST /v1/bundles/{id}/publish      replay-gated publish
    POST /v1/bundles/{id}/activate     rollback/forward pointer move
    POST /v1/replays                   run candidate vs golden set (+reference)
    GET  /v1/replays[/{run_id}]        replay reports
    POST /v1/replays/{run_id}/acknowledge
    GET  /v1/escalations[/{id}]        the inbox
    POST /v1/escalations/{id}/resolve  adjudicate (ledgered)
    GET  /v1/cases                     golden case corpus
    GET  /v1/health

AUTH: X-API-Key header. Keys come from the KERNL_API_KEYS env var:
    KERNL_API_KEYS="<key>:<company_id>:<role>[,<key>:<company_id>:<role>...]"
Roles: owner (everything) | approver (read + resolve) | agent (evaluate/read).
No keys configured => every request is 401 (fail closed, never open).

GUARANTEES surfaced here:
  - Write-ahead: a 200 from /decisions/evaluate means the ledger row exists.
  - 503 on ledger/storage failure -- never a fixture, never a silent fallback.
  - 400 on malformed facts / unknown workflow -- request errors, not decisions.

STORAGE: this process serves the storage container in backend.v1_container;
the in-memory reference stores are the tested contract. The Supabase adapters
(backend/schema.sql tables) implement the same protocols -- swapping them in
is a container change, not an API change.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.bundle.lifecycle import PublishGateError
from backend.bundle.schema import Bundle
from backend.escalation.service import AlreadyResolvedError
from backend.ledger.events import Actor
from backend.ledger.service import LedgerUnavailableError
from backend.runtime.evaluator import InvalidFactsError
from backend.v1_container import Container, get_container

router = APIRouter(prefix="/v1", tags=["v1"])

ROLE_RANK = {"agent": 1, "approver": 2, "owner": 3}


class Principal(BaseModel):
    company_id: str
    role: str
    key_id: str

    def actor(self, actor_type: str = "agent") -> Actor:
        return Actor(type=actor_type, id=self.key_id, api_key_id=self.key_id)


def _parse_keys() -> dict[str, Principal]:
    raw = os.environ.get("KERNL_API_KEYS", "")
    keys: dict[str, Principal] = {}
    for i, entry in enumerate(filter(None, (e.strip() for e in raw.split(",")))):
        parts = entry.split(":")
        if len(parts) != 3 or parts[2] not in ROLE_RANK:
            continue  # malformed entries are ignored, never partially trusted
        key, company, role = parts
        keys[key] = Principal(company_id=company, role=role, key_id=f"key_{i}")
    return keys


def require(min_role: str):
    def dep(x_api_key: Optional[str] = Header(default=None)) -> Principal:
        principal = _parse_keys().get(x_api_key or "")
        if principal is None:
            raise HTTPException(status_code=401, detail="invalid or missing API key")
        if ROLE_RANK[principal.role] < ROLE_RANK[min_role]:
            raise HTTPException(status_code=403, detail=f"requires role >= {min_role}")
        return principal

    return dep


# ---------------------------------------------------------------------------
# request/response models


class EvaluateRequest(BaseModel):
    workflow: str
    facts: dict[str, Any]
    idempotency_key: str = Field(min_length=1, max_length=256)


class ResolveRequest(BaseModel):
    chosen_action: str
    outcome_kind: str
    rationale: str = Field(min_length=1)
    promote_to_golden: bool = False


class DraftRequest(BaseModel):
    bundle: dict[str, Any]  # Bundle JSON; validated by the schema


class ReplayRequest(BaseModel):
    candidate_record_id: str
    include_reference: bool = True


# ---------------------------------------------------------------------------
# decisions + ledger


@router.post("/decisions/evaluate")
def evaluate_decision(
    req: EvaluateRequest,
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    active = c.lifecycle.active_bundle(p.company_id)
    if active is None:
        raise HTTPException(status_code=409, detail="no published bundle for tenant")
    try:
        event, created = c.decisions.decide(
            company_id=p.company_id,
            workflow=req.workflow,
            facts=req.facts,
            actor=p.actor(),
            idempotency_key=req.idempotency_key,
            bundle=active.bundle,
            bundle_hash=active.content_hash,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"unknown workflow: {exc}") from exc
    except InvalidFactsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LedgerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=f"ledger unavailable: {exc}") from exc

    escalation = c.escalations.open_for(event) if created else c.escalations_by_decision(
        p.company_id, event.event_id
    )
    return {
        "decision_id": event.event_id,
        "created": created,
        "outcome": event.outcome,
        "bundle_hash": event.bundle_hash,
        "escalation_id": escalation.escalation_id if escalation else None,
    }


@router.get("/decisions/{event_id}")
def get_decision(
    event_id: str,
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    event = c.ledger.get(p.company_id, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return event.model_dump(mode="json")


@router.get("/ledger")
def list_ledger(
    workflow: Optional[str] = None,
    outcome: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    rows = c.ledger.list(p.company_id, workflow=workflow, outcome_kind=outcome,
                         limit=min(limit, 200), offset=offset)
    return {"events": [e.model_dump(mode="json") for e in rows]}


@router.get("/ledger/verify")
def verify_ledger(
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    return {"chain_valid": c.ledger.verify_chain(p.company_id),
            "chain_head": c.ledger.chain_head(p.company_id)}


# ---------------------------------------------------------------------------
# bundles


@router.get("/bundles")
def list_bundles(
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    return {"bundles": [
        {"record_id": r.record_id, "content_hash": r.content_hash,
         "status": r.status.value, "created_at": r.created_at,
         "published_at": r.published_at, "policy_count": len(r.bundle.policies)}
        for r in c.bundles.list(p.company_id)
    ]}


@router.get("/bundles/active")
def active_bundle(
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    r = c.lifecycle.active_bundle(p.company_id)
    if r is None:
        raise HTTPException(status_code=404, detail="no published bundle")
    return {"record_id": r.record_id, "content_hash": r.content_hash,
            "bundle": r.bundle.model_dump(mode="json")}


@router.post("/bundles/drafts")
def create_draft(
    req: DraftRequest,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    try:
        bundle = Bundle.model_validate({**req.bundle, "company_id": p.company_id})
    except Exception as exc:  # pydantic ValidationError -> 422-style detail
        raise HTTPException(status_code=400, detail=f"invalid bundle: {exc}") from exc
    record = c.lifecycle.save_draft(p.company_id, bundle, created_by=p.key_id)
    return {"record_id": record.record_id, "content_hash": record.content_hash,
            "status": record.status.value}


@router.post("/bundles/{record_id}/publish")
def publish_bundle(
    record_id: str,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    try:
        record = c.lifecycle.publish(p.company_id, record_id, published_by=p.key_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PublishGateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"record_id": record.record_id, "content_hash": record.content_hash,
            "status": record.status.value, "replay_run_id": record.replay_run_id}


@router.post("/bundles/{record_id}/activate")
def activate_bundle(
    record_id: str,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    try:
        record = c.lifecycle.activate(p.company_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PublishGateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"record_id": record.record_id, "content_hash": record.content_hash,
            "status": record.status.value}


# ---------------------------------------------------------------------------
# replay


@router.post("/replays")
def run_replay(
    req: ReplayRequest,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    record = c.bundles.get(p.company_id, req.candidate_record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="unknown bundle record")
    cases = c.cases.list(p.company_id)
    if not cases:
        raise HTTPException(status_code=409, detail="no golden cases for tenant")
    reference = None
    if req.include_reference:
        active = c.lifecycle.active_bundle(p.company_id)
        reference = active.bundle if active else None
    run = c.replay.run(company_id=p.company_id, cases=cases,
                       candidate=record.bundle, reference=reference)
    return run.model_dump(mode="json")


@router.get("/replays")
def list_replays(
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    return {"runs": [
        {"run_id": r.run_id, "candidate_bundle_hash": r.candidate_bundle_hash,
         "created_at": r.created_at, "summary": r.summary.model_dump(),
         "acknowledged_by": r.acknowledged_by}
        for r in c.replay_runs.list(p.company_id)
    ]}


@router.get("/replays/{run_id}")
def get_replay(
    run_id: str,
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    run = c.replay_runs.get(p.company_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="replay run not found")
    return run.model_dump(mode="json")


@router.post("/replays/{run_id}/acknowledge")
def acknowledge_replay(
    run_id: str,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    try:
        run = c.replay.acknowledge(p.company_id, run_id, by=p.key_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"run_id": run.run_id, "acknowledged_by": run.acknowledged_by,
            "acknowledged_at": run.acknowledged_at}


# ---------------------------------------------------------------------------
# escalations


@router.get("/escalations")
def list_escalations(
    status: Optional[str] = None,
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    from backend.escalation.service import EscalationStatus

    st = EscalationStatus(status) if status else None
    return {"escalations": [
        e.model_dump(mode="json") for e in c.escalation_store.list(p.company_id, status=st)
    ]}


@router.get("/escalations/{escalation_id}")
def get_escalation(
    escalation_id: str,
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    esc = c.escalation_store.get(p.company_id, escalation_id)
    if esc is None:
        raise HTTPException(status_code=404, detail="escalation not found")
    return esc.model_dump(mode="json")


@router.post("/escalations/{escalation_id}/resolve")
def resolve_escalation(
    escalation_id: str,
    req: ResolveRequest,
    p: Principal = Depends(require("approver")),
    c: Container = Depends(get_container),
):
    try:
        esc = c.escalations.resolve(
            company_id=p.company_id,
            escalation_id=escalation_id,
            resolver=p.actor(actor_type="human"),
            chosen_action=req.chosen_action,
            outcome_kind=req.outcome_kind,
            rationale=req.rationale,
            promote_to_golden=req.promote_to_golden,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AlreadyResolvedError as exc:
        raise HTTPException(status_code=409, detail=f"already resolved: {exc}") from exc
    except LedgerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=f"ledger unavailable: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return esc.model_dump(mode="json")


# ---------------------------------------------------------------------------
# drafts (extraction proposals -- never runtime authority)


@router.get("/drafts")
def list_drafts(
    status: str = "pending_review",
    p: Principal = Depends(require("owner")),
):
    """Policy drafts proposed by the extraction pipeline (Step 6). Persisted
    to the policy_drafts table by compile runs; requires the database."""
    db_url = os.environ.get("KERNL_DB_URL") or os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise HTTPException(
            status_code=503,
            detail="drafts require the database (set KERNL_DB_URL); "
            "extraction drafts are persisted by compile runs",
        )
    import psycopg
    from psycopg.rows import dict_row

    schema = os.environ.get("KERNL_DB_SCHEMA", "public")
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(f'SET search_path TO "{schema}"')
            cur.execute(
                "SELECT draft_id, compile_job_id, source_skill_id, proposed_json,"
                " issues_json, evidence_texts, publishable, status, created_at"
                " FROM policy_drafts WHERE company_id = %s AND status = %s"
                " ORDER BY created_at DESC LIMIT 200",
                (p.company_id, status),
            )
            rows = cur.fetchall()
    for r in rows:
        r["created_at"] = r["created_at"].isoformat()
    return {"drafts": rows}


# ---------------------------------------------------------------------------
# cases + health


@router.get("/cases")
def list_cases(
    workflow: Optional[str] = None,
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    return {"cases": [
        g.model_dump(mode="json") for g in c.cases.list(p.company_id, workflow=workflow)
    ]}


@router.get("/health")
def v1_health(_c: Container = Depends(get_container)):
    # the container dependency is intentional: first health ping initializes
    # stores + seed, so a green /v1/health means "ready to decide"
    return {"status": "ok", "evaluator": "kernl-evaluator/1.0.0"}
