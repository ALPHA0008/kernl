---
name: kernl-build-and-env
description: Load this when setting up the kernl dev environment from scratch, fixing a broken install, or debugging "ModuleNotFoundError", pip dependency gaps, .env / VLLM_BASE_URL misconfiguration, Docker / Hugging Face Spaces build issues, or Windows path problems. Provides the verified prerequisites, backend/frontend install runbooks, the honest gaps in requirements.txt, the correct .env template (backend/.env.example is stale), zero-dependency install verification, and known traps (port mismatches, PYTHONPATH, first-run model downloads).
---

# kernl — Build and Environment Setup

**What this covers:** recreating the dev environment from nothing — prerequisites, Python/Node installs, `.env`, install verification, optional Supabase DB, Docker/HF Spaces, and Windows traps.

**When NOT to use this:**
- Starting/operating the running app, endpoints, compile jobs → `kernl-run-and-operate`
- Env vars/flags semantics beyond initial setup → `kernl-config-and-flags`
- Something installed fine but behaves wrong → `kernl-debugging-playbook`
- Running evals or QA → `kernl-validation-and-qa`; code/architecture rules → `kernl-architecture-contract`; making changes → `kernl-change-control`

---

## 1. Prerequisites

| Tool | Version | Why |
|---|---|---|
| Python | 3.11 | Production pins `python:3.11-slim` (Dockerfile:1). Use 3.11 locally to match. |
| Node.js | 20+ | Frontend is Next.js **16.2.5** (frontend/package.json:12) — newer than most AI models' training data. The frontend has its own conventions: read `frontend/AGENTS.md` and `node_modules/next/dist/docs/` before writing frontend code; do not assume Next.js APIs from memory. |
| git | any recent | Repo history is a diagnostic tool (see `kernl-failure-archaeology`). |

**Jargon, defined once:**
- **vLLM gateway** — a shared, live HTTP proxy in front of a vLLM inference server. The backend talks to it via `backend/core/llm.py` using plain `httpx` POSTs to `{VLLM_BASE_URL}/generate` (llm.py:94), *not* the OpenAI SDK. It is a shared resource: do not hammer it to "test your install" (see section 9).
- **Supabase** — hosted Postgres used as the skills database. Optional for local dev (section 5).
- **Brain** — the compiled skills JSON the pipeline produces; the runtime agent reads it from DB or from a local fallback file.

**Trap:** the root `CLAUDE.md` describes an older layout (`backend/main.py`, `backend/llm.py`, OpenAI SDK client, 5-table schema). The actual code is `backend/api.py`, `backend/core/llm.py` (httpx client), and a 7-table `backend/schema.sql` (as of 2026-07-07). When CLAUDE.md and code disagree, the code wins.

---

## 2. Backend setup runbook

All commands run **from the repo root**. The path contains a space — quote it everywhere.

```powershell
cd "d:\Abhijith P\Desktop\Project\kernl"
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # PowerShell; use .venv\Scripts\activate.bat for cmd
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

### The honest gaps in requirements.txt (as of 2026-07-07)

`backend/requirements.txt` lists exactly: `fastapi>=0.115, uvicorn[standard], openai, langgraph>=0.4, sentence-transformers, numpy, supabase, python-dotenv, python-multipart, pydantic`. Three problems:

| Gap | Detail |
|---|---|
| **Dead dependency** | `openai` is listed but no longer imported anywhere in `backend/` or `scripts/` (verify: `grep -rn "import openai" backend scripts` → no hits). Safe to install; do not write new code against it. |
| **Implicit dependencies** | `backend/core/llm.py:5-8` imports `httpx`, `torch`, and `transformers` directly. None are listed. Today they arrive **transitively** (`httpx` via `supabase`/`openai`; `torch`+`transformers` via `sentence-transformers`) — this is fragile: a future `sentence-transformers` release could drop or change them and silently break the install. Note the `sentence_transformers` package itself is never imported; it exists in requirements only as the transitive carrier. |
| **Scripts need `requests`** | `scripts/smoke_test.py:11` and `scripts/stress_test.py:14` import `requests`, which is not listed and not guaranteed transitively. |

**Safe install line** — run after the requirements install to pin the implicit deps explicitly:

```powershell
pip install httpx torch transformers requests
```

(On a CPU-only machine, `pip install torch` pulls the large default wheel; that is expected — the embedding model runs on CPU, `torch.set_num_threads(2)` at llm.py:31.)

---

## 3. Environment file (.env)

**Warning: `backend/.env.example` is stale (as of 2026-07-07).** It shows `VLLM_BASE_URL=http://<MI300X_IP>:8000/v1` — the `/v1` suffix is wrong for the current code, it omits `VLLM_API_KEY`, and its `COMPANY_ID` is read by nothing (the eval harness hardcodes `rivanly-inc` at backend/tests/eval_harness.py:33).

