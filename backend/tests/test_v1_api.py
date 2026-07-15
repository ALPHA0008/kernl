"""HTTP-level tests: the complete V1 loop over the real FastAPI app.

Scenario -> Evaluation -> Trace -> Ledger -> Escalation -> Adjudication ->
Golden promotion -> Replay -> gated publish -- all through /v1 endpoints,
with auth and role enforcement.

Deterministic: no LLM, no DB, no network (TestClient is in-process).
    py -3 backend/tests/test_v1_api.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ["KERNL_API_KEYS"] = (
    "owner-key:rivanly-inc:owner,"
    "agent-key:rivanly-inc:agent,"
    "approver-key:rivanly-inc:approver,"
    "other-key:other-co:owner"
)
os.environ["KERNL_SEED_RIVANLY"] = "1"
# HARD GUARD: this suite must never touch a real database -- it uses the
# in-memory reference stores regardless of what .env configures.
os.environ["KERNL_DB_URL"] = ""
os.environ["SUPABASE_DB_URL"] = ""

from fastapi.testclient import TestClient

from backend.v1_api import router
from backend.v1_container import reset_container
from fastapi import FastAPI

# A minimal app with only the v1 router: these tests must not import the
# legacy pipeline (engine/, LLM client) -- v1 stands alone.
app = FastAPI()
app.include_router(router)

OWNER = {"X-API-Key": "owner-key"}
AGENT = {"X-API-Key": "agent-key"}
APPROVER = {"X-API-Key": "approver-key"}


def _client() -> TestClient:
    reset_container()
    return TestClient(app)


def test_auth_required_and_roles_enforced():
    cl = _client()
    assert cl.get("/v1/ledger").status_code == 401
    assert cl.get("/v1/ledger", headers={"X-API-Key": "wrong"}).status_code == 401
    body = {"workflow": "refund", "facts": {}, "idempotency_key": "x"}
    assert cl.post("/v1/decisions/evaluate", headers=AGENT, json=body).status_code == 200
    # agent cannot publish or resolve
    assert cl.post("/v1/bundles/drafts", headers=AGENT, json={"bundle": {}}).status_code == 403
    assert cl.post("/v1/escalations/nope/resolve", headers=AGENT,
                   json={"chosen_action": "a", "outcome_kind": "approve",
                         "rationale": "r"}).status_code == 403


def test_me_returns_principal():
    cl = _client()
    assert cl.get("/v1/me").status_code == 401
    me = cl.get("/v1/me", headers=APPROVER).json()
    assert me == {"company_id": "rivanly-inc", "role": "approver", "key_id": me["key_id"]}
    assert cl.get("/v1/me", headers=OWNER).json()["role"] == "owner"


def test_seeded_bundle_is_active_and_evaluates():
    cl = _client()
    active = cl.get("/v1/bundles/active", headers=AGENT).json()
    assert active["content_hash"].startswith("sha256:")
    r = cl.post("/v1/decisions/evaluate", headers=AGENT, json={
        "workflow": "refund",
        "facts": {"plan_type": "annual", "days_since_purchase": 9},
        "idempotency_key": "t-1",
    }).json()
    assert r["outcome"]["kind"] == "approve"
    assert r["outcome"]["action"] == "approve_full_refund"
    assert r["escalation_id"] is None
    trace = cl.get(f"/v1/decisions/{r['decision_id']}", headers=AGENT).json()
    assert trace["trace"]["precedence"]["winner"] == "refund.annual_full_14d"
    assert trace["bundle_hash"] == active["content_hash"]


def test_idempotency_over_http():
    cl = _client()
    body = {"workflow": "refund",
            "facts": {"plan_type": "annual", "days_since_purchase": 9},
            "idempotency_key": "same-key"}
    a = cl.post("/v1/decisions/evaluate", headers=AGENT, json=body).json()
    b = cl.post("/v1/decisions/evaluate", headers=AGENT, json=body).json()
    assert a["decision_id"] == b["decision_id"]
    assert b["created"] is False


def test_request_errors_are_400_not_decisions():
    cl = _client()
    r = cl.post("/v1/decisions/evaluate", headers=AGENT, json={
        "workflow": "nonexistent", "facts": {}, "idempotency_key": "e1"})
    assert r.status_code == 400
    r = cl.post("/v1/decisions/evaluate", headers=AGENT, json={
        "workflow": "refund", "facts": {"days_since_purchase": "nine"},
        "idempotency_key": "e2"})
    assert r.status_code == 400
    # neither wrote a ledger row
    events = cl.get("/v1/ledger", headers=AGENT).json()["events"]
    assert all(e["idempotency_key"] not in ("e1", "e2") for e in events)


def test_full_loop_escalation_adjudication_promotion_replay_gate():
    cl = _client()

    # 1. incomplete facts -> escalate + inbox item
    r = cl.post("/v1/decisions/evaluate", headers=AGENT, json={
        "workflow": "refund", "facts": {"days_since_purchase": 20},
        "idempotency_key": "loop-1"}).json()
    assert r["outcome"]["kind"] == "escalate"
    esc_id = r["escalation_id"]
    assert esc_id

    inbox = cl.get("/v1/escalations?status=open", headers=APPROVER).json()["escalations"]
    assert any(e["escalation_id"] == esc_id for e in inbox)

    # 2. approver adjudicates + promotes to golden
    resolved = cl.post(f"/v1/escalations/{esc_id}/resolve", headers=APPROVER, json={
        "chosen_action": "approve_prorated_refund", "outcome_kind": "approve",
        "rationale": "Verified annual plan in billing.", "promote_to_golden": True,
    }).json()
    assert resolved["status"] == "resolved"

    # 3. adjudication is on the ledger, chain intact
    assert cl.get("/v1/ledger/verify", headers=AGENT).json()["chain_valid"] is True
    adj_id = resolved["resolution"]["adjudication_event_id"]
    adj = cl.get(f"/v1/decisions/{adj_id}", headers=AGENT).json()
    assert adj["event_type"] == "adjudication"
    assert adj["linked_event_id"] == r["decision_id"]

    # 4. promoted case is in the corpus, non-synthetic
    cases = cl.get("/v1/cases", headers=AGENT).json()["cases"]
    promoted = [c for c in cases if c["provenance"].startswith("adjudication:")]
    assert len(promoted) == 1 and promoted[0]["synthetic"] is False

    # 5. double-resolve is 409
    again = cl.post(f"/v1/escalations/{esc_id}/resolve", headers=APPROVER, json={
        "chosen_action": "deny_refund", "outcome_kind": "deny", "rationale": "no"})
    assert again.status_code == 409

    # 6. a modified draft cannot publish without an acknowledged replay
    active = cl.get("/v1/bundles/active", headers=AGENT).json()
    bundle = active["bundle"]
    for pol in bundle["policies"]:
        if pol["id"] == "refund.annual_full_14d":
            pol["conditions"][1]["value"] = 7  # tighten 14 -> 7
    draft = cl.post("/v1/bundles/drafts", headers=OWNER, json={"bundle": bundle}).json()
    blocked = cl.post(f"/v1/bundles/{draft['record_id']}/publish", headers=OWNER)
    assert blocked.status_code == 409

    # 7. replay shows the blast radius (flips + golden failures)
    run = cl.post("/v1/replays", headers=OWNER, json={
        "candidate_record_id": draft["record_id"]}).json()
    assert run["summary"]["flips"] >= 1
    assert run["summary"]["golden_failed"] >= 1

    # 8. after acknowledgment (a human owns the blast radius) publish succeeds
    cl.post(f"/v1/replays/{run['run_id']}/acknowledge", headers=OWNER)
    published = cl.post(f"/v1/bundles/{draft['record_id']}/publish", headers=OWNER)
    assert published.status_code == 200
    assert cl.get("/v1/bundles/active", headers=AGENT).json()["content_hash"] == \
        draft["content_hash"]

    # 9. rollback: reactivate the previous bundle (pointer move)
    bundles = cl.get("/v1/bundles", headers=OWNER).json()["bundles"]
    prior = next(b for b in bundles if b["content_hash"] == active["content_hash"])
    rolled = cl.post(f"/v1/bundles/{prior['record_id']}/activate", headers=OWNER)
    assert rolled.status_code == 200
    assert cl.get("/v1/bundles/active", headers=AGENT).json()["content_hash"] == \
        active["content_hash"]


def test_tenant_isolation_over_http():
    cl = _client()
    other = {"X-API-Key": "other-key"}
    # other-co has no bundle and sees nothing of rivanly's data
    assert cl.get("/v1/bundles/active", headers=other).status_code == 404
    assert cl.get("/v1/ledger", headers=other).json()["events"] == []
    r = cl.post("/v1/decisions/evaluate", headers=other, json={
        "workflow": "refund", "facts": {}, "idempotency_key": "x"})
    assert r.status_code == 409  # no published bundle for tenant


def test_metrics_endpoint_reflects_decisions():
    cl = _client()
    assert cl.get("/v1/metrics").status_code == 401  # fail-closed like everything else
    cl.post("/v1/decisions/evaluate", headers=AGENT, json={
        "workflow": "refund", "facts": {"plan_type": "annual", "days_since_purchase": 9},
        "idempotency_key": "metrics-probe"})
    text = cl.get("/v1/metrics", headers=AGENT).text
    assert "# TYPE kernl_decisions_total counter" in text
    assert 'kernl_decisions_total{outcome="approve",tenant="rivanly-inc"}' in text
    assert "# TYPE kernl_decision_latency_ms histogram" in text
    assert "kernl_decision_latency_ms_count{" in text


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
