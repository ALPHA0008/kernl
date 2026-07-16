---
name: kernl-debugging-playbook
description: Load this skill when something in Kernl is BROKEN or behaving strangely. For V1 (/v1 API, ledger, evaluator, replay, onboarding, console frontend) issues, see section 0 below FIRST. Sections 1+ are a legacy-pipeline playbook (compile hangs, SSE timeouts, brain has zero skills, eval harness ImportErrors) for the retired pre-V1 system - kept for archaeological reference, not applicable to /v1.
---

# Kernl: Debugging Playbook

**What this covers:** symptom -> first check -> likely cause -> fix pointer.
**When NOT to use this:** starting/calling the API normally -> `kernl-run-and-operate`. Installing deps / env setup -> `kernl-build-and-env`. Validating a change -> `kernl-validation-and-qa`. Fixing anything you diagnose here -> `kernl-change-control` first.

---

## 0. V1 issues (start here for anything /v1-related)

`backend/api.py`'s legacy surface (compile, SSE, skills marketplace, `/agent/*`) was fully retired 2026-07-16 — every route returns a clean `410`. **If you're seeing 410s and expected a legacy endpoint to work, that's not a bug** — see `kernl-run-and-operate` section 7 for the retirement rationale and the `/v1` equivalent.

| Symptom | First check | Likely cause | Fix pointer |
|---|---|---|---|
| `backend.api` import is slow (multi-second) or pulls huge memory | `python -c "import time; t=time.perf_counter(); from backend.api import app; print(time.perf_counter()-t)"` | Something re-introduced an eager import of the legacy pipeline (`backend.engine.*`) into `backend/api.py`'s module scope | Should be <1s importing only `backend.v1_api`. Check `git diff backend/api.py` against the 2026-07-16 retirement commit. |
| Server crashes on startup with a `numpy`/`pandas` ABI error | `pip show numpy` | Unpinned/upgraded numpy resolved to 2.x, binary-incompatible with pandas pulled in transitively via `sentence-transformers` | `pip install "numpy<2"`; confirm `backend/requirements.txt` still pins it |
| `POST /v1/decisions/evaluate` (or any write) returns a raw `500` under concurrent load | Check server logs for `ChainConflict`/`chain break` | Two writers for the same tenant raced to seal against the same ledger head | Should self-heal via retry (`backend/ledger/service.py`, `_MAX_CHAIN_CONFLICT_RETRIES`) and surface as a clean `503`, not a `500`, if it's still happening after 2026-07-16 that retry logic regressed |
| `POST /v1/tenants` returns 401 even with what looks like the right key | `echo $KERNL_ADMIN_KEY` in the shell that started uvicorn, not your current shell | Admin key is read once at request time from the *server process's* env, not the caller's | Restart the server with `KERNL_ADMIN_KEY` set in the same shell/session that launches uvicorn |
| `POST /v1/onboarding/drafts/{id}/ground` returns 400 on a citation you're sure is correct | Byte-compare your `excerpt` against the source at `[span_start:span_end]` exactly, including whitespace | The grounding check is a strict byte-match by design (constitutional rule 2: no uncited norm) — no fuzzy matching | Fix the span/excerpt to match exactly; this is not a bug to work around |
| `POST /v1/bundles/{id}/publish` returns 409 | `GET /v1/replays?candidate_record_id=<id>` | No acknowledged replay run for this exact bundle hash yet | Run `POST /v1/replays` then `POST /v1/replays/{run_id}/acknowledge` first — see `kernl-run-and-operate` section 4 |
| `npm run dev` spawns many `node.exe` processes / OOMs | `tasklist \|` filter on `node.exe` (Windows) | Turbopack root-inference bug on some Windows/Git-Bash setups (fixed 2026-07-16 via `turbopack.root` pin) | Confirm `frontend/next.config.ts` still has the pin; `taskkill /F /IM node.exe` to clear orphans; fall back to `npm run build && npm run start` |
| Frontend shows a raw error instead of a clean message | Check `frontend/src/lib/api.ts`'s `ApiError` and `frontend/src/components/ui/ErrorNotice.tsx` | Every `/v1` call is normalized through `ApiError`; if a screen bypasses `call()` it loses that normalization | Route the fetch through the shared client, don't hand-roll a new one |

