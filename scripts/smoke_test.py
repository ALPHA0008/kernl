"""V1 smoke test: proves the full Decision Ledger loop works end-to-end
against a running /v1 server -- provisioning, onboarding, evaluation, trace,
ledger, escalation, adjudication, replay-gated publish, and metrics.

This replaces the legacy compile-pipeline smoke test (retired with /agent/*).
Matches docs/V1_EXECUTION_PLAN.md Step 8 DoD: "smoke test green end-to-end."

Provisions a throwaway tenant (smoke-<random>) so it never touches the seeded
rivanly-inc reference data. Requires KERNL_ADMIN_KEY to match the running
server's admin key.

Usage:
    KERNL_ADMIN_KEY=... python scripts/smoke_test.py [--base-url http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys

import httpx

SOURCE_TEXT = (
    "Refund Policy\n\n"
    "Customers on annual plans who request a refund within 14 days of "
    "purchase receive a full refund.\n"
)

_passed = 0
_failed = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  OK   {label}")
    else:
        _failed += 1
        print(f"  FAIL {label}  {detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("KERNL_API_URL", "http://127.0.0.1:8000"))
    args = parser.parse_args()

    admin_key = os.environ.get("KERNL_ADMIN_KEY")
    if not admin_key:
        print("ERROR: set KERNL_ADMIN_KEY to the running server's admin key.")
        return 2

    c = httpx.Client(base_url=args.base_url, timeout=30.0)
    admin = {"X-API-Key": admin_key}

    print(f"1. Health check against {args.base_url}")
    r = c.get("/v1/health")
    check("GET /v1/health -> 200", r.status_code == 200, str(r.status_code))
    if r.status_code != 200:
        print("Backend unreachable -- aborting.")
        return 1

    print("2. Provision a throwaway tenant")
    co = f"smoke-{secrets.token_hex(4)}"
    r = c.post("/v1/tenants", headers=admin, json={"company_id": co, "name": "Smoke Test"})
    check("POST /v1/tenants -> 200", r.status_code == 200, r.text[:200])
    owner_key = r.json()["owner_api_key"]
    OWNER = {"X-API-Key": owner_key}
    check("owner_api_key issued", owner_key.startswith("kk_"))

    r = c.get("/v1/me", headers=OWNER)
    check("GET /v1/me resolves the issued key", r.status_code == 200 and r.json()["role"] == "owner")

    print("3. New tenant has no bundle yet")
    r = c.get("/v1/bundles/active", headers=OWNER)
    check("GET /v1/bundles/active -> 404 before onboarding", r.status_code == 404)

    print("4. Onboarding: upload source, author, ground, accept, assemble")
    r = c.post("/v1/sources", headers=OWNER, json={"filename": "refund.md", "content": SOURCE_TEXT})
    check("POST /v1/sources -> 200", r.status_code == 200, r.text[:200])
    source_id = r.json()["source_id"]

    policy = {
        "id": "refund.annual_14d", "workflow": "refund",
        "effect": {"kind": "approve", "action": "approve_full_refund"}, "priority": 70,
        "conditions": [{"field": "days_since_purchase", "operator": "lte",
                        "value": 14, "value_type": "number"}],
        "authority": {"approval_required": False}, "evidence": [], "overrides": [],
        "unconditional_ack": False, "rationale": "smoke test",
    }
    r = c.post("/v1/onboarding/drafts", headers=OWNER, json={"proposed": policy})
    check("POST /v1/onboarding/drafts -> 200", r.status_code == 200, r.text[:200])
    draft = r.json()
    draft_id = draft["draft_id"]
    check("fresh draft is not publishable (no citation yet)", draft["publishable"] is False)

    start = SOURCE_TEXT.index("Customers on annual")
    end = SOURCE_TEXT.index("full refund.") + len("full refund.")
    excerpt = SOURCE_TEXT[start:end]
    r = c.post(f"/v1/onboarding/drafts/{draft_id}/ground", headers=OWNER,
               json={"source_id": source_id, "span_start": start, "span_end": end, "excerpt": excerpt})
    check("ground with the exact source span -> publishable", r.status_code == 200 and r.json()["publishable"])

    r = c.post(f"/v1/onboarding/drafts/{draft_id}/ground", headers=OWNER,
               json={"source_id": source_id, "span_start": 0, "span_end": 10, "excerpt": "not the bytes"})
    check("grounding a WRONG span -> 400 (no uncited norm)", r.status_code == 400)

    r = c.post(f"/v1/onboarding/drafts/{draft_id}/status", headers=OWNER, json={"status": "accepted"})
    check("accept the grounded draft -> 200", r.status_code == 200)

    r = c.post("/v1/onboarding/assemble", headers=OWNER)
    check("assemble accepted drafts into a bundle -> 200", r.status_code == 200, r.text[:200])
    record_id = r.json()["record_id"]

    print("5. Publish gate: blocked without replay, then unlocked")
    r = c.post(f"/v1/bundles/{record_id}/publish", headers=OWNER)
    check("publish without acknowledged replay -> 409", r.status_code == 409)

    r = c.post("/v1/replays", headers=OWNER, json={"candidate_record_id": record_id})
    check("run replay (empty golden set = clean baseline) -> 200", r.status_code == 200)
    run_id = r.json()["run_id"]
    c.post(f"/v1/replays/{run_id}/acknowledge", headers=OWNER)

    r = c.post(f"/v1/bundles/{record_id}/publish", headers=OWNER)
    check("publish after acknowledgment -> 200", r.status_code == 200, r.text[:200])

    r = c.get("/v1/bundles/active", headers=OWNER)
    check("active bundle now serves the published content", r.status_code == 200)

    print("6. Evaluate a real decision + inspect its trace")
    r = c.post("/v1/decisions/evaluate", headers=OWNER, json={
        "workflow": "refund", "facts": {"days_since_purchase": 9},
        "idempotency_key": "smoke-decision-1"})
    check("POST /v1/decisions/evaluate -> 200", r.status_code == 200, r.text[:200])
    decision = r.json()
    check("outcome is approve/approve_full_refund",
          decision["outcome"]["kind"] == "approve" and decision["outcome"]["action"] == "approve_full_refund")

    r = c.get(f"/v1/decisions/{decision['decision_id']}", headers=OWNER)
    check("GET /v1/decisions/{id} returns the full trace", r.status_code == 200)
    trace = r.json()["trace"]
    check("trace cites the winning policy", trace["precedence"]["winner"] == "refund.annual_14d")

    print("7. Idempotency: same key returns the SAME decision")
    r2 = c.post("/v1/decisions/evaluate", headers=OWNER, json={
        "workflow": "refund", "facts": {"days_since_purchase": 999},
        "idempotency_key": "smoke-decision-1"})
    check("retry with the same key -> created=False, same id",
          r2.json()["created"] is False and r2.json()["decision_id"] == decision["decision_id"])

    print("8. Escalation: missing facts -> escalate -> adjudicate")
    r = c.post("/v1/decisions/evaluate", headers=OWNER, json={
        "workflow": "refund", "facts": {}, "idempotency_key": "smoke-escalation-1"})
    check("evaluate with no facts -> escalate", r.json()["outcome"]["kind"] == "escalate")
    esc_id = r.json()["escalation_id"]
    check("escalation was opened", esc_id is not None)

    r = c.post(f"/v1/escalations/{esc_id}/resolve", headers=OWNER, json={
        "chosen_action": "approve_full_refund", "outcome_kind": "approve",
        "rationale": "Smoke test adjudication.", "promote_to_golden": True})
    check("resolve escalation -> 200", r.status_code == 200, r.text[:200])

    r = c.get("/v1/cases", headers=OWNER)
    promoted = [x for x in r.json()["cases"] if x["provenance"].startswith("adjudication:")]
    check("adjudication promoted a non-synthetic golden case", len(promoted) == 1 and not promoted[0]["synthetic"])

    print("9. Ledger integrity")
    r = c.get("/v1/ledger/verify", headers=OWNER)
    check("hash chain verifies", r.status_code == 200 and r.json()["chain_valid"] is True)

    print("10. Metrics reflect this run")
    r = c.get("/v1/metrics", headers=OWNER)
    text = r.text
    check("GET /v1/metrics -> 200", r.status_code == 200)
    check("kernl_decisions_total counter present", "kernl_decisions_total" in text)
    check("kernl_decision_latency_ms histogram present", "kernl_decision_latency_ms" in text)

    c.close()
    print(f"\nResults: {_passed} passed, {_failed} failed  (tenant {co})")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
