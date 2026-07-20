---
name: kernl-validation-and-qa
description: Load this when you need to prove a Kernl change works - running the deterministic backend suite, the property-based/metamorphic evaluator tests, smoke/stress tests against a running /v1 server, or a replay run to gate a bundle publish. Covers the V1 evidence hierarchy, the golden case corpus (status, gaps, how to add cases), and what publish-gating replay actually checks. Also indexes the retired legacy 40-scenario LLM eval harness as historical record only - do not run it expecting it to validate V1.
---

# Kernl Validation and QA

**What this covers:** what counts as evidence for a V1 change, the deterministic test suite, replay as the publish gate, the golden case corpus and its real gaps, and how to add cases/tests.

**When NOT to use this:**
- Fixing a failing test or a wrong answer → `kernl-debugging-playbook`.
- Whether you are *allowed* to change code or a bundle → `kernl-change-control`.
- Starting the API → `kernl-run-and-operate`. Installing deps → `kernl-build-and-env`.
- What the evaluator/ledger/bundle model is supposed to do → `kernl-architecture-contract`.

---

## 1. The V1 evidence hierarchy

Cheapest evidence first. Run the tier you can afford; never claim a fix works on a tier you didn't run.

| Tier | What | Command (from repo root) | Needs | Cost |
|---|---|---|---|---|
| 1 | Full deterministic backend suite (bundle, evaluator, ledger, escalation/replay lifecycle, seed, `/v1` API, onboarding, observability, property-based + metamorphic evaluator tests) | `python -m pytest backend/tests/ -q --ignore=backend/tests/test_pg_stores.py` | Nothing — no LLM, no DB, no network | Seconds |
| 2 | Live-DB contract suite (Postgres adapters match the in-memory reference protocol) | `python -m pytest backend/tests/test_pg_stores.py -v` | Real Postgres via `KERNL_DB_URL` | Seconds, real DB round trips |
| 3 | Smoke test: full onboarding→publish→evaluate→escalate→adjudicate loop against a running server | `KERNL_ADMIN_KEY=<key> python scripts/smoke_test.py --base-url http://127.0.0.1:8000` | Running `backend.api:app` | Seconds |
| 4 | Stress test: concurrent load, idempotency-under-retry, malformed input, chain integrity | `KERNL_ADMIN_KEY=<key> python scripts/stress_test.py --base-url http://127.0.0.1:8000 [--workers N --per-worker N]` | Running server | Tens of seconds at the safe default (2×8) |
| 5 | Replay: candidate bundle vs the golden case set + reference bundle | `POST /v1/replays` (see `kernl-run-and-operate`) | Running server + tenant with a golden case set | Sub-second — LLM-free by construction |

All five tiers are LLM-free. This is a deliberate constitutional property (`CLAUDE.md` rule 1: no non-deterministic enforce-path ruling) — nothing in the actual decision/evaluation/replay path calls an LLM, so nothing in *validating* it needs to either.

**Tier 3/4 are provisioning-isolated**: both scripts provision a throwaway tenant (`smoke-<hex>` / `stress-<hex>`) and never touch seeded reference data. Safe to run against a shared server without coordinating with anyone.

---

## 2. Replay — the actual publish gate

Replay is what stands between a draft bundle and production, per `CLAUDE.md` constitutional rule 4 and the arc's build order (Part 15, step 3): "grow the eval corpus into golden replay CI gating every compile."

`POST /v1/bundles/{id}/publish` returns **409 unless a replay run for that exact bundle hash has been acknowledged.** A replay run (`POST /v1/replays`) evaluates the candidate bundle against:
- every golden case in the tenant's corpus (`GET /v1/cases`), and
- the currently-active (reference) bundle, if one exists,

and reports flips (cases whose outcome changed), new escalations, and unchanged count. Acknowledging the report (`POST /v1/replays/{run_id}/acknowledge`) unlocks the publish for that specific hash — a different bundle hash needs its own fresh replay.

This is the mechanism that makes "CI for your refund policy" true. It only works as well as the golden case corpus behind it (section 4).

---

## 3. Deterministic evaluator hardening

Beyond example-based unit tests, `backend/tests/test_evaluator_properties.py` runs property-based (Hypothesis, generated bundles + facts) and metamorphic (controlled bundle mutations) tests against the evaluator directly:

- **Property tests** (invariants that must hold for *any* generated bundle/facts pair): determinism, strictness (a condition on a missing fact is never silently "pass" — this is the direct test of constitutional rule 1), escalation/winner mutual exclusivity, the defeasible dominance rule, "an overridden policy never wins," effective facts are declared-fields-only.
- **Metamorphic tests** (relate two runs under a controlled mutation, rather than asserting one absolute expected output): an irrelevant extra fact doesn't change the outcome; removing the winner's required fact dethrones it; raising the winner's priority can't dethrone it; a new policy that overrides *every* currently-matched policy becomes the sole survivor and wins outright.

Run with the rest of tier 1. If you touch `backend/runtime/evaluator.py`, this is the suite most likely to catch a subtle precedence regression that example-based tests miss — it generates ~150 examples per property by default (`settings(max_examples=150)`).

---

## 4. Golden case corpus — real status and gaps

As of 2026-07-17: **86 golden cases across two corpora** — `rivanly-inc` (58 cases, 22 policies across 9 workflows) and `higgsfield` (28 cases, 18 policies across 3 workflows: refund, bug_triage, expense — grounded in `higgsfield_customer_policy.md`, `higgsfield_eng_runbook.md`, and `higgsfield_hr_finance.md` respectively). All `[synthetic]` except one real adjudication-promoted case in `rivanly-inc` (`case_id=adj-86024a0f`) that predates the corpus expansion and currently fails against the live bundle (incomplete facts — missing `plan_type` — so the strictness rule correctly renders it undeterminable rather than a clean pass). That one case is flagged, not silently fixed: it's real historical adjudication data, and "no mutation of history" means editing someone else's promoted case isn't a call to make unilaterally — route it through `kernl-change-control`.

