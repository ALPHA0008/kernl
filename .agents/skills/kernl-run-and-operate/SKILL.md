---
name: kernl-run-and-operate
description: Load this skill when you need to START, CALL, or OPERATE the Kernl backend - launching uvicorn, provisioning a tenant, hitting any /v1 endpoint (decisions, ledger, escalations, replays, onboarding, bundles), running the smoke/stress scripts, or deploying. Provides the full /v1 endpoint reference, auth model, copy-pasteable curl runbooks, and known operating limits (verified via real load testing).
---

# kernl: Run and Operate

**What this covers:** starting the API, every `/v1` HTTP endpoint (request/response shapes), auth, the onboarding-to-decision runbook, smoke/stress tooling, deploy, and verified operating limits.
**When NOT to use this:** environment setup / installing deps -> `kernl-build-and-env`. Architecture internals (bundle IR, evaluator, ledger) -> `kernl-architecture-contract`. Something is broken -> `kernl-debugging-playbook`. Running golden-case replay -> `kernl-validation-and-qa`. Changing runtime behavior -> `kernl-change-control`.

**Jargon (defined once):**
- **Bundle** — the compiled, content-addressed policy artifact (`backend/bundle/schema.py`). Immutable once published; `bundle_hash` identifies it.
- **Ledger** — the append-only, hash-chained decision log (`backend/ledger/`). Every decision is a row before the HTTP response returns (write-ahead).
- **Draft** — a proposed policy (possibly LLM-extracted) that is NOT authority until it has a verified evidence span and is accepted + assembled + published.
- **Principal** — the resolved identity behind an `X-API-Key`: `{company_id, role}`.

---

## 1. Start the API

Run from the **repo root** (imports are `backend.*`):

```bash
cd /path/to/Kernl
KERNL_ADMIN_KEY="<pick-a-bootstrap-secret>" uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

```powershell
$env:KERNL_ADMIN_KEY = "<pick-a-bootstrap-secret>"
uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

**Env vars** (all optional except as noted):

| Var | Effect |
|---|---|
| `KERNL_DB_URL` (or `SUPABASE_DB_URL`) | Set -> Postgres adapters, real persistence. Unset -> in-memory reference stores (fine for dev/tests, **volatile — data is lost on restart**). |
| `KERNL_ADMIN_KEY` | Gates `POST /v1/tenants`. **Unset = provisioning is closed** (fails closed, not open) — you cannot create a new tenant without it. |
| `KERNL_API_KEYS` | Static bootstrap tenant keys: `"<key>:<company_id>:<role>[,...]"`, roles are `owner`\|`approver`\|`agent`. Optional — tenants provisioned via `/v1/tenants` get DB-backed keys instead. |
| `KERNL_SIGNING_KEY` | Ed25519 private key (64 hex chars) used to sign published bundles. Generate with `python -m backend.bundle.signing`. **Unset -> bundles publish UNSIGNED** (explicitly recorded as such; `/v1/bundles/active` reports `signed:false`). Set it in production; the absence is visible, never silent. The matching public key is returned on every bundle response (`signing_pubkey`) so verifiers need no separate distribution. |

**Health check:**
```bash
curl http://127.0.0.1:8000/v1/health
```
`{"status": "ok"}` if the process is up and the container initialized. This does NOT ping the DB — a DB outage surfaces as a 503 on the first request that needs storage, not on `/v1/health`.

Ports: the Dockerfile and `README.md` frontmatter now agree on **7860** (the HF Spaces convention; the Dockerfile honors `$PORT` and falls back to 7860). This skill's local runbooks use **8000** purely by convention — locally, any free port works as long as `--port` and your client agree. (Historical note: the Dockerfile used to hardcode 8081 while the README said 7860, so HF forwarded to a dead port; reconciled 2026-07-17.)

---

## 2. Auth model

Every `/v1` route except `/v1/health` and `/v1/tenants` (provisioning) requires `X-API-Key`. No key configured for a request => 401 (fail closed, never open — this is a constitutional rule, not a convenience default).

Three roles, strictly increasing scope:
- **agent** — evaluate decisions, read.
- **approver** — agent + resolve escalations.
- **owner** — approver + author/publish bundles, manage onboarding, provision nothing (provisioning itself needs the separate admin key).