For anything not covered above, tier 1 of `kernl-validation-and-qa` (the full deterministic suite) is the fastest way to find out if a symptom is a real regression or environmental.

---

## 1+. Legacy pipeline playbook (historical — not applicable to /v1)

Everything below describes the pre-V1 compile/SSE/eval-harness system. Its endpoints (`/compile`, `/compile/{job_id}/stream`, `/agent/query`, `/skills/*`) are retired and return `410`. Kept for archaeological reference only — do not follow these runbooks expecting them to work against the current server.

**Jargon (defined once):**
- **Brain / skills file** — the compiled JSON the pipeline produces (`{skills, graph_json, metadata_json, meta}`); "skills" are structured policy rules, not Codex skills.
- **Compile** — running the LangGraph pipeline (`POST /compile`) that turns files in `data/sources/<company_id>/` into a brain. LangGraph is a DAG orchestrator; kernl fans out five extraction nodes in parallel, then joins at a barrier node (backend/engine/graph.py).
- **vLLM gateway** — the shared, rate-limited HTTP proxy that serves ALL LLM calls. It is a custom shape: `POST {VLLM_BASE_URL}/generate` with an `x-api-key` header (backend/core/llm.py:94-98). It is NOT OpenAI-compatible; there is no `/v1/chat/completions`.
- **SSE** — Server-Sent Events; `GET /compile/{job_id}/stream` streams pipeline stage events (backend/core/sse.py).

**Ground rules while debugging:** the gateway and Supabase are LIVE shared resources. Prefer read-only probes (`/health`, log reading, file inspection) over re-running compiles or evals. Never paste the `VLLM_API_KEY` value into logs, docs, or commits — refer to backend/core/llm.py:14.

## 0. Two-minute baseline (run before anything else)

From the repo root — **the path contains a space, always quote it**:

```powershell
cd "D:\Abhijith P\Desktop\Project\kernl"      # PowerShell
# or in Git Bash:  cd "/d/Abhijith P/Desktop/Project/kernl"

# 1. Is the backend up, and can IT reach the gateway and DB?
curl.exe -s http://localhost:8081/health
# Healthy shape: {"status":"ok","vllm":{"healthy":true,"url":"...","mode":"vllm_gateway"},"database":"connected"}

# 2. Gateway reachable without the backend in the way? (reads env; never echo the key)
python backend/test_health.py
```

`/health` (backend/api.py:55-63) calls `check_vllm_health()` which does `GET {VLLM_BASE_URL}/health` with header `x-api-key` (backend/core/llm.py:68-80). `"vllm":{"healthy":false,...}` isolates the fault to gateway URL/key/network before you read a single line of pipeline code.

## 1. Symptom table

