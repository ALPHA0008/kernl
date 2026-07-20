---
name: kernl-build-and-env
description: Load this when setting up the Kernl dev environment from scratch, fixing a broken install, or debugging "ModuleNotFoundError", pip dependency gaps, .env misconfiguration (KERNL_DB_URL, KERNL_ADMIN_KEY, KERNL_API_KEYS), Docker/Hugging Face Spaces build issues, or Windows path problems. Provides verified prerequisites, backend/frontend install runbooks, the honest gaps in requirements.txt, the correct .env template (backend/.env.example is stale), zero-dependency install verification, and known traps.
---

# Kernl — Build and Environment Setup

**What this covers:** recreating the dev environment from nothing — prerequisites, Python/Node installs, `.env`, install verification, optional Postgres DB, Docker/HF Spaces, and Windows traps.

**When NOT to use this:**
- Starting/operating the running app, `/v1` endpoints → `kernl-run-and-operate`
- Env vars/flags semantics beyond initial setup → `kernl-config-and-flags`
- Something installed fine but behaves wrong → `kernl-debugging-playbook`
- Running replay/golden-case QA → `kernl-validation-and-qa`; architecture rules → `kernl-architecture-contract`; making changes → `kernl-change-control`

---

## 1. Prerequisites

| Tool | Version | Why |
|---|---|---|
| Python | 3.11 | Production pins `python:3.11-slim` (`Dockerfile:1`). |
| Node.js | 20+ | Frontend is Next.js **16.2.5** (`frontend/package.json`) — newer than most AI models' training data. Read `frontend/AGENTS.md` and `node_modules/next/dist/docs/` before writing frontend code; do not assume Next.js APIs from memory. |
| git | any recent | |

**Trap:** the root `AGENTS.md` mirrors `CLAUDE.md` and is accurate for the current V1 architecture — but do not trust any doc's specific file paths or line numbers without re-verifying; this repo has moved fast and stale specifics are the norm, not the exception, in older skill files.

---

## 2. Backend setup runbook

All commands run **from the repo root**.

```bash
cd /path/to/Kernl
python -m venv .venv
source .venv/Scripts/activate    # or .venv\Scripts\Activate.ps1 on PowerShell
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

### requirements.txt, as it actually stands

```
fastapi>=0.115, uvicorn[standard], openai, langgraph>=0.4, sentence-transformers,
numpy<2, supabase, python-dotenv, python-multipart, pydantic,
psycopg[binary]>=3.2, hypothesis>=6.100
```

Two things worth knowing:

| Gap | Detail |
|---|---|
| **numpy is deliberately pinned `<2`** | An unpinned resolve pulls numpy 2.x, which is binary-incompatible with the pandas version pulled in transitively via `sentence-transformers` (`ValueError: numpy.dtype size changed`). This isn't hypothetical — it crashed the whole server mid-session before being pinned. Don't remove the pin without re-verifying the whole `sentence-transformers -> transformers -> sklearn -> pandas` chain is still numpy-1.x-compatible. |
| **`openai`, `langgraph`, `sentence-transformers` are legacy-pipeline deps** | They're needed only by `backend/engine/` (the retired extraction pipeline, still used as a library by `backend/tests/eval_harness.py` and diagnostic scripts) — **not** by the live `/v1` API, which `backend/api.py` no longer eagerly imports as of 2026-07-16. If you only care about `/v1`, `python -c "from backend.api import app"` should complete in well under a second; if it's slow, something is re-introducing an eager legacy import. |

`psycopg[binary]` and `hypothesis` are V1-era additions (Postgres adapters, property-based evaluator tests) — make sure your install actually picked them up if you're working from an older venv.

---

## 3. Environment file (`backend/.env`)

**`backend/.env.example` is stale** — it documents the pre-V1 legacy-pipeline setup (`VLLM_BASE_URL`, `COMPANY_ID`) and is missing every variable the live `/v1` system actually reads.

Correct template for **V1 work** — create `backend/.env` (gitignored):

```bash
# Postgres persistence. Unset -> in-memory reference stores (fine for tests/
# quick local dev, but VOLATILE: all state is lost on process restart).
KERNL_DB_URL=postgresql://...    # or SUPABASE_DB_URL -- either name works