The corpus is meaningfully broader than it was (three workflows per tenant, boundary + precedence + documented-gap cases in each), but the standing arc target is still the real bar: promoting *real* adjudications into golden cases over time (`CLAUDE.md` build order step 4 — "deliberation hardens into precedent"), not authored synthetic fixtures. What's still not modeled from the higgsfield sources: the Slack/ticket JSON exports (`higgsfield_slack_*.json`, `higgsfield_tickets.json`) and finer-grained rules within each doc (e.g. deploy-window / rollback criteria in the eng runbook, PIP/termination in HR). Those are the next authoring targets if this corpus needs to grow further.

**How cases actually grow, in priority order:**
1. **Adjudication promotion** (the intended, real mechanism): resolving an escalation with `promote_to_golden: true` (`POST /v1/escalations/{id}/resolve`) adds a non-synthetic case with `provenance: "adjudication:<event_id>"`. This is how the corpus is *supposed* to grow in production — every real ambiguous decision that gets ruled on becomes a regression test.
2. **Authored synthetic cases**, for coverage the adjudication path hasn't hit yet: see `backend/bundle/seed_rivanly.py`'s `_case(...)` helper for the pattern (id, workflow, facts, expected outcome kind + action). Every case's expected outcome must trace back to a real, cited policy — do not author a case whose "correct" answer isn't grounded.
3. **A second corpus** for `higgsfield` doesn't exist yet. Building one means: reading the actual source docs in `data/sources/higgsfield/`, authoring policies with evidence spans verified byte-for-byte against those docs (via `POST /v1/onboarding/drafts` + `/ground`, same as any real tenant onboarding — see `kernl-run-and-operate` section 4), then authoring golden cases against the resulting bundle. This is meaningful, careful work, not a script — do not synthesize evidence spans that don't actually appear in the source text; the ground endpoint will 400 you if they don't match, which is the point.

---

## 5. Adding a resolver/evaluator unit test

`backend/tests/test_evaluator.py` and `backend/tests/test_bundle.py` are plain pytest-collectable functions — no hand-rolled runner, no registration list to remember. Add a `test_*` function, run `pytest backend/tests/test_evaluator.py -v` to confirm it's picked up.

Keep new tests deterministic: no LLM, no DB, no network, no randomness (property-based tests use Hypothesis's seeded, reproducible generation — that's not "randomness" in the sense to avoid). If you're testing a precedence/priority edge case, check whether it's better expressed as a metamorphic relation (section 3) than a single example — it'll generalize further.

---

## 6. Legacy eval harness — historical record only

**Do not run this expecting it to validate V1. It predates the bundle/ledger/replay model entirely and is not wired to it.**

`backend/tests/eval_harness.py` is a 40-scenario, LLM-in-the-loop evaluation of the *retired* extraction pipeline (`backend/engine/`, `backend/runtime/brain_agent.py`) against a shared vLLM gateway. `CLAUDE.md` is explicit: *"Historical eval numbers (15.0%/52.5% `[synthetic]`) remain diagnostic history only."* It still exists as a library-importable script (see `kernl-run-and-operate` section 7 on what's still importable vs retired from the live HTTP surface), kept for archaeological reference on the eval-inversion investigation, not as a current QA gate.

If you need the old details (scenario families, strict/relaxed/rule-hit semantics, known-broken sub-scripts like `resolver_only_eval.py`), they're preserved in git history for this file as of commit `2c93107` and earlier — re-derive from there rather than trusting a live copy in this skill, since none of it has been re-verified since the V1 rewrite and several of the known-broken items may have silently rotted further.

**`scripts/smoke_test.py` and `scripts/stress_test.py` no longer touch this system at all** — as of 2026-07-16 both were fully rewritten to test `/v1` (section 1, tiers 3–4). Earlier versions of these scripts edited `data/sources/rivanly-inc/` on disk and triggered real recompiles against the shared gateway; that behavior is gone. If you find old documentation (including older copies of this skill, or memory from a prior session) describing smoke/stress as mutating shared source files or needing port 8081/8080 — it's describing the retired scripts, not the current ones.

---

## Provenance and maintenance

Facts verified against the repo on **2026-07-16**. Re-verify volatile facts before relying on them:

| Fact | Re-verify with (from repo root) |
|---|---|
| Full suite is LLM/DB/network-free and its count | `python -m pytest backend/tests/ -q --ignore=backend/tests/test_pg_stores.py` |
| Property/metamorphic test list | `grep -n "^def test_" backend/tests/test_evaluator_properties.py` |
| Publish gate (409 without ack'd replay) | `grep -n "409" backend/v1_api.py` near the publish handler |
| Golden case corpus size per corpus | `grep -c "^\s*_case(" backend/bundle/seed_rivanly.py backend/bundle/seed_higgsfield.py` |
| higgsfield seed exists and its scope | `python -c "from backend.bundle.seed_higgsfield import build_bundle; b=build_bundle(); print(len(b.policies), [w.name for w in b.workflows])"` |
| Adjudication promotion path | `grep -n "promote_to_golden" backend/v1_api.py backend/escalation/service.py` |
| smoke/stress now target /v1, not the compile pipeline | `grep -n "onboarding\|decisions/evaluate" scripts/smoke_test.py` |
| eval_harness.py is not wired to /v1 | `grep -rln "eval_harness" backend/v1_api.py backend/ledger/ backend/replay/` (expect no hits) |
