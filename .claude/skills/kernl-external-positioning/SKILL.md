---
name: kernl-external-positioning
description: Load this before writing ANYTHING external about kernl — a paper draft, blog post, README claim, demo script, investor/stakeholder deck, HF Space description, or comparison to RAG/Graphiti/rules-engines/guardrails frameworks. Provides the claim inventory, the honest prior-art map, the claim-vs-evidence status table (several headline claims are currently REFUTED by the repo's own eval), the reproducibility standard for publishing any number, and demo discipline (what may be shown live vs never).
---

# kernl External Positioning

**What this covers:** what kernl claims to be, which claims are novel vs known prior art, which claims the repo's own numbers currently support/refute, the reproducibility bar any published number must clear, and what a live demo may honestly show.

**When NOT to use this:**
- Running or extending the eval, interpreting strict/relaxed semantics, baseline files → `kernl-validation-and-qa`.
- The campaign to FIX the eval numbers → `kernl-eval-inversion-campaign`.
- Internal docs style, README/CLAUDE.md maintenance → `kernl-docs-and-writing`.
- What the pipeline actually does technically → `kernl-architecture-contract`, `knowledge-compilation-reference` (retrieval/entropy math lives there).
- Open research ideas and hypotheses → `kernl-research-frontier`; how to run an experiment → `kernl-research-methodology`; statistics for claims → `kernl-proof-and-analysis-toolkit`.
- Whether you may change code/baselines at all → `kernl-change-control` (never route around it).

Jargon, defined once:
- **Compiled brain** — the JSON artifact the pipeline produces per company: `skills` (extracted policy rules with evidence + confidence), `graph_json` (entity/edge graph), `metadata_json` (discovered vocabularies + weights + thresholds), `meta`. Committed snapshot: `backend/tests/last_compiled_brain.json` (12 skills for the fictional demo company Rivanly Inc., compiled 2026-06-15).
- **Constraint resolver** — deterministic (no-LLM) decision layer: `backend/runtime/constraint_resolver.py`. Picks an action or declares "ambiguous".
- **Strict accuracy** — the agent's `action_type` exactly equals the expected canonical label (`backend/tests/eval_harness.py:509`). **Relaxed** = semantic/substring match (`eval_harness.py:521`).
- **Full-stack / runtime eval** — retrieval + resolver + LLM verbalizer + guardrail, all together (the 40-scenario harness). **Resolver-only eval** — same scenarios, no LLM.
- **Entropy** — normalized Shannon entropy over candidate-action confidences (`constraint_resolver.py:102-112`); above the `ambiguity_entropy` threshold (default 0.75, `constraint_resolver.py:27`) the resolver answers "ambiguous" instead of guessing.

---

## 1. THE HARD RULE (read before writing a single external sentence)

As of 2026-07-10, the committed eval shows (see `kernl-validation-and-qa` for run mechanics):

| Committed run | File | Date | Strict accuracy |
|---|---|---|---|
| Full-stack runtime (40 scenarios) | `backend/tests/eval_results_baseline.json` | 2026-06-16 | **15.0%** (6/40); relaxed 52.5% |
| Resolver-only (same 40, no LLM) | `backend/tests/resolver_eval_results.json` | 2026-06-15 | **62.5%** (25/40) |

The full stack scores WORSE than its own deterministic core — adding the LLM layer currently destroys accuracy (this is the "eval inversion"; the fix campaign is `kernl-eval-inversion-campaign`). Therefore:

> **Nothing about deterministic reliability, policy-exactness, or "the LLM cannot make it wrong" may be claimed externally until the full-stack eval says otherwise.** The headline capability is currently refuted by the project's own committed numbers. There is no marketing framing that overrides this rule.

What you CAN say externally today: kernl is a working knowledge-compilation pipeline with a deterministic decision layer under active evaluation, and the architecture is designed so the deterministic layer's accuracy becomes the system's accuracy. That is an architecture claim, not a results claim.

---

## 2. Claim inventory — what kernl asserts, and where it lives in code

| # | Claim | One-line statement | Implementation anchor |
|---|---|---|---|
| C1 | Compile-don't-search ("agents are compilers") | Tribal knowledge is compiled ONCE into structured executable skills; the runtime reads compiled output instead of searching raw documents at query time | Thesis: `CLAUDE.md:10`; pipeline DAG: `backend/engine/graph.py:33-80` (load → chunk → 5-way parallel extraction → graph → metadata → skills → evidence → confidence → write) |
| C2 | Resolver decides, LLM explains, guardrail enforces | The deterministic resolver picks the action; the LLM is prompted as "a policy explainer ... Do NOT override the action" (`backend/runtime/brain_agent.py:748`); a pure-logic module hard-overwrites any LLM divergence | `backend/runtime/guardrails.py:44-50`; module "NEVER calls an LLM" (`guardrails.py:8`) |
| C3 | Compile-time DISCOVERED metadata | Valid vocabularies (departments, severities, workflow types, customer tiers, condition fields) and the action ontology are derived from the corpus, not hardcoded | `backend/engine/nodes/discover_operational_metadata.py:95-112` (`valid_sets` at :100, ontology at :96-99) |
| C4 | Evidence-linked, versioned brains with semantic diff | Every skill carries an `evidence` array of source quotes; brains are versioned (`v_<unix-ts>`, `backend/engine/nodes/write_brain.py:66`) in the `skills_files` table (`backend/schema.sql:12-21`); versions are diffable via `GET /diff/{v1}/{v2}` (`backend/api.py:410`) | evidence node: `backend/engine/nodes/link_evidence.py:7`; versions API: `backend/api.py:319` |
| C5 | Entropy-based "know when you don't know" | When candidate confidences are too flat (entropy > 0.75), the system declares "ambiguous" instead of guessing | `constraint_resolver.py:102-112, :262, :494` |

**Honesty caveats you must carry into any external text (as of 2026-07-10):**
- C1: the runtime still performs hybrid retrieval at query time — over *compiled skills*, not raw documents (`brain_agent.py:380` `_hybrid`). Say "no raw-document search at query time", never "no retrieval at query time".
- C3 is only HALF true: `valid_sets`, `action ontology`, `heuristic_patterns`, and `authority_levels` are genuinely derived from the corpus, but `retrieval_weights` and `thresholds` are hardcoded constants stamped into the discovered metadata (`discover_operational_metadata.py:77-92`, identical to the runtime fallback defaults at `brain_agent.py:22-37`). **Never claim weights or thresholds are learned/discovered.**
- C4: skill `evidence` quotes are produced by an LLM prompt ("find the most specific evidence excerpts", `link_evidence.py:27-45`); nothing verifies the quotes appear verbatim in the sources. The "semantic diff" (`api.py:410-494`) is exact-string field comparison on `rule`/`rationale` plus confidence deltas > 0.01 — it is a *structured* diff, not an embedding-level semantic diff. Do not oversell either.
- C5: the mechanism exists and is unit-tested, but its calibration is poor today (Section 3, row "knows when it doesn't know").

---

## 3. Claim → required evidence → current status

Status vocabulary: **PROVEN** (committed artifact demonstrates it), **PARTIAL** (mechanism exists, numbers incomplete), **REFUTED** (committed numbers contradict it), **UNTESTED** (no committed evidence either way). All statuses as of 2026-07-10; re-verify with the Provenance table before reuse.

| Claim (external phrasing) | Required evidence before claiming | Current status |
|---|---|---|
| "Compiles unstructured tribal knowledge into structured skills end-to-end" | A committed compiled brain traceable to committed sources | **PROVEN** — `backend/tests/last_compiled_brain.json`: 12 skills, 15 entities, 4 edges from the 8 files in `data/sources/rivanly-inc/` |
| "Deterministic on boundary scenarios" | COND family 8/8 strict on the FULL stack | **REFUTED** — runtime COND 1/8 strict; resolver-only COND 5/8 (per-family counts computed from the two committed results JSONs) |
| "Deterministic on clear-policy scenarios" | DET family 6/6 strict on the full stack, plus a working stability re-run | **PARTIAL** — runtime DET 5/6 strict; resolver-only DET 6/6; the `--stability` runner is broken (see §5) |
| "Knows when it doesn't know" | DET 6/6 AND a low false-ambiguity rate (answers "ambiguous" only when the docs are genuinely ambiguous) | **PARTIAL/REFUTED** — runtime run answered "ambiguous" 17/40 times, 11 of them on scenarios whose expected action was concrete (false-ambiguous); resolver-only had 6 false-ambiguous. The abstention mechanism works; its calibration does not |
| "The LLM can never override policy" | Guardrail unit tests + eval traces showing overrides fire correctly | **PARTIAL** — pure-logic guardrail exists and is unit-tested (`backend/tests/test_constraint_resolver.py:408-442`); but the guardrail only pins `action_type` — free-text `recommended_action`/`reasoning` are NOT checked, and full-stack strict accuracy shows the pinned action is often wrong anyway |
| "Metadata is discovered from the corpus, not hardcoded" | Show `valid_sets`/ontology differ per corpus | **PARTIAL** — true for vocabularies/ontology (rivanly brain: 9 departments, 4 severities, 8 workflow types, 6 condition fields — all corpus-derived); false for weights/thresholds (hardcoded, §2 caveat) |
| "Hybrid retrieval weights are justified" | Committed ablation results across configs A–E | **UNTESTED** — the harness supports `--ablation` (`eval_harness.py:566-596, :889`) but no `eval_ablation_results.json` exists in `backend/tests/` |
| "Every skill is evidence-linked to sources" | A verifier showing evidence quotes exist verbatim in source files | **UNTESTED** — evidence arrays exist for all 12 skills, but quotes are LLM-generated and unverified |
| "Compiled brain beats a generic LLM" | A scored A/B eval (same scenarios, `with_brain` true vs false), not anecdotes | **UNTESTED** — the A/B mechanism exists (§6) but no committed side-by-side scores |
| "Versioned brains with diffable changes" | Two brain versions + a diff response | **PARTIAL** — mechanism implemented (`api.py:319, :410`); works against live Supabase; no committed two-version fixture in the repo, so it is demo-provable but not repo-provable |

If a claim you want to make is not in this table, it defaults to **UNTESTED** — add it here with its required evidence before using it externally.

---

## 4. Prior art, honestly mapped

Rule: name the prior art yourself before a reviewer does. The novelty is in the *combination and the compile-time direction*, not in any single component.

| Prior art | What it already does | What kernl actually adds | What you may NOT claim |
|---|---|---|---|
| **RAG** (retrieval-augmented generation) | Embed docs, retrieve chunks at query time, let the LLM synthesize an answer | The thesis is anti-RAG *at query time*: extraction, contradiction-detection, ontology discovery, and confidence scoring happen at compile time; the runtime consults compiled skills + a deterministic resolver | "kernl does no retrieval" — false; it does hybrid retrieval over compiled skills (`brain_agent.py:380`). Also don't claim compiled-knowledge beats RAG empirically — no committed head-to-head exists |
| **Graphiti** (getzep) — its full README is vendored at `graphiti.md` (repo root, 665 lines; arXiv 2501.13956) | Temporal context graphs: every fact has a validity window, facts get invalidated when superseded, incremental updates, bitemporal queries | kernl's graph (`backend/engine/nodes/build_operational_graph.py`) is a plain entity/edge graph built at compile time — **no validity windows, no fact invalidation, not temporal today** (skills carry a small static `temporal_constraints` field like `{'window_days': 1}`; that is a rule condition, not temporal graph semantics). kernl's differentiator is the deterministic action-resolution layer on top, which Graphiti does not attempt | Any temporal-reasoning parity with Graphiti. Change-tracking in kernl = whole-brain recompile + version diff, not incremental fact invalidation |
| **Classic BRMS / rules engines** (Drools, business-rules products) | Deterministic evaluation of hand-authored rules; decades old | Rules are *extracted from unstructured tribal knowledge* (Slack exports, tickets, playbooks) with per-rule confidence weighting, evidence links, and contradiction detection — the authoring step is the novelty, not the deterministic evaluation | Novelty for the resolver/condition-evaluation itself. "Deterministic rule engine" is table stakes; say so |
| **LangGraph multi-agent pipelines** | Fan-out/fan-in orchestration; `Send`-based parallelism | Nothing — kernl's 5-way parallel extraction (`engine/graph.py:21-27`) is a textbook LangGraph pattern. It's infrastructure, not contribution | Any orchestration novelty |
| **Guardrails frameworks** (Guardrails AI, NeMo Guardrails) | Validate/repair LLM output against schemas or policies, often with LLM-in-the-loop retries | kernl's guardrail is a **hard override**: 52 lines, zero LLM calls, resolver verdict always wins (`guardrails.py`). Simpler and stricter — an authority inversion (LLM subordinate to symbolic layer), presented as a design choice | That this is a breakthrough; hard-override is simple by construction. And remember it only pins `action_type` (§3) |

Genuinely novel-if-proven (the honest pitch, in one sentence): *compile-time discovery of a company-specific action ontology and valid-value sets from unstructured sources, feeding a deterministic constraint resolver whose verdict an LLM may verbalize but never change, with entropy-calibrated abstention* — where "if proven" currently means Section 3 must flip its REFUTED/UNTESTED rows.

---

## 5. Reproducibility standard for any published number

Any accuracy/latency/count that leaves this repo (paper, blog, deck, README) must ship with ALL of:

1. **Code sha** — `git rev-parse HEAD` at the time of the run.
2. **The exact brain** — the compiled-brain JSON used (e.g. `backend/tests/last_compiled_brain.json` at that sha, or the `skills_files` row `version` string like `v_1750...`).
3. **The `metadata_json`** — because retrieval weights and thresholds live inside the brain and change behavior (`constraint_resolver.py:34-43` reads thresholds from it). It is nested in the brain file — no separate step if (2) is done, but SAY which weights/thresholds were active.
4. **Scenario-set version** — `SCENARIOS` in `backend/tests/eval_harness.py` at that sha (currently 40 scenarios: 6 DET, 8 COND, 26 policy-family; note the file's own docstring at `eval_harness.py:4` still says "21-scenario + 5 adversarial" — a stale docstring, and `scenario_counts.adversarial` is 0 in the committed baseline; don't propagate it).
5. **Raw results JSON committed** — the full per-scenario output (like `eval_results_baseline.json`), not just the headline percentage.

**Weight/ablation claims** additionally require a committed ablation run: `python -m backend.tests.eval_harness --ablation` sweeps five weight configs `A_semantic_only` → `E_with_conditions` (`eval_harness.py:566-596`; note the docstring at `eval_harness.py:8` says "4 configs" — there are 5) and writes `backend/tests/eval_ablation_results.json` (`eval_harness.py:941`). No such file is committed as of 2026-07-10, so no weight claim is currently publishable.

**Operational constraints on producing numbers:**
- Every eval run calls the shared vLLM gateway and live Supabase. Do NOT run the harness casually to "get a fresh number" — coordinate per `kernl-change-control`, and never overwrite baseline JSONs without the sign-off rules in `kernl-validation-and-qa`.
- Two repro paths are broken (as of 2026-07-10) and must not be cited as run instructions: `backend/tests/resolver_only_eval.py` imports four names that no longer exist in `brain_agent.py` (`resolver_only_eval.py:20-28`: `_load_skills_from_file`, `_compute_hybrid_score`, `_build_admissible_actions`, `RETRIEVAL_WEIGHTS` — post-refactor the functions are `_load_file`/`_hybrid`/`_admissible`, and the weights constant moved inside `_MD`), so the committed 62.5% cannot currently be re-run as-is; and `--stability` (`eval_harness.py:954`) passes `company_id=`/`context=` kwargs to `handle_agent_query(cid, scenario, ctx, ...)` (`brain_agent.py:635`), so every call raises, is swallowed by the `except`, records `"error"` three times, and reports a fake 100% consistency. Details and fix ownership: `kernl-validation-and-qa` / `kernl-debugging-playbook`.
- Never publish anything containing credentials. The HF token in git history (commit `22ee2f0`) is compromised and must be revoked; refer to it only by commit sha. The gateway key default: see `backend/core/llm.py:12-13` — never copy the value.

---

## 6. Demo discipline — what a live demo may honestly show

The demo surface: Next.js frontend (`frontend/src/app/{compile,skills,demo}`) against the FastAPI backend (start-up: `kernl-run-and-operate`).

**CAN show honestly (as of 2026-07-10):**

| Demo beat | Mechanism | Honest framing |
|---|---|---|
| Live compile of Rivanly Inc. with stage-by-stage streaming | `POST /compile` (`backend/api.py:200`) + SSE `GET /compile/{job_id}/stream` (`api.py:229`) | "Watch tribal knowledge become structured skills" — pipeline completion is proven; the committed compile took ~291s (`last_compiled_brain.json` meta), so pre-compile a fallback |
| Evidence-linked skills browser | `GET /skills/{company_id}` (`api.py:291`) | Show rule + rationale + evidence quotes + confidence. Say "evidence as extracted"; do NOT claim quotes are verified verbatim (§3) |
| A/B: brain agent vs generic LLM | Demo page fires the same scenario twice — `with_brain: true` and `false` (`frontend/src/app/demo/[companyId]/page.tsx:47-48`; baseline prompt "You are a generic AI assistant... NO company-specific knowledge" at `brain_agent.py:813`) | "Same model, with and without the compiled brain" — a qualitative contrast. Do NOT read a win-rate off it; that's the UNTESTED A/B row in §3 |
| Brain versions + semantic diff | `GET /brain/versions/{company_id}` (`api.py:319`), `GET /diff/{v1}/{v2}` (`api.py:410`) | Recompile after editing a source doc, show added/deleted/modified skills and confidence shifts. Call it a "structured diff" |

**CANNOT show / must never be scripted:**
- **Strict determinism on free-typed scenarios.** At 15.0% full-stack strict, an audience-chosen boundary question ("customer bought 15 days ago, annual plan — refund?") is more likely wrong than right. Never invite free-form boundary inputs; never say "it always follows policy".
- **Abstention as a feature demo.** With 11/40 false-ambiguous answers in the committed run, "watch it say it doesn't know" will fire on questions it *should* answer.
- **Any number on a slide** that fails the Section 5 standard.
- Anything the demo depends on live Supabase/vLLM for — have recorded fallbacks; it is a shared environment you don't control mid-demo.

---

## Provenance and maintenance

Facts verified 2026-07-10 against the working tree (git HEAD `d215501`). All numbers/line-refs below are volatile — re-verify before reuse. Run from repo root; quote paths (they contain a space).

| Volatile fact | Re-verify with |
|---|---|
| Full-stack strict 15.0 / relaxed 52.5 (2026-06-16) | `py -c "import json;d=json.load(open('backend/tests/eval_results_baseline.json'));print(d['run_timestamp'],d['strict_accuracy_pct'],d['relaxed_accuracy_pct'])"` |
| Resolver-only 62.5 (25/40, 2026-06-15) | `py -c "import json;d=json.load(open('backend/tests/resolver_eval_results.json'));print(d['timestamp'],d['strict_passed'],d['accuracy_pct'])"` |
| Per-family: runtime DET 5/6, COND 1/8; resolver DET 6/6, COND 5/8 | `py -c "import json,collections;f=lambda p,k:print({pfx:[sum(1 for r in json.load(open(p))['results'] if r['id'].startswith(pfx) and r[k]),sum(1 for r in json.load(open(p))['results'] if r['id'].startswith(pfx))] for pfx in('DET','COND')});f('backend/tests/eval_results_baseline.json','strict_pass');f('backend/tests/resolver_eval_results.json','pass')"` |
| 11 runtime false-ambiguous (of 17 ambiguous answers) | `py -c "import json;rs=json.load(open('backend/tests/eval_results_baseline.json'))['results'];print(sum(1 for r in rs if r['actual_action_type']=='ambiguous'),sum(1 for r in rs if r['actual_action_type']=='ambiguous' and 'ambig' not in r['expected_action']))"` |
| Ablation configs A–E, output filename | `grep -n "A_semantic_only\|E_with_conditions\|eval_ablation_results" backend/tests/eval_harness.py` |
| No committed ablation results | `ls backend/tests/` (look for `eval_ablation_results.json`) |
| Guardrail hard override, no LLM | `grep -n "NEVER calls an LLM\|Overridden" backend/runtime/guardrails.py` |
| "Policy explainer" LLM prompt | `grep -n "policy explainer" backend/runtime/brain_agent.py` |
| Hardcoded retrieval_weights/thresholds in "discovered" metadata | `grep -n -A6 "retrieval_weights = {" backend/engine/nodes/discover_operational_metadata.py` |
| Entropy fn + ambiguity threshold 0.75 | `grep -n "ambiguity_entropy\|def compute_entropy" backend/runtime/constraint_resolver.py` |
| Brain version scheme `v_<ts>`, metadata_json in brain | `grep -n "version_str\|metadata_json" backend/engine/nodes/write_brain.py` |
| Diff + versions + agent endpoints | `grep -n "@app" backend/api.py` |
| A/B `with_brain` wiring | `grep -rn "with_brain" backend/core/models/schemas.py "frontend/src/app/demo"` |
| graphiti.md is the Graphiti README (temporal graphs) | `head -30 graphiti.md` |
| kernl graph non-temporal | `grep -n -i "temporal\|valid_from\|invalid" backend/engine/nodes/build_operational_graph.py` (expect no validity-window hits) |
| Compiled brain: 12 skills, 2026-06-15, ~291s | `py -c "import json;d=json.load(open('backend/tests/last_compiled_brain.json'));print(d['meta'])"` |
| resolver_only_eval import break | `grep -n "_load_skills_from_file\|RETRIEVAL_WEIGHTS" backend/tests/resolver_only_eval.py backend/runtime/brain_agent.py` (names absent from brain_agent) |
| --stability kwarg break | `grep -n "company_id=COMPANY_ID" backend/tests/eval_harness.py; grep -n "def handle_agent_query" backend/runtime/brain_agent.py` |
| Thesis sentence | `sed -n 10p CLAUDE.md` |