# Gates POST /v1/tenants (tenant provisioning). Unset = provisioning is
# closed, not open -- this is intentional fail-closed behavior, not a bug.
KERNL_ADMIN_KEY=<pick a bootstrap secret>

# Optional: static bootstrap tenant keys, bypassing /v1/tenants entirely.
# "<key>:<company_id>:<role>[,...]", role is owner|approver|agent.
KERNL_API_KEYS=

# Only needed if you're touching the legacy extraction pipeline
# (backend/engine/, eval_harness.py) -- not required for /v1 work.
VLLM_BASE_URL=http://<gateway-host>:<port>   # NO trailing /v1
VLLM_API_KEY=<ask the team; do NOT commit>
```

Rules:
- Never commit credentials.
- **Security:** a Hugging Face token was committed in git history (commit `22ee2f0`, old `backend/llm.py`). Treat it as compromised — revoked, never reused, never reproduced anywhere including docs or chat.
- `load_dotenv(override=True)` in `backend/core/llm.py` means `backend/.env` **overrides** already-set shell env vars for the legacy LLM module specifically — doesn't apply to `KERNL_*` vars, which are read via plain `os.environ.get`.

---

## 4. Verify the install (no LLM, no DB, no network)

**Step 1 — imports resolve, and fast:**

```bash
python -c "import time; t=time.perf_counter(); from backend.api import app; print(f'{time.perf_counter()-t:.2f}s, {len(app.routes)} routes')"
```

Expect well under 1 second and 50+ routes. If it takes several seconds, something is re-introducing an eager legacy import into the `/v1` startup path — that's a regression, not normal.

**Step 2 — the full deterministic suite** (no LLM, no DB, no network — this is the canonical "is my checkout + Python sane" check):

```bash
python -m pytest backend/tests/ -q --ignore=backend/tests/test_pg_stores.py
```

Expect `144 passed` (as of 2026-07-16; re-verify the count, it grows). This covers bundle IR, the evaluator (including property-based + metamorphic suites), ledger, escalation/replay lifecycle, seed data, the `/v1` API surface, onboarding, and observability — all deterministic.

**Step 3 — the live-DB contract suite (needs `KERNL_DB_URL` set to a real Postgres):**

```bash
python -m pytest backend/tests/test_pg_stores.py -v
```

Runs against a throwaway schema in the real DB. Skipped (not failed — a hard `sys.exit(0)`, which `pytest -q` on the whole `backend/tests/` directory will report as a collection error unless you `--ignore` it, as in Step 2) if `KERNL_DB_URL`/`SUPABASE_DB_URL` is unset.

**Step 4 — end-to-end smoke test against a running server:**

```bash
uvicorn backend.api:app --host 127.0.0.1 --port 8000 &
KERNL_ADMIN_KEY=<your key> python scripts/smoke_test.py --base-url http://127.0.0.1:8000
```

Expect `29 passed, 0 failed`. See `kernl-run-and-operate` for the full endpoint reference and runbook.

---

## 5. Database setup

The app **runs without Postgres** — `KERNL_DB_URL` unset means the container falls back to in-memory reference stores (`backend/v1_container.py`). Fine for tests and quick local iteration; state does not survive a restart.

For real persistence: run `backend/schema.sql` against your Postgres instance (17 `CREATE TABLE` statements as of 2026-07-16 — the original 7-table legacy schema plus the V1 bundle/ledger/escalation/replay tables). Then set `KERNL_DB_URL` in `backend/.env`.

Seed data ships in the repo: `data/sources/rivanly-inc/` (used by `backend/bundle/seed_rivanly.py` — 22 authored policies, 58 golden cases) and `data/sources/higgsfield/` (used by `backend/bundle/seed_higgsfield.py` — 8 authored policies scoped to the refund workflow, 15 golden cases — see `kernl-validation-and-qa` for corpus status and remaining scope).

---

## 6. Frontend setup

```bash
cd frontend
npm install
npm run build && npm run start    # production mode -- see the dev-mode trap below
```

- Targets the backend via `NEXT_PUBLIC_KERNL_API_URL`, defaulting to `http://127.0.0.1:8000`. Override in `frontend/.env.local` (gitignored) if your backend runs elsewhere.
- Stack: Next.js 16.2.5, React 19.2.4, Tailwind v4, TypeScript.

