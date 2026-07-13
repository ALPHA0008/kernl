# V1 EXECUTION PLAN — "The Decision Ledger"

**Status:** Execution plan of record for V1
**Date:** 2026-07-13
**Authority:** `docs/Kernel_arc.md` (Part 16, V1 definition; Part 15 build order) — strategy frozen, this document plans execution only
**Scope:** Policy Bundle · Deterministic Evaluation Runtime · Decision Trace · Decision Ledger · Replay Engine · Escalation Workflow. Nothing else.
**Verified against:** working tree 2026-07-13; runtime facts cross-checked with `kernl-architecture-contract` and `kernl-validation-and-qa` skills (facts verified 2026-07-07)

---

## 1. Repository Audit

### 1.1 What already exists and works

| Asset | Where | Evidence |
|---|---|---|
| **Deterministic decision core** — resolver, precedence, typed-condition evaluation, guardrails; zero LLM calls | `backend/runtime/constraint_resolver.py`, `precedence.py`, `condition_eval.py`, `guardrails.py` | 26/26 unit tests pass (`backend/tests/test_constraint_resolver.py`) |
| **Ambiguity as first-class output** — entropy over candidates → `action_type="ambiguous"` | `constraint_resolver.py:102, :262, :490-494` | The seed of the Escalation workflow |
| **Typed conditions on policies** — `{field, operator, value, type}` with operator whitelists per type | `backend/engine/nodes/synthesize_skills.py:6-10, :82-130`; evaluated in `condition_eval.py` | The seed of the Policy IR |
| **Versioned compiled artifact with single-current enforcement** — `skills_files` rows, `is_current` partial unique index | `backend/schema.sql:12-23`; `write_brain.py:66-89` | The seed of the Policy Bundle registry |
| **Evidence linking** — skills carry `evidence` + `source_files` | `backend/engine/nodes/link_evidence.py` | Seed of "no evidence, no publish" |
| **Extraction pipeline (draft proposer)** — LangGraph: sources → 5-way parallel extraction → synthesis, correct Send/barrier/reducer discipline | `backend/engine/graph.py`, `state.py`, `nodes/` | Compiles the 12-skill reference brain in ~291 s |
| **Golden scenario corpus** — 40 hand-written scenarios (10 families incl. boundary + determinism + adversarial), canonical action labels, alias table | `backend/tests/eval_harness.py` (scenarios, `CANONICAL_ACTIONS`, `ACTION_ALIASES`) | The seed of the Replay Engine's case sets |
| **API skeleton + SSE streaming** — 16 routes: health, sources CRUD, compile+stream+status, agent query, skills, versions, diff | `backend/api.py:55-410`, `backend/core/sse.py` | FastAPI + uvicorn, works |
| **Synthetic corpora ×2** | `data/sources/rivanly-inc/` (8 files), `data/sources/higgsfield/` (6 files) | Dev/eval substrate `[synthetic]` |

### 1.2 Partially implemented (the V1 seeds)

| V1 component | What exists | What's missing |
|---|---|---|
| Policy Bundle | `brain_json` artifact, versioned rows, `is_current` index | Content-address (SHA-256 of canonical JSON), draft→review→publish lifecycle, immutability discipline (no in-place overwrite), bundle = *only* runtime authority |
| Deterministic Runtime | Resolver core (pure, tested) | Pure-function *contract* end-to-end: today `handle_agent_query` mixes DB loading, embedding retrieval, LLM verbalization, and a fixture fallback into one path (`brain_agent.py:602-641`) |
| Decision Trace | Resolver emits `decision_trace` with candidates/entropy; eval records retrieval traces | A complete, schema-versioned derivation object (per-policy condition results, precedence reason, bundle hash, evaluator version) — and it is never *persisted* |
| Decision Ledger | Nothing — decisions are returned, never recorded | The entire component: append-only `decision_events`, write-ahead discipline |
| Replay Engine | `eval_harness.py` replays 40 scenarios vs expected labels | Replay any *candidate bundle* over case sets / ledger history, diff vs published outcomes, persisted replay runs, publish gate |
| Escalation Workflow | `ambiguous` outcome exists in-process | Persistence, queue, adjudication (action + rationale + identity), lifecycle, promote-to-golden-case |

### 1.3 Missing entirely

