---
name: kernl-change-control
description: Load this BEFORE changing any kernl code, prompt, threshold, config, schema, or doc — or when asked "can I merge this", "do I need to run the eval", "is this change safe", or anything touching secrets, baselines, the Rivanly ground-truth data, the shared vLLM gateway, or live Supabase. Provides the change-class → gate mapping, the non-negotiables table with the incidents behind them, the evidence bar for merging behavior changes, and the pre-merge checklist.
---

# kernl Change Control

**What this covers:** how a change is classified, which gate (test/eval/measurement) each class must pass, the project's non-negotiable rules with rationale and incident history, the evidence bar for merging a behavior change, and the pre-merge checklist. Gating lives HERE — no other skill may advise routing around it.

**When NOT to use this:**
- How to *run* tests/evals and interpret their output in depth → `kernl-validation-and-qa` (owns baseline files and pass/fail semantics).
- A gate failed and you need to find out why → `kernl-debugging-playbook`.
- Past incidents in narrative depth → `kernl-failure-archaeology`.
- What the architecture is supposed to be → `kernl-architecture-contract`; pipeline internals → `knowledge-compilation-reference`.
- Env vars, thresholds-as-config → `kernl-config-and-flags`. Starting the app → `kernl-run-and-operate`. Improving the eval numbers themselves → `kernl-eval-inversion-campaign`.

Jargon, defined once:
- **Compiled brain / skills file** — the JSON the compilation pipeline produces (policy "skills" for the fictional demo company Rivanly Inc.). The runtime answers only from this.
- **Engine** — the compile-time LangGraph pipeline (`backend/engine/`). **Runtime** — the query-time answering stack (`backend/runtime/`). **Resolver** — `backend/runtime/constraint_resolver.py`, the deterministic layer that picks an action without the LLM.
- **Eval harness** — `backend/tests/eval_harness.py`, 40 ground-truth scenarios scored two ways: **strict** (exact action-type match, the determinism metric) and **relaxed** (semantically-acceptable answer).
- **Baseline** — the git-committed eval result JSONs you compare against (see gate table).
- **vLLM gateway** — the company-shared LLM HTTP service the backend calls (`POST {VLLM_BASE_URL}/generate` with an `x-api-key` header, default URL in `backend/core/llm.py:13`). It is NOT an OpenAI-compatible endpoint and it is a shared, limited resource.

---

## 1. Classify your change, then run its gate

Find the row that matches what you touched. If a change spans rows, run the union of gates. Commands run from the repo root; quote the path (it contains a space).

| Class | You touched | Required gate (before AND after your change) |
|---|---|---|
| **Runtime / resolver logic** | anything in `backend/runtime/` (brain_agent, constraint_resolver, guardrails, precedence, condition_eval, graph_retriever) | (a) 26 unit tests: `python backend/tests/test_constraint_resolver.py` — pure-deterministic, no LLM, exits 1 on failure. (b) Full 40-scenario eval: `python -m backend.tests.eval_harness` — calls the shared gateway ~40+ times; see gateway rules below. Compare strict/relaxed vs the committed baseline (section 4). |
| **Engine / extraction prompts** | anything in `backend/engine/` (node code, `SYSTEM` prompts, synthesis, scoring) | (a) Recompile the brain (`POST /compile` against a running backend, or `python backend/test_compile.py`). (b) Brain-quality audit: `python backend/show_brain.py` (reads `backend/tests/last_compiled_brain.json` via a repo-root-relative path — run from repo root) and eyeball skill count, confidences, rules vs the 12 expected Rivanly skills. (c) Full eval as above — extraction changes shift retrieval and resolution downstream. |
| **Config / threshold / weight** | `DEFAULT_THRESHOLDS` (`backend/runtime/constraint_resolver.py:26`), retrieval weights, `Semaphore(4)` (`backend/core/llm.py:16`), timeouts | Ablation-style measurement: run the eval with and without the new value and report both. The harness has a built-in weights ablation: `python -m backend.tests.eval_harness --ablation` (5 configs × 40 scenarios = ~200 gateway calls — schedule it; writes `backend/tests/eval_ablation_results.json`). A threshold change with no measurement attached does not merge. |
| **DB schema** | `backend/schema.sql`, Supabase tables | Supabase is LIVE and shared. Additive DDL only (new columns/tables/indexes); never `DROP`, `TRUNCATE`, or destructive `UPDATE`/`DELETE` on live tables. Keep `backend/schema.sql` in sync with what you actually ran. |
| **Docs-only** | `AGENTS.md`, `README.md`, `docs/`, `.Codex/skills/` | No eval. But: must not contradict code (see section 5 for a live contradiction handled correctly), must date-stamp volatile claims, and must never contain credential values. |
| **Frontend** | `frontend/` | `npm run build` must pass; manual check of the touched page. No eval. Known frontend↔backend endpoint mismatches are catalogued in `kernl-architecture-contract` — check there before "fixing" an API call. |