**`npm run dev` trap (found and fixed 2026-07-16):** Turbopack's automatic workspace-root detection could misresolve to the repo root instead of `frontend/` on some Windows/Git-Bash setups, causing a `Can't resolve 'tailwindcss'` crash-loop that leaked a worker process per retry — observed spawning 300+ orphaned `node.exe` processes until the machine ran out of memory. Fixed by pinning `turbopack.root` explicitly in `frontend/next.config.ts`. If `npm run dev` ever misbehaves again on Windows: (1) verify that pin is still present, (2) `taskkill /F /IM node.exe` to clear any orphans — stopping the dev-server process does not reliably kill its full Windows process tree, (3) fall back to `npm run build && npm run start` (production mode, no Turbopack dev-compiler) while investigating.

---

## 7. Docker and Hugging Face Spaces

Root `Dockerfile`: `python:3.11-slim` base, installs `backend/requirements.txt`, copies `backend/` and `data/`, sets `PYTHONPATH=/app`, `EXPOSE 7860`, and binds `${PORT:-7860}`:

```
uvicorn backend.api:app --host 0.0.0.0 --port ${PORT}
```

Ports are aligned on **7860**: `README.md`'s HF frontmatter declares `app_port: 7860`, and the Dockerfile `EXPOSE`s 7860 and binds `${PORT:-7860}` (HF injects `PORT` at runtime). HF routes external traffic to `app_port`, which the container now listens on. (Reconciled 2026-07-17; it previously bound 8081 while the README said 7860, so the Space was unreachable.)

**PYTHONPATH mirror:** locally, always run from the repo root so `backend.*` imports resolve the same way the container's `PYTHONPATH=/app` does.

---

## 8. Windows traps

| Trap | Rule |
|---|---|
| `backend.*` imports fail (`ModuleNotFoundError: backend`) | Wrong working directory. Run `python -m ...` and test scripts **from the repo root**. |
| Stray `nul` files | Windows redirection to `NUL` under Git Bash can create literal files named `nul`. Gitignored — don't chase them as bugs. |
| PowerShell 5.1 | No `&&` chaining; use `;` or separate commands. |
| `npm run dev` fork-bomb | See section 6 — pin `turbopack.root`, and always verify `node.exe` process count after stopping a dev/start server. |
| First embedding call hangs/downloads | Only if you're touching the legacy pipeline: `sentence-transformers/all-MiniLM-L6-v2` downloads from Hugging Face on first use. Not on the `/v1` critical path. |

---

## 9. What NOT to do

- Do not run the legacy compile pipeline or evals to "test your install" — the shared vLLM gateway is live infrastructure, and none of it is on the `/v1` critical path anyway. Section 4 is the actual install check.
- Do not "fix" `requirements.txt`, ports, or the Dockerfile inline while setting up — file it through `kernl-change-control`.
- Do not paste credential values (gateway key, DB connection strings, anything from commit `22ee2f0`) into files, logs, or chat.

---

## Provenance and maintenance

Facts verified directly against the repo on **2026-07-16**. Re-verify volatile facts before trusting this document:

| Fact | Re-verification command (from repo root) |
|---|---|
| requirements.txt exact contents | `cat backend/requirements.txt` |
| numpy pin reason | `git log -p --follow -- backend/requirements.txt \| grep -A3 numpy` |
| backend.api import time | `python -c "import time; t=time.perf_counter(); from backend.api import app; print(time.perf_counter()-t)"` |
| Full test count | `python -m pytest backend/tests/ -q --ignore=backend/tests/test_pg_stores.py` |
| Schema table count | `grep -c "CREATE TABLE" backend/schema.sql` |
| Seed corpus status | `grep -c "^\s*_case(" backend/bundle/seed_rivanly.py`; check `data/sources/higgsfield/` for a seed script |
| Turbopack root pin | `grep -n "turbopack" frontend/next.config.ts` |
| Docker/HF port aligned on 7860 | `grep -n "PORT\|EXPOSE" Dockerfile; head -9 README.md` |
| Leaked-token commit (do not print contents) | `git log --oneline 22ee2f0 -1` |