- Tenant/actor identity on API calls (ledger events without actor identity are audit-worthless — minimal API-key auth is **in scope, justified** under Ledger integrity).
- Facts validation at the decision boundary (required-fields → escalate, not silently pass — arc runtime contract).
- Any persisted decision, escalation, or replay record. The system currently has no memory of what it decided.

### 1.4 Dead code, abandoned experiments, superseded systems

| Item | Where | Verdict |
|---|---|---|
| **Graph decision path** — W1: all 21 graph policies are unconditional `approve`, priority 0, no conditions; when the graph gate fires, deny-scenarios get approved | `build_operational_graph.py:69-73`; gate at `constraint_resolver.py:543-548` | Superseded. V1 evaluates the bundle exhaustively; the graph is not decision authority (CLAUDE.md status; arc Part 15) |
| **Embedding hybrid retrieval on the decision path** — top-5 semantic scoring picks the candidate set before the resolver sees it | `brain_agent.py:380-420, :554-599` | Superseded *for deciding*. A V1 bundle has O(10–100) policies — evaluate **all** of them against facts; no retrieval needed on the enforce path. (Embeddings may stay for console search only — out of critical path) |
| **Local fixture fallback** — DB failure silently serves `backend/tests/last_compiled_brain.json` | `brain_agent.py:602-604, :627` | Production-disqualifying. Replace with explicit 503 |
| **Demo A/B page** (`with_brain=false` comparison) | `frontend/src/app/demo/[companyId]/page.tsx`; `with_brain` param in `brain_agent.py:635` | Retired proof (CLAUDE.md "never resurrect") |
| **Broken test infra** — `resolver_only_eval.py` import-broken; `--stability` kwargs crash; ADV counter always 0; `condition_accuracy` structurally 0.0%; `stress_test.py` stale port 8080 | Verified in `kernl-validation-and-qa` §4 | Fix as part of V1 QA (small, enumerated) |
| **Frontend, all of it** — dashboard, compile stream, skills viewer, demo, glass-card components, mock `auth.tsx` | `frontend/src/*` | **Per owner directive: rip and rebuild.** Keep the stack (Next.js 16 / React 19 / Tailwind) and `lib/api.ts` *pattern* only |
| Stale docstrings/claims — "MemorySaver" checkpointing (none exists: `graph.py:85`), eval docstring says 21 scenarios (actual 40) | various | Fix opportunistically |

---

## 2. V1 Gap Analysis

| Capability | Current Status | Reuse % | Work Remaining | Priority |
|---|---|---|---|---|
| **Policy Bundle** | Versioned JSON artifact + single-current index exist; no hash, no lifecycle, skills-shape not policy-shape | 40% | Policy IR schema; skill→policy converter; canonical-JSON SHA-256; `policy_bundles`/`policies` tables; draft→review→publish→activate lifecycle; rollback = pointer move | **P0** |
| **Runtime** | Resolver core solid (26/26); wrapped in retrieval+LLM+fallback | 70% | Extract `evaluate(facts, bundle) → decision` pure function; exhaustive bundle evaluation (drop retrieval gate + graph gate from enforce path); facts validation; explicit 503 on DB loss; LLM explain becomes optional post-decision endpoint (guardrail retained) | **P0** |
| **Trace System** | Partial in-memory trace | 50% | Versioned Trace schema: facts as validated, every policy considered w/ per-condition results, exclusion reasons, precedence winner+rule, bundle hash, evaluator version | **P0** |
| **Ledger** | Does not exist | 10% (DB client + schema patterns reusable) | `decision_events` append-only table; write-ahead (no response before commit); idempotency keys; actor identity; hash-chain field (cheap, per arc Part 10 year-1) | **P0** |
| **Replay** | Eval harness is the embryo | 30% | Replay engine: case sets (golden + ledger ranges) × candidate bundle → outcome diff (flips / new escalations / unchanged); persisted `replay_runs`; wired as publish gate | **P1** |
| **Escalation** | `ambiguous` outcome only | 25% | `escalations` table + lifecycle (open→resolved/expired); adjudication (action, rationale, identity) recorded to ledger; promote-to-golden-case | **P1** |
| **Testing** | Tier-1 unit tests healthy; tiers 2–4 damaged | 60% | Fix 5 enumerated infra breaks; add unit suites for bundle hashing, facts validation, ledger write-ahead, replay diff; keep zero-LLM discipline for tiers 1–2 | **P1** |
| **Evaluation** | 40 scenarios, canonical labels, aliases; baseline-overwrite hazard; label mismatch compiler↔runtime↔eval | 55% | One label scheme end-to-end; scenarios become seed `golden_cases` rows; runs pinned to (bundle hash, evaluator version, case-set hash); stop in-place baseline overwrites | **P1** |

