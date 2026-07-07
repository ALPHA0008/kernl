---
name: kernl-validation-and-qa
description: Load this when you need to prove a kernl change works, run or extend any test (resolver unit tests, the 40-scenario eval harness, smoke/stress HTTP tests), interpret strict/relaxed/rule-hit accuracy numbers, add an eval scenario, or decide whether a baseline JSON may be overwritten. Covers the evidence hierarchy, the certified golden baselines (eval_results_baseline.json, resolver_eval_results.json, last_compiled_brain.json), and the known-broken test infrastructure.
---

# kernl Validation and QA

**What this covers:** what counts as evidence in kernl, the four-tier test hierarchy, the certified golden-baseline inventory, exact pass/fail semantics of the eval harness, known-broken test infra, and checklists for adding scenarios and unit tests.

**When NOT to use this:**
- Fixing a failing test or a wrong answer → `kernl-debugging-playbook`.
- The campaign to fix the eval/resolver mismatch itself → `kernl-eval-inversion-campaign`.
- Whether you are *allowed* to change code or baselines → `kernl-change-control` (gating lives there, never route around it).
- Starting the API / compile pipeline → `kernl-run-and-operate`. Env vars and .env → `kernl-config-and-flags`. Installing deps → `kernl-build-and-env`.
- What the pipeline/graph is supposed to do → `kernl-architecture-contract`, `knowledge-compilation-reference`.

Jargon used below, defined once:
- **Compiled brain / skills file** — the JSON output of the compilation pipeline (12 policy "skills" for the fictional demo company Rivanly Inc.). The runtime answers questions from this file only.
- **Brain agent** — the query-time engine (`backend/runtime/brain_agent.py`): hybrid retrieval over skills + graph, then an LLM call to phrase the answer.
- **Constraint resolver** — the deterministic decision layer (`backend/runtime/constraint_resolver.py`) that picks an action (or declares "ambiguous") *without* the LLM.
- **LLM gateway** — the shared vLLM server. URL and key come from env (`VLLM_BASE_URL` / `VLLM_API_KEY`; defaults at `backend/core/llm.py:13-14` — do not copy the key value anywhere). It is a **shared live environment**: every eval scenario spends real GPU time on it.

---

## 1. The evidence hierarchy

Cheapest evidence first. Always run the tier you can afford; never claim a fix works on a tier you did not run. (as of 2026-07-07)

| Tier | What | Command (from repo root; quote the path — it contains a space) | Needs | Status |
|---|---|---|---|---|
| 1 | 26 deterministic resolver unit tests | `python backend/tests/test_constraint_resolver.py` | Nothing (no LLM, no DB, no network) | WORKING — 26/26 pass (verified 2026-07-07) |
| 2 | Resolver-only eval: all 40 scenarios through retrieval + resolver, no LLM decision call | `python -m backend.tests.resolver_only_eval` | Local embedding model only | **IMPORT-BROKEN** — see §4 |
| 3 | Full 40-scenario eval harness (end-to-end, LLM answers) | `python -m backend.tests.eval_harness` | LLM gateway reachable; brain loaded from Supabase or the local file fallback | WORKING but see baseline-overwrite warning in §3 |
| 4 | Smoke / stress HTTP tests | `python scripts/smoke_test.py` / `python scripts/stress_test.py` | Backend API running (`uvicorn backend.api:app --port 8081`) + gateway + DB | smoke OK; stress has a stale port — see §8 |

Notes:
- On Windows boxes where `python` is not on PATH, use `py` instead (verified working here).
- Tier 1 always runs. Run it before and after ANY change to `backend/runtime/`.
- Embeddings are computed **locally** (`sentence-transformers/all-MiniLM-L6-v2` via `transformers`, CPU — `backend/core/llm.py:38-53`). First-ever run downloads the model from Hugging Face; after that, no network. Only the chat/decision calls hit the gateway.
- The eval can run without Supabase: `handle_agent_query` tries the DB first and falls back to the checked-in brain file `backend/tests/last_compiled_brain.json` (`backend/runtime/brain_agent.py:602, 627-641`).

