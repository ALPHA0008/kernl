---
name: kernl-config-and-flags
description: Load this skill whenever you need to know or change ANY kernl configuration value — environment variables (VLLM_BASE_URL, VLLM_API_KEY, SUPABASE_URL/KEY, NEXT_PUBLIC_API_URL), retrieval weights, decision thresholds (metadata_confidence, ambiguity_entropy, graph_fallback_threshold, etc.), hardcoded constants (semaphore, timeouts, chunk sizes, top-K), or ports. Also load it when .env setup fails, when a threshold experiment is requested, when "where is X configured?" comes up, or before adding a new config axis. It is the single catalog of every configuration axis with defaults, status, and re-verification commands.
---

# kernl configuration and flags — the complete catalog

**What this covers:** every knob in the kernl repo — env vars, the brain's `metadata_json` runtime config (the most important and least obvious axis), hardcoded constants, ports, and the checklist for adding a new config axis. Each value carries its file:line source and a re-verification command, because config drifts.

**When NOT to use this:**
- Installing deps / creating the venv / building the Docker image → `kernl-build-and-env`
- Starting the server, running a compile, calling endpoints → `kernl-run-and-operate`
- "The value is right but behavior is wrong" → `kernl-debugging-playbook`
- Getting a change to a threshold/weight approved permanently → `kernl-change-control`
- What the thresholds mean for eval accuracy / how to run experiments → `kernl-eval-inversion-campaign`, `kernl-validation-and-qa`
- Why the config is duplicated the way it is (history) → `kernl-failure-archaeology`

All facts verified against the repo on 2026-07-08. Re-verify with section 7 before trusting anything load-bearing.

---

## 1. Config axes at a glance

| Axis | Where it lives | Read at | Status |
|---|---|---|---|
| Env vars (4 real + 1 dead) | `backend/.env` via `python-dotenv` | process start / module import | production |
| `metadata_json` (weights + thresholds) | inside each compiled brain (`brain_json`) | every agent query | production |
| `_MD` fallback defaults | `backend/runtime/brain_agent.py:8-38` | when brain lacks `metadata_json` | production (drift hazard) |
| Hardcoded constants | scattered (section 4) | varies | production |
| Ablation configs A–E | `backend/tests/eval_harness.py:566-598` | `--ablation` runs only | experimental |
| Ports | Dockerfile, README, frontend, scripts | deploy/run time | 8081 canonical; others stale (section 5) |

---

## 2. Environment variables

All backend env vars are loaded with `python-dotenv`. **Gotcha:** `backend/core/llm.py:11` calls `load_dotenv(override=True)` — values in the `.env` FILE override already-exported shell variables for the LLM module. Exporting `VLLM_BASE_URL` in your shell does nothing if `.env` also sets it. (`backend/core/db/supabase.py:5` uses plain `load_dotenv()`, no override.)