| # | Symptom | First check (exact command, repo root) | Likely cause | Fix pointer |
|---|---------|----------------------------------------|--------------|-------------|
| a | Compile hangs, then `pipeline_error` at ~600s | `curl.exe -s http://localhost:8081/health` | `asyncio.wait_for(..., timeout=600.0)` fired (backend/api.py:174); usually gateway down/slow or rate-limit backoff eating the budget | §2a |
| b | Compile "succeeds" but brain has 0/few skills | Read uvicorn console for `Node extract_*: N/M chunks relevant` and `extracted N rules` lines | `safe_llm_json_call` silently returned `[]` after two failed JSON parses (backend/core/llm.py:216-217), or 0 relevant chunks | §2b |
| c | Every LLM call fails, or "hangs" for minutes | `python backend/test_health.py` then `grep -n "VLLM_BASE_URL" backend/.env` | `VLLM_BASE_URL` has the stale OpenAI `/v1` shape from `.env.example`, or rate-limit backoff (10/20/40/80s waits) looks like a hang | §2c |
| d | Frontend 404s on `/companies/{id}` and `/auth/config` | `grep -n "companies\|auth/config" backend/api.py` (returns nothing) | Those endpoints do not exist in the backend — known break since commit 2ca7f83, not user error | §2d |
| e | "Connection refused" / wrong port | `netstat -ano \| findstr :8081` | Port confusion: canonical is 8081; 7860/8080/8000 references are stale or special-purpose | §2e |
| f | `ImportError` from `resolver_only_eval.py`; `--stability` gives all-"error" runs | `python -m backend.tests.resolver_only_eval` (fails fast, no LLM calls) | Eval scripts not updated after the brain_agent refactor — known-broken | §2f, `kernl-validation-and-qa` |
| g | Agent returns `"ambiguous"` for nearly everything | Inspect `constraint_result` and `decision_trace.constraint_entropy` in an `/agent/query` response you already have | Entropy over-fire vs `ambiguity_entropy: 0.75` threshold — this is the eval-inversion problem, not an outage | §2g, `kernl-eval-inversion-campaign` |
| h | "No compiled brain found. Please compile first." | `dir "backend\tests\last_compiled_brain.json"` and check DB `skills_files` rows | DB empty for that `company_id` AND the local fallback file is missing | §2h |
| i | First `/agent/query` after boot takes very long; retrieval quality poor on long rules | Watch console for HuggingFace download progress on first call | Embedding model downloads on first use; separately, inputs are truncated at 128 tokens | §2i |
| j | SSE stream ends with `{"event":"timeout"}` | Did any stage event arrive in the last 5 min? Re-check job: `curl.exe -s http://localhost:8081/compile/<job_id>/status` | 300s idle timeout on the event queue (backend/core/sse.py:26) — stream died, job may still be running | §2j |
| k | Commands fail weirdly only on this machine (Windows) | Is your CWD the repo root? Is the path quoted? | Unquoted space in `D:\Abhijith P\...`, or `backend.*` imports run from the wrong directory | §2k |

## 2. Discriminating experiments per symptom

### 2a. Compile hangs or dies at ~600 seconds

The whole graph runs inside `asyncio.wait_for(graph.ainvoke(initial_state), timeout=600.0)` (backend/api.py:174). On timeout the SSE stream gets `pipeline_error` with `"Pipeline execution timed out after 600 seconds."` (backend/api.py:177-178) and `compile_runs.status` is set to `error`.

Triage order:
1. `curl.exe -s http://localhost:8081/health` — if `vllm.healthy` is false, it's the gateway, stop here. Fix `VLLM_BASE_URL`/key per §2c.
2. If healthy: check the uvicorn console for `[vLLM Gateway] Rate limit hit, waiting Ns` lines. Backoff waits are 10/20/40/80s per call attempt (`2 ** (attempt + 1) * 5`, backend/core/llm.py:115-116) and each HTTP attempt itself can take up to 120s (`httpx.AsyncClient(timeout=120.0)`, backend/core/llm.py:92). Five extraction nodes run in parallel through a `Semaphore(4)` (backend/core/llm.py:16), so a rate-limited gateway can legitimately blow the 600s budget with nothing "hung".
3. If neither: read the traceback the API prints (`Graph execution failed for {job_id}:`, backend/api.py:181) — that is the real node-level error.

Do NOT raise the 600s timeout as a "fix" without going through `kernl-change-control`; the timeout is masking a throughput problem, not causing it.

### 2b. Pipeline "succeeds" but skills are missing or few — the silent-empty-list

`safe_llm_json_call` (backend/core/llm.py:161-217) parses the LLM output as JSON; on failure it retries once with a corrective prompt; if the retry also fails to parse, `except Exception: return []` (backend/core/llm.py:216-217). **No exception propagates. The node records zero extractions and the pipeline completes "successfully" with an anemic brain.**

Discriminate with the logs, not the exit status:
- Every extraction node prints two lines per run, e.g. `[{job_id}] Node extract_decisions: {N}/{M} chunks relevant` (backend/engine/nodes/extract_decisions.py:26-28) and `[{job_id}] extract_decisions: extracted {N} rules` (line 54).
- The SSE stream carries the same counts: `stage` events like `EXTRACT_DECISIONS_DONE` / `Found N rules` (extract_decisions.py:55-59), and the final `pipeline_complete` event includes `skills_count` (backend/engine/nodes/write_brain.py:170).

