"""HTTP-level test: the complete NEW-TENANT onboarding loop over /v1.

Provision a tenant -> upload a source doc -> author a policy -> ground it in a
verified source span -> accept -> assemble a bundle -> replay -> acknowledge ->
publish -> evaluate a real decision on the brand-new tenant. All through the
API, with the admin/owner auth boundaries enforced.

Deterministic: no LLM, no DB, no network (TestClient in-process, in-memory stores).
    py -3 backend/tests/test_onboarding_api.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ["KERNL_API_KEYS"] = ""  # no bootstrap tenant keys; all keys are issued
os.environ["KERNL_ADMIN_KEY"] = "admin-secret"
os.environ["KERNL_SEED_RIVANLY"] = "0"  # start empty; this test provisions its own tenant
os.environ["KERNL_DB_URL"] = ""  # HARD GUARD: never touch a real DB
os.environ["SUPABASE_DB_URL"] = ""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.v1_api import router
from backend.v1_container import reset_container

app = FastAPI()
app.include_router(router)

ADMIN = {"X-API-Key": "admin-secret"}

SOURCE = (
    "Refund Policy\n\n"
    "Customers on annual plans who request a refund within 14 days of "
    "purchase receive a full refund.\n"
)


def _client() -> TestClient:
    reset_container()
    return TestClient(app)


def _policy() -> dict:
    return {
        "id": "refund.annual_14d",
        "workflow": "refund",
        "effect": {"kind": "approve", "action": "approve_full_refund"},
        "priority": 70,
        "conditions": [
            {"field": "plan_type", "operator": "eq", "value": "annual", "value_type": "string"},
            {"field": "days_since_purchase", "operator": "lte", "value": 14, "value_type": "number"},
        ],
        "authority": {"approval_required": False},
        "overrides": [],
        "unconditional_ack": False,
        "rationale": "Annual plans refundable within 14 days.",
    }


def test_provisioning_requires_admin():
    cl = _client()
    # no admin key -> 401
    assert cl.post("/v1/tenants", json={"company_id": "acme", "name": "Acme"}).status_code == 401
    assert cl.post("/v1/tenants", headers={"X-API-Key": "wrong"},
                   json={"company_id": "acme", "name": "Acme"}).status_code == 401


def test_full_new_tenant_onboarding_loop():
    cl = _client()

    # 1. provision -> owner key issued once
    prov = cl.post("/v1/tenants", headers=ADMIN,
                   json={"company_id": "acme-corp", "name": "Acme Corp"})
    assert prov.status_code == 200
    key = prov.json()["owner_api_key"]
    assert key.startswith("kk_")
    OWNER = {"X-API-Key": key}

    # the issued key authenticates against /v1/me as owner of the new tenant
    me = cl.get("/v1/me", headers=OWNER).json()
    assert me["company_id"] == "acme-corp" and me["role"] == "owner"

    # brand-new tenant has no bundle yet
    assert cl.get("/v1/bundles/active", headers=OWNER).status_code == 404

    # 2. upload the source document (immutable snapshot)
    up = cl.post("/v1/sources", headers=OWNER,
                 json={"filename": "refund.md", "content": SOURCE}).json()
    source_id = up["source_id"]
    assert up["content_hash"].startswith("sha256:")

    # 3. author a policy draft -> not publishable (no evidence yet)
    d = cl.post("/v1/onboarding/drafts", headers=OWNER, json={"proposed": _policy()}).json()
    draft_id = d["draft_id"]
    assert d["publishable"] is False
    assert any("grounded evidence" in i for i in d["issues_json"])

    # 4. ground it: select the exact sentence -> verified citation
    start = SOURCE.index("Customers on annual")
    end = SOURCE.index("full refund.") + len("full refund.")
    excerpt = SOURCE[start:end]
    grounded = cl.post(f"/v1/onboarding/drafts/{draft_id}/ground", headers=OWNER,
                       json={"source_id": source_id, "span_start": start,
                             "span_end": end, "excerpt": excerpt}).json()
    assert grounded["publishable"] is True

    # grounding a WRONG span is rejected (no uncited norm)
    bad = cl.post(f"/v1/onboarding/drafts/{draft_id}/ground", headers=OWNER,
                  json={"source_id": source_id, "span_start": start,
                        "span_end": end, "excerpt": "a paraphrase"})
    assert bad.status_code == 400

    # 5. accept -> assemble a bundle
    acc = cl.post(f"/v1/onboarding/drafts/{draft_id}/status", headers=OWNER,
                  json={"status": "accepted"})
    assert acc.status_code == 200
    asm = cl.post("/v1/onboarding/assemble", headers=OWNER).json()
    record_id = asm["record_id"]
    assert asm["policy_count"] == 1 and asm["workflow_count"] == 1

    # 6. publish is gated: needs an acknowledged replay first
    blocked = cl.post(f"/v1/bundles/{record_id}/publish", headers=OWNER)
    assert blocked.status_code == 409

    # 7. first replay has no golden corpus -> clean empty run, still must be ack'd
    run = cl.post("/v1/replays", headers=OWNER,
                  json={"candidate_record_id": record_id}).json()
    assert run["summary"]["total"] == 0 and run["summary"]["golden_failed"] == 0
    cl.post(f"/v1/replays/{run['run_id']}/acknowledge", headers=OWNER)

    # 8. publish now succeeds -> the new tenant has a live dashboard
    pub = cl.post(f"/v1/bundles/{record_id}/publish", headers=OWNER)
    assert pub.status_code == 200
    active = cl.get("/v1/bundles/active", headers=OWNER).json()
    assert active["content_hash"] == asm["content_hash"]

    # 9. a real decision runs against the freshly-onboarded bundle
    dec = cl.post("/v1/decisions/evaluate", headers=OWNER, json={
        "workflow": "refund",
        "facts": {"plan_type": "annual", "days_since_purchase": 9},
        "idempotency_key": "acme-first-decision",
    }).json()
    assert dec["outcome"]["kind"] == "approve"
    assert dec["outcome"]["action"] == "approve_full_refund"

    # 10. the trace cites the grounded evidence
    trace = cl.get(f"/v1/decisions/{dec['decision_id']}", headers=OWNER).json()
    assert trace["trace"]["precedence"]["winner"] == "refund.annual_14d"


def test_tenant_isolation_for_provisioned_tenants():
    cl = _client()
    k1 = cl.post("/v1/tenants", headers=ADMIN,
                 json={"company_id": "co-one", "name": "One"}).json()["owner_api_key"]
    k2 = cl.post("/v1/tenants", headers=ADMIN,
                 json={"company_id": "co-two", "name": "Two"}).json()["owner_api_key"]
    # co-one uploads a source; co-two must not see it
    cl.post("/v1/sources", headers={"X-API-Key": k1},
            json={"filename": "a.md", "content": "hello world"})
    assert cl.get("/v1/sources", headers={"X-API-Key": k2}).json()["sources"] == []
    # duplicate provisioning is a conflict
    dup = cl.post("/v1/tenants", headers=ADMIN, json={"company_id": "co-one", "name": "Dup"})
    assert dup.status_code == 409


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