| Variable | Default if unset | Read at | Required? |
|---|---|---|---|
| `VLLM_BASE_URL` | `http://172.20.7.22:9000` (`backend/core/llm.py:13`) | import of `core/llm.py` | Yes, for any LLM call |
| `VLLM_API_KEY` | hardcoded default at `backend/core/llm.py:14` — do NOT print or copy it | import of `core/llm.py` | Yes (default works against the internal gateway) |
| `SUPABASE_URL` | `None` (`backend/core/db/supabase.py:7`) | import of `core/db/supabase.py` | No — see degradation below |
| `SUPABASE_KEY` | `None` (`backend/core/db/supabase.py:8`) | same | No |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8081` (`frontend/src/lib/api.ts:1-2`) | Next.js build/runtime (frontend only) | No |
| `COMPANY_ID` | — | **read by nothing** (see below) | No — dead |

Per-variable notes:

- **`VLLM_BASE_URL`** points at a **custom internal gateway, NOT an OpenAI-shaped endpoint**. The code does `POST {VLLM_BASE_URL}/generate` with an `x-api-key` header (`backend/core/llm.py:94-98`) and `GET {VLLM_BASE_URL}/health` (`llm.py:72`). There is no `/v1`, no `Authorization: Bearer`, no `model` field in the body. The default `http://172.20.7.22:9000` is an internal-network IP (as of 2026-07-08) — it is unreachable from outside the company network, and it is a **shared live gateway**: do not hammer it with test loops.
- **`VLLM_API_KEY`** has a hardcoded fallback at `backend/core/llm.py:14`. Never copy that value into docs, chat, commits, or other skills — reference it only as "see backend/core/llm.py:14". Related security fact: a Hugging Face token was committed in git history (commit `22ee2f0`); it is compromised and must be revoked, never reused or reproduced.
- **`SUPABASE_URL` / `SUPABASE_KEY`** are genuinely optional. If either is missing, `backend/core/db/supabase.py:10-15` sets the client to `None` and every DB helper no-ops (returns `None`/`[]`/`{}`). The agent then falls back to the **local-file brain**: `handle_agent_query` tries the DB first, and on any error loads `backend/tests/last_compiled_brain.json` (`backend/runtime/brain_agent.py:602-604, 635-642`). A compile without Supabase still produces skills but `write_brain` emits a `pipeline_error` for the DB step (`backend/engine/nodes/write_brain.py:56-62`); `backend/test_compile.py:125-130` writes the result to `last_compiled_brain.json` precisely for this DB-less path.
- **`NEXT_PUBLIC_API_URL`** is the only frontend env var (verify: `grep -rn "process.env" frontend/src` returns exactly one hit). Set it in `frontend/.env.local` (gitignored) when the backend is not on `localhost:8081`.
- **`COMPANY_ID`** appears in `backend/.env.example:4` but **no code reads it** (as of 2026-07-08). The only `os.getenv` calls in the repo are for `VLLM_BASE_URL`, `VLLM_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY` (verify command in section 7). The eval harness hardcodes the company as a Python constant instead: `COMPANY_ID = "rivanly-inc"` at `backend/tests/eval_harness.py:33`. Setting the env var does nothing. ("Rivanly Inc." is the fictional demo company whose synthetic source docs in `data/sources/rivanly-inc/` are the pipeline's ground truth — see `kernl-validation-and-qa`.)

### 2.1 `.env.example` is STALE — do not copy it

`backend/.env.example` (as of 2026-07-08) shows `VLLM_BASE_URL=http://<MI300X_IP>:8000/v1` — the `/v1` suffix is from a pre-refactor OpenAI-SDK era and will 404 against the current gateway code; it omits `VLLM_API_KEY` entirely; and its `COMPANY_ID` is dead (above). The root `AGENTS.md` env section is stale in the same way.

Correct template — create `backend/.env` (gitignored; repo root also works, since python-dotenv searches upward from the calling module):

```bash
# Custom gateway: NO /v1 suffix. Code appends /generate and /health itself.
VLLM_BASE_URL=http://<gateway-host>:<port>
VLLM_API_KEY=<ask the team; never commit; default fallback exists at backend/core/llm.py:14>

# Optional. Omit both to run in local-file-brain mode.
SUPABASE_URL=<your supabase project url>
SUPABASE_KEY=<your supabase anon key>
```

If a health check 404s, the first suspect is a trailing `/v1` on `VLLM_BASE_URL`.

---

## 3. The brain's `metadata_json` — runtime config inside the data

This is the most important and least obvious configuration axis: **the retrieval weights and decision thresholds are not in any config file — they travel inside each compiled brain.**

Flow (each hop verified):

1. **Compile time:** the LangGraph pipeline node `discover_operational_metadata` (`backend/engine/nodes/discover_operational_metadata.py:7`) builds a `metadata` dict containing `retrieval_weights` (lines 77-83) and `thresholds` (lines 85-93), plus discovered `action_types`, `valid_sets`, `heuristic_patterns`, `authority_levels`. It runs between `build_operational_graph` and `synthesize_skills` (`backend/engine/graph.py:78-79`).
2. **Persist:** `write_brain` stores it as the `metadata_json` key of the brain (`backend/engine/nodes/write_brain.py:44`) — in Supabase `skills_files.brain_json`, and/or `backend/tests/last_compiled_brain.json` locally.
3. **Query time:** `_load_metadata` (`backend/runtime/brain_agent.py:41-49`) reads `brain["metadata_json"]`, filling any missing top-level key from the `_MD` fallback dict (`brain_agent.py:8-38`).

So the values are **per-brain overridable**: two brains compiled from different sources can (in principle) carry different thresholds, and editing a brain's `metadata_json` changes runtime behavior with no code change.

### 3.1 `retrieval_weights` — hybrid retrieval mix

The brain agent ranks skills with a weighted sum of five signals (`_hybrid`, `backend/runtime/brain_agent.py:380-398`): `final = semantic*w + metadata*w + keyword*w + severity*w + condition*w + specificity_bonus`, then keeps the top 5 (`brain_agent.py:687`).

| Weight | Default | Signal it scales |
|---|---|---|
| `semantic` | 0.45 | cosine similarity of query embedding vs skill embedding |
| `metadata` | 0.20 | department/action-type match between query signals and skill's trusted operational fields |
| `keyword` | 0.15 | overlap of query tokens with the skill's `keywords` list |
| `severity` | 0.10 | severity match (P0/P1/P2/sla/...) |
| `condition` | 0.10 | fraction of the skill's structured conditions satisfied by query context |

Defaults are identical in all three copies: `discover_operational_metadata.py:77-83`, `brain_agent.py:22-28` (`_MD`), and the current local brain (`backend/tests/last_compiled_brain.json:5987-5993`).

### 3.2 `thresholds` — decision gates

| Threshold | Default | What it gates (verified usage) |
|---|---|---|
| `metadata_confidence` | 0.60 | Per-field trust gate: a skill's `operational` field (department, severity, action_type, workflow_type, customer_tier) is used in scoring only if that field's compile-time confidence ≥ 0.60, else treated as absent (`brain_agent.py:263-278`) |
| `conditions_confidence` | 0.60 | Same idea for the skill's structured `conditions` list — below 0.60 the conditions are ignored (`brain_agent.py:281-282`) |
| `ambiguity_entropy` | 0.75 | Normalized Shannon entropy (base-2, divided by log2(n), so 0–1) of the candidate-action score distribution (`brain_agent.py:541-551`); above 0.75 the resolver flags the answer ambiguous (`backend/runtime/constraint_resolver.py:204, 434`) |
| `min_confidence_for_auto_action` | 0.40 | **Defined in all three copies but READ BY NO CODE (as of 2026-07-08)** — a dead threshold; verify with the section 7 command before assuming it does anything |
| `graph_fallback_threshold` | 0.5 | Graph-first retrieval gate: the operational-graph answer is used only when `graph_confidence >= 0.5`, else fall back to skill retrieval (`brain_agent.py:648-650`, `constraint_resolver.py:543`) |
| `score_differential_threshold` | 0.10 | Minimum score gap used in the skill-fallback ambiguity decision (`constraint_resolver.py:435`) |
| `specificity_bonus_scale` | 0.02 | Additive retrieval bonus `(specificity_level/5) * 0.02` for more specific skills (`brain_agent.py:383, 396-398`) |

### 3.3 DRIFT HAZARD: the defaults exist in THREE places

1. `backend/engine/nodes/discover_operational_metadata.py:77-93` — what future compiles write into brains.
2. `backend/runtime/brain_agent.py:8-38` (`_MD`) — runtime fallback when a brain has no `metadata_json`; additionally, individual `_t(...)` call sites repeat literal defaults (e.g. `_t(meta, "metadata_confidence", 0.60)` at `brain_agent.py:265`).
3. `backend/runtime/constraint_resolver.py:26-31` (`DEFAULT_THRESHOLDS`) — a 4-key subset used when the resolver is called without metadata (`_get_thresholds`, lines 34-41).

Today all three agree. If you change one and not the others, compile-time and runtime behavior silently diverge, and old brains keep old values forever. **Any threshold change must touch all three sites (or consciously justify not doing so) and goes through `kernl-change-control` with eval evidence.** The diff command in section 7 detects divergence.

### 3.4 How to change a threshold — experiment vs permanent

**Local experiment (runtime only, no code change, no recompile):**
1. Ensure you are on the local-file path (no `SUPABASE_URL`/`SUPABASE_KEY` in `.env`), so the agent reads `backend/tests/last_compiled_brain.json`.
2. Edit that file's top-level `metadata_json.thresholds` (around line 5994) or `metadata_json.retrieval_weights` (around line 5987).
3. Re-run your query or the eval harness — `_load_metadata` picks the edited values up immediately.
4. This file is regenerated by every `backend/test_compile.py` run (`test_compile.py:125-130`), so your edit is ephemeral. Copy the file aside if you need the variant later.

Caveat: `constraint_resolver.py` uses its own `DEFAULT_THRESHOLDS` only when called without metadata; the normal agent path passes the brain's metadata through, so editing the brain file covers the standard flow.

**Retrieval-weight experiments have a first-class path:** `run_eval(retrieval_weights=...)` (`backend/tests/eval_harness.py:601`) threads weights into every query via the `rw` kwarg (`eval_harness.py:628`, `brain_agent.py:635, 655`). `python -m backend.tests.eval_harness --ablation` runs 5 predefined weight configs `A_semantic_only` … `E_with_conditions` (`eval_harness.py:566-598`; the docstring at line 8 saying "4 configs" is stale). Note the eval calls the live gateway — coordinate before running (see `kernl-validation-and-qa`).

**Affecting future compiles:** edit the literals in `discover_operational_metadata.py:77-93`. Only newly compiled brains get the new values; existing brains (Supabase rows, the local file) keep the old ones.

**Permanent change:** all three copies + eval evidence + `kernl-change-control`. Never ship a threshold change validated only by editing the local brain file.

---

## 4. Hardcoded constants worth knowing

All in-code, no env override (as of 2026-07-08). Changing any of these is a code change → `kernl-change-control`.

| Constant | Value | Location | Effect |
|---|---|---|---|
| LLM concurrency semaphore | `Semaphore(4)` | `backend/core/llm.py:16` | Max 4 concurrent gateway calls process-wide; parallel pipeline nodes queue behind it |
| Per-LLM-call HTTP timeout | 120 s | `backend/core/llm.py:92` | One `/generate` request |
| Health-check timeout | 10 s | `backend/core/llm.py:70` | `GET /health` |
| Retry schedule | 5 attempts; rate-limit (429/413/"rate_limit") waits `2**(attempt+1)*5` s = 10/20/40/80; other errors: 2 s sleep, max 3 tries, then `RuntimeError` | `backend/core/llm.py:90-127` | Worst case one call can burn ~150 s+ of the pipeline budget on backoff alone |
| `temperature` / `max_tokens` | params default 0.1 / 4096 but are **NOT sent to the gateway** — the POST body contains only `messages` | `backend/core/llm.py:83-105` | Dead parameters today; the gateway decides sampling. Do not "tune temperature" and expect an effect |
| Pipeline hard timeout | 600 s | `backend/api.py:174` (`asyncio.wait_for(graph.ainvoke(...), timeout=600.0)`) | Whole compile aborts with `pipeline_error` |
| SSE idle timeout | 300 s | `backend/core/sse.py:26` | Stream emits `{"event": "timeout"}` (`sse.py:32`) and closes if no event for 5 min; the compile may still be running |
| Chunk size / overlap | 2000 / 200 (estimated tokens; code multiplies by 4 for chars: `chunk_size*4`, `overlap*4`) | `backend/chunking/chunkers.py:7-8, 11-12, 23, 36` | Ingestion chunking of source docs |
| Embedding truncation | `max_length=128` tokens | `backend/core/llm.py:41` | Query/skill text beyond ~128 tokens is invisible to semantic retrieval |
| Embedding model / threads | `all-MiniLM-L6-v2`, `torch.set_num_threads(2)` | `backend/core/llm.py:31-35` | CPU, in-process |
| Retrieval top-K | 5 (`scored[:5]`) | `backend/runtime/brain_agent.py:687` | Candidates passed to reasoning |
| Ranked-action cap | 4 (`[:4]`) | `backend/runtime/brain_agent.py:598` | Max candidate actions after heuristic merge |
| Eval company | `COMPANY_ID = "rivanly-inc"` | `backend/tests/eval_harness.py:33` | Python constant, not env |

---

## 5. Ports matrix

One canonical port; three stale/special ones that regularly waste debugging time.

| Port | Where | Status (2026-07-08) |
|---|---|---|
| **8081** | Dockerfile:29-31 (`EXPOSE 8081`, `uvicorn ... --port 8081`), `frontend/src/lib/api.ts:2`, `scripts/smoke_test.py:17`, docs | **CANONICAL** backend port |
| 7860 | `README.md:7` (`app_port: 7860`, Hugging Face Spaces frontmatter) | **MISMATCH** vs Dockerfile's 8081 — known open defect; HF routes to 7860 where nothing listens. Fix via `kernl-change-control`; details in `kernl-run-and-operate` |
| 8080 | `scripts/stress_test.py:20` (stale — edit to 8081 before use); `serve_chat.py:3` (standalone scratch chat page server — intentionally separate) | stale / special-purpose |
| 8000 | `backend/.env.example:1`, root `AGENTS.md` | pre-refactor vLLM-direct era; nothing current listens there |

`backend/api.py` itself contains no port — the port comes entirely from the `uvicorn` command line (Dockerfile or your shell).

---

## 6. How to ADD a config axis (checklist)

Follow in order; skipping steps is how `.env.example` got stale and `COMPANY_ID` became a zombie.

1. **Prefer an existing axis.** A retrieval/decision knob belongs in `metadata_json` thresholds (all three copies, section 3.3), not a new env var.
2. Read it once at module import: `MY_FLAG = os.getenv("MY_FLAG", "<safe-default>")` next to the existing reads in the module that owns the behavior. The default must keep current behavior unchanged.
3. Remember `load_dotenv(override=True)` semantics (section 2) if your module imports `core/llm.py` first — document which wins.
4. Add the variable with a placeholder (never a real credential) to `backend/.env.example` — and fix the stale lines there while you are in the file.
5. Add a row to section 2 of THIS skill (name, default, file:line, read-at, required?) and a re-verification command to section 7.
6. If it changes eval-relevant behavior, run the eval before/after and attach both — `kernl-change-control` gates the merge.
7. Re-run the section 7 verification for your row and confirm it prints what you documented.

---

## Provenance and maintenance

All facts above verified directly against the repo on **2026-07-08**. Line numbers drift; run these from the repo root (quote paths — the repo path contains spaces) before relying on any specific claim.

| Fact | Re-verification command (repo root) |
|---|---|
| Complete env-var surface (should list only VLLM_BASE_URL, VLLM_API_KEY, SUPABASE_URL, SUPABASE_KEY + test_compile's check) | `grep -rn "os.getenv\|os.environ" backend frontend scripts --include="*.py"` |
| VLLM defaults + `override=True` | `grep -n "load_dotenv\|VLLM_" backend/core/llm.py` |
| Gateway shape (POST /generate, x-api-key, GET /health) | `grep -n "generate\|x-api-key\|/health" backend/core/llm.py` |
| Supabase optional / None fallback | `grep -n "getenv\|supabase = None" backend/core/db/supabase.py` |
| Local-file brain fallback path | `grep -n "_LOCAL_BRAIN\|_load_file" backend/runtime/brain_agent.py` |
| Frontend env var + default 8081 | `grep -rn "process.env" frontend/src` |
| COMPANY_ID still dead as env var | `grep -rn "COMPANY_ID" backend --include="*.py"` (only the `eval_harness.py` Python constant should appear; any `os.getenv("COMPANY_ID")` hit means this skill is stale) |
| `.env.example` still stale | `cat backend/.env.example` (still `:8000/v1`, still no VLLM_API_KEY?) |
| `_MD` defaults (weights + thresholds) | `sed -n '8,38p' backend/runtime/brain_agent.py` |
| Compile-time copy of defaults | `sed -n '77,93p' backend/engine/nodes/discover_operational_metadata.py` |
| Resolver's third copy | `sed -n '26,31p' backend/runtime/constraint_resolver.py` |
| Three-way drift check | `python -c "import re; f=lambda p:dict(re.findall(r'\"(\w+)\": ([0-9.]+)',open(p).read())); a=f('backend/runtime/brain_agent.py'); b=f('backend/engine/nodes/discover_operational_metadata.py'); print({k:(a.get(k),b.get(k)) for k in set(a)|set(b) if a.get(k)!=b.get(k)} or 'IN SYNC')"` (crude; prints `IN SYNC` when literal numeric defaults match) |
| `min_confidence_for_auto_action` still unread | `grep -rn "min_confidence_for_auto_action" backend --include="*.py"` (hits only in the three defaults dicts = still dead) |
| metadata_json written into brains | `grep -n "metadata_json" backend/engine/nodes/write_brain.py backend/runtime/brain_agent.py` |
| Current local brain's live values | `python -c "import json; print(json.load(open('backend/tests/last_compiled_brain.json'))['metadata_json']['thresholds'])"` |
| Semaphore(4), 120 s call timeout, retry schedule | `grep -n "Semaphore\|timeout=\|2 \*\* (attempt" backend/core/llm.py` |
| 600 s pipeline timeout | `grep -n "timeout=600" backend/api.py` |
| 300 s SSE idle timeout | `grep -n "timeout=300" backend/core/sse.py` |
| Chunk 2000/200 (token-estimate ×4 chars) | `sed -n '7,12p' backend/chunking/chunkers.py` |
| Embedding max_length 128 | `grep -n "max_length" backend/core/llm.py` |
| Top-5 retrieval | `grep -n "scored\[:5\]" backend/runtime/brain_agent.py` |
| Ablation configs A–E (5, not the docstring's 4) | `grep -n "ABLATION_CONFIGS\|\"[A-E]_" backend/tests/eval_harness.py` |
| Port 8081 canonical / 7860 mismatch / 8080 stale | `grep -n "8081" Dockerfile frontend/src/lib/api.ts; grep -n "app_port" README.md; grep -n "8080" scripts/stress_test.py serve_chat.py` |
| temperature/max_tokens not forwarded | `sed -n '92,105p' backend/core/llm.py` (POST body has only `messages`?) |