---

## 3. Repository Rationalization (recommendations only — nothing executed)

### Keep (directly supports V1)

- `backend/runtime/constraint_resolver.py`, `precedence.py`, `condition_eval.py`, `guardrails.py` — the deterministic core (refactored, not rewritten)
- `backend/engine/` pipeline + nodes — demoted to **draft proposer** (extraction → policy drafts for review); Send/barrier/reducer discipline preserved
- `backend/core/` (llm client, sse, db client, schemas) — SSE reused for compile-draft streaming
- `backend/tests/test_constraint_resolver.py` (tier-1 gate), `eval_harness.py` (scenario corpus → golden cases), both baseline JSONs (frozen diagnostic history)
- `backend/schema.sql` — extended, not replaced: `companies`, `source_files`, `compile_runs` stay live
- `data/sources/*` (both corpora), `scripts/smoke_test.py`, `scripts/stress_test.py` (port fix)
- `frontend/` stack config (Next 16, React 19, Tailwind) — the shell, not the contents
- `.agents/skills/` + `.claude/skills/`, `CLAUDE.md`/`AGENTS.md`/`README.md`, `docs/Kernel_arc.md`, `docs/Product_summit.md`

### Archive (superseded direction, keep for reference)

- `backend/runtime/graph_retriever.py` — graph path off the enforce path (W1); park behind a dead flag or move to an `attic/` module until a future version re-earns it with real conditions
- `backend/runtime/brain_agent.py` retrieval scoring (`_hybrid`, `_admissible`) — superseded by exhaustive bundle evaluation; the LLM verbalizer + guardrail portion survives into the optional explain endpoint
- `backend/tests/resolver_only_eval.py` — fix imports *or* archive once the new replay engine supersedes it (it exists only to re-measure the old 62.5% number)
- `frontend/src/app/*`, `frontend/src/components/*`, `frontend/src/lib/auth.tsx` — replaced wholesale by the V1 console (§7)

### Delete (no V1 value)

- `frontend/src/app/demo/[companyId]/` and the `with_brain=false` code path — retired proof, constitutionally barred from resurrection
- `backend/test_higgsfield.py`, `backend/show_brain.py`, `backend/test_health.py`, `backend/start_eval.py`, `backend/run_eval_background.py` — ad-hoc scripts superseded by the tiered test hierarchy (verify each is unreferenced before deletion)
- Stale `MemorySaver`/checkpointing claims wherever they appear in comments

---

## 4. Build Order (dependency-aware)

> Complexity: S ≤ 2 dev-days · M ≤ 5 · L ≤ 10. One engineer + AI assistance assumed; two engineers roughly halve the calendar.

### Step 0 — Truth fixes (no new features)
**Goal:** remove the two production-disqualifying behaviors and repair test infra so every later step is measurable.
**Files:** `brain_agent.py` (delete fixture fallback → explicit 503; delete `with_brain` param), `constraint_resolver.py` (graph gate off), `resolver_only_eval.py` (4 import renames), `eval_harness.py` (stability kwargs, ADV counter, condition_accuracy read, docstring, stop overwriting baselines — write `eval_results_<date>.json`), `stress_test.py` (port 8081).
**Depends on:** nothing. **Complexity: S.**
**DoD:** tier-1 26/26 still green; tier-2 runs LLM-free end-to-end; DB-down query returns 503 with explicit error body; no code path can read `last_compiled_brain.json` at runtime.