Decision tree:
- `0/M chunks relevant` → chunker didn't tag any chunk with that node's domain; the LLM was never called. Look at chunking, not the gateway (`knowledge-compilation-reference`).
- `N/M chunks relevant` but `extracted 0 rules` → the silent-empty-list fired: the model returned non-JSON twice (or legitimately found nothing — rare for the Rivanly corpus). Re-run is cheap to hypothesize, expensive on the shared gateway; first inspect whether OTHER nodes also got 0 (gateway-wide problem) or only one (prompt/content problem).
- Counts look right but final `skills_count` is low → loss is downstream in synthesis/scoring, not extraction.

### 2c. All LLM calls failing — URL shape, and backoff that looks like a hang

The current gateway contract (as of 2026-07-08): `POST {VLLM_BASE_URL}/generate`, headers `x-api-key` and `x-user-name: kernl`, body `{"messages":[...]}`, response JSON field `"response"` (backend/core/llm.py:93-107). Default `VLLM_BASE_URL` is `http://172.20.7.22:9000` (backend/core/llm.py:13).

**Trap:** `backend/.env.example` is STALE — its first line is `VLLM_BASE_URL=http://<MI300X_IP>:8000/v1` (backend/.env.example:1), the OLD OpenAI-compatible shape. If someone copies it, every call goes to `.../v1/generate` and fails. `AGENTS.md` lines 82-83, 100, and 381 describe the same dead `/v1` world. The repo code wins.

Checks:
```powershell
grep -n "VLLM_BASE_URL" backend/.env        # must NOT end in /v1
python backend/test_health.py               # direct gateway probe using your .env
```
If health passes but calls still "hang": that is almost certainly rate-limit backoff. `llm_call` retries up to 5 times, sleeping 10/20/40/80s on 429/413/rate-limit errors (backend/core/llm.py:110-121) — worst case 150s of pure sleep plus up to 120s per attempt, per call, silently except for console prints. Watch the console before declaring a deadlock.

### 2d. Frontend 404s on `/companies/{id}` and `/auth/config` — known break

The frontend calls `GET {API_BASE}/companies/${id}` (frontend/src/app/page.tsx:36) and `GET {API_BASE}/auth/config` (frontend/src/lib/auth.tsx:30). **Neither route exists in backend/api.py** — grep it and you will find nothing. The auth backend (`backend/auth/jwt.py`) and the login/register/onboarding pages were deleted in commit 2ca7f83 (the core/engine/runtime restructure), but `frontend/src/lib/auth.tsx` and the `page.tsx` call survived.

This is a known break, not a misconfiguration on your side. Do not "fix" it by hand-adding stub endpoints without `kernl-change-control` — the open decision is whether auth returns or the frontend remnants get removed.

### 2e. Port confusion matrix (as of 2026-07-08)

| Port | Where | Status |
|------|-------|--------|
| **8081** | Dockerfile (`EXPOSE 8081`, uvicorn CMD), frontend default `API_BASE` (frontend/src/lib/api.ts:1-2), scripts/smoke_test.py:17 | **Canonical backend port** |
| 7860 | README.md:7 (`app_port: 7860`, Hugging Face Space header) | MISMATCH vs Dockerfile's 8081 — HF Spaces expects the app on `app_port`; known inconsistency |
| 8080 | scripts/stress_test.py:20 (stale), serve_chat.py:3 (scratch chat UI, separate server) | stress_test is stale; serve_chat is intentionally its own port |
| 8000 | AGENTS.md:82-83, 100, 381 | Stale pre-refactor docs (old vLLM `/v1` world); ignore |

Canonical local start (from repo root): `python -m uvicorn backend.api:app --port 8081` (this exact hint is printed by scripts/smoke_test.py:293).

### 2f. Eval scripts: ImportError and the silently-broken `--stability`

Both are **known-broken** (as of 2026-07-08); full detail and workarounds live in `kernl-validation-and-qa`. What you'll see:

