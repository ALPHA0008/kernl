---
name: kernl-run-and-operate
description: Load this skill when you need to START, CALL, or OPERATE the kernl backend - launching uvicorn, hitting any HTTP endpoint (/health, /compile, /agent/query, /skills, /diff), watching a compile over SSE, running a compile or agent-query runbook, finding where artifacts land (last_compiled_brain.json, Supabase tables, eval JSONs), inspecting a compiled brain, or deploying to Hugging Face Spaces. Provides the full endpoint reference, the SSE event contract, copy-pasteable curl runbooks, the artifact-conventions table, and shared-gateway/Supabase etiquette.
---

# kernl: Run and Operate

**What this covers:** starting the API, every HTTP endpoint (request/response shapes), the SSE streaming contract, compile and query runbooks, inspection tooling, where every artifact lands, HF Spaces deploy, and operating limits.
**When NOT to use this:** environment setup / installing deps → `kernl-build-and-env`. Env vars, thresholds, and flags → `kernl-config-and-flags`. Pipeline internals (nodes, LangGraph fan-out) → `kernl-architecture-contract` and `knowledge-compilation-reference`. Something is broken → `kernl-debugging-playbook`. Running the eval harness → `kernl-validation-and-qa`. Changing any of this behavior → `kernl-change-control`.

**Jargon (defined once):**
- **Brain / skills file** — the compiled JSON output of the pipeline: `{skills, graph_json, metadata_json, meta}` (backend/engine/nodes/write_brain.py:41-53). "Skills" here are structured policy rules, not Claude skills.
- **Compile** — running the LangGraph pipeline that turns files in `data/sources/<company_id>/` into a brain.
- **vLLM gateway** — a shared, rate-limited HTTP proxy in front of the LLM. All pipeline and agent LLM calls go through it (backend/core/llm.py). It is a LIVE shared resource.
- **Supabase** — the live hosted Postgres this repo writes to. Also shared and live.
- **Constraint resolver** — deterministic engine (backend/runtime/constraint_resolver.py) that picks the action at query time; the LLM only verbalizes it.

---

## 1. Start the API

Run from the **repo root** — every import is `backend.*` (e.g. backend/api.py:22), so uvicorn must be launched where the `backend/` package is visible.

```powershell
# PowerShell (repo path contains a space - always quote it)
cd "d:\Abhijith P\Desktop\Project\kernl"
uvicorn backend.api:app --port 8081
```

```bash
# bash / Git Bash
cd "/d/Abhijith P/Desktop/Project/kernl"
uvicorn backend.api:app --port 8081
```

Port **8081** is the convention: the Dockerfile CMD uses it (Dockerfile:31) and the frontend defaults to `http://localhost:8081` (frontend/src/lib/api.ts:1-2). (as of 2026-07-07)

**Health check** (in PowerShell use `curl.exe`, not the `curl` alias):

```bash
curl http://localhost:8081/health
```

Response (backend/api.py:55-63, backend/core/llm.py:68-80):

| Field | Meaning |
|---|---|
| `status` | Always `"ok"` if the API process is up. Says nothing about dependencies. |
| `vllm.healthy` | `true` iff `GET {VLLM_BASE_URL}/health` returned 200 within 10s. |
| `vllm.url` | The gateway URL in use (env `VLLM_BASE_URL`; default at backend/core/llm.py:13). |
| `vllm.mode` | Always `"vllm_gateway"` on success; on failure the dict is `{healthy: false, error: "..."}` with no `url`/`mode`. |
| `database` | `"connected"` if the Supabase client initialized, else `"not configured"`. It does NOT ping the DB. |

`vllm.healthy: false` → compiles and queries will fail. `database: "not configured"` → compiles fail at write_brain; queries fall back to the local brain file (section 5).

---

## 2. Endpoint reference

All verified against backend/api.py (as of 2026-07-07). Base URL `http://localhost:8081`. All bodies are JSON unless noted.