### Step 1 — Policy IR + Bundle registry
**Goal:** the immutable, content-addressed artifact that is the *only* runtime authority.
**Build:** Policy schema (id, version, status, scope/workflow, effect{kind, action}, priority, typed conditions[], authority{approval_required}, evidence[{source_id, source_version, span}], precedence{overrides, superseded_by}); canonical-JSON serializer + SHA-256; tables `policy_bundles` (id, company_id, hash, status draft|published|retired, created_by, published_by, parent_bundle_id) and `policies` (projection, keyed to bundle); lifecycle endpoints; **skill→policy converter** so the 2026-06-15 reference brain's 12 skills become the first draft bundle (the 5 condition-bearing skills convert cleanly; the 7 without conditions become drafts flagged `needs_conditions` — they cannot publish without either conditions or an explicit unconditional-effect review sign-off).
**Files:** new `backend/bundle/` module; `backend/schema.sql` additive; `backend/api.py` routes.
**Depends on:** Step 0. **Complexity: M.**
**DoD:** publish produces an immutable row with stable hash (same content → same hash, key-order independent); republishing identical content is a no-op; rollback activates a prior bundle without mutation; unit tests for hashing + lifecycle.

### Step 2 — Deterministic evaluation as a pure function + Trace
**Goal:** `evaluate(facts, bundle, evaluator_version) → (decision, trace)` — no DB, no clock, no LLM, no retrieval inside.
**Build:** facts validation (required fields per workflow → missing ⇒ `escalate` with `missing_facts` in trace); exhaustive evaluation of every in-scope policy via existing `condition_eval`; precedence via existing `precedence.py` (explicit supersession → specificity → priority → authority → escalate on unresolved tie — arc/PRD order); ambiguity logic re-anchored on *condition-matched* policies (entropy inputs change from retrieval scores to match results — resolver tests updated accordingly); Trace v1 schema (decision_id, bundle_hash, evaluator_version, validated_facts, per-policy {matched, per-condition {field, op, expected, actual, result}, exclusion_reason}, precedence{winner, rule}, outcome).
**Files:** `constraint_resolver.py` (refactor), new `backend/runtime/evaluator.py` + `trace.py`; unit tests.
**Depends on:** Step 1. **Complexity: L** (the heart of V1).
**DoD:** same (facts, bundle) → byte-identical decision+trace across 100 repeated runs and across process restarts; new unit suite ≥ 25 cases incl. boundary operators (`lte` at exactly 14, string equality, missing-field); tier-1 still green.

### Step 3 — Decision Ledger
**Goal:** no decision exists unless its ledger entry exists.
**Build:** `decision_events` append-only (decision_id, tenant, workflow, actor{type,id,key_id}, idempotency_key unique-per-tenant, facts, outcome, bundle_hash, trace JSONB, prev_event_hash chain field, created_at); write-ahead ordering (commit → then respond); idempotent replay of same key returns the original decision; minimal API-key auth (per-tenant keys, roles: owner | approver | agent) — **justified in-scope: ledger rows need actor identity to be audit-grade**.
**Files:** new `backend/ledger/`; `schema.sql`; `api.py` → `POST /v1/decisions:evaluate`, `GET /v1/decisions/{id}`, `GET /v1/ledger`.
**Depends on:** Step 2. **Complexity: M.**
**DoD:** killing the process between ledger commit and HTTP response never loses a recorded decision; duplicate idempotency key returns the original; every row verifies against its `prev_event_hash`; DB-down evaluation returns 503 and writes nothing.

### Step 4 — Escalation Workflow
**Goal:** ambiguity becomes work, and adjudication becomes history.
**Build:** on `escalate`/`ambiguous` outcomes, create `escalations` row (id, decision_id, reason enum {missing_facts, conflict, tie, low_evidence, authority_required}, candidates from trace, status open|resolved|expired, assigned_role); resolve endpoint (chosen action, rationale, resolver identity) → writes an `adjudication` decision-event to the ledger linked to the original; optional `promote_to_golden_case` flag copies (facts, chosen action) into `golden_cases`.
**Files:** new `backend/escalation/`; `schema.sql`; `api.py`.
**Depends on:** Step 3. **Complexity: M.**
**DoD:** an ambiguous evaluation produces exactly one open escalation; resolving it is idempotent, ledgered, and identity-stamped; promoted cases appear in the golden set with provenance.