- `python -m backend.tests.resolver_only_eval` → `ImportError`. It imports `_load_skills_from_file`, `_compute_hybrid_score`, `_build_admissible_actions`, `RETRIEVAL_WEIGHTS` from `backend.runtime.brain_agent` (backend/tests/resolver_only_eval.py:20-26); after the brain_agent refactor those symbols are now `_load_file`, `_hybrid`, `_admissible`, and `_MD["retrieval_weights"]` (backend/runtime/brain_agent.py). Import fails before any LLM call, so this check is safe to run.
- `python -m backend.tests.eval_harness --stability` → does NOT crash, which is worse. `run_stability_test` calls `handle_agent_query(company_id=..., scenario=..., context=...)` (backend/tests/eval_harness.py:970-974) but the real signature is `handle_agent_query(cid, scenario, ctx=None, with_brain=True, rw=None)` (backend/runtime/brain_agent.py:635). The `TypeError` is swallowed by the surrounding `except Exception`, every run records `action_type: "error"`, and the test happily reports 100% "consistent". Treat any `--stability` output as meaningless until fixed.

The main eval (`python -m backend.tests.eval_harness`, no flags) uses the correct kwargs (eval_harness.py:623-628) and does work — but it makes ~40+ live LLM calls; don't run it casually on the shared gateway.

### 2g. Agent returns "ambiguous" for everything — entropy over-fire

Not an outage. The constraint resolver computes normalized entropy over candidate actions and declares ambiguity above `ambiguity_entropy: 0.75` (defaults at backend/runtime/brain_agent.py:32 and backend/runtime/constraint_resolver.py:27; applied at constraint_resolver.py:204, 434). With 2-4 candidates whose scores are close, normalized entropy is near 1.0, so the threshold fires constantly. This is the mechanism behind the **eval inversion**: the full runtime scores 15.0% strict / 52.5% relaxed vs 62.5% strict for the resolver-only path (backend/tests/eval_results_baseline.json, backend/tests/resolver_eval_results.json, runs of 2026-06-15/16).

Discriminate before touching thresholds: in the `/agent/query` response, read `constraint_result` and `decision_trace` — `candidate_entropy` vs `constraint_entropy`, and `all_admissible_actions` with their confidences. If candidates are genuinely tied, the brain lacks discriminating metadata (compile-side problem); if one candidate clearly dominates but entropy still fires, it's the threshold/normalization (runtime problem). The whole campaign — hypotheses, measurements, allowed experiments — is in `kernl-eval-inversion-campaign`. Threshold changes go through `kernl-change-control`.

### 2h. "No compiled brain found" — the DB-then-file fallback

`handle_agent_query` loads the brain in two steps (backend/runtime/brain_agent.py:638-641): first Supabase (`skills_files` table, latest `compiled_at` for the `company_id`, `_load_db` at line 607); if that errors or returns nothing, it falls back to a local file `backend/tests/last_compiled_brain.json` (`_LOCAL_BRAIN`, lines 602-604; `_load_file` at 627). Only if BOTH fail do you get the error.

Key facts:
- The server compile pipeline writes ONLY to the DB (backend/engine/nodes/write_brain.py). The local fallback file is written by `python backend/test_compile.py` (backend/test_compile.py:126) — the direct, no-API pipeline runner. If you've only ever compiled through the API on a machine without DB creds, the fallback file never existed.
- A brain that loads but has `skills: []` produces a different message: `"Brain is empty — no skills compiled."` (brain_agent.py:645) — that means §2b happened at compile time.
- Inspect the local brain cheaply: `python backend/show_brain.py` (reads `backend/tests/last_compiled_brain.json`; must run from repo root — the path in it is relative).

### 2i. Embeddings: slow first call, and the 128-token truncation trap

The embedding model (`sentence-transformers/all-MiniLM-L6-v2`) is downloaded from Hugging Face and loaded lazily on the FIRST `get_embedding` call (backend/core/llm.py:28-35). Symptom: the first `/agent/query` or compile after process start stalls for the duration of a model download — this is normal once per environment, not a hang.

The trap: `get_embedding` tokenizes with `truncation=True, max_length=128` (backend/core/llm.py:40-42). Anything past ~128 tokens of a skill's `category + rule + rationale` text is invisible to semantic retrieval. Long rules whose distinguishing clause comes late will retrieve poorly and can masquerade as "the retriever is broken". Discriminate by checking whether the mismatch text lies beyond the truncation window.

