# Kernl — CLAUDE.md

Canonical operating file for AI coding sessions. `AGENTS.md` mirrors this file — **edit here first, sync there.**
This file contains no schemas, file trees, or endpoint lists: those rot. They live in the maintained skills under `.agents/skills/`.

---

## What Kernl is

Kernl is the **Institutional Kernel**: the compiler, runtime, and constitution that turn an organization's judgment — its policies, exceptions, precedents, and authority — into versioned, provable, executable decisions for humans and AI agents. Everything reduces to one sentence: *truth is a log, policy is a compiled pure function, explanations are derivations, views are disposable, and governance is the system applied to itself.*

**What we are building right now is V1 — "The Decision Ledger":** one operational domain (refund / credit / discount decisions) running through deterministic, reviewed policy bundles, with an escalation inbox, an append-only ledger, and replay-diff on every policy change — "CI for your refund policy."

## The plan of record (the only two strategy documents)

| Document | Role |
|---|---|
| `docs/Kernel_arc.md` | **The binding build plan.** Technical architecture (Parts 1–15) and the versioned roadmap V0→V7 (Part 16). Build order, invariants, what's deferred, what's never built |
| `docs/Product_summit.md` | **The vision.** Why Kernl exists, the category (Institutional Computing), the warrant primitive, the 10-year end-state. Direction only — never cite it as current scope |

Everything else in the repo (README, skills, code) must agree with these two. If you find a contradiction, the plan of record wins; fix the other artifact.

## Current status (V1 backend core SHIPPED — honest, dated 2026-07-13)

The V1 Decision Ledger backend exists and is fully tested (115/115: 108 across 8 deterministic suites with zero LLM/DB/network, plus 7 Postgres adapter contract tests run green against live Supabase):
- **`backend/bundle/`** — Policy IR (typed conditions, evidence-gated, override edges), canonical SHA-256 content addressing, replay-gated draft→publish→activate lifecycle.
- **`backend/runtime/evaluator.py`** — the pure decision function: exhaustive per-workflow evaluation, matched/failed/undeterminable semantics, overrides→specificity→priority precedence, defeasible dominance rule, complete derivation trace. Strict: a condition on a missing fact NEVER silently passes.
- **`backend/ledger/`** — append-only, write-ahead, hash-chained, idempotent decision events; adjudications link to originals.
- **`backend/escalation/`** — inbox lifecycle; resolutions are ledgered adjudications; promote-to-golden closes the precedent loop.
- **`backend/replay/`** — golden-case + reference-bundle replay with flip/new-escalation reporting; the publish gate.
- **`backend/v1_api.py` + `v1_container.py`** — /v1 REST surface, API-key auth (owner/approver/agent), tenant isolation, 503-never-fallback.
- **Seed:** `backend/bundle/seed_rivanly.py` — 22 authored policies across 9 workflows, every evidence span verified against source bytes; 58 golden cases pass 100% `[synthetic]`. Second corpus `backend/bundle/seed_higgsfield.py` — 8 authored policies (refund workflow), 15 golden cases pass 100% `[synthetic]`.
- **Persistence (LIVE):** `backend/stores_pg.py` — five psycopg3 adapters over Supabase Postgres (session pooler); append-only enforced by DB trigger; per-company advisory-lock chain appends; `KERNL_DB_URL` set → Postgres, unset → in-memory reference stores. Contract suite (`backend/tests/test_pg_stores.py`) runs against the real DB in a throwaway schema. Restart-persistence verified: bundle, ledger chain, and idempotency survive process death.
- **Extraction demoted (Step 6 done):** `backend/bundle/converter.py` — skills → policy *drafts* only, never publishable without verified spans; W8 warnings surfaced; legacy `/agent/*` endpoints retired (410).

Truth fixes applied: fixture fallback **removed** (DB failure → explicit error); Brain-vs-Generic baseline **rejected at runtime**; graph decision gate **off** (`GRAPH_AUTHORITY_ENABLED=False`, unit-test-guarded); legacy eval harness no longer overwrites golden baselines.

**Remaining for V1 complete:** the console frontend (rip-and-rebuild per `docs/V1_EXECUTION_PLAN.md` §7) · property-based + metamorphic evaluator suites (Tier-1 hardening) · hardening pass (structured logs, metrics, smoke/stress on /v1, skills/docs sync). Historical eval numbers (15.0%/52.5% `[synthetic]`) remain diagnostic history only.

## The constitutional rules — no session may violate these (V1, from the arc)

1. **No non-deterministic enforce-path ruling.** Zero LLM calls in `backend/runtime/` decision-path modules (`constraint_resolver.py`, `precedence.py`, `condition_eval.py`, `guardrails.py`, `graph_retriever.py`). LLMs propose and explain; deterministic code decides.
2. **No uncited norm.** A policy without source identity + version + span is a draft, never runtime authority. Extraction proposes; it never disposes.
3. **No mutation of history.** The ledger is append-only; bundles are immutable and content-addressed; rollback moves a pointer.
4. **No ruling skips the ledger.** Write-ahead: no decision exists unless its ledger entry exists. No fixture fallbacks.
5. **Escalation is a first-class output.** Missing facts, conflict, or low evidence → `escalate`. Never guess, never default to approve.
6. **Kernl authorizes; it never executes.** Write actions go through explicit approval adapters. The moment Kernl executes, it becomes a workflow engine and dies.

## Build order (arc Part 15 — in this order, nothing skipped)

1. Reify the **bundle** (content-addressed, signed, versioned decision artifact — replaces "skills file")
2. Pure-function resolver + **ledger** every evaluation
3. Grow the eval corpus into **golden replay CI** gating every compile
4. **Escalation + adjudication** loop (deliberation hardens into precedent)
5. **Conflict detection** with concrete counterexamples
6. Warrants (V4 — only on customer pull: an agent that acts, not drafts)

**Never build:** blockchain · a workflow/execution engine · autonomous self-modifying policy · a universal ontology upfront · chat-as-the-product. **Hype to avoid:** agent-framework churn (LangGraph is scaffolding, never load-bearing) · GraphRAG-as-identity · vector-DB-as-brain · ZK before V7 · fine-tuning-as-moat.

## Operating rules for sessions

- Architecture changes: load `.agents/skills/kernl-architecture-contract` first; behavior-changing work routes through `.agents/skills/kernl-change-control`.
- Setup/run/eval how-to: `kernl-build-and-env`, `kernl-run-and-operate`, `kernl-validation-and-qa` skills. `.agents/skills/` is canonical; `.claude/skills/` is a synced copy.
- Label every synthetic-corpus metric `[synthetic]` — the two corpora in `data/sources/` are authored test fixtures, not proof.
- Never resurrect: Company Brain positioning, graph-as-decision-authority, breadth-first demo scope, or Brain-vs-Generic demo theater as product proof.
- The four V1 unacceptable debts (arc Part 16) are constitutional: non-determinism on the enforce path, uncited norms, history mutation, ledger-skipping rulings.

## Layout (top level only — details live in skills)

`backend/{core,engine,runtime,tests}` · `frontend/` · `data/sources/` · `scripts/` · `docs/` · `.agents/skills/`