### Step 5 — Replay Engine + publish gate
**Goal:** no bundle publishes without seeing its blast radius.
**Build:** `golden_cases` table seeded by migrating the 40 harness scenarios (id, facts, expected_action, expected_rule_fragment, provenance, `[synthetic]` label); replay run = case source (golden set and/or ledger facts in a date range) × candidate bundle → per-case (previous outcome vs candidate outcome) + summary (flips, new escalations, newly-passing, invariant: determinism check); persisted `replay_runs` (id, bundle_hash_candidate, bundle_hash_reference, case_set_hash, summary, per_case JSONB); publish endpoint requires an acknowledged replay run for that exact draft hash.
**Files:** new `backend/replay/`; `schema.sql`; `api.py`.
**Depends on:** Steps 2, 3 (ledger as case source), 1 (bundles). **Complexity: M.**
**DoD:** publishing without a matching replay run is rejected; replay of identical bundles reports zero flips; replay is LLM-free and completes the 40-case golden set in < 5 s; label scheme identical across compiler drafts, runtime outcomes, and case expectations (one enum, one place).

### Step 6 — Draft proposer integration (compiler → review)
**Goal:** the existing extraction pipeline feeds Policy Creation instead of minting authority.
**Build:** pipeline output lands as policy *drafts* (status draft, `needs_review`) with evidence spans; compile endpoints renamed under `/v1/drafts:extract` semantics; SSE stream reused for progress; silent-empty-extraction (W8) surfaced as a draft-count warning on the run record.
**Files:** `write_brain.py` → writes drafts not authority; `api.py`.
**Depends on:** Step 1. **Complexity: S–M.**
**DoD:** a full extraction run produces reviewable drafts and zero published policies; W8 failure yields a visible warning, not a quiet success.

### Step 7 — V1 Console (frontend, rebuilt from zero)
**Goal:** the six screens in §7, production-grade, against the real API only.
**Files:** `frontend/src/` rebuilt; old pages/components deleted per §3.
**Depends on:** Steps 1–6 (build screens behind each API as it lands — Evaluate+Trace can start after Step 3).
**Complexity: L.**
**DoD:** per-screen success metrics in §7; no mock data anywhere; auth-gated; renders correct states for 503/unavailable.

### Step 8 — Hardening pass
**Goal:** production posture for the whole loop.
**Build:** structured logs w/ tenant+decision+bundle ids; latency/outcome/escalation metrics; retention policy documented; smoke/stress updated to the new endpoints; README/skills updated to V1 reality (per `kernl-docs-and-writing` discipline).
**Depends on:** all. **Complexity: M.**
**DoD:** smoke test green end-to-end against a clean deploy; docs describe the system that exists.

**Total: ~35–45 dev-days (7–9 weeks single-engineer; ~5 weeks with two).**

---

## 5. V1 Critical Path

Minimum task set demonstrating **Scenario → Evaluation → Trace → Ledger Entry → Replay → Escalation**:

1. Step 0 items 1–2 only (kill fixture fallback, disable graph gate)
2. Step 1 without lifecycle UI (bundle schema + hash + publish/activate endpoints; convert the 5 condition-bearing reference skills as the first published bundle)
3. Step 2 in full (pure evaluator + trace)
4. Step 3 without full auth polish (single tenant key)
5. Step 4 core (escalation row + resolve endpoint)
6. Step 5 golden-set replay only (ledger-range replay can follow)
7. Console: Evaluate + Trace Inspector + Ledger + Escalations Inbox + Replay Report (Policy Workbench read-only initially)

Everything else in §4 is required for *quality* V1 but not for the loop demonstration. Critical path ≈ **18–22 dev-days**.

---

## 6. Risk Register (repository-specific)

### Architectural
| Risk | Grounding | Mitigation |
|---|---|---|
| Ambiguity logic mis-anchored after retrieval removal — entropy currently computed over retrieval-scored candidates; switching to condition-matched sets changes its distribution | `constraint_resolver.py:102, :490-494` | Step 2 re-derives thresholds against the 40-scenario set; DET-family scenarios are the acceptance gate (6/6 must stay ambiguous) |
| Skill→policy conversion loses semantics — 7 of 12 reference skills have no typed conditions (W5); naive conversion publishes condition-less approvals (repeating W1 at bundle level) | `last_compiled_brain.json`; W1/W5 | Converter flags `needs_conditions`; publish gate blocks unconditioned effects without explicit reviewer sign-off |
| Authority naming schemes mixed (`founder` vs `role_founder`), duplicated AUTHORITY_LEVEL tables can drift | W4; `entities.py:73-106`, `precedence.py:16-47` | Step 2 normalizes to one enum in the Policy IR; single source module |
| Supabase as single external dependency on the decision path | `brain_agent.py:607` | In-process bundle cache keyed by hash (immutable ⇒ cache-safe); explicit 503 semantics; bundle pull-by-hash is the only DB read needed to evaluate |
| Label-scheme divergence re-emerges (the 15% vs 62.5% incomparability repeats) | `kernl-validation-and-qa` §3 | One action enum owned by the bundle module; compiler, runtime, cases all import it (Step 5 DoD) |