### 2j. SSE stream ends with a "timeout" event

The SSE generator waits at most 300s for the next event; on idle timeout it yields `{"event":"timeout","data":{}}` and closes, deleting the job's queue (backend/core/sse.py:26-35). Two implications:
1. A `timeout` event means the STREAM gave up — the background compile task may still be running (it has its own 600s budget, §2a). Check `curl.exe -s http://localhost:8081/compile/<job_id>/status` (reads the `compile_runs` row).
2. Because the queue is deleted in `finally`, you cannot reattach to the same `job_id` stream and see missed events. Rely on `/compile/{job_id}/status` and the server console after a stream death.

Normal termination is a `pipeline_complete` or `pipeline_error` event (sse.py:29-30) — anything else ending the stream is abnormal.

### 2k. Windows traps

- **The repo path contains a space** (`D:\Abhijith P\...`). Every unquoted use eventually bites — in shell commands, in tools that split on whitespace, in scripts that build paths. Always quote: `cd "D:\Abhijith P\Desktop\Project\kernl"` / `"/d/Abhijith P/Desktop/Project/kernl"` in Git Bash.
- **Run module commands from the repo root.** All backend code imports as `backend.*` (e.g. backend/api.py:22-36). `python -m backend.tests.eval_harness`, `python -m uvicorn backend.api:app --port 8081`, `python backend/show_brain.py` all assume CWD = repo root. From anywhere else you get `ModuleNotFoundError: No module named 'backend'` (or, for show_brain, a `FileNotFoundError` on its relative path).
- `curl` in PowerShell 5.1 is an alias for `Invoke-WebRequest`; use `curl.exe` for the commands in this playbook.

## 3. Traps that cost real time

One paragraph each; the full chronicle of every incident lives in `kernl-failure-archaeology`.

**The stale `.env.example`.** The gateway migrated from an OpenAI-compatible vLLM endpoint (`http://<host>:8000/v1`, `openai` SDK) to a custom proxy (`POST {base}/generate`, `x-api-key`), but `backend/.env.example:1` and large parts of `AGENTS.md` (lines 82-83, 100, 381) still describe the old world. Anyone bootstrapping from the example env gets 100% LLM failure with confusing errors, because `/health` on the wrong base URL can even succeed while `/generate` 404s. Rule of thumb this repo teaches: **trust backend/core/llm.py, never the docs**, for the gateway contract.

**The silent empty list.** `safe_llm_json_call`'s double-parse-failure path returns `[]` instead of raising (backend/core/llm.py:216-217). Extraction nodes extend their results with it, the graph completes, `write_brain` persists a near-empty brain, and the SSE stream proudly reports success. Downstream, the agent gives weak answers and the eval craters — days later, far from the cause. The counts in the node print-lines and `stage` events (§2b) are the ONLY early signal; make reading them a reflex after every compile.

**The port matrix.** Four different ports appear in this repo (8081 canonical, 7860 in the HF Space header, 8080 in the stale stress test and the scratch chat server, 8000 in pre-refactor docs). Each stale number came from a different era and each has sent someone to debug a "down" backend that was listening fine on 8081. Check §2e's table before touching network config; the README `app_port: 7860` vs Dockerfile 8081 mismatch is a real open defect for HF deployment, not just cosmetic.

**The auth amputation.** Commit 2ca7f83 deleted the backend auth (`backend/auth/jwt.py`) and the login/register/onboarding pages, but left `frontend/src/lib/auth.tsx` and the `/companies/{id}` fetch in `page.tsx`. The result is a frontend that 404s on boot-path requests in a way that looks exactly like a misconfigured `API_BASE`. It is not; see §2d.

**The leaked HF token.** Commit 22ee2f0 ("automatic serverless fallback to Hugging Face router") hard-coded a Hugging Face token into `backend/llm.py`; it is retrievable from git history and must be treated as **compromised — revoke it**, never reuse or reproduce it. When debugging anything gateway-related, do not "helpfully" copy old credentials out of history. Refer to secrets only as `commit 22ee2f0` / `backend/core/llm.py:14`.