**Cost discipline:** one standard eval run = 40 scenarios = 40+ LLM calls on the shared gateway. `--ablation` runs 5 configs × 40 = 200+. Do not run the full eval to "see if it still works" — run tier 1, and reserve tier 3 for changes that plausibly move accuracy.

---

## 2. Eval harness anatomy (`backend/tests/eval_harness.py`)

40 hand-written ground-truth scenarios against Rivanly Inc. (`COMPANY_ID = "rivanly-inc"`, line 33), derived from the 8 synthetic source docs in `data/sources/rivanly-inc/`.

### 2a. Scenario families (as of 2026-07-07)

| Family | Count | IDs | Tests |
|---|---|---|---|
| REF | 7 | REF-01..REF-07 | Refund SOP rules (14-day window, prorate, enterprise escalate, LTD deny, >$500 founder, 60-day cutoff) |
| CS | 3 | CS-01..CS-03 | Churn-signal thresholds, enterprise onboarding |
| ENG | 4 | ENG-01..ENG-04 | P0/P1 severity, SLA breach, outage protocol |
| HR | 2 | HR-01..HR-02 | Founder approval on offers, PIP trigger |
| PRICE | 3 | PRICE-01..PRICE-03 | Discount authority ladder |
| SLACK | 1 | SLACK-01 | Tribal-knowledge exception (loyalty precedent from Slack) |
| OPS | 1 | OPS-01 | Vendor invoice routing |
| ADV | 5 | **ENG-ADV-01, REF-ADV-01, HR-ADV-01, CS-ADV-01, PRICE-ADV-01** | Adversarial retrieval traps (note the family prefix comes FIRST — this breaks a counter, §4) |
| DET | 6 | DET-01..DET-06 | Determinism: expected_action is the sentinel string `"ambiguous"` — correct answer is *refusing to pick* |
| COND | 8 | COND-01..COND-08 | Condition boundaries (exactly 14 days, $500 vs $501, exactly 30%, 60-day cutoff, string-equality match) |

### 2b. Scenario record shape

```python
{
    "id": "REF-01",                       # FAMILY-NN
    "source": "notion_refund_sop.md",     # ground-truth source doc
    "scenario": "...natural-language situation...",
    "context": {"plan_type": "annual", "days_since_purchase": 9},  # typed fields
    "expected_action": "approve",         # canonical label, or "ambiguous"
    "expected_rule_contains": "14 days",  # substring the cited rule must contain ("" for DET)
    "rationale": "why this is the only correct answer",
}
```

### 2c. Canonical actions and the ambiguous sentinel

`CANONICAL_ACTIONS` (eval_harness.py:437-453) — 15 labels; strict matching only ever passes on these (or `ambiguous`):

`approve, approve_prorated, deny, escalate, schedule_am_call, initiate_enterprise_onboarding, monitor, page_on_call, notify_am_and_eng_lead, send_incident_template, resolve_within_4_hours, get_founder_approval, initiate_pip, approve_20_percent_startup_discount, route_to_ops_lead`

`"ambiguous"` is NOT in that list — it is a sentinel used as `expected_action` on all 6 DET scenarios and COND-05, meaning the runtime should return `action_type == "ambiguous"`.

### 2d. Pass definitions — exact semantics

| Metric | Function | Semantics |
|---|---|---|
| **Strict** | `check_action_strict` (line 509) | `response["action_type"]`, lowercased, stripped, spaces→underscores, must **equal** `expected_action`. Measures determinism. |
| **Relaxed** | `check_action_relaxed` (line 521) | Passes if ANY of: (a) *soft pass*: `action_type == "ambiguous"` AND `expected_action` appears in `response["decision_trace"]["candidate_actions"]`; (b) substring match either direction between `response["recommended_action"]` (free text) and `expected_action`; (c) any alias from `ACTION_ALIASES` (lines 456-501) for the expected action appears in the free text. Measures "the LLM understood". |
| **Rule hit** | `check_rule_contains` (line 552) | `expected_rule_contains` (case-insensitive substring) in `response["rule_applied"]`. Empty fragment → always False, so **DET scenarios can never rule-hit** by construction. |
| **Boundary pass rate** | lines 760-764 | % of COND-* scenarios passing strict OR relaxed. |
| **Condition accuracy** | lines 768-790 | Intended: pass rate among scenarios where a condition fired. **Structurally broken** — see §4. |