Correct template — create `backend/.env` (gitignored):

```bash
# Gateway base URL: NO /v1 suffix. Code appends /generate and /health itself
# (backend/core/llm.py:72,94). Defaults live at llm.py:13-14 if unset.
VLLM_BASE_URL=http://<gateway-host>:<port>
VLLM_API_KEY=<ask the team; do NOT commit>

# Optional — app runs without these (section 5)
SUPABASE_URL=<your supabase project url>
SUPABASE_KEY=<your supabase anon key>
```

Rules:
- `VLLM_BASE_URL` is the **gateway shape without `/v1`**. If health checks 404, the first suspect is a trailing `/v1`.
- Never commit credentials. For current default values see `backend/core/llm.py:13-14` — do not copy them into docs or chat.
- **Security:** a Hugging Face token was committed in git history (commit `22ee2f0`, in the old `backend/llm.py`). Treat it as compromised — it must be revoked, never reused, and never reproduced anywhere.
- `load_dotenv(override=True)` at llm.py:11 means `backend/.env` **overrides** already-set shell env vars for the LLM module.

---

## 4. Verify the install (no LLM, no DB, no network)

Run in this order; each step widens the surface tested.

**Step 1 — imports resolve** (from repo root, venv active):

```powershell
python -c "import fastapi, uvicorn, langgraph, numpy, supabase, httpx, torch, transformers; print('imports OK')"
```

**Step 2 — the zero-dependency smoke check.** `backend/tests/test_constraint_resolver.py` runs **26 tests** of the deterministic constraint resolver — no LLM calls, no DB, no network (its import chain is pure stdlib):

```powershell
python backend/tests/test_constraint_resolver.py
```

Expect `Results: 26/26 passed, 0 failed`, exit code 0. This is the canonical "is my checkout + Python sane" check. It self-inserts the repo root into `sys.path` (test file line 11), but run it from the repo root anyway for consistency.

**Step 3 — gateway reachability (needs network + credentials).** Only after `.env` is set:

```powershell
python backend/test_health.py
```

This calls `check_vllm_health()` (backend/core/llm.py:68) — it requires the shared gateway to be reachable. `{"healthy": True, ...}` means you are fully wired. If it fails, recheck `VLLM_BASE_URL` shape (no `/v1`) and `VLLM_API_KEY`. Do not proceed to compiles to "test harder" — see section 9.

---

## 5. Database setup (optional)

The app **runs without Supabase**. `backend/core/db/supabase.py:10-15` sets the client to `None` when `SUPABASE_URL`/`SUPABASE_KEY` are absent, and the brain agent falls back to a checked-in compiled brain at `backend/tests/last_compiled_brain.json` (fallback path defined at backend/runtime/brain_agent.py:602-604). Query-time agent work therefore needs no DB. Compile runs that persist versions do need it.

To set up the DB: open the Supabase SQL editor and run the whole of `backend/schema.sql`. It creates **7 tables** — `companies`, `skills_files`, `skills`, `source_files`, `compile_runs`, `operational_entities`, `relationship_edges` — and seeds the demo company `rivanly-inc` (schema.sql:10, idempotent `ON CONFLICT DO NOTHING`). Then fill `SUPABASE_URL`/`SUPABASE_KEY` in `backend/.env`.

Demo source data ships in the repo: 8 files under `data/sources/rivanly-inc/` (5 markdown SOPs + 3 JSON exports).

---

## 6. Frontend setup

```powershell
cd "d:\Abhijith P\Desktop\Project\kernl\frontend"
npm install
npm run dev          # Next.js dev server on http://localhost:3000
```

- The frontend targets the backend via `NEXT_PUBLIC_API_URL`, defaulting to `http://localhost:8081` (frontend/src/lib/api.ts:2). Override in `frontend/.env.local` (gitignored) if your backend runs elsewhere.
- Stack: Next.js 16.2.5, React 19.2.4, Tailwind v4, TypeScript (frontend/package.json). Again: this Next.js version postdates most models' training data — consult `frontend/AGENTS.md` and the in-repo Next docs before coding.

---

## 7. Docker and Hugging Face Spaces

The root `Dockerfile` builds the **backend only**: `python:3.11-slim` base, installs `backend/requirements.txt` (so it inherits the same implicit-dependency fragility as section 2), copies `backend/` and `data/`, sets `ENV PYTHONPATH=/app`, `EXPOSE 8081`, and runs:

```
uvicorn backend.api:app --host 0.0.0.0 --port 8081
```

**Known break (as of 2026-07-07):** the README's HF Spaces frontmatter declares `app_port: 7860` (README.md:7) while the container serves on **8081**. HF Spaces routes traffic to `app_port`, so with this mismatch the Space cannot reach the app. Fix one side (change `app_port` to 8081, or the Dockerfile/CMD to 7860) — via change control (`kernl-change-control`), not ad hoc.