Broken gates you must NOT rely on (as of 2026-07-08):
- `python -m backend.tests.resolver_only_eval` is **import-broken**: it imports `_load_skills_from_file`, `_compute_hybrid_score`, `_build_admissible_actions`, `RETRIEVAL_WEIGHTS` from `backend/runtime/brain_agent.py` — none exist there anymore.
- `python -m backend.tests.eval_harness --stability` is **kwarg-broken**: `run_stability_test` calls `handle_agent_query(company_id=…, context=…)` but the signature is `handle_agent_query(cid, scenario, ctx=None, with_brain=True, rw=None)` (`backend/runtime/brain_agent.py:635`).
- The harness's own exit code is not a usable gate: `_main` exits 1 whenever relaxed accuracy < 90% (`backend/tests/eval_harness.py:1008-1010`), and the committed baseline is 52.5% relaxed — so a plain run currently ALWAYS exits 1. Read the printed numbers, not the exit code.

---

## 2. The non-negotiables

Every rule below has been paid for. RATIONALE says why; INCIDENT says what happened (or what the code shows would happen).

| # | Rule | Rationale / incident |
|---|---|---|
| 1 | **All LangGraph nodes are `async def`.** All 13 nodes in `backend/engine/nodes/` are async (verify command in Provenance). | A sync node blocks the event loop and serializes the "parallel" extractor fan-out, and `AGENTS.md:412` records this as rule #1 from the original parallelization refactor (commit a688aff replaced a sequential 3-node pipeline). |
| 2 | **Fan-out uses the `Send` API; parallel extractors join ONLY at a single barrier node.** `Send` is LangGraph's primitive for launching N parallel node invocations from a conditional edge (`route_to_extraction`, `backend/engine/graph.py:21-28`, returns 5 `Send`s). All five extractors edge into ONE node, `build_operational_graph` (`backend/engine/graph.py:72-76`), which acts as the barrier; only it continues to the sequential chain. Never wire an extractor directly to `synthesize_skills` or any other downstream sequential node. | Direct edges from each parallel extractor to a sequential node make that node fire once per extractor instead of once after all — duplicate synthesis, duplicated skills. `AGENTS.md:413` preserves this as a hard rule from the a688aff refactor. |
| 3 | **Fan-in state fields use `Annotated[List[...], operator.add]` reducers.** See `backend/engine/state.py:8-32` (`raw_decisions`, `workflow_steps`, `exception_rules`, `contradictions`, `extracted_entities`, `extracted_relationships`, `extracted_authority_rules`, `errors`). A reducer tells LangGraph how to merge writes from parallel branches. | Without the reducer, parallel extractor writes to the same list field overwrite each other — last writer wins, everything else silently lost. |
| 4 | **Never read raw source files at query time.** The brain agent reads the compiled brain only: DB first, then the file fallback `backend/tests/last_compiled_brain.json` (`backend/runtime/brain_agent.py:603,627`). | This is the project's core thesis ("compile once, read compiled output forever" — `AGENTS.md:10`). Reading raw sources at query time reintroduces RAG-over-documents, defeats evidence-linking and versioning, and makes answers depend on files the runtime shouldn't even have access to in production. |
| 5 | **Every LLM JSON call goes through the repair + retry-once-then-empty discipline.** `safe_llm_json_call` (`backend/core/llm.py:161-217`): strip code fences → regex-repair JSON → parse; on `JSONDecodeError`, retry ONCE with a stricter prompt; if that also fails, return `[]`. (Transport/rate-limit errors are separately retried inside `llm_call`, up to 5 attempts with backoff, `backend/core/llm.py:90-127`.) | The 72B model intermittently wraps JSON in prose or emits trailing commas. One unguarded `json.loads` in one extractor kills an entire compile run that already burned dozens of shared-gateway calls. Returning `[]` degrades one extractor's output instead of the whole pipeline. |
| 6 | **`skills_files.is_current` is enforced by a partial unique index** — at most one current brain per company (`backend/schema.sql:23`). `write_brain` flips the old current row to false before inserting the new one (`backend/core/db/supabase.py:172-184`). | Two "current" brains means the runtime nondeterministically answers from different policy versions. The index makes the invariant a DB-level guarantee, not an application promise — do not drop or work around it. |
| 7 | **Extraction temperature is 0.1.** It is the default on `llm_call` and `safe_llm_json_call` (`backend/core/llm.py:86,164`); do not raise it in extraction paths. ⚠ Honest note (as of 2026-07-08): the gateway request body only sends `messages` (`backend/core/llm.py:99-105`) — `temperature`/`max_tokens` are accepted by the Python function but NOT transmitted, so effective sampling is whatever the gateway sets. The rule stands as written intent; wiring the parameter through is an open fix, and any PR doing so must run the full eval (it can change every number). | Extraction must be near-deterministic: creative paraphrases of policy rules break strict-match evaluation and produce unstable compiled brains from identical sources. |
| 8 | **CORS stays on** — `CORSMiddleware` with `allow_origins=["*"]` (`backend/api.py:41-42`). Tightening the origin list is fine; removing the middleware is not. | The Next.js frontend is served from a different origin than the backend (port 8081); without CORS every browser call fails. |
| 9 | **Never commit secrets — and NEVER obfuscate to bypass scanning hooks.** See the incident story below this table. Refer to credential values only by location: the gateway key default is at `backend/core/llm.py:14`; the leaked token is in commit `22ee2f0`. Never paste either anywhere. | Commit `22ee2f0` (2026-05-10) added a Hugging Face API token to `backend/llm.py` **split into two concatenated string constants**, with a comment literally reading "Obfuscated default token to bypass static push scanning hook". It worked — the scanner missed it — and the token is now in permanent git history. It must be treated as compromised and revoked; the obfuscation turned a blockable mistake into a permanent leak. This is why "the hook is annoying" is never a reason: the hook firing IS the system working. |
| 10 | **Never permanently edit `data/sources/rivanly-inc/`.** The 8 files there are calibrated ground truth: they are authored to compile into exactly the 12 expected skills that the 40 eval scenarios score against. Tests that must mutate them follow save/edit/restore: `scripts/smoke_test.py` snapshots the SOP (`:138-139`), restores it (`:212-215`) and re-restores in its error path (`:317-319`); `scripts/stress_test.py` does the same (`:156-186`). | Editing a source file silently re-calibrates the entire eval: every accuracy number before the edit becomes incomparable to every number after, and the committed baselines become meaningless. If a test crashes mid-mutation, restore from git before doing anything else. |
| 11 | **The vLLM gateway is a shared, limited company resource.** Client concurrency is capped at `Semaphore(4)` (`backend/core/llm.py:16`) — do not raise it without agreement. Batch heavy work (full evals, ablations, recompiles) and schedule it off-peak; don't loop the eval interactively. The client already backs off on 429/413 (`backend/core/llm.py:110-121`) — treat backoff messages as a signal to stop, not push through. | Other teams share this endpoint. One person hammering it rate-limits everyone, and rate-limit noise corrupts your own eval numbers (timeouts score as failures). |
| 12 | **Supabase is live — no destructive SQL, ever.** No `DROP`/`TRUNCATE`/mass `DELETE`/`UPDATE` outside the code paths that exist. Schema changes are additive and mirrored into `backend/schema.sql`. | There is one live project backing dev, demo, and the compiled-brain history. There is no staging copy to restore from. |