### 2e. Modes

```bash
python -m backend.tests.eval_harness              # standard 40-scenario run
python -m backend.tests.eval_harness --ablation   # 5 retrieval-weight configs x 40 (ABLATION_CONFIGS, line 566) -> eval_ablation_results.json
python -m backend.tests.eval_harness --stability  # 3x6 DET consistency check -- CRASHES today, see section 4
```

The standard run writes `eval_results_partial.json` after every scenario (live checkpoint, lines 727-735) and `eval_results_baseline.json` at the end (line 1003), then **exits 1 if relaxed < 90%** (lines 1008-1010). Since current relaxed is 52.5%, a standard run today always exits non-zero — do not treat that exit code alone as "my change broke it".

---

## 3. Golden baselines — the certified inventory

These files in `backend/tests/` are the certified reference points (all facts below re-read from the files on 2026-07-07):

| File | Timestamp in file | Headline numbers | Provenance |
|---|---|---|---|
| `eval_results_baseline.json` | 2026-06-16T15:29 | **strict 15.0%** (6/40), **relaxed 52.5%** (21/40), rule-hit 55.0%, condition_accuracy 0.0% (metric broken, §4), boundary 62.5% (5/8) | Full LLM eval on the post-refactor runtime |
| `eval_results_partial.json` | (no timestamp; completed 40/40) | Same run's per-scenario checkpoint. Verified: its `results` array is byte-identical to the baseline's. **NOT a different era** — do not treat it as an independent data point. | Same run as above |
| `resolver_eval_results.json` | 2026-06-15T11:31 | **strict 62.5%** (25/40), no LLM | Produced by **PRE-refactor** brain_agent code. The numbers remain valid as a target; the script that produced them (`resolver_only_eval.py`) no longer runs (§4) |
| `last_compiled_brain.json` | compiled 2026-06-15T08:14 | 12 skills (5 with typed conditions), 15 entities / 4 edges, 21 graph policies, 5 authority rules, compile 291 s | Output of a full pipeline compile; also serves as the runtime's file fallback when the DB is unreachable |

The headline gap — resolver alone 62.5% strict vs full pipeline 15.0% strict — is the central open problem; the plan of attack lives in `kernl-eval-inversion-campaign`.

### Baseline protection rule

**Never overwrite these files without recording the code version (git SHA) and config that produced them.** New runs get new filenames or are reported alongside the golden numbers.

DANGER: the harness's default behavior violates this rule — a standard run **overwrites `eval_results_baseline.json` and `eval_results_partial.json` in place** (eval_harness.py:1003, 727; `backend/start_eval.py` does the same). Before any eval run:

```bash
cp backend/tests/eval_results_baseline.json backend/tests/eval_results_baseline_2026-06-16_golden.json  # once, if not already preserved
```

then after your run, rename the fresh output (e.g. `eval_results_<date>_<sha>.json`) and restore/keep the golden file. Whether a new run may *become* the new baseline is a `kernl-change-control` decision, not yours alone.

---

## 4. Known-broken test infra (each item verified against source, 2026-07-07)