**PYTHONPATH mirror:** the container relies on `PYTHONPATH=/app` so `backend.*` imports resolve. Locally you get the same effect by always running from the repo root:

```powershell
python -m uvicorn backend.api:app --port 8081     # from repo root, venv active
```

Note: `scripts/smoke_test.py:17` targets `http://localhost:8081`, but `scripts/stress_test.py:20` targets `http://localhost:8080` — the stress test port is stale (as of 2026-07-07); edit or ignore accordingly.

---

## 8. Windows traps

| Trap | Rule |
|---|---|
| Path contains a space (`d:\Abhijith P\...`) | Quote every path in every command, script, and config. Unquoted paths fail in surprising places (pip, npm scripts, PowerShell args). |
| `backend.*` imports fail (`ModuleNotFoundError: backend`) | You ran from the wrong directory. Run `python -m ...` and all test scripts **from the repo root** so the `backend` package resolves (mirrors the container's `PYTHONPATH=/app`). |
| Stray `nul` files | Windows redirection to `NUL` under Git Bash can create literal files named `nul`. They are gitignored (`.gitignore`: `nul`, `backend/nul`) — do not commit or chase them as bugs. |
| First embedding call hangs/downloads | `sentence-transformers/all-MiniLM-L6-v2` downloads from Hugging Face on first use (backend/core/llm.py:32-35). Needs network access and a minute or two; cached afterward in the HF cache dir. Budget for this on first agent query or eval. |
| PowerShell 5.1 | No `&&` chaining; run commands separately or use `;`. |

---

## 9. What NOT to do

- **Do not run compiles or evals to test your install.** The vLLM gateway is a shared live environment; a compile fans out many LLM calls. The install check is section 4 — the 26 resolver unit tests plus one `test_health.py` ping. Nothing more.
- Do not "fix" `requirements.txt`, ports, or the Dockerfile inline while setting up — file it through `kernl-change-control`.
- Do not write new code against the `openai` package (dead dep) or against CLAUDE.md's described layout (stale).
- Do not paste credential values (gateway key, Supabase keys, anything from commit `22ee2f0`) into files, logs, or chat.

---

## Provenance and maintenance

All facts verified directly against the repo on **2026-07-07**. Re-verify volatile facts before trusting this document:

| Fact | Re-verification command (from repo root) |
|---|---|
| requirements.txt exact contents | `cat backend/requirements.txt` |
| `openai` is a dead dep | `grep -rn "import openai\|from openai" backend scripts` (expect no hits) |
| httpx/torch/transformers implicit imports | `grep -n "import httpx\|import torch\|from transformers" backend/core/llm.py` (expect lines 5, 7, 8) |
| scripts need `requests` | `grep -n "import requests" scripts/smoke_test.py scripts/stress_test.py` |
| Gateway URL shape (no /v1) and defaults | `grep -n "VLLM_BASE_URL\|VLLM_API_KEY" backend/core/llm.py` (lines 13-14); `grep -n "/generate\|/health" backend/core/llm.py` |
| `.env.example` still stale | `cat backend/.env.example` (still shows `:8000/v1` + `COMPANY_ID`?) |
| Resolver test count = 26 | `grep -c "def test_" backend/tests/test_constraint_resolver.py` |
| Resolver test is LLM/DB-free | `head -5 backend/tests/test_constraint_resolver.py` |
| Supabase optional / None client | `sed -n '10,16p' backend/core/db/supabase.py` |
| Local brain fallback path | `grep -n "last_compiled_brain" backend/runtime/brain_agent.py` (~line 603) |
| Schema table count = 7 + seed | `grep -c "CREATE TABLE" backend/schema.sql` ; `grep -n "rivanly-inc" backend/schema.sql` |
| Docker port 8081 / PYTHONPATH | `grep -n "EXPOSE\|PYTHONPATH\|CMD" Dockerfile` |
| HF `app_port` 7860 mismatch | `grep -n "app_port" README.md` |
| Next.js / React versions | `grep -n '"next"\|"react"' frontend/package.json` |
| Frontend API URL default 8081 | `grep -n "NEXT_PUBLIC_API_URL" frontend/src/lib/api.ts` |
| smoke=8081 vs stress=8080 ports | `grep -n "^API = " scripts/smoke_test.py scripts/stress_test.py` |
| `nul` gitignore entries | `grep -n "^nul\|backend/nul" .gitignore` |
| Embedding model first-use download | `grep -n "all-MiniLM-L6-v2" backend/core/llm.py` |
| Leaked-token commit exists | `git show --stat 22ee2f0` (do not print its diff into shared docs) |