### The commit 22ee2f0 story, in full (rule 9's incident)

On 2026-05-10, a fallback LLM path via the Hugging Face router was added to the old `backend/llm.py`. To make it "work out of the box", a real HF token was hardcoded — split across two variables (`_HF_P1 + _HF_P2`) specifically so the pre-push secret scanner would not match it. The author's own comment in the diff admits this. The commit shipped; the code was later removed in the `2ca7f83` restructure, but git history is permanent: anyone with repo access can read the token today. Consequences and standing orders:
- The token is **compromised and must be revoked** at the provider (open item — verify revocation, don't assume it).
- Never reproduce the token or the `VLLM_API_KEY` default in any file, log, doc, or chat — cite `commit 22ee2f0` / `backend/core/llm.py:14` instead.
- If a scanner/hook blocks your push: remove the secret and use env vars (`backend/.env`, gitignored). Bypassing, encoding, splitting, or `--no-verify` converts a 5-minute fix into a permanent breach.

---

## 3. Honest note: the `compile_runs` append-only contradiction

`AGENTS.md:417` (Critical Rules #6) says: **"`compile_runs` table is append-only — never update rows, only insert status."**

The code contradicts this in three places (as of 2026-07-08):
- `backend/engine/nodes/write_brain.py:146` — `db.table("compile_runs").update({...status: "complete"...}).eq("id", job_id)` on success.
- `backend/api.py:187` — same table `.update({...status: "error"...})` in the pipeline error path.
- `backend/core/db/supabase.py:54` — a general `update_compile_run(run_id, data)` helper.

The actual runtime pattern is insert-then-update: `/compile` inserts a `running` row (`backend/api.py:215`), and completion/error updates it in place. **Both sides are stated here deliberately.** Treat the doc rule as aspirational until someone reconciles it — either change the code to insert status-transition rows (and fix everything that reads the table, e.g. the status poll at `backend/api.py:242`), or amend `AGENTS.md`. Until then: do not add NEW code paths that mutate `compile_runs` beyond the existing insert-then-finalize pattern, and do not "fix" the existing updates without a decision recorded in the PR. (General warning: `AGENTS.md` predates the `2ca7f83` restructure and is stale in other places too — `kernl-architecture-contract` has the current map.)

---

## 4. Evidence bar for merging a behavior change

A "behavior change" is anything that can alter what the runtime answers or what the pipeline compiles. To merge one:

1. **Report the eval delta with exact numbers.** Before/after, from real runs, in the PR description:

   | Metric | Baseline (committed) | After change |
   |---|---|---|
   | Strict accuracy | 15.0% (6/40) | your number |
   | Relaxed accuracy | 52.5% (21/40) | your number |
   | Rule-hit rate | 55.0% | your number |

   The committed baseline lives in `backend/tests/eval_results_baseline.json` (run of 2026-06-16); the resolver-only reference is `backend/tests/resolver_eval_results.json` (strict 62.5%, 25/40, 2026-06-15). "It seems better" and single-scenario spot checks do not meet the bar.
2. **Baseline-overwrite protocol.** Running `python -m backend.tests.eval_harness` OVERWRITES `backend/tests/eval_results_baseline.json` in place (`backend/tests/eval_harness.py:1003`) and also writes `eval_results_partial.json` during the run (`:727`). So: run the eval, read the numbers, get the delta with `git diff -- backend/tests/eval_results_baseline.json`, then either **restore** (`git restore backend/tests/eval_results_baseline.json backend/tests/eval_results_partial.json`) or **deliberately commit the new file as the new certified baseline** — an explicit, called-out act in the PR, never a side effect. Baseline certification rules live in `kernl-validation-and-qa`.
3. **No regression on family scores.** The harness prints a per-source-file breakdown (strict/relaxed per `notion_refund_sop.md`, `zendesk_tickets.json`, etc.). A change that raises the total by winning one family while silently losing another needs the loss explained, not hidden by the aggregate.
4. **Threshold/weight changes cite a measurement.** Any change to `DEFAULT_THRESHOLDS` (`ambiguity_entropy` 0.75, `min_confidence_for_auto_action` 0.40, `graph_fallback_threshold` 0.5, `score_differential_threshold` 0.10 — `backend/runtime/constraint_resolver.py:26-31`) or to retrieval weights must cite an ablation run (`--ablation`) or an equivalent A/B measurement showing the number moved for the stated reason. "Felt too strict" does not merge.
5. **26/26 unit tests pass** for any runtime/resolver change — these are free (no LLM) and non-negotiable.

---

## 5. Pre-merge checklist

Copy into the PR and tick every line. All commands from the repo root, e.g. `cd "D:\Abhijith P\Desktop\Project\kernl"`.

```text
[ ] Classified the change (section 1) and ran the union of required gates
[ ] Runtime/resolver touched? -> python backend/tests/test_constraint_resolver.py  => 26/26 passed
[ ] Behavior change? -> full eval run; before/after strict, relaxed, rule-hit numbers pasted in PR
[ ] Per-source family scores checked; any family regression explained in PR
[ ] Baseline JSONs: restored (git restore) OR re-certification explicitly declared in PR
[ ] Engine/prompt touched? -> recompiled + python backend/show_brain.py audit summarized in PR
[ ] Threshold/weight changed? -> ablation/measurement cited in PR
[ ] git status shows NO leftover edits under data/sources/rivanly-inc/
[ ] No secrets in the diff; no encoding/splitting/--no-verify to get past hooks (rule 9)
[ ] No new violation of non-negotiables 1-8 (async nodes, Send+barrier, reducers,
    compiled-brain-only reads, JSON discipline, is_current index, temp 0.1, CORS)
[ ] No destructive SQL against live Supabase; schema.sql updated if DDL was added
[ ] Heavy gateway usage (eval/ablation/recompile) was batched/scheduled, not looped
[ ] Docs touched? -> claims date-stamped, nothing contradicts code (compile_runs caveat: section 3)
```

---

## Provenance and maintenance

All facts verified against the repo on **2026-07-08** (HEAD `d215501`). Re-verify volatile facts before relying on them:

| Fact | Re-verify with (repo root) |
|---|---|
| 26 unit tests | `grep -c "def test_" backend/tests/test_constraint_resolver.py` |
| 40 eval scenarios | `grep -c "\"scenario\":" backend/tests/eval_harness.py` (returns 41: 40 defs + 1 result-builder at :696); or `grep total_scenarios backend/tests/eval_results_baseline.json` |
| Baseline numbers 15.0 / 52.5 / 55.0 | `grep -E "strict_accuracy_pct|relaxed_accuracy_pct|rule_hit_rate_pct" backend/tests/eval_results_baseline.json` |
| Resolver-only 62.5% | `grep accuracy_pct backend/tests/resolver_eval_results.json` |
| Eval overwrites its own baseline | `grep -n "eval_results_baseline.json" backend/tests/eval_harness.py` |
| Harness exit-1-below-90% quirk | `grep -n "90.0" backend/tests/eval_harness.py` |
| `--stability` kwarg mismatch | `grep -n "company_id=" backend/tests/eval_harness.py` vs `grep -n "def handle_agent_query" backend/runtime/brain_agent.py` |
| `resolver_only_eval` broken imports | `grep -n "RETRIEVAL_WEIGHTS" backend/runtime/brain_agent.py` (no hits = still broken) |
| All nodes async | `grep -L "^async def" backend/engine/nodes/*.py` (only `__init__.py`/`_utils.py` may appear) |
| Send fan-out + barrier edges | `grep -n "Send(\|add_edge" backend/engine/graph.py` |
| Reducer fields | `grep -n "operator.add" backend/engine/state.py` |
| Compiled-brain-only fallback path | `grep -n "last_compiled_brain" backend/runtime/brain_agent.py` |
| JSON repair/retry discipline | `grep -n "_repair_json\|retry_prompt\|return \[\]" backend/core/llm.py` |
| Partial unique index | `grep -n "is_current = true" backend/schema.sql` |
| Temperature default + missing wire-through | `grep -n "temperature" backend/core/llm.py` then inspect the `json={...}` payload at `backend/core/llm.py:99-105` |
| CORS | `grep -n "allow_origins" backend/api.py` |
| Leak commit exists (never print its diff) | `git log --oneline 22ee2f0 -1` |
| Gateway URL/key location + Semaphore(4) | `grep -n "VLLM_BASE_URL\|VLLM_API_KEY\|Semaphore" backend/core/llm.py` |
| `compile_runs` update sites | `grep -rn "compile_runs" backend/engine/nodes/write_brain.py backend/api.py backend/core/db/supabase.py` |
| AGENTS.md append-only rule | `grep -n "append-only" AGENTS.md` |
| Rivanly ground truth intact (8 files) | `ls data/sources/rivanly-inc` and `git status --short data/sources/` |
| Smoke/stress save-restore | `grep -n "restore\|original" scripts/smoke_test.py scripts/stress_test.py` |
| Thresholds | `grep -n -A5 "DEFAULT_THRESHOLDS = " backend/runtime/constraint_resolver.py` |
| Ablation configs (5) | `grep -n -A2 "ABLATION_CONFIGS" backend/tests/eval_harness.py` |

If any command's output disagrees with this skill, the repo wins — update this file and re-date the stamp.