**The eval that can't crash.** `--stability` mode passes wrong kwargs, but its blanket `except Exception` converts the `TypeError` into `action_type: "error"` for every run — three identical "error" strings count as "consistent", so it reports a perfect stability score while testing nothing (§2f). Lesson: in this codebase, broad exception handlers routinely convert crashes into plausible-looking output (`safe_llm_json_call`, `_baseline`'s `_parse`, the eval loops). When a number looks fine but the world doesn't, suspect a swallowed exception first.

## Provenance and maintenance

Facts verified against the working tree on **2026-07-08**. Re-verify volatile facts before trusting them (all commands from repo root, Git Bash; quote the repo path):

| Fact | Re-verification command |
|------|-------------------------|
| 600s pipeline timeout | `grep -n "wait_for" backend/api.py` |
| `/health` route & shape | `grep -n "def health_check" -A 8 backend/api.py` |
| Gateway contract: POST `{base}/generate`, `x-api-key` | `grep -n "generate\|x-api-key" backend/core/llm.py` |
| `VLLM_BASE_URL` default | `grep -n "VLLM_BASE_URL = " backend/core/llm.py` |
| Backoff waits 10/20/40/80s, 5 attempts, 120s HTTP timeout | `grep -n "attempt\|timeout=120" backend/core/llm.py` |
| Silent `[]` on double parse failure | `grep -n "return \[\]" backend/core/llm.py` |
| Semaphore(4) concurrency cap | `grep -n "Semaphore" backend/core/llm.py` |
| SSE 300s idle timeout + `timeout` event | `grep -n "timeout" backend/core/sse.py` |
| DB-then-file brain fallback, `_LOCAL_BRAIN` path | `grep -n "_LOCAL_BRAIN\|_load_file()\|_load_db(" backend/runtime/brain_agent.py` |
| `handle_agent_query` signature (`cid`, `ctx`) | `grep -n "async def handle_agent_query" backend/runtime/brain_agent.py` |
| `ambiguity_entropy: 0.75` | `grep -rn "ambiguity_entropy" backend/runtime/` |
| Embedding truncation `max_length=128` | `grep -n "max_length" backend/core/llm.py` |
| Canonical port 8081 | `grep -n "8081" Dockerfile frontend/src/lib/api.ts scripts/smoke_test.py` |
| README HF `app_port: 7860` mismatch | `grep -n "app_port" README.md` |
| Stale 8080 / 8000 references | `grep -n "8080" scripts/stress_test.py serve_chat.py; grep -n "8000" AGENTS.md backend/.env.example` |
| Stale `/v1` in `.env.example` | `head -1 backend/.env.example` |
| Missing `/companies` & `/auth/config` routes | `grep -n "companies\|auth/config" backend/api.py` (expect no route hits) |
| Frontend still calls them | `grep -n "companies\|auth/config" frontend/src/app/page.tsx frontend/src/lib/auth.tsx` |
| resolver_only_eval stale imports | `grep -n "from backend.runtime.brain_agent import" -A 7 backend/tests/resolver_only_eval.py` |
| `--stability` wrong kwargs | `grep -n "company_id=COMPANY_ID" backend/tests/eval_harness.py` |
| Extraction count log lines | `grep -n "chunks relevant\|extracted" backend/engine/nodes/extract_decisions.py` |
| `pipeline_complete` carries `skills_count` | `grep -n "skills_count" backend/engine/nodes/write_brain.py` |
| `last_compiled_brain.json` writer | `grep -rn "last_compiled_brain" backend --include=*.py` |
| Eval headline numbers (15.0 / 52.5 / 62.5) | `grep -o "\"strict_accuracy_pct\":[^,]*\|\"relaxed_accuracy_pct\":[^,]*" backend/tests/eval_results_baseline.json; grep -o "accuracy_pct\":[^,]*" backend/tests/resolver_eval_results.json` |
| Auth deletion commit | `git show --stat 2ca7f83 -- backend/auth frontend/src/app/login` |
| Leaked-token commit (do NOT print the token) | `git show 22ee2f0 --stat` |