`POST /v1/tenants` is the one bootstrap exception: it needs `X-API-Key: <KERNL_ADMIN_KEY>`, not a tenant key (a new tenant has no key yet). It returns the tenant's **owner** key **once, in plaintext** — the store only ever keeps its hash. Save it immediately; there is no recovery endpoint.

---

## 3. Endpoint reference

Base URL `http://127.0.0.1:8000` (or wherever you bound uvicorn). All bodies JSON unless noted. Verified directly against `backend/v1_api.py` route decorators (2026-07-16).

| Method + path | Role | Purpose |
|---|---|---|
| `GET /v1/health` | none | Liveness only. |
| `GET /v1/metrics` | agent+ | Prometheus text: `kernl_decisions_total`, `kernl_decision_latency_ms` histogram, `kernl_escalations_opened_total`, `kernl_escalations_resolved_total`, `kernl_publishes_total`. |
| `GET /v1/me` | agent+ | Resolve the calling key: `{company_id, role}`. |
| `POST /v1/tenants` | admin key | Provision a tenant, issue its owner key (shown once). |
| `GET /v1/tenants` | admin key | List tenants. |
| `POST /v1/sources` | owner | Upload a raw source doc (`{filename, content}`) for evidence grounding. |
| `GET /v1/sources` / `GET /v1/sources/{id}` | owner | List / fetch uploaded sources. |
| `POST /v1/onboarding/extract` | owner | LLM-assisted draft proposal from a source (never publishable on its own — draft only). |
| `POST /v1/onboarding/drafts` | owner | Author a policy draft directly (typed, not LLM). |
| `GET /v1/onboarding/drafts[/{id}]` | owner | List / fetch drafts. |
| `POST /v1/onboarding/drafts/{id}/ground` | owner | Attach a verified `(source_id, span_start, span_end, excerpt)` citation. **400 if the excerpt doesn't byte-match the source at that span** — no uncited norm, ever. |
| `DELETE /v1/onboarding/drafts/{id}/evidence/{index}` | owner | Remove a citation. |
| `POST /v1/onboarding/drafts/{id}/status` | owner | Accept/reject a draft. Only accepted + cited drafts assemble. |
| `POST /v1/onboarding/assemble` | owner | Assemble accepted drafts into a candidate bundle record. |
| `GET /v1/bundles` | owner | Bundle registry (draft/published/superseded). |
| `GET /v1/bundles/active` | agent+ | The live published bundle. 404 if the tenant has never published. |
| `POST /v1/bundles/drafts` | owner | Register a raw draft bundle (bypasses onboarding; used by tests/seed scripts). |
| `POST /v1/bundles/{id}/publish` | owner | **409 unless a replay run for this exact bundle hash has been acknowledged.** The publish gate — no bundle goes live without a blast-radius check. |
| `POST /v1/bundles/{id}/activate` | owner | Roll back/forward the active pointer to a previously published bundle. Never mutates history. |
| `POST /v1/replays` | owner | Run a candidate bundle against the golden case set + reference bundle. |
| `GET /v1/replays[/{run_id}]` | owner | Replay reports (flips, new escalations, unchanged count). |
| `POST /v1/replays/{run_id}/acknowledge` | owner | Unlocks publish for that bundle hash. |
| `GET /v1/cases` | owner | Golden case corpus for this tenant. |
| `POST /v1/decisions/evaluate` | agent+ | The core call: `{workflow, facts, idempotency_key}` -> ledgered decision. Same idempotency key replays the original (created=false), never re-evaluates. |
| `GET /v1/decisions/{event_id}` | agent+ | Full trace: every policy considered, why it matched/failed/was excluded, the precedence winner. |
| `GET /v1/ledger` | agent+ | Paged, filterable (workflow/outcome) event browser. |
| `GET /v1/ledger/verify` | agent+ | Walks the hash chain; `{chain_valid: bool}`. |
| `GET /v1/escalations[/{id}]` | approver+ | The inbox. |
| `POST /v1/escalations/{id}/resolve` | approver+ | Adjudicate: `{chosen_action, outcome_kind, rationale, promote_to_golden?}`. Rationale is mandatory. Ledgered as a linked adjudication event. |
| `GET /v1/drafts` | owner | (Legacy alias surface for onboarding drafts — prefer `/v1/onboarding/drafts`.) |