| # | What | Symptom | Root cause | Fix direction |
|---|---|---|---|---|
| 1 | `resolver_only_eval.py` | `ImportError` on launch | Imports `_load_skills_from_file`, `_compute_hybrid_score`, `_build_admissible_actions`, `RETRIEVAL_WEIGHTS` from `backend.runtime.brain_agent` (resolver_only_eval.py:20-26). The refactor renamed them: current names are `_load_file` (brain_agent.py:627), `_hybrid` (:380), `_admissible` (:554), and weights come from `_wts(meta)` (:68) — there is no module-level `RETRIEVAL_WEIGHTS` constant anywhere in `backend/`. (`_extract_query_signals` still exists at :193.) | Update the 4 imports + the `w = RETRIEVAL_WEIGHTS` line and check the renamed functions' signatures (`_hybrid(sem, skill, qs, wts=None, meta=None)`, `_admissible(top_r, qs, meta=None)`). **Fixing this is a prerequisite of the eval-inversion campaign** — it is the only LLM-free way to re-measure the 62.5% number. |
| 2 | `eval_harness --stability` | `TypeError: handle_agent_query() got an unexpected keyword argument 'company_id'` | `run_stability_test` calls `handle_agent_query(company_id=..., scenario=..., context=..., with_brain=True)` (eval_harness.py:970-974) but the real signature is `handle_agent_query(cid, scenario, ctx=None, with_brain=True, rw=None)` (brain_agent.py:635). The main eval loop uses the correct kwargs (eval_harness.py:623-629). | Change kwargs to `cid=`/`ctx=`. |
| 3 | Adversarial counter always 0 | Summary prints `Adversarial: 0` and baseline JSON has `"adversarial": 0` despite 5 ADV scenarios | Counter filters `r["id"].startswith("ADV-")` (eval_harness.py:754) but the IDs are `ENG-ADV-01`, `REF-ADV-01`, ... (family prefix first). | Match `"-ADV-" in r["id"]` instead. Cosmetic for totals, but blocks the per-family ADV metric the master plan requires. |
| 4 | `condition_accuracy` structurally 0.0% | Baseline shows 0.0% even when condition-gated scenarios pass | Metric reads `r["retrieval_trace"]["components"]["condition_score"]` (eval_harness.py:768-790), but the per-result `retrieval_trace` dict is built WITHOUT a `components` key — it stores flattened fields only (eval_harness.py:710-722). Denominator is always 0 → `max(1, 0)` → 0.0%. | Either store `components` in the result record or read the flattened fields. Until fixed, ignore this number. |
| 5 | Stale docstring | eval_harness.py:4 says "21-scenario + 5 adversarial" | Actual `len(SCENARIOS)` is 40. | Update docstring when touching the file. |
| 6 | `stress_test.py` port | Connects to `http://localhost:8080` (stress_test.py:20) | Canonical API port is 8081 everywhere else (Dockerfile:31, `frontend/src/lib/api.ts`, smoke_test.py:17). | Edit `API` to 8081 before use. |
| (minor) | DET-06 has a duplicated `expected_rule_contains` key (eval_harness.py:353-354) — harmless in Python (last one wins) but tidy up when nearby. | | | |

All fixes above touch test infra, not runtime behavior — they still go through `kernl-change-control` like any other change.

---

## 5. How to ADD an eval scenario — checklist

