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
    GET  /v1/tenants/{id}/keys          list a tenant's keys (metadata only)
    POST /v1/tenants/{id}/keys          issue a key (rotation: issue then revoke)
    DELETE /v1/tenants/{id}/keys/{kid}  revoke a key (idempotent; last-owner-safe)
    DELETE /v1/tenants/{id}             purge a tenant + all data (admin-gated)
    GET  /v1/me                        principal introspection (tenant + role)
    GET  /v1/health
    GET  /v1/metrics                   Prometheus text: latency/outcome/escalation counters

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
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field

from backend.bundle.diff import diff_bundles
from backend.bundle.lifecycle import PublishGateError
from backend.bundle.schema import Bundle
from backend.escalation.service import AlreadyResolvedError
from backend.ledger.events import Actor
from backend.ledger.service import LedgerUnavailableError
from backend.observability import METRICS, log_event, observe_latency, render_prometheus
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


def _resolve_principal(x_api_key: Optional[str], c: Container) -> Optional[Principal]:
    """Resolve a key from BOTH sources: the static KERNL_API_KEYS env (bootstrap
    keys) and the tenant store (keys issued by onboarding, stored hashed). Env
    keys win if both define the same key. Onboarding-issued keys let a brand-new
    tenant use the console the moment it is provisioned."""
    if not x_api_key:
        return None
    env_principal = _parse_keys().get(x_api_key)
    if env_principal is not None:
        return env_principal
    record = c.tenants.resolve(x_api_key)
    if record is not None:
        return Principal(
            company_id=record.company_id, role=record.role, key_id=record.key_id
        )
    return None


def require(min_role: str):
    def dep(
        x_api_key: Optional[str] = Header(default=None),
        c: Container = Depends(get_container),
    ) -> Principal:
        principal = _resolve_principal(x_api_key, c)
        if principal is None:
            raise HTTPException(status_code=401, detail="invalid or missing API key")
        if ROLE_RANK[principal.role] < ROLE_RANK[min_role]:
            raise HTTPException(status_code=403, detail=f"requires role >= {min_role}")
        return principal

    return dep


def _signature_block(record) -> dict:
    """The signature status of a bundle record, as returned to API callers.
    Reports three states honestly: signed-and-valid, signed-but-invalid
    (tampered / wrong key -- a red flag), and unsigned (no signing key was
    configured at publish). `verified` is computed here, not trusted from
    storage, so a tampered content_hash cannot masquerade as valid."""
    return {
        "signed": record.is_signed,
        "verified": record.verify_signature(),
        "signing_pubkey": record.signing_pubkey,
        "signature_scheme": record.signature_scheme,
    }


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


class ProvisionRequest(BaseModel):
    company_id: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=200)


class IssueKeyRequest(BaseModel):
    role: str = Field(pattern=r"^(owner|approver|agent)$")


class SourceUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=256)
    content: str = Field(min_length=1)


class DraftSaveRequest(BaseModel):
    proposed: dict[str, Any]  # Policy-shaped JSON (editable)
    draft_id: Optional[str] = None
    origin: str = "authored"


class GroundRequest(BaseModel):
    source_id: str
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=0)
    excerpt: str = Field(min_length=1)


class DraftStatusRequest(BaseModel):
    status: str  # "accepted" | "rejected" | "draft"


# ---------------------------------------------------------------------------
# decisions + ledger