**Guarantees surfaced at this layer** (from `backend/v1_api.py`'s own docstring):
- Write-ahead: a 200 from `/decisions/evaluate` means the ledger row is already committed.
- 503 on ledger/storage failure — never a fixture, never a silent fallback.
- 400 on malformed facts / unknown workflow — a request error, not a decision (nothing is ledgered).

---

## 4. Onboarding-to-decision runbook

Full loop, minimal case (see `scripts/smoke_test.py` for the exhaustive version this is drawn from):

```bash
ADMIN=<your KERNL_ADMIN_KEY>
BASE=http://127.0.0.1:8000

# 1. Provision a tenant, capture the owner key
curl -s -X POST $BASE/v1/tenants -H "X-API-Key: $ADMIN" \
  -d '{"company_id":"acme","name":"Acme Inc"}'
# -> {"owner_api_key": "kk_...", ...}  SAVE THIS, shown once.
OWNER=kk_...

# 2. Upload a source, author + ground a draft
curl -s -X POST $BASE/v1/sources -H "X-API-Key: $OWNER" \
  -d '{"filename":"refund.md","content":"Annual plans refunded in full within 14 days."}'
# -> {"source_id": "..."}

curl -s -X POST $BASE/v1/onboarding/drafts -H "X-API-Key: $OWNER" \
  -d '{"proposed": {"id":"refund.annual_14d","workflow":"refund","effect":{"kind":"approve","action":"approve_full_refund"},"priority":70,"conditions":[{"field":"days_since_purchase","operator":"lte","value":14,"value_type":"number"}],"authority":{"approval_required":false},"evidence":[],"overrides":[],"unconditional_ack":false,"rationale":"..."}}'
# -> {"draft_id": "..."}

curl -s -X POST $BASE/v1/onboarding/drafts/<draft_id>/ground -H "X-API-Key: $OWNER" \
  -d '{"source_id":"<source_id>","span_start":0,"span_end":45,"excerpt":"Annual plans refunded in full within 14 days."}'
# excerpt MUST byte-match the source at that span exactly, or 400.

curl -s -X POST $BASE/v1/onboarding/drafts/<draft_id>/status -H "X-API-Key: $OWNER" \
  -d '{"status":"accepted"}'

# 3. Assemble, replay, publish
curl -s -X POST $BASE/v1/onboarding/assemble -H "X-API-Key: $OWNER"
# -> {"record_id": "..."}

curl -s -X POST $BASE/v1/replays -H "X-API-Key: $OWNER" \
  -d '{"candidate_record_id":"<record_id>"}'
# -> {"run_id": "..."}

curl -s -X POST $BASE/v1/replays/<run_id>/acknowledge -H "X-API-Key: $OWNER"
curl -s -X POST $BASE/v1/bundles/<record_id>/publish -H "X-API-Key: $OWNER"

# 4. Evaluate a decision
curl -s -X POST $BASE/v1/decisions/evaluate -H "X-API-Key: $OWNER" \
  -d '{"workflow":"refund","facts":{"days_since_purchase":9},"idempotency_key":"demo-1"}'
```

---

## 5. Smoke and stress tooling

```bash
KERNL_ADMIN_KEY=<key> python scripts/smoke_test.py --base-url http://127.0.0.1:8000
KERNL_ADMIN_KEY=<key> python scripts/stress_test.py --base-url http://127.0.0.1:8000 [--workers N --per-worker N]
```

Both provision a throwaway tenant (`smoke-<hex>` / `stress-<hex>`), run their full loop, and print pass/fail. Never touches seeded reference data (`rivanly-inc`). See `kernl-validation-and-qa` for the golden-case replay suite, which is a different thing (bundle correctness, not API load).

---

## 6. Verified operating limits

From this session's actual load testing (`scripts/stress_test.py`), not estimated:

- **Concurrency**: the current dev topology (`backend/stores_pg.py`) uses one Postgres connection per store, guarded by a lock — deliberate, documented "correctness first, pooling is a later, measured optimization." At 2 concurrent writers per tenant it's clean (P50 ~3s, P95 ~4s against live Supabase). At 4+ concurrent writers on the SAME tenant, tail latency balloons (P99 observed >30s) as writes queue behind the lock.
- **Concurrent-write correctness**: two decisions for the same tenant racing to seal against the same ledger head is a real, previously-found bug — it's now handled by a bounded retry (`backend/ledger/service.py`, `_MAX_CHAIN_CONFLICT_RETRIES = 8`); exhausting retries surfaces as a clean `503`, never data loss or corruption (verified: hash chain always validates, exact event counts, no duplicates, even under contention).
- **Idempotency**: safe to retry any `/v1/decisions/evaluate` call with the same `idempotency_key` under any concurrency level — verified under literal connection resets during stress testing.
- **numpy is pinned `<2`** (`backend/requirements.txt`) — an unpinned resolve pulls a version binary-incompatible with the installed pandas, which used to be able to crash the whole process via `backend/api.py`'s legacy import chain. That legacy surface is now retired (see below), so this is lower-stakes than it was, but keep the pin.

---

## 7. What's NOT here anymore

`backend/api.py` used to mount a whole pre-ledger surface: unauthenticated source upload to local disk, an LLM compile pipeline (`POST /compile`, SSE streaming, `skills_files`/`brain_json` blobs in Supabase), a skills marketplace, semantic diff, and the free-text `/agent/handle` + `/agent/query` endpoints. **All of it is retired as of 2026-07-16** — every one of those routes now returns `410 Gone` with a pointer to the `/v1` equivalent. It was unauthenticated, unledgered, and its eager LLM-pipeline import (`langgraph` -> `transformers` -> `sklearn` -> `pandas`) was a single point of failure that could take down `/v1` on an unrelated dependency break (which is exactly what happened before this retirement). The underlying modules (`backend/engine/`, `backend/core/llm.py`, `backend/runtime/brain_agent.py`) still exist and are still directly importable by `backend/tests/eval_harness.py` and the diagnostics scripts under `kernl-diagnostics-and-tooling` — only the live HTTP surface is gone. If you're looking for the old SSE/compile runbook, it no longer applies; do not resurrect it without reading `kernl-change-control` first.

---

## 8. Deploy

**Backend → Hugging Face Spaces** (if still targeting this): Space is configured by `README.md` frontmatter (`sdk: docker`, `app_port: 7860`). The Dockerfile now binds `${PORT:-7860}` and `EXPOSE`s 7860, matching the frontmatter — HF routes external traffic to `app_port` (7860) and the container listens there. (Reconciled 2026-07-17; it previously bound 8081 while the README said 7860, so the Space was unreachable.)

**Secrets:** never bake credentials into the image or README. Set `KERNL_DB_URL`, `KERNL_ADMIN_KEY`, `KERNL_API_KEYS`, `KERNL_SIGNING_KEY` via the platform's secret store only. A Hugging Face token was leaked in git history (commit 22ee2f0, old `backend/llm.py`) — treat as compromised, do not reproduce it.

**Frontend.** Next.js app under `frontend/`. `npm run build && npm run start` for production serving — **`npm run dev` has a known Turbopack root-inference issue on some Windows/Git-Bash setups; if it crash-loops or spawns runaway processes, verify `frontend/next.config.ts` has `turbopack.root` pinned** (fixed 2026-07-16). Points at `NEXT_PUBLIC_KERNL_API_URL`, defaulting to `http://127.0.0.1:8000`.

---

## Provenance and maintenance

Facts verified against the repo on **2026-07-16**. Re-verify volatile facts before trusting them:

| Fact | Re-verify with (from repo root) |
|---|---|
| Full /v1 route list | `grep -n "@router\.(get\|post\|delete\|put)" backend/v1_api.py` |
| Auth roles + env vars | `sed -n '1,35p' backend/v1_api.py` (module docstring) |
| Admin-key gate on provisioning | `grep -n "require_admin" backend/v1_api.py` |
| Storage selection (Postgres vs in-memory) | `grep -n "KERNL_DB_URL" backend/v1_container.py` |
| Legacy surface fully retired | `grep -n "_RETIRED_LEGACY_ROUTES" backend/api.py` |
| Chain-conflict retry bound | `grep -n "_MAX_CHAIN_CONFLICT_RETRIES" backend/ledger/service.py` |
| numpy pin | `grep -n "numpy" backend/requirements.txt` |
| Dockerfile/HF port aligned on 7860 | `grep -n "PORT\|EXPOSE" Dockerfile; head -9 README.md` |
| Turbopack root fix | `grep -n "turbopack" frontend/next.config.ts` |
| Leaked-token commit (do not print contents) | `git log --oneline 22ee2f0 -1` |