### Product
| Risk | Mitigation |
|---|---|
| Escalation inbox with no adjudicator engagement = dead precedent loop | Inbox is a console centerpiece (§7); resolve flow ≤ 3 clicks; promote-to-golden makes adjudication visibly compound |
| Replay cold-start (empty ledger) | Golden set (40 seeded cases, growable) is a first-class case source from day one |
| Two synthetic corpora only — `[synthetic]` numbers get quoted as capability | Label enforced in UI and API responses for synthetic tenants (CLAUDE.md rule) |

### Technical debt
| Risk | Mitigation |
|---|---|
| W7 (no compile checkpointing) — 291 s all-or-nothing extraction | Accept for V1: extraction is now a *draft* path, failure costs a retry, never correctness. Documented, not fixed |
| W8 (silent `[]` extraction) poisons draft counts | Step 6 surfaces as warning; never blocks the decision path (drafts aren't authority) |
| W6 (embedding truncation) | Moot on the enforce path (embeddings removed from deciding); note kept for console search if added |
| Baseline overwrite hazard destroys history | Step 0 makes eval outputs date-stamped; goldens frozen |

### Evaluation
| Risk | Mitigation |
|---|---|
| New evaluator invalidates old numbers; team "loses" the 15%/62.5% story | Correct and intended: old artifacts stay frozen as diagnostic history; V1 metrics are (bundle-hash, evaluator-version, case-set-hash)-pinned from first run |
| `condition_accuracy` and ADV metrics broken → boundary quality invisible exactly when Step 2 needs it | Fixed in Step 0 *before* evaluator work begins |
| Golden set too small (40) to gate publishes credibly | Every adjudication can promote a case; DoD for Step 8 includes ≥ 60 cases across both corpora |

---

## 7. Product Surface Design (V1 Console)

**Owner directive acknowledged:** existing frontend is discarded entirely. Stack retained: Next.js 16 / React 19 / Tailwind. No mock data, no demo modes, real auth, production only.

### Personas
| Persona | Role in V1 | Primary screens |
|---|---|---|
| **Policy Owner** (support-ops lead) | Authors/reviews policies, publishes bundles, reads replay reports | Policy Workbench, Replay, Ledger |
| **Approver / Adjudicator** (support manager) | Works the escalation queue; their rulings become adjudication events | Escalations Inbox, Trace Inspector |
| **Integrator** (platform engineer / agent) | Calls the decision API; verifies behavior in the console | Evaluate, Trace Inspector, Ledger |

### User journey (the V1 loop)
Policy Creation → publish (replay-gated) → Evaluation (API or console) → Trace Inspection → Ledger accumulation → Replay on next change → Escalation adjudication → golden-case growth → repeat.

### Navigation & information architecture
```
Sidebar (persistent):
  ▸ Policies      (workbench: drafts, published bundle, diff)
  ▸ Evaluate      (decision console)
  ▸ Ledger        (append-only event browser)
  ▸ Escalations   (inbox + resolution)
  ▸ Replay        (runs + reports; publish gate lives here)
  ▸ Sources       (read-only list + extract-drafts trigger)   [thin]
  ▸ Settings      (API keys, tenant)                          [thin]
Deep-link objects: /decisions/{id} (trace) · /bundles/{hash} · /replays/{id} · /escalations/{id}
```

### Screens

**1. Policy Workbench** — *Purpose:* create, review, and publish the bundle.
Actions: list policies by status; edit draft (typed conditions builder with operator whitelist, effect, priority, evidence spans required); review extraction drafts (accept/edit/reject, citation shown inline); diff draft bundle vs published; request publish → blocked until a replay run for this exact draft hash is acknowledged.
Backend: bundle/policy CRUD, draft list, diff endpoint, publish gate.
Success: time-to-review-per-policy (target < 5 min); zero published policies without evidence; 100% publishes preceded by acknowledged replay.

**2. Evaluate (Decision Console)** — *Purpose:* run a real decision.
Actions: pick workflow; typed facts form (schema-driven) + raw JSON tab; submit → outcome card (approve/deny/route/escalate + action), bundle hash, link to trace; repeat-with-same-facts button (should prove determinism visibly).
Backend: `POST /v1/decisions:evaluate`; workflow fact-schemas.
Success: P50 evaluate < 300 ms; identical facts → identical decision_id-referenced outcome 100%.

**3. Trace Inspector** — *Purpose:* the receipt.
Actions: view validated facts; every policy considered with per-condition expected/actual/result; exclusion reasons; precedence winner + rule; evidence excerpts; bundle hash + evaluator version; buttons: *re-evaluate now* (proves replay equality) and *replay against draft bundle*.
Backend: `GET /v1/decisions/{id}` (full trace).
Success: an adjudicator can answer "why this outcome" without leaving the screen; re-evaluate equality 100%.

**4. Ledger** — *Purpose:* the institutional memory, browsable.
Actions: filter by workflow/outcome/actor/date/bundle; row → Trace Inspector; export (CSV/JSON) for audit; chain-verification indicator.
Backend: `GET /v1/ledger` (paged, filtered); chain verify endpoint.
Success: any past decision reachable in ≤ 3 interactions; export used in pilot audits.

**5. Escalations Inbox** — *Purpose:* where ambiguity becomes precedent. The adjudicator's daily surface.
Actions: queue with reason chips (missing facts / conflict / tie / authority); detail = trace + candidate actions with their supporting policies side-by-side; resolve (choose action, mandatory rationale) → ledgered adjudication; optional promote-to-golden-case toggle; status board (open/resolved, age).
Backend: escalations list/detail/resolve; golden-case promote.
Success: median time-to-resolution < 1 business day in pilot; ≥ 30% of resolutions promoted to golden cases; zero resolutions without rationale.

**6. Replay** — *Purpose:* blast radius before publish; CI for policy.
Actions: pick candidate bundle (draft) + case source (golden set / ledger range); run; report = flips table (case, old → new, which policy caused it), new escalations, unchanged count; acknowledge report (unblocks publish); history of runs pinned to hashes.
Backend: replay run/create/get; publish-gate acknowledgment.
Success: 100% of publishes gated; a Policy Owner can predict a change's impact without asking engineering.

### Backend architecture (V1 target, additive to today)

```
backend/
  bundle/        Policy IR, canonical hash, lifecycle, skill→policy converter
  runtime/       evaluator.py (pure fn) + trace.py + existing condition_eval/precedence/guardrails
  ledger/        decision_events, write-ahead, idempotency, hash chain, auth (API keys)
  escalation/    lifecycle + adjudication events + golden-case promotion
  replay/        case sets, run engine, diff, publish gate
  engine/        (existing) extraction pipeline → policy DRAFTS only
  core/          (existing) llm, sse, db
  api.py         /v1/decisions:evaluate · /v1/decisions/{id} · /v1/ledger ·
                 /v1/bundles* · /v1/policies* · /v1/replays* · /v1/escalations* ·
                 /v1/drafts:extract · /health
```

New tables (additive): `policy_bundles`, `policies`, `decision_events`, `escalations`, `golden_cases`, `replay_runs`, `api_keys`. Existing 7 tables retained; `skills_files`/`skills`/`operational_entities`/`relationship_edges` frozen as legacy after the converter runs (read-only, not dropped in V1).

**Out of scope, explicitly (per freeze):** warrants, signatures beyond the hash chain, agent gateway, org twin, simulation beyond replay, constitution machinery, edge evaluator, Rust port, multi-region anything. The only V1 crypto is SHA-256 content addressing and the ledger hash chain — both required by the components in scope.

---

## Provenance

Facts verified against the working tree 2026-07-13 (routes, schema, frontend inventory, requirements) and the skill-verified audit of 2026-07-07 (runtime chain, weak points W1–W8, test-infra breaks, baseline numbers). Re-verify volatile facts with the commands in the two skills' provenance tables before implementation begins.