@router.post("/decisions/evaluate")
def evaluate_decision(
    req: EvaluateRequest,
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    started = time.perf_counter()
    active = c.lifecycle.active_bundle(p.company_id)
    if active is None:
        METRICS.inc("kernl_decisions_total", {"tenant": p.company_id, "outcome": "no_bundle"})
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
        METRICS.inc("kernl_decisions_total", {"tenant": p.company_id, "outcome": "error_unknown_workflow"})
        raise HTTPException(status_code=400, detail=f"unknown workflow: {exc}") from exc
    except InvalidFactsError as exc:
        METRICS.inc("kernl_decisions_total", {"tenant": p.company_id, "outcome": "error_invalid_facts"})
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LedgerUnavailableError as exc:
        METRICS.inc("kernl_decisions_total", {"tenant": p.company_id, "outcome": "error_ledger_unavailable"})
        raise HTTPException(status_code=503, detail=f"ledger unavailable: {exc}") from exc

    escalation = c.escalations.open_for(event) if created else c.escalations_by_decision(
        p.company_id, event.event_id
    )
    elapsed_ms = observe_latency(
        "kernl_decision_latency_ms", started, {"tenant": p.company_id, "workflow": req.workflow}
    )
    METRICS.inc(
        "kernl_decisions_total",
        {"tenant": p.company_id, "outcome": event.outcome.get("kind", "unknown")},
    )
    if escalation is not None and created:
        METRICS.inc("kernl_escalations_opened_total", {"tenant": p.company_id})
    log_event(
        "decision.evaluated",
        tenant=p.company_id,
        decision_id=event.event_id,
        workflow=req.workflow,
        bundle_hash=event.bundle_hash,
        outcome_kind=event.outcome.get("kind"),
        created=created,
        escalation_id=escalation.escalation_id if escalation else None,
        latency_ms=round(elapsed_ms, 2),
        actor=f"{p.actor().type}:{p.actor().id}",
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
    bundle_hash: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    rows = c.ledger.list(p.company_id, workflow=workflow, outcome_kind=outcome,
                         bundle_hash=bundle_hash, since=since, until=until,
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
         "published_at": r.published_at, "policy_count": len(r.bundle.policies),
         **_signature_block(r)}
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
            "bundle": r.bundle.model_dump(mode="json"), **_signature_block(r)}


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


@router.get("/bundles/{record_id}/diff")
def diff_bundle(
    record_id: str,
    against: Optional[str] = None,
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    """Structural diff of `record_id` against another bundle -- by default the
    tenant's currently active (published) bundle, or an explicit `against`
    record_id. Powers the Policy Workbench's "diff draft vs published" view.
    This is a content diff (which policies changed), distinct from a replay
    (which diffs decision *outcomes* on a case set) -- both matter before publish."""
    record = c.bundles.get(p.company_id, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="unknown bundle record")

    if against is not None:
        baseline = c.bundles.get(p.company_id, against)
        if baseline is None:
            raise HTTPException(status_code=404, detail="unknown baseline bundle record")
    else:
        baseline = c.lifecycle.active_bundle(p.company_id)
        if baseline is not None and baseline.record_id == record.record_id:
            baseline = None  # diffing the active bundle against itself is meaningless

    diff = diff_bundles(baseline.bundle if baseline is not None else None, record.bundle)
    return {
        "record_id": record.record_id,
        "baseline_record_id": baseline.record_id if baseline is not None else None,
        "diff": diff.model_dump(mode="json"),
    }


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
        METRICS.inc("kernl_publishes_total", {"tenant": p.company_id, "result": "gate_blocked"})
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    METRICS.inc("kernl_publishes_total", {"tenant": p.company_id, "result": "published"})
    log_event(
        "bundle.published",
        tenant=p.company_id,
        bundle_hash=record.content_hash,
        record_id=record.record_id,
        replay_run_id=record.replay_run_id,
        published_by=p.key_id,
        signed=record.is_signed,
    )
    return {"record_id": record.record_id, "content_hash": record.content_hash,
            "status": record.status.value, "replay_run_id": record.replay_run_id,
            **_signature_block(record)}


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
    # A tenant's FIRST bundle has no golden corpus yet: an empty replay is a
    # legitimate clean run (nothing to regress against). The gate still applies
    # -- an owner must acknowledge the (empty) blast radius before publishing.
    cases = c.cases.list(p.company_id)
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
    METRICS.inc("kernl_escalations_resolved_total", {"tenant": p.company_id, "outcome": req.outcome_kind})
    log_event(
        "escalation.resolved",
        tenant=p.company_id,
        escalation_id=escalation_id,
        decision_id=esc.decision_event_id,
        adjudication_event_id=esc.resolution.adjudication_event_id if esc.resolution else None,
        outcome_kind=req.outcome_kind,
        promoted_to_golden=req.promote_to_golden,
        resolver=f"{p.key_id}",
    )
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
# onboarding: provision -> upload -> author/ground -> assemble -> publish


def require_admin(x_api_key: Optional[str] = Header(default=None)) -> str:
    """Provisioning a brand-new tenant needs a bootstrap credential, because a
    new tenant has no key yet. KERNL_ADMIN_KEY gates it; if unset, provisioning
    is closed (never open)."""
    admin = os.environ.get("KERNL_ADMIN_KEY", "")
    if not admin or x_api_key != admin:
        raise HTTPException(status_code=401, detail="admin key required to provision tenants")
    return x_api_key


@router.post("/tenants")
def provision_tenant(
    req: ProvisionRequest,
    _admin: str = Depends(require_admin),
    c: Container = Depends(get_container),
):
    """Create a tenant and issue its first owner key. The plaintext key is
    returned ONCE here and never again -- the store keeps only its hash."""
    try:
        tenant, key = c.tenants.provision(req.company_id, req.name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "company_id": tenant.company_id,
        "name": tenant.name,
        "owner_api_key": key,  # shown once; store it now
    }


@router.get("/tenants")
def list_tenants(
    _admin: str = Depends(require_admin),
    c: Container = Depends(get_container),
):
    return {
        "tenants": [
            {"company_id": t.company_id, "name": t.name, "created_at": t.created_at}
            for t in c.tenant_store.list_tenants()
        ]
    }


@router.get("/tenants/{company_id}/keys")
def list_tenant_keys(
    company_id: str,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    """List a tenant's API keys as METADATA ONLY -- never the plaintext or the
    hash. An owner can see what exists in order to rotate it. Scoped to the
    caller's own tenant."""
    if company_id != p.company_id:
        raise HTTPException(status_code=403, detail="can only manage your own tenant's keys")
    return {
        "keys": [
            {
                "key_id": k.key_id,
                "role": k.role,
                "created_at": k.created_at,
                "revoked_at": k.revoked_at,
                "active": k.revoked_at is None,
            }
            for k in c.tenants.list_keys(company_id)
        ]
    }


@router.post("/tenants/{company_id}/keys")
def issue_tenant_key(
    company_id: str,
    req: IssueKeyRequest,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    """Issue a new API key for the caller's own tenant. The plaintext is
    returned ONCE here and never again. This is the 'issue' half of key
    rotation: mint a replacement, then revoke the old key."""
    if company_id != p.company_id:
        raise HTTPException(status_code=403, detail="can only manage your own tenant's keys")
    try:
        record, plaintext = c.tenants.issue_key(company_id, role=req.role)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_event("tenant.key_issued", tenant=company_id, key_id=record.key_id,
              role=record.role, issued_by=p.key_id)
    return {
        "key_id": record.key_id,
        "role": record.role,
        "api_key": plaintext,  # shown once; store it now
    }


@router.delete("/tenants/{company_id}/keys/{key_id}")
def revoke_tenant_key(
    company_id: str,
    key_id: str,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    """Revoke a key for the caller's own tenant. Idempotent. Refuses to revoke
    the last active owner key (that would lock the tenant out of its own
    administration -- issue a new owner key first, then revoke the old one)."""
    if company_id != p.company_id:
        raise HTTPException(status_code=403, detail="can only manage your own tenant's keys")
    try:
        revoked = c.tenants.revoke_key(company_id, key_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    log_event("tenant.key_revoked", tenant=company_id, key_id=key_id, revoked_by=p.key_id)
    return {"key_id": revoked.key_id, "revoked_at": revoked.revoked_at}


@router.delete("/tenants/{company_id}")
def delete_tenant(
    company_id: str,
    _admin: str = Depends(require_admin),
    c: Container = Depends(get_container),
):
    """Purge a tenant and ALL its data. Admin-gated, same as provisioning.
    Whole-tenant removal is sanctioned by docs/RETENTION_POLICY.md -- discard
    the entire logbook as a unit, which is not history mutation. Irreversible."""
    deleted = c.delete_tenant(company_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"unknown tenant {company_id!r}")
    log_event("tenant.deleted", tenant=company_id)
    return {"company_id": company_id, "deleted": True}


@router.post("/sources")
def upload_source(
    req: SourceUploadRequest,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    """Store an immutable, content-addressed snapshot of a document. Evidence
    spans will cite into it; the bytes are frozen so citations stay verifiable."""
    from backend.onboarding.sources import make_snapshot

    snap = c.source_store.add(make_snapshot(p.company_id, req.filename, req.content))
    return {
        "source_id": snap.source_id,
        "filename": snap.filename,
        "content_hash": snap.content_hash,
        "byte_length": snap.byte_length,
        "created_at": snap.created_at,
    }


@router.get("/sources")
def list_sources(
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    return {
        "sources": [
            {
                "source_id": s.source_id,
                "filename": s.filename,
                "content_hash": s.content_hash,
                "byte_length": s.byte_length,
                "created_at": s.created_at,
            }
            for s in c.source_store.list(p.company_id)
        ]
    }


@router.get("/sources/{source_id}")
def get_source(
    source_id: str,
    p: Principal = Depends(require("agent")),
    c: Container = Depends(get_container),
):
    """The full source text -- the reviewer highlights within it to ground a
    citation, so the client needs the exact bytes to compute span offsets."""
    snap = c.source_store.get(p.company_id, source_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="source not found")
    return snap.model_dump(mode="json")


@router.post("/onboarding/extract")
async def extract_drafts(
    req: dict,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    """LLM-propose policy drafts from an uploaded source. Each proposal lands as
    an ungrounded 'extracted' draft the reviewer must still cite. 503 if the LLM
    backend is unavailable -- the author-directly path never depends on it."""
    from backend.onboarding.extract import ExtractionUnavailable, propose_drafts_from_source

    source_id = req.get("source_id")
    if not source_id:
        raise HTTPException(status_code=400, detail="source_id is required")
    snap = c.source_store.get(p.company_id, source_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="source not found")
    try:
        drafts = await propose_drafts_from_source(snap)
    except ExtractionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    stored = [c.draft_store.upsert(d) for d in drafts]
    return {"drafts": [d.model_dump(mode="json") for d in stored]}


@router.get("/onboarding/drafts")
def list_onboarding_drafts(
    status: Optional[str] = None,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    return {
        "drafts": [d.model_dump(mode="json") for d in c.draft_store.list(p.company_id, status)]
    }


@router.get("/onboarding/drafts/{draft_id}")
def get_onboarding_draft(
    draft_id: str,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    d = c.draft_store.get(p.company_id, draft_id)
    if d is None:
        raise HTTPException(status_code=404, detail="draft not found")
    return d.model_dump(mode="json")


@router.post("/onboarding/drafts")
def save_onboarding_draft(
    req: DraftSaveRequest,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    """Create or update a draft's proposed policy. Evidence already grounded on
    an existing draft is preserved; publishability is re-evaluated."""
    d = c.onboarding.save_draft(
        p.company_id, req.proposed, origin=req.origin, draft_id=req.draft_id
    )
    return d.model_dump(mode="json")


@router.post("/onboarding/drafts/{draft_id}/ground")
def ground_draft(
    draft_id: str,
    req: GroundRequest,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    """Attach a VERIFIED source span as evidence. The span's bytes must exactly
    match the source at those offsets, or this is a 400 -- no uncited norm."""
    from backend.onboarding.sources import GroundingError

    try:
        d = c.onboarding.ground_span(
            p.company_id, draft_id, req.source_id, req.span_start, req.span_end, req.excerpt
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GroundingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return d.model_dump(mode="json")


@router.delete("/onboarding/drafts/{draft_id}/evidence/{index}")
def remove_draft_evidence(
    draft_id: str,
    index: int,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    try:
        d = c.onboarding.remove_evidence(p.company_id, draft_id, index)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return d.model_dump(mode="json")


@router.post("/onboarding/drafts/{draft_id}/status")
def set_draft_status(
    draft_id: str,
    req: DraftStatusRequest,
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    try:
        d = c.onboarding.set_status(p.company_id, draft_id, req.status)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return d.model_dump(mode="json")


@router.post("/onboarding/assemble")
def assemble_onboarding_bundle(
    p: Principal = Depends(require("owner")),
    c: Container = Depends(get_container),
):
    """Assemble all accepted drafts into a Bundle and register it as a DRAFT
    bundle record. It still goes through the normal replay gate before it can
    publish -- onboarding does not bypass the gate."""
    from backend.onboarding.service import AssembleError

    try:
        bundle = c.onboarding.assemble_bundle(p.company_id)
    except AssembleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record = c.lifecycle.save_draft(p.company_id, bundle, created_by=p.key_id)
    return {
        "record_id": record.record_id,
        "content_hash": record.content_hash,
        "status": record.status.value,
        "policy_count": len(bundle.policies),
        "workflow_count": len(bundle.workflows),
    }


# ---------------------------------------------------------------------------
# cases + health


@router.get("/me")
def whoami(p: Principal = Depends(require("agent"))):
    """Principal introspection: which tenant + role this key carries. The
    console uses it to validate a key at login and gate UI actions (the
    server still enforces roles on every endpoint regardless)."""
    return {"company_id": p.company_id, "role": p.role, "key_id": p.key_id}


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


@router.get("/metrics")
def v1_metrics(_p: Principal = Depends(require("agent"))):
    """Prometheus text exposition format: decision latency histograms, and
    decision/escalation/publish counters labeled by tenant + outcome. Any
    valid tenant key can read it (metrics are process-wide, not a leak of
    another tenant's ledger data) -- but the endpoint stays behind auth
    because the API is fail-closed everywhere, no exceptions."""
    return Response(content=render_prometheus(), media_type="text/plain; version=0.0.4")