| Method + path | Request | Response | Notes (api.py line) |
|---|---|---|---|
| `GET /health` | — | `{status, vllm, database}` | :55 |
| `POST /compile` (alias `POST /compile/run`) | `{"company_id": str, "force_recompile": bool=false}` | `{job_id, status:"started"}` | :200-201. 400 if `data/sources/<company_id>/` is missing/empty. `force_recompile` is accepted but never read — every call compiles. Inserts a `compile_runs` row, runs pipeline as a background task. |
| `GET /compile/{job_id}/stream` | — | SSE stream (section 3) | :229 |
| `GET /compile/{job_id}/status` | — | `compile_runs` row: `{id, company_id, status, started_at, completed_at, duration_ms, result_version, error_detail}` or `{status:"not_found"}` | :237. Poll this if you missed the SSE stream. |
| `POST /sources/upload` | multipart form: `company_id` field + `file` | `{filename, sha256, status:"uploaded"}` | :73. Writes to `data/sources/<company_id>/` on the API host AND inserts a `source_files` DB row. |
| `GET /sources/{company_id}` | — | `{files: [{filename, size_bytes, sha256}], company_id}` | :102. Reads local disk, not DB. |
| `DELETE /sources/{company_id}/{filename}` | — | `{status:"deleted", filename}` | :123. Deletes local file + DB row. 404 if absent. |
| `POST /agent/handle` | `{company_id, scenario, context?, with_brain=true}` | agent response (section 5) | :251. **Legacy field names** (schemas.py:10-16). The demo frontend page still posts here (frontend/src/app/demo/[companyId]/page.tsx:47-48) — do not remove without a frontend change. |
| `POST /agent/query` | `{company_id, scenario_text, json_context?, with_brain=true}` | same agent response | :259. **Canonical** schema (schemas.py:19-25). Both routes call the same `handle_agent_query`. |
| `GET /skills?company_id=X` | query param | raw `brain_json` of the **most recently compiled** brain (ordered by `compiled_at`) | :273. Legacy. |
| `GET /skills/{company_id}` | — | `{skills, version, compiled_at, source_hashes, brain_id}` of the **`is_current`** brain | :291. Note: this and the legacy route can disagree if an import or manual DB edit changed `is_current`. |
| `GET /brain/versions/{company_id}` | — | `{versions: [{id, version, compiled_at, is_current, source_count, skill_count}], company_id}` | :319 |
| `GET /skills/{company_id}/download` | — | the `brain_json` as a file attachment `skills_<company>_<version>.json` | :360. Uses the `is_current` brain; 404 if none. |
| `POST /skills/import` | `{company_id, version="imported", skills:[...], source_label="marketplace_import"}` | `{status:"imported", company_id, version, skill_count, skills_file_id}` | :386. Flips `is_current` to the imported brain (backend/core/db/supabase.py:167-174) — this changes what `/skills/{company_id}` serves. |
| `GET /diff/{v1}/{v2}?company_id=X` | v1/v2 are version strings like `v_1750000000` (from `/brain/versions`) | `{v1_version, v2_version, added, deleted, modified, confidence_shifts, summary}` | :410. 404 if either version missing. |

**Known break — endpoints the frontend calls that DO NOT exist** (as of 2026-07-07): `GET /companies/{id}` (frontend/src/app/page.tsx:36) and `GET /auth/config` (frontend/src/lib/auth.tsx:30). The dashboard and auth flow 404 against this backend. Fixing this is a contract change — see `kernl-change-control`.

---

## 3. SSE event contract

SSE (Server-Sent Events): a long-lived HTTP response of `data: ...\n\n` frames. Implementation: backend/core/sse.py.

- Events are **unnamed** (no `event:` line) so browser `EventSource.onmessage` fires (sse.py:19-21). Do not add named events without a frontend change.
- Every frame is `data: {"event": "<type>", "data": {...}}\n\n` — the type lives INSIDE the JSON payload.
- Event types: `pipeline_start` (api.py:172), `stage` (each node emits `{name, detail}` at start and end), `pipeline_complete` (write_brain.py:168-178, payload `{status:"success", version, skills_count, source_count, duration_ms}`), `pipeline_error` (`{error, traceback?}`), `timeout`.
- **Idle timeout:** if no event arrives for 300s the stream emits `{"event":"timeout","data":{}}` and closes (sse.py:26-32). Individual LLM-heavy stages normally emit well within this.
- The stream ends after `pipeline_complete` or `pipeline_error`, and the per-job queue is **deleted** (sse.py:33-35). Consequences: (a) only ONE consumer per job — a second connection steals/loses events; (b) connecting after the job finished gets nothing and hangs until the 300s timeout fires. Use `/compile/{job_id}/status` instead.

