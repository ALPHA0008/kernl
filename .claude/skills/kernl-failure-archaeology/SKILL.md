---
name: kernl-failure-archaeology
description: Load this before proposing an architecture change, resurrecting deleted code, "fixing" a 404, adding an LLM-provider fallback, or asking "why was X removed?" in the kernl repo. It is the chronicle of every major investigation, dead end, rejected approach, and revert (symptom -> root cause -> evidence -> status), so you do not re-fight settled battles. Triggers: git history questions, deleted files, auth 404s, HF token leak, Neo4j, Gemini, eval inversion, the 38-day gap, graphiti.md, per-source ingest nodes.
---

# kernl failure archaeology

**What this covers:** the repo's decision graveyard — every abandoned architecture, deleted subsystem, rejected technology, and known-broken leftover, each with the commit evidence and a verdict (settled / open / fenced-off). Read the relevant entry BEFORE re-proposing anything that resembles it.

**When NOT to use this:**
- Diagnosing a live failure right now -> `kernl-debugging-playbook`
- What the architecture IS today -> `kernl-architecture-contract`
- The eval-inversion investigation in depth (numbers, hypotheses, next experiments) -> `kernl-eval-inversion-campaign`
- Making a change (approval, gating, commit rules) -> `kernl-change-control`
- Ports, env vars, running things -> `kernl-build-and-env`, `kernl-run-and-operate`

## How to read this file

Each entry is: **Symptom/Trigger -> Root cause -> Evidence -> Status -> Lesson.**

Status meanings:
| Status | Meaning |
|---|---|
| **settled** | Decision was made deliberately. Do not reopen without new evidence + change control. |
| **open** | Known problem, no decision yet. Safe to work on — start from the entry's evidence. |
| **fenced-off** | Dead artifact left in the tree. Not part of the product. Do not build on it, do not delete it without change control. |

## The commit timeline (as of 2026-07-08)

The repo has 9 commits, one human author (two git identities). Reproduce with:

```bash
git -C "d:/Abhijith P/Desktop/Project/kernl" log --oneline --format='%h %ad %s' --date=short
```