1. **ID**: `<FAMILY>-<NN>` using an existing family prefix (REF/CS/ENG/HR/PRICE/SLACK/OPS/DET/COND) or `<FAMILY>-ADV-<NN>` for adversarial. Keep IDs unique; the summary buckets rely on prefixes (`DET-`, `COND-` — and the broken `ADV-` filter, §4).
2. **expected_action**: MUST be a label from `CANONICAL_ACTIONS` (eval_harness.py:437) or the `"ambiguous"` sentinel. If the correct action genuinely isn't representable, extend `CANONICAL_ACTIONS` **and** add an entry to `ACTION_ALIASES` (line 456) with the free-text variants an LLM would plausibly emit — otherwise relaxed matching can never pass.
3. **context keys must match condition field names** or the scenario will never exercise the typed-condition path. Field names in the current compiled brain (as of the 2026-06-15 brain): `days_since_purchase`, `discount_percent`, `customer_tier` (inspect with `python -c "import json; [print(s['id'], s['conditions']) for s in json.load(open('backend/tests/last_compiled_brain.json'))['skills'] if s.get('conditions')]"`). A scenario that says "enterprise" only in prose, with no `customer_tier` key, tests retrieval, not conditions.
4. **expected_rule_contains**: pick a short, distinctive fragment of the source-doc rule (e.g. `"14 days"`). Use `""` only for ambiguous scenarios (it then never rule-hits — by design).
5. **rationale**: one sentence saying why this is the ONLY defensible answer, citing the source doc. Every existing scenario has one; keep the discipline.
6. **source**: the filename under `data/sources/rivanly-inc/` that grounds the rule. If no source doc supports your expected answer, the scenario is invalid — fix the doc first (that is a compile-input change; see `kernl-change-control`).
7. Re-run the full eval (cost: §1) and re-baseline per the §3 protection rule — total counts and all percentages shift when N changes, so a 41-scenario run is NOT comparable to the 40-scenario golden numbers. Report old and new side by side.

---

## 6. How to add resolver unit tests (`backend/tests/test_constraint_resolver.py`)

- Tests are **plain module-level `test_*` functions** with bare `assert` — no framework imports. Helpers `_make_graph_policy`, `_make_graph_result`, `_make_skill_action`, `_make_authority_rules`, `_make_resolver_result` build fixtures; reuse them.
- The file has a **hand-rolled runner**: the `tests` list in the `__main__` block (line 544) is executed sequentially and prints `Results: N/M passed`. **Gotcha: a new `test_*` function is silently skipped by `python backend/tests/test_constraint_resolver.py` unless you also append `("name", test_fn)` to that list.**
- The functions are also pytest-collectable (`pytest backend/tests/test_constraint_resolver.py`) since they are plain `test_*` — UNVERIFIED whether pytest is installed in this environment; the hand-rolled runner is the canonical gate.
- Keep tests deterministic: no LLM, no DB, no network, no randomness. Thresholds come from `DEFAULT_THRESHOLDS` (imported at line 13-19; e.g. `DEFAULT_THRESHOLDS["ambiguity_entropy"]`) — assert against the constant, not a hardcoded copy.
- Current count: 26 (4 entropy, 5 graph-resolution, 3 skill-fallback, 3 authority, 7 guardrail, 4 edge-case). Update the count in this skill's provenance table when you add one.

---

## 7. Acceptance thresholds — design targets vs today

From the master plan (`docs/operational-graph-master-plan.md:1386-1395`). **These are the design doc's targets, NOT current reality** — today's full-pipeline strict accuracy is 15.0% (§3):

| Scenario type | Phase 1 target | Phase 4 target |
|---|---|---|
| Standard (REF, CS, ENG, HR, PRICE) | 90% relaxed | 95% strict |
| Boundary (COND-*) | 70% relaxed | **100% deterministic** |
| Adversarial (*-ADV-*) | 80% relaxed | 90% strict |

Plus (plan line 1148): resolver-vs-LLM agreement must be 100% at Phase 4, and the standing rule, quoted from plan line 1395: **"If any phase causes regression, stop and stabilize before proceeding."** The harness's own 90%-relaxed exit gate (§2e) encodes the Phase-1 standard target.

---

## 8. Smoke and stress tests (`scripts/`)

Both need a **running backend API** plus gateway and DB, and both **trigger full recompiles** (multi-minute, many LLM calls each) — these are the most expensive tier. Start the API first: `python -m uvicorn backend.api:app --port 8081` (see `kernl-run-and-operate`).

**`python scripts/smoke_test.py`** — targets port **8081** (smoke_test.py:17). Proves the system is dynamic:
1. health check → 2. initial compile → 3. gibberish rejection (expects confidence < 0.4) → 4. **dynamic policy-change test**: it **edits `data/sources/rivanly-inc/notion_refund_sop.md` on disk** (30→60 day window), recompiles, queries, then restores the original (smoke_test.py:132-215). If the run dies mid-test, check that the SOP was restored (`git diff data/sources/`) before doing anything else. → 5. semantic diff endpoint check.