Expected `stage.name` sequence for a successful compile (extraction block is parallel, order varies): `LOADING_DOCS(_DONE)` → `CHUNKING(_DONE)` → `EXTRACT_DECISIONS / EXTRACT_WORKFLOWS / EXTRACT_EXCEPTIONS / DETECT_CONTRADICTIONS / EXTRACT_ENTITIES` (each with `_DONE`) → `BUILD_GRAPH(_DONE)` → `DISCOVER_METADATA(_DONE)` → `SYNTHESIZING_SKILLS / SYNTHESIZING_DONE` → `LINKING_EVIDENCE / LINKING_DONE` → `SCORING_CONFIDENCE / SCORING_DONE` → `WRITING_DB` → `DONE` → `pipeline_complete`. (Names verified in backend/engine/nodes/*.py; pipeline order in backend/engine/graph.py:31-85.)

---

## 4. Compile runbook (rivanly-inc)

**Read the frugality warning in section 8 first.** A full compile makes dozens of LLM calls against the shared gateway and writes rows to live Supabase. Do not compile to "see if it works" — use `/health` and existing artifacts.

1. Confirm sources exist: `data/sources/rivanly-inc/` ships with 8 files (5 notion `.md`, 2 slack `.json`, 1 zendesk `.json`).
2. Start the compile:
   ```bash
   curl -X POST http://localhost:8081/compile \
     -H "Content-Type: application/json" \
     -d '{"company_id": "rivanly-inc"}'
   # -> {"job_id": "<uuid>", "status": "started"}
   ```
   (PowerShell: `curl.exe -X POST http://localhost:8081/compile -H "Content-Type: application/json" -d '{\"company_id\": \"rivanly-inc\"}'`)
3. Watch it live (attach promptly — one consumer only, see section 3):
   ```bash
   curl -N http://localhost:8081/compile/<job_id>/stream
   ```
4. Or poll: `curl http://localhost:8081/compile/<job_id>/status` until `status` is `complete` or `error`.

**Timeline:** the reference brain (compiled 2026-06-15) took 291,170 ms (~4.9 min) and produced 12 skills for rivanly-inc (backend/tests/last_compiled_brain.json `meta`). Hard ceiling: `asyncio.wait_for(..., timeout=600.0)` — 600s, after which `pipeline_error` fires and `compile_runs` is marked `error` (api.py:174-197).

**Where results land** (write_brain.py:73-153): Supabase only —
- `skills_files`: new row with full `brain_json`, `version` = `v_<unix-epoch>`, `is_current=true` (previous current flipped to false);
- `skills`: one row per skill (embedding stripped);
- `operational_entities`, `relationship_edges`: graph rows;
- `compile_runs`: updated to `complete` with `duration_ms` and `result_version`.

**An API compile does NOT write `backend/tests/last_compiled_brain.json`.** That file is written only by the standalone script backend/test_compile.py:124-130 (which runs the same graph directly, bypassing the API and DB-status updates). If you need a fresh local brain file, that script is the tool — but it burns the same gateway budget as a full compile.

---

## 5. Query runbook (/agent/query)

Worked example — the refund SOP (data/sources/rivanly-inc/notion_refund_sop.md:9 says annual-plan refunds within 14 days are auto-approved):

```bash
curl -X POST http://localhost:8081/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "rivanly-inc",
    "scenario_text": "A customer on an annual plan purchased 10 days ago is requesting a full refund.",
    "json_context": {"plan": "annual", "days_since_purchase": 10, "amount": 588},
    "with_brain": true
  }'
```

`json_context` keys are matched against compiled skill conditions by lowercase field name; numeric strings are coerced to float, `"true"/"yes"` to booleans (backend/runtime/brain_agent.py:239-252). `with_brain: false` returns a no-context generic-LLM baseline for A/B comparison (brain_agent.py:812-819).

**Brain loading order** (brain_agent.py:602-641): the **most recently compiled** `skills_files` row for the company (ordered by `compiled_at`, NOT `is_current`); if the DB is unreachable, falls back to the local file `backend/tests/last_compiled_brain.json`; if both fail you get an error-shaped response with the reason in `reasoning`.

**How to read the response** (all fields set in brain_agent.py:787-809):

| Field | What it tells you |
|---|---|
| `action_type` | The decision (e.g. `approve`, `deny`, `escalate`, or `ambiguous`). Set by the constraint resolver, not the LLM — the guardrail overrides any LLM divergence. |
| `constraint_result` | The resolver's full verdict: `{primary_action, all_admissible_actions, is_ambiguous, entropy, escalation_required, escalation_target, resolution_source, reasoning_steps}` (constraint_resolver.py:85-99). `resolution_source` is `"graph"` (typed policy from the operational graph) or skill-retrieval. Read `reasoning_steps` first when debugging a wrong answer. |
| `retrieval_trace` | Why the top skill won: `{top_skill, final_score, components {semantic_confidence, operational_confidence, keyword_score, ...}, matched_conditions, why_matched, runner_up, why_runner_up_lost}` (brain_agent.py:423-483). |
| `_guardrail_fired` / `_guardrail_reason` | `true` means the LLM's verbalization disagreed with (or omitted) the resolver's action and was overridden (backend/runtime/guardrails.py:14-52). Frequent firing on a scenario class = retrieval or prompt problem, see `kernl-debugging-playbook`. |
| `graph_used` / `graph_reasoning` / `graph_policies` | Whether the operational-graph retriever answered with confidence ≥ the `graph_fallback_threshold` (default 0.5, brain_agent.py:34), plus its steps and matched policies. |
| `recommended_action`, `rule_applied`, `evidence`, `reasoning` | Human-readable explanation layer (LLM-generated; trust `action_type`/`constraint_result` over prose). |
| `retrieval_scores`, `cached_embedding`, `decision_trace.candidate_entropy` | Top-5 hybrid scores; whether stored embeddings were used; normalized entropy over candidate actions (1.0 = maximally ambiguous). |

Each query makes one gateway LLM call (plus embeddings computed locally on CPU). Cheap compared to a compile, but still shared-resource traffic.

---

## 6. Inspection tools

| Tool | Command (from repo root) | What you get |
|---|---|---|
| Brain pretty-printer | `python backend/show_brain.py` | Prints `backend/tests/last_compiled_brain.json`: compiled_at, duration, every skill (confidence / dept / rule / evidence count), graph stats + entities + edges + authority rules, and operational metadata (action types, valid sets, authority levels). Path is hard-coded relative (`show_brain.py:3`) — MUST run from repo root, and shows the local file, which may be older than what is in the DB. |
| Download current brain | `curl -o brain.json http://localhost:8081/skills/rivanly-inc/download` | The `is_current` brain as JSON. |
| List versions | `curl http://localhost:8081/brain/versions/rivanly-inc` | All compiled versions with skill/source counts. |
| Diff two versions | `curl "http://localhost:8081/diff/v_1750000000/v_1750100000?company_id=rivanly-inc"` | Added/deleted/modified skills and confidence shifts between the two version strings. |

---

## 7. Artifact conventions — what lands where

| Artifact | Producer | When |
|---|---|---|
| Supabase `skills_files` row (+ `skills`, `operational_entities`, `relationship_edges`) | `write_brain` node (backend/engine/nodes/write_brain.py) | Every successful compile via API. New `v_<epoch>` version becomes `is_current`. Also written by `POST /skills/import`. |
| Supabase `compile_runs` row | `POST /compile` (insert) + `write_brain`/error handler (update) | Every compile attempt. |
| Supabase `source_files` row + file under `data/sources/<company>/` | `POST /sources/upload` | Every upload. |
| `backend/tests/last_compiled_brain.json` | **backend/test_compile.py only** (:124-130) | Manual standalone compile run. Read by show_brain.py and as the agent's DB fallback. NOT touched by API compiles. |
| `backend/tests/higgsfield_brain.json` | backend/test_higgsfield.py (:62) | Manual second-company compile test. |
| `backend/tests/eval_results_baseline.json` | eval harness (backend/tests/eval_harness.py:1003) via backend/start_eval.py | Eval run (see `kernl-validation-and-qa`). |
| `backend/tests/eval_results_partial.json` | eval harness checkpointing (eval_harness.py:728) | Mid-eval, so a killed run is not a total loss. |
| `backend/tests/resolver_eval_results.json` | backend/tests/resolver_only_eval.py (:228) | Resolver-only (no LLM) eval. |
| `eval_output.log` + `run_eval_background.py` | backend/start_eval.py (:24-31) | Written to the **current working directory** where you launched it — that is why stray copies appear at repo root or `backend/`. |
| Full DB schema | backend/schema.sql (7 tables) | Reference for what the rows above look like. |

---

## 8. Deploy

**Backend → Hugging Face Spaces.** The Space is configured by the README **frontmatter** (README.md:1-9): `sdk: docker`, `app_port: 7860`. HF builds the root Dockerfile and routes external traffic to `app_port`.

> **Port mismatch warning (as of 2026-07-07):** the frontmatter says `app_port: 7860` but the Dockerfile listens on 8081 (`EXPOSE 8081`, `CMD [... "--port", "8081"]`, Dockerfile:29-31). As written, HF forwards to 7860 where nothing listens. Reconcile one side (a contract change — `kernl-change-control`) before expecting the Space to serve traffic.

Dockerfile facts worth knowing: it copies `backend/` and `data/`, sets `PYTHONPATH=/app` (which is why `backend.*` imports work in the container), and `chmod 777`s `/app/data` so uploads work as the HF non-root user (Dockerfile:18-27).

**Secrets:** never bake credentials into the image or README. A Hugging Face token was leaked in git history (commit 22ee2f0, in the old backend/llm.py) — treat it as **compromised; it must be revoked**. Do not reproduce it or the `VLLM_API_KEY` default (see backend/core/llm.py:14) anywhere. Set secrets via HF Space secrets / env vars only.

**Frontend.** Next.js app under `frontend/`; standard `npm run dev` on port 3000 (frontend/README.md). It assumes the backend at `NEXT_PUBLIC_API_URL`, defaulting to `http://localhost:8081` (frontend/src/lib/api.ts:1-2). Two of its calls (`/companies/{id}`, `/auth/config`) have no backend implementation (section 2), and the demo page still uses the legacy `/agent/handle` schema — factor both into any deploy plan. Frontend Next.js version has breaking changes vs. training data — read frontend/AGENTS.md before touching it.

---

## 9. Operating limits and etiquette

The gateway and the database are **shared, live infrastructure**. Rules of the road:

1. **Concurrency ceiling:** all LLM calls in this process share `asyncio.Semaphore(4)` (backend/core/llm.py:16). Do not raise it; the gateway is shared with other users.
2. **Backoff schedule:** on 429/413/rate-limit errors, retry up to 5 attempts with waits of `2^(attempt+1) * 5` seconds = 10s, 20s, 40s, 80s (llm.py:115-121). Other errors get two quick 2s retries then raise. A rate-limited compile can therefore stall for minutes without being dead — check the SSE stream before killing it.
3. **Per-call timeout:** each gateway request has a 120s httpx timeout (llm.py:92); the whole pipeline has the 600s ceiling (api.py:174).
4. **Gateway frugality:** one rivanly compile = dozens of LLM calls. Batch your reasons for compiling; prefer reading `backend/tests/last_compiled_brain.json`, `/skills/{company_id}`, or `/brain/versions` over recompiling. Never loop compiles in a script.
5. **Supabase is production-live:** every compile inserts rows and flips `is_current`; `POST /skills/import` also flips `is_current`. Do not run destructive experiments against it; there is no staging DB (as of 2026-07-07).
6. **Do not run the eval harness casually** — it multiplies query-time LLM calls by the scenario count. Coordinate via `kernl-validation-and-qa`.
7. Identify yourself: pipeline calls send header `x-user-name: kernl` (llm.py:97) so gateway operators can attribute load. Keep it.

---

## Provenance and maintenance

Facts verified against the repo on **2026-07-07** (git HEAD 2ca7f83). Re-verify volatile facts before trusting them:

| Fact | Re-verify with (from repo root) |
|---|---|
| Port 8081 convention | `grep -n "8081" Dockerfile frontend/src/lib/api.ts` |
| Endpoint list & paths | `grep -n "@app\." backend/api.py` |
| 600s pipeline timeout | `grep -n "timeout=600" backend/api.py` |
| SSE 300s idle timeout, unnamed events | `grep -n "timeout=300" backend/core/sse.py` |
| Stage event names | `grep -rn '"name": "' backend/engine/nodes/` |
| Semaphore(4), backoff formula, gateway URL default | `grep -n "Semaphore\|2 \*\* (attempt\|VLLM_BASE_URL =" backend/core/llm.py` |
| Legacy vs canonical agent schemas | `grep -n "class Agent" backend/core/models/schemas.py` |
| Demo page still on /agent/handle | `grep -rn "agent/handle" frontend/src` |
| Missing frontend endpoints | `grep -rn "companies/\|auth/config" frontend/src` |
| last_compiled_brain.json writer | `grep -rn "last_compiled_brain" backend/` |
| Reference brain stats (12 skills, 291170ms, 2026-06-15) | `python -c "import json; m=json.load(open('backend/tests/last_compiled_brain.json'))['meta']; print(m)"` |
| write_brain DB targets | `grep -n "db.table(" backend/engine/nodes/write_brain.py` |
| Agent loads latest-by-compiled_at, file fallback | `grep -n "compiled_at\|_LOCAL_BRAIN" backend/runtime/brain_agent.py` |
| Guardrail override fields | `grep -n "_guardrail_fired" backend/runtime/guardrails.py` |
| HF frontmatter vs Dockerfile port mismatch | `head -9 README.md; grep -n "port" Dockerfile` |
| Eval artifact paths | `grep -rn "eval_results\|eval_output.log" backend/` |
| Leaked-token commit (do not print contents) | `git log --oneline 22ee2f0 -1` |