| SHA | Date | What | Archaeology entries |
|---|---|---|---|
| `0762fba` | 2026-05-08 | Initial commit: linear 5-node pipeline + frontend | E1, E8 |
| `f1c4fd6` | 2026-05-08 | Untrack private docs (6 min after initial commit) | E8 |
| `a688aff` | 2026-05-09 | Parallel Send-API architecture; per-source ingest nodes | E1, E2 |
| `5f7dc7e` | 2026-05-09 | Dashboard UI + auth flow + generic chunking registry (deletes per-source ingest) | E2, E3 |
| `1f0c290` | 2026-05-09 | Root Dockerfile for HF Spaces (port 7860) | E5 |
| `f00b2f4` | 2026-05-09 | Root README with HF Space config (`app_port: 7860`) | E5 |
| `22ee2f0` | 2026-05-10 | HF-router fallback + hardcoded token incident | E4 |
| *(38-day gap)* | | | E5 |
| `2ca7f83` | 2026-06-17 | +18.8k-line restructure: core/engine/runtime, constraint resolver, eval harness; deletes auth + HF fallback | E3, E4, E5, E6, E7, E9 |
| `d215501` | 2026-07-07 | Adds `.claude/` skill library (this file's ancestors) | — |

---

## E1 — Linear 5-node pipeline replaced by Send-API parallel architecture

- **Symptom/Trigger:** the initial pipeline processed everything sequentially and could not extract different knowledge types (decisions vs workflows vs exceptions) in parallel, nor ingest multiple source types concurrently.
- **Root cause:** initial commit `0762fba` shipped a strictly linear LangGraph graph of 5 nodes: `load_and_chunk -> cluster_evidence -> synthesize_skills -> quality_normalize -> write_brain` (see `git show --stat 0762fba`, files under `backend/graph/nodes/`). Sequential edges mean total latency = sum of all LLM calls, and one generic "cluster" step instead of typed extraction.
- **Fix:** `a688aff` replaced it with a fan-out architecture using the LangGraph **Send API**. *Jargon:* `Send("node_name", state)` is LangGraph's mechanism for dispatching several node invocations in parallel from a routing function; a **barrier/join node** is a node that all parallel branches edge into, so downstream work runs exactly once after all branches finish. `a688aff` deleted `cluster_evidence.py`, `load_and_chunk.py`, `quality_normalize.py` and added parallel extraction nodes. (Note: the `a688aff` commit message says "sequential 3-node pipeline" — the diff shows 5 nodes were deleted; trust the diff.)
- **Evidence:** `git show --stat 0762fba`; `git show --stat a688aff`; current fan-out at `backend/engine/graph.py:21-27` (`route_to_extraction` returns 5 `Send` objects: extract_decisions, extract_workflows, extract_exceptions, detect_contradictions, extract_entities) (as of 2026-07-08).
- **Status:** **settled.** Send-API fan-out with a barrier join is the architecture. Do not re-linearize. Structural rules live in `kernl-architecture-contract`.
- **Lesson:** parallel extraction was designed in on day 2; any "simplify to a sequential pipeline" proposal is a regression, not a cleanup.

## E2 — Per-source ingest nodes: lived exactly one commit

- **Symptom/Trigger:** someone reading `a688aff` sees dedicated `ingest_slack.py` / `ingest_notion.py` / `ingest_tickets.py` / `ingest_join.py` nodes and is tempted to bring back per-source ingestion "for cleanliness".
- **Root cause:** `a688aff` (May 9, 01:41) added 3 per-source ingest nodes + an `ingest_join` barrier. `5f7dc7e` (May 9, 22:53 — the very next commit, ~21 hours later) deleted all four and replaced them with a **generic chunking registry**: `backend/chunking/chunkers.py` (301 lines) + `backend/chunking/registry.py` (68 lines), driven by content-based format detection (`_detect_by_content` in `backend/chunking/registry.py` sniffs HTML/markdown/JSON-array/JSON-object), consumed by one graph node `chunk_documents` (now `backend/engine/nodes/chunk_documents.py`). Per-source nodes hardcoded knowledge of each source format into graph topology; the registry makes source formats data, not structure — adding a source type means adding a chunker, not rewiring the graph.
- **Evidence:** `git show --stat a688aff` (four `ingest_*` files added); `git show --stat 5f7dc7e` (same four files deleted, `backend/chunking/` added) (as of 2026-07-08).
- **Status:** **settled. Do NOT resurrect per-source ingest nodes.** New source types go through the chunking registry.
- **Lesson:** the author tried type-specific graph nodes and reversed within a day. The registry won on extensibility; that argument does not need to be re-had.

## E3 — Auth subsystem: built, then amputated; frontend stump remains (OPEN)

- **Symptom/Trigger (today, reproducible):** login/register attempts fail — `frontend/src/lib/auth.tsx:30` fetches `${API_BASE}/auth/config`, which no backend route serves (404). The dashboard's company load at `frontend/src/app/page.tsx:36` fetches `/companies/${id}` — also no backend route. `frontend/src/components/TopBar.tsx:52` and `:74` (and `auth.tsx:119`) `router.push("/login")` — the `/login` page no longer exists (Next.js 404). Verify the missing routes: `git grep -n "@app\." backend/api.py` lists no `/auth/*` and no `/companies/*` endpoints (as of 2026-07-08).
- **Root cause:** `5f7dc7e` added a full auth stack: `backend/auth/jwt.py` (46 lines), frontend `login`/`register`/`onboarding` pages, and `frontend/src/lib/auth.tsx`. The big restructure `2ca7f83` deleted `backend/auth/jwt.py` and the three frontend pages — but left `frontend/src/lib/auth.tsx` (124 lines), its `AuthProvider` still mounted app-wide at `frontend/src/app/layout.tsx:32`, and the `/login` links in `TopBar`/`NavBar`. The amputation was half-done.
- **Evidence:** `git show --stat 5f7dc7e` (auth files added); `git show --stat 2ca7f83` (`backend/auth/jwt.py -46`, `login/page.tsx -139`, `onboarding/page.tsx -224`, `register/page.tsx -155`); surviving stump at `frontend/src/lib/auth.tsx`, `frontend/src/components/TopBar.tsx`.
- **Status:** **OPEN wound — needs a decision.** Two coherent exits: (a) reinstate backend endpoints (`/auth/config`, Supabase-token verification, `/companies/{id}`), or (b) strip the frontend auth surface (`auth.tsx`, `AuthProvider` in `layout.tsx`, `/login` pushes, the `useAuth` call in `page.tsx:29`). Either is a product decision — route it through `kernl-change-control`. Do not "fix the 404" by inventing a third half-state. Live-debugging the resulting console errors: `kernl-debugging-playbook`.
- **Lesson:** deleting a subsystem means grepping BOTH sides of the API for every reference. `git grep -rn "auth\|/login" frontend/src` would have caught the stump.

## E4 — HF-router fallback and the hardcoded-token incident

- **Symptom/Trigger:** someone proposes "add a fallback LLM provider in case the gateway is down" — this was tried, and it produced a security incident.
- **Root cause:** `22ee2f0` (May 10) added an automatic fallback from the primary vLLM endpoint to the Hugging Face serverless router (`https://router.huggingface.co/v1`) inside the then-monolithic `backend/llm.py` (+51/-7). To make the fallback work with zero config, a real HF API token was **hardcoded, deliberately split into two string constants (`_HF_P1` + `_HF_P2`) to bypass the git push secret-scanning hook** — the code comment says so verbatim. **Never print, reconstruct, or reuse that token. It is permanently in git history (`git show 22ee2f0:backend/llm.py`) and must be treated as compromised and revoked at huggingface.co.** Do not paste the file's contents into logs, PRs, or skills; refer to it only as "commit `22ee2f0`, `backend/llm.py`".
- **The reversal:** `2ca7f83` deleted `backend/llm.py` entirely (-204 lines, including the token and the whole OpenAI-SDK fallback chain) and replaced it with `backend/core/llm.py` — a custom `httpx` client against a single private vLLM gateway: `POST {VLLM_BASE_URL}/generate` with an `x-api-key` header (`backend/core/llm.py:94-98`), a concurrency semaphore, and built-in resilience instead of a second provider: 5 attempts, exponential backoff `2**(attempt+1)*5` seconds on 429/413 (`backend/core/llm.py:90-124`) (as of 2026-07-08). Note `VLLM_API_KEY` has a hardcoded default at `backend/core/llm.py:14` — do not print that value either; config details live in `kernl-config-and-flags`.
- **Evidence:** `git show --stat 22ee2f0`; `git show --stat 2ca7f83` (backend/llm.py deleted, backend/core/llm.py added, 217 lines).
- **Status:** **settled — single-gateway client with retry/backoff. No provider-fallback chains.** The gateway is shared, live infrastructure (see `kernl-run-and-operate`); do not exercise it casually.
- **Lesson:** fallback chains breed hardcoded credentials and mask primary-outage signals. Also: obfuscating a secret to defeat a push hook is an incident, not a workaround. History rewriting to purge it was never done — assume the token is public.

## E5 — The 38-day gap and the +18.8k-line big-bang commit (what rotted)

- **Symptom/Trigger:** you diff `22ee2f0` (2026-05-10) against `2ca7f83` (2026-06-17) and find 38 days of work landed as ONE commit: 67 files, +18,818/−1,638 (`git show --stat 2ca7f83`).
- **What it did:** restructured `backend/` into `core/` (llm, db, models, sse) + `engine/` (compile graph + nodes) + `runtime/` (brain_agent, **constraint resolver** — the deterministic rule-evaluation layer at `backend/runtime/constraint_resolver.py`, 571 lines), renamed `backend/main.py` -> `backend/api.py`, and added the eval harness (`backend/tests/eval_harness.py`, 1014 lines) plus committed eval results.
- **Root cause of the damage:** a big-bang commit updates the code it touches and silently strands every satellite that referenced the old shape. Confirmed rot (all verified 2026-07-08):

| Rotted satellite | Symptom | Evidence |
|---|---|---|
| `CLAUDE.md` | Documents the pre-`2ca7f83` tree: `backend/main.py`, `backend/llm.py`, `backend/graph/` (`CLAUDE.md:19-26`); mandates `AsyncOpenAI` (`CLAUDE.md:117`) though the client is now raw `httpx`. One full refactor stale. | `git grep -n "main.py\|graph/" CLAUDE.md` |
| `backend/tests/resolver_only_eval.py` | ImportError on run: imports `_load_skills_from_file`, `_compute_hybrid_score`, `_build_admissible_actions`, `RETRIEVAL_WEIGHTS` from `backend.runtime.brain_agent` (`resolver_only_eval.py:20-26`) — those symbols were renamed (`_load_file`, `_hybrid`, `_admissible`; `RETRIEVAL_WEIGHTS` gone). | `git grep -n "RETRIEVAL_WEIGHTS" backend/runtime/brain_agent.py` (no hits) |
| `eval_harness.py --stability` | Silently meaningless: `eval_harness.py:970-975` calls `handle_agent_query(company_id=..., context=...)` but the signature is `(cid, scenario, ctx, with_brain, rw)` (`backend/runtime/brain_agent.py:635`); the `TypeError` is swallowed by `except` at `:976`, every run records `"error"`, identical errors count as CONSISTENT. | compare `eval_harness.py:623-629` (correct kwargs) vs `:970-975` |
| `README.md` | `app_port: 7860` (`README.md:7`) vs Dockerfile `EXPOSE 8081` / uvicorn `--port 8081` (`Dockerfile:29-31`) — `2ca7f83` changed the Dockerfile, not the README. Canonical port facts: `kernl-build-and-env`. | `git grep -n "7860\|8081" README.md Dockerfile` |
| Frontend auth stump | See E3 — same commit, same mechanism. | E3 |

- **Status:** rot items are **open** individually (fix under change control); the restructure itself is **settled**.
- **Lesson:** big-bang commits rot satellites. After any large refactor, sweep: CLAUDE.md, README, Dockerfile, `backend/tests/`, `scripts/`, and the frontend — grep for every renamed symbol and path. Doc-repair procedure: `kernl-docs-and-writing`.

## E6 — The eval inversion discovery (the flagship OPEN problem)

- **Symptom/Trigger:** committed eval results show the full LLM runtime scoring **15.0% strict accuracy** while the deterministic resolver alone scores **62.5% strict** on the same 40 scenarios — adding the LLM layer made answers 4x worse.
- **Definitions (once):** *strict* = the agent's `action_type` exactly matches the expected canonical label after lowercase/underscore normalization (`check_action_strict`, `backend/tests/eval_harness.py:509`); *relaxed* = credit via candidate/semantic matching (`check_action_relaxed`, `:521`). The scenarios are the **Rivanly ground truth** — a synthetic company (`data/sources/rivanly-inc/`) whose policies have known correct answers.
- **Evidence (both files committed in `2ca7f83`-era work, verified 2026-07-08):**
  - Full runtime: `backend/tests/eval_results_baseline.json` — `run_timestamp` 2026-06-16, 40 scenarios, `strict_accuracy_pct: 15.0`, `relaxed_accuracy_pct: 52.5`, `condition_accuracy_pct: 0.0`.
  - Resolver-only: `backend/tests/resolver_eval_results.json` — timestamp 2026-06-15, 40 scenarios, 25 strict passes, `accuracy_pct: 62.5`.
- **Root cause (working diagnosis, not fully closed):** the LLM layer destroys label fidelity (free-text answers that fail strict matching — note relaxed 52.5% vs strict 15.0%) and the ambiguity/entropy gate over-fires (entropy machinery at `backend/runtime/brain_agent.py:541` `_entropy`), returning "ambiguous" where the resolver commits to an action.
- **Status:** **OPEN — this is the repo's flagship campaign.** All hypotheses, experiment queue, and re-run procedure are owned by `kernl-eval-inversion-campaign`; measurement tooling by `kernl-validation-and-qa` and `kernl-proof-and-analysis-toolkit`. Do not re-derive the numbers here — and do not re-run the eval casually; it hits the shared live gateway.
- **Lesson:** deterministic baseline first, LLM layer second, and eval both separately — that instrumentation is the only reason this inversion was even visible.

## E7 — Rejected technologies (do not re-propose without new facts)

| Rejected | Where recorded | Rationale on record | Status |
|---|---|---|---|
| **Neo4j** (graph DB) | `docs/operational-graph-master-plan.md:1405-1414` ("Probably never Neo4j") | Per-company graph is small (<10k nodes); schema still evolving; Neo4j adds ops overhead and cognitive load "with zero benefit at this stage". Chosen instead: in-memory dict + JSONB persistence (`graph_json JSONB` on `skills_files`); pgvector adjacency is a *maybe-later* at 100+ companies. | **settled** |
| **Gemini free tier** | `gemini_test_response.txt` (repo root) | The one recorded attempt returned HTTP 429 `RESOURCE_EXHAUSTED` with free-tier quota **limit: 0** for `gemini-2.0-flash` — i.e., no usable free quota at all, not merely rate-limited. | **settled** (as a free-tier option; a paid tier was never evaluated) |
| **Ollama/Gemma local chat** | `chat.html` + `serve_chat.py` (repo root) | Scratch experiment: `serve_chat.py` serves `chat.html` on port 8080 (`serve_chat.py:3`), which calls a local Ollama server at `http://localhost:11434/api/chat` with model `gemma4:12b` (`chat.html:63-66`). Not wired to the product; no product code imports it. | **fenced-off** — not part of the product; do not extend, do not document as a feature |

All three landed/were recorded in `2ca7f83` (as of 2026-07-08). Reopening any of these = new evidence + `kernl-change-control`.

## E8 — Private docs untracked 6 minutes after the initial commit

- **Symptom/Trigger:** CLAUDE.md-era docs reference a PRD, but `company_brain_PRD_v4.md` and `brand_alchemy_company_brain.html` are nowhere in the working tree.
- **Root cause:** `0762fba` (20:03:22 IST) accidentally committed them (1,061 and 254 lines); `f1c4fd6` (20:09:42 IST, 6 minutes later) untracked both and added them to `.gitignore` (`.gitignore:45-46`, still there as of 2026-07-08). They were private/company documents.
- **Evidence:** `git show --stat f1c4fd6`. They are absent from this clone's working tree but **remain recoverable from history**: `git show 0762fba:company_brain_PRD_v4.md` (read-only reference; treat as private — do not re-add, quote at length, or publish).
- **Status:** **settled/fenced-off.** Deliberately gitignored. The PRD is useful archaeology for original intent; product-truth questions go to `knowledge-compilation-reference` and `kernl-architecture-contract`, not a 4-versions-old PRD.
- **Lesson:** the .gitignore entries are load-bearing; do not "clean them up".

## E9 — graphiti.md is someone else's README

- **Symptom/Trigger:** `graphiti.md` (665 lines, repo root) looks like an in-house temporal-graph design doc.
- **Root cause:** it is a verbatim copy of the **getzep/graphiti** open-source project README, saved as prior-art reference during the operational-graph design work (`2ca7f83`). Tells: Zep hiring notice (`graphiti.md:11`), "Graphiti and Zep" section (`graphiti.md:54-58`), getzep.com links throughout.
- **Evidence:** `git grep -n "getzep" graphiti.md` (as of 2026-07-08).
- **Status:** **fenced-off.** It is NOT kernl's design, NOT a roadmap, and nothing in it is a commitment. kernl's actual graph design lives in `docs/operational-graph-master-plan.md` (see E7 row 1). External/marketing claims: `kernl-external-positioning`.
- **Lesson:** label prior-art imports at the top of the file — or expect exactly this confusion.

---

## Pre-flight checklist before proposing a change

- [ ] Does it resurrect per-source ingest nodes? -> E2, settled, stop.
- [ ] Does it add an LLM-provider fallback? -> E4, settled, stop.
- [ ] Does it touch auth, `/login`, `/auth/config`, `/companies/{id}`? -> E3 is the open decision; get it decided via `kernl-change-control` first.
- [ ] Does it introduce Neo4j / a graph database? -> E7, settled.
- [ ] Does it build on `chat.html`, `serve_chat.py`, or `graphiti.md`? -> E7/E9, fenced-off.
- [ ] Does it "explain" the 15% eval number as a bug to hotfix? -> E6 is a campaign, not a bug; read `kernl-eval-inversion-campaign` first.
- [ ] Is it a large multi-subsystem refactor? -> E5: plan the satellite sweep (CLAUDE.md, README, Dockerfile, tests, scripts, frontend) into the same change.

## Provenance and maintenance

Facts verified 2026-07-08 against the working tree and git history at the repo root (path contains a space — keep it quoted). All commands run from the repo root; `git grep`/`git show` work in both PowerShell and Git Bash.

| Volatile fact | Re-verify with |
|---|---|
| 9 commits, timeline | `git log --oneline --format='%h %ad %s' --date=short` |
| Initial 5 nodes (E1) | `git show --stat 0762fba` (look for `backend/graph/nodes/`) |
| Send fan-out, 5 extract branches (E1) | `git grep -n "Send(" backend/engine/graph.py` |
| ingest_* added then deleted (E2) | `git show --stat a688aff; git show --stat 5f7dc7e` |
| Chunking registry present (E2) | `git grep -n "_detect_by_content" backend/chunking/registry.py` |
| No `/auth/*` or `/companies/*` routes (E3) | `git grep -n "@app." backend/api.py` |
| Frontend still calls them (E3) | `git grep -n "auth/config" frontend/src/lib/auth.tsx` and `git grep -n "companies/" frontend/src/app/page.tsx` |
| `/login` pushes remain (E3) | `git grep -n "/login" frontend/src` |
| Token incident shape, no values (E4) | `git show 22ee2f0 --stat` (inspect the diff only if necessary; never copy string constants out of it) |
| Gateway endpoint + header (E4) | `git grep -n "x-api-key" backend/core/llm.py` |
| Retry/backoff constants (E4) | `git grep -n "range(5)" backend/core/llm.py` and `git grep -n "2 \*\* (attempt" backend/core/llm.py` |
| `2ca7f83` size (E5) | `git show --stat 2ca7f83` (expect "+18818 insertions") |
| CLAUDE.md staleness (E5) | `git grep -n "main.py" CLAUDE.md` |
| Broken imports (E5) | `git grep -n "RETRIEVAL_WEIGHTS" backend/runtime/brain_agent.py` (0 hits = still broken) vs `backend/tests/resolver_only_eval.py:20-26` |
| `--stability` kwargs bug (E5) | `git grep -n "company_id=COMPANY_ID" backend/tests/eval_harness.py` vs `git grep -n "def handle_agent_query" backend/runtime/brain_agent.py` |
| Port mismatch 7860 vs 8081 (E5) | `git grep -n "7860" README.md; git grep -n "8081" Dockerfile` |
| Eval numbers 15.0 / 52.5 / 62.5 (E6) | `git grep -n "accuracy_pct" backend/tests/eval_results_baseline.json backend/tests/resolver_eval_results.json` |
| strict/relaxed checker lines (E6) | `git grep -n "def check_action_strict\|def check_action_relaxed" backend/tests/eval_harness.py` |
| Neo4j rejection text (E7) | `git grep -n "never Neo4j" docs/operational-graph-master-plan.md` |
| Gemini quota 0 (E7) | `git grep -n "limit: 0" gemini_test_response.txt` |
| Chat scratch ports (E7) | `git grep -n "PORT = 8080" serve_chat.py; git grep -n "11434" chat.html` |
| Private docs gitignored (E8) | `git grep -n "company_brain_PRD_v4" .gitignore` |
| graphiti.md provenance (E9) | `git grep -n "getzep" graphiti.md` |

If any command's output diverges from an entry, the repo wins — update this file (through `kernl-change-control`) rather than trusting the chronicle.