**`python scripts/stress_test.py`** — targets port **8080, which is STALE** (stress_test.py:20); edit to 8081 before use (§4). Resilience tests: injects a malformed-markdown file and a contradictory Slack "hot take" JSON into `data/sources/rivanly-inc/` (both deleted afterward), verifies compile survives, verifies the diff endpoint detects changes, and runs 3 consecutive compiles for stability. Same cleanup caveat: if it crashes mid-run, look for leftover `malformed_test.md` / `slack_hot_take.json` in the sources dir.

Neither script is safe to point at a backend someone else is demoing from — they mutate source files and recompile the shared company brain.

---

## Provenance and maintenance

All facts above verified directly against the repo on **2026-07-07** (unit tests actually executed: 26/26 pass; baseline JSONs re-read; line numbers re-checked). Percentages describe the checked-in baseline files, not any live run. Re-verify volatile facts before relying on them:

| Fact | Re-verify with (from repo root; Git Bash for `grep`, or use `Select-String` in PowerShell; `py` if `python` is missing) |
|---|---|
| 26/26 unit tests pass | `python backend/tests/test_constraint_resolver.py` (last line: `Results: 26/26 passed, 0 failed`) |
| 40 scenarios | `grep -c '"id": "' backend/tests/eval_harness.py` → 40 |
| Canonical action labels | `grep -n -A 17 "CANONICAL_ACTIONS = " backend/tests/eval_harness.py` |
| Baseline numbers (15.0 / 52.5 / 55.0 / 0.0 / 62.5) | `python -c "import json;d=json.load(open('backend/tests/eval_results_baseline.json'));print({k:v for k,v in d.items() if k!='results'})"` |
| Resolver baseline 62.5% | `python -c "import json;d=json.load(open('backend/tests/resolver_eval_results.json'));print(d['accuracy_pct'], d['strict_passed'], d['total_scenarios'])"` |
| partial == baseline (same run) | `python -c "import json;print(json.load(open('backend/tests/eval_results_baseline.json'))['results']==json.load(open('backend/tests/eval_results_partial.json'))['results'])"` |
| Brain: 12 skills / 5 conditioned / 15 entities / 4 edges | `python -c "import json;d=json.load(open('backend/tests/last_compiled_brain.json'));print(d['meta'], sum(1 for s in d['skills'] if s.get('conditions')))"` |
| resolver_only_eval still import-broken | `grep -n "_load_skills_from_file\|RETRIEVAL_WEIGHTS" backend/tests/resolver_only_eval.py` vs `grep -n "def _load_file\|def _hybrid\|def _admissible\|def _wts" backend/runtime/brain_agent.py` |
| --stability kwargs bug | `grep -n "company_id=COMPANY_ID" backend/tests/eval_harness.py` (hit ≈ line 971 = still broken) |
| ADV counter bug | `grep -n 'startswith("ADV-")' backend/tests/eval_harness.py` (hit ≈ line 754 = still broken) |
| condition_accuracy bug | `grep -n '"components"' backend/tests/eval_harness.py` (result-record builder at ~710-722 has no such key while ~768-790 reads it = still broken) |
| Ports (smoke 8081 / stress 8080-stale) | `grep -n "localhost:80" scripts/smoke_test.py scripts/stress_test.py` |
| handle_agent_query signature | `grep -n "async def handle_agent_query" backend/runtime/brain_agent.py` |
| Master-plan targets table | `grep -n "90% relaxed" docs/operational-graph-master-plan.md` (≈ line 1390) |
| Gateway env (never paste the key) | `grep -n "VLLM_BASE_URL\|VLLM_API_KEY" backend/core/llm.py` (lines 13-14) |
| 90%-relaxed exit gate | `grep -n "below 90" backend/tests/eval_harness.py` |
