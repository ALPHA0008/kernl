---
title: Kernl Backend
emoji: 🧠
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Kernl

**Kernl is the Institutional Kernel** — the compiler, runtime, and constitution that turn an organization's judgment (its policies, exceptions, precedents, and authority) into versioned, provable, executable decisions for humans and AI agents.

The idea in one sentence: *truth is a log, policy is a compiled pure function, explanations are derivations, views are disposable, and governance is the system applied to itself.*

**An LLM never decides a policy-sensitive action inside Kernl.** LLMs propose policy drafts from cited evidence and explain outcomes in natural language. Reviewed, deterministic code decides.

---

## What we're building now: V1 — "The Decision Ledger"

One operational domain (refund / credit / discount decisions) running through deterministic, reviewed policy bundles:

- an **append-only ledger** — every decision recorded, pinned to the exact policy-bundle hash that produced it
- an **escalation inbox** — ambiguity is a first-class outcome, routed to humans, hardened into precedent
- **replay-diff on every policy change** — "CI for your refund policy": see which historical decisions flip before you publish

The full architecture (warrants, simulation, the organizational twin, the constitutional layer) arrives in versioned stages V1→V7 — see the plan of record below. Later versions add organs; they never transplant them.

## Status (honest, dated 2026-07-13)

**The V1 Decision Ledger backend core is built and fully tested** — 100/100 across 7 deterministic suites (zero LLM, DB, or network calls in any test).

| Shipped and verified | Explicitly not trusted / not done |
|---|---|
| Policy Bundle IR: typed conditions, evidence-gated publish, canonical SHA-256 content addressing ([backend/bundle/](backend/bundle/)) | The operational graph as decision authority — gated off (`GRAPH_AUTHORITY_ENABLED=False`), unit-test-guarded |
| Pure deterministic evaluator with complete derivation traces ([backend/runtime/evaluator.py](backend/runtime/evaluator.py)) | Historical eval artifacts (15.0% / 52.5% `[synthetic]`) — frozen diagnostic history, never capability proof |
| Append-only, hash-chained, idempotent Decision Ledger ([backend/ledger/](backend/ledger/)) | Console frontend — not yet rebuilt (next: [docs/V1_EXECUTION_PLAN.md](docs/V1_EXECUTION_PLAN.md) §7) |
| Escalation inbox → ledgered adjudication → golden-case promotion ([backend/escalation/](backend/escalation/)) | Supabase persistence adapters — DDL ready in [backend/schema.sql](backend/schema.sql); in-memory stores are the tested contract |
| Replay engine + replay-gated publish ([backend/replay/](backend/replay/)) | Any metric from synthetic corpora unless labeled `[synthetic]` |
| /v1 REST API with key auth, roles, tenant isolation ([backend/v1_api.py](backend/v1_api.py)) | Legacy fixture fallback — **removed**; DB failure is an explicit error |
| Authored reference bundle: 22 policies / 9 workflows, every evidence span byte-verified; 45 golden cases at 100% `[synthetic]` ([backend/bundle/seed_rivanly.py](backend/bundle/seed_rivanly.py)) | |

## The constitutional rules

Violating one of these is an architecture change, never a refactor:

1. **No non-deterministic enforce-path ruling.** LLMs propose and explain; deterministic code decides.
2. **No uncited norm.** Every published policy carries source identity, version, and span. No evidence, no publish.
3. **No mutation of history.** Append-only ledger; immutable content-addressed bundles; rollback moves a pointer.
4. **No ruling skips the ledger.** Write-ahead: no decision exists unless its ledger entry exists.
5. **Escalation is a first-class output.** Missing facts, conflict, or low evidence → `escalate`, never a guess.
6. **Kernl authorizes; it never executes.** Write actions require explicit approval adapters.

## Repository map

```
backend/
  core/        shared infra: LLM client, SSE bus, DB client, schemas
  engine/      compilation pipeline (LangGraph): extraction → synthesis
  runtime/     deterministic decision core: constraint resolver, precedence,
               condition evaluation, guardrails (zero LLM calls — keep it that way)
  tests/       eval harness + golden scenario corpora + historical eval artifacts
frontend/      Next.js console
data/sources/  synthetic company corpora (rivanly-inc, higgsfield) for eval/dev
scripts/       smoke and stress tests
docs/          the plan of record (two documents — see below)
.agents/skills/  canonical operational skills (`.claude/skills/` is a synced copy)
```

## Running it

Setup, run, compile, serve, and eval instructions are maintained as skills (verified against the tree; this README deliberately does not duplicate them):

- Environment & build: [.agents/skills/kernl-build-and-env/SKILL.md](.agents/skills/kernl-build-and-env/SKILL.md)
- Run & operate: [.agents/skills/kernl-run-and-operate/SKILL.md](.agents/skills/kernl-run-and-operate/SKILL.md)
- Evals & QA: [.agents/skills/kernl-validation-and-qa/SKILL.md](.agents/skills/kernl-validation-and-qa/SKILL.md)

## The plan of record

| Document | Role |
|---|---|
| [docs/Kernel_arc.md](docs/Kernel_arc.md) | **The binding build plan** — full technical architecture (computing model, IR, compiler, runtime, simulator, formal methods, crypto, distributed systems) and the versioned roadmap V0→V7 |
| [docs/Product_summit.md](docs/Product_summit.md) | **The vision** — why Kernl exists, the category (Institutional Computing), the warrant primitive, the 10-year end-state. Direction, never current scope |

For AI coding sessions: [CLAUDE.md](CLAUDE.md) (canonical) / [AGENTS.md](AGENTS.md) (mirror) carry the operating rules. Everything in this repo must tell the same story as the two plan documents; where anything disagrees, the plan of record wins.
