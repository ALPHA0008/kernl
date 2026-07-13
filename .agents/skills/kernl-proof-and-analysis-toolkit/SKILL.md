---
name: kernl-proof-and-analysis-toolkit
description: Load this when you need to PROVE a claim about kernl instead of eyeballing it — "is this deterministic", "why is entropy always ~0.97", "which retrieval signal caused this wrong answer", "would this ambiguity-rule change help", "are the brain's conditions complete", "did the pipeline catch the planted contradiction", or before/after any threshold or weight tuning. Provides 8 first-principles analysis recipes (determinism proof, entropy algebra, offline replay from committed eval JSONs, ablation methodology, hybrid-score decomposition, boundary truth tables, coverage audit, contradiction verification) each with a worked example using this repo's real recorded numbers.
---

# kernl Proof and Analysis Toolkit

**What this covers:** eight recipes for demonstrating — with numbers, not vibes — how the kernl runtime behaves. The house rule is "prove it, don't just tweak it": before changing a threshold, weight, or rule, produce evidence of what the change does, ideally offline from the committed eval artifacts.

**When NOT to use this:**
- Deciding whether a change may merge and what gates it must pass → `kernl-change-control` (gating lives there; nothing here overrides it).
- Actually running the full eval and interpreting baselines → `kernl-validation-and-qa`; the campaign to fix the strict/relaxed inversion → `kernl-eval-inversion-campaign`.
- Something is broken and you're hunting the cause → `kernl-debugging-playbook`; past incidents → `kernl-failure-archaeology`.
- How the pipeline/architecture is supposed to work → `kernl-architecture-contract`, `knowledge-compilation-reference`. Thresholds as config → `kernl-config-and-flags`. Starting services → `kernl-run-and-operate`. Research method beyond this repo → `kernl-research-methodology`.

## Jargon (defined once, used throughout)

| Term | Meaning |
|---|---|
| **Resolver** | `backend/runtime/constraint_resolver.py` — deterministic policy engine; picks an action with **no LLM call** (its docstring says so at `constraint_resolver.py:11`). |
| **ConstraintResult** | The resolver's output dataclass (`constraint_resolver.py:74-99`): primary action, all admissible actions, `entropy`, `is_ambiguous`, escalation fields, reasoning steps. `.to_dict()` rounds floats to 4 dp. |
| **Normalized Shannon entropy** | `compute_entropy` (`constraint_resolver.py:102-112`): confidences → probabilities (divide by sum), H = −Σ p·log₂p, divided by log₂(n). 0 = one clear winner, 1 = perfect tie. |
| **Hybrid score / 5 signals** | Retrieval score per skill = weighted sum of **semantic, metadata, keyword, severity, condition** signals plus a small specificity bonus (`brain_agent.py:380-420`). Default weights `brain_agent.py:22-28`: 0.45 / 0.20 / 0.15 / 0.10 / 0.10 (as of 2026-07-10). |
| **Compiled brain** | The skills JSON the compile pipeline produces for the demo company **Rivanly Inc** (fictional; sources under `data/sources/rivanly-inc/`). Committed snapshot: `backend/tests/last_compiled_brain.json` (12 skills). |
| **Eval harness** | `backend/tests/eval_harness.py` — 40 ground-truth scenarios; **strict** = exact `action_type` match (determinism metric), **relaxed** = semantic match. Families by ID prefix: REF×7, CS×3, ENG×4, HR×2, PRICE×3, SLACK×1, OPS×1, `*-ADV`×5 (adversarial), DET×6 (expect `ambiguous`), COND×8 (boundary cases). |
| **Offline replay** | Re-computing a hypothesis from the **committed** eval JSONs' recorded traces — zero LLM/gateway/Supabase calls. The cheapest instrument in the repo. |
| **Typed condition** | `{field, operator, value, type}` dict attached to a skill/policy, e.g. `days_since_purchase <= 14.0` (number). |

**Safety note (as of 2026-07-10):** `python -m backend.tests.eval_harness` (standard, `--ablation`, `--stability`) drives `handle_agent_query` → the **shared live vLLM gateway and Supabase**. Do not run it casually; clear it per `kernl-change-control`. Everything marked OFFLINE below touches no network. On Windows without `python` on PATH, substitute `py` for `python`. Run all commands from the repo root: `cd "D:\Abhijith P\Desktop\Project\kernl"` (path contains a space — keep the quotes).

## The three committed instruments (as of 2026-07-10)

| File | What it holds | Key stats |
|---|---|---|
| `backend/tests/eval_results_baseline.json` | Full-pipeline (LLM) run of all 40 scenarios, 2026-06-16 | strict 15.0%, relaxed 52.5%, rule-hit 55.0%, avg hybrid score 0.3316; per-scenario `retrieval_trace` |
| `backend/tests/eval_results_partial.json` | Live-progress copy of the same run | `results` array is byte-identical to baseline's (verified 2026-07-10) — use either |
| `backend/tests/resolver_eval_results.json` | Resolver-only run (retrieval + resolver, no LLM verbalization), 2026-06-15 | strict 25/40 = 62.5%; per-scenario `entropy`, `is_ambiguous`, and `all_admissible` action/confidence lists |
| `backend/tests/last_compiled_brain.json` | Brain snapshot: 12 skills, conditions, metadata, weights, thresholds | 9 typed conditions across 4 skills |

Caveat: `resolver_eval_results.json` predates a `brain_agent.py` refactor — `backend/tests/resolver_only_eval.py` is **import-broken** as of 2026-07-10 (imports `_load_skills_from_file`, `_compute_hybrid_score`, `_build_admissible_actions`, `RETRIEVAL_WEIGHTS` at `resolver_only_eval.py:20-26`; brain_agent now has `_load_file`, `_hybrid`, `_admissible`, and weights inside `_MD`). You can *analyze* its committed output; you cannot re-run it without fixing the imports (and even fixed, it calls `get_embedding` → gateway). Likewise `--stability` is kwarg-broken: `eval_harness.py:970-975` passes `company_id=`/`context=` but the signature is `handle_agent_query(cid, scenario, ctx=None, ...)` (`brain_agent.py:635`).

---

## Recipe 1 — Determinism proof

**When:** you claim (or doubt) that a code path "never involves the LLM" or "always gives the same answer." Required evidence before labeling anything deterministic in docs or PRs.

**Steps**
1. Run the pure unit suite (OFFLINE, no network): `python -m backend.tests.test_constraint_resolver` — 26 tests, self-running `__main__` (no pytest needed). Expected: `Results: 26/26 passed, 0 failed` (verified 2026-07-10).
2. Run the target function **twice on deep-copied identical inputs** and diff the serialized outputs. Verified snippet (OFFLINE):

```python
import json, copy
from backend.runtime.constraint_resolver import resolve

graph_result = {"success": False, "graph_confidence": 0.0, "policies": [],
                "condition_results": [], "precedence_edges": []}
skill_admissible = [
    {"action": "approve", "retrieval_score": 0.30, "action_confidence": 0.9, "category": "Refunds",
     "conditions": [{"field": "days_since_purchase", "operator": "<=", "value": 14.0, "type": "number"}]},
    {"action": "deny", "retrieval_score": 0.22, "action_confidence": 0.8, "category": "Refunds",
     "conditions": [{"field": "days_since_purchase", "operator": ">", "value": 60.0, "type": "number"}]},
]
context = {"plan_type": "annual", "days_since_purchase": 9}
qs = {"raw_text": "Customer on an annual plan requesting a refund, purchased 9 days ago."}
r1 = resolve(copy.deepcopy(graph_result), copy.deepcopy(skill_admissible), dict(context), dict(qs)).to_dict()
r2 = resolve(copy.deepcopy(graph_result), copy.deepcopy(skill_admissible), dict(context), dict(qs)).to_dict()
assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True), "NONDETERMINISTIC"
print("DETERMINISTIC:", r1["primary_action"]["action_type"], "entropy", r1["entropy"])
```

Verified output (2026-07-10): `DETERMINISTIC: approve entropy 0.8046`. (Entropy 0.8046 > 0.75 yet not ambiguous — the relative score gap 0.674 clears the 0.10 differential gate; see Recipe 2.)

**What breaks determinism** (check for these before trusting a "same twice" result):
- **Any LLM or embedding call** in the path — `handle_agent_query` and `get_embedding` hit the gateway; the resolver and `condition_eval` do not.
- **Dict/set iteration order** feeding a decision — Python dicts preserve insertion order, so results are reproducible only if inputs arrive in the same order. The resolver's `sort(key=lambda a: a.confidence)` (`constraint_resolver.py:476`) is a stable sort: exact confidence ties are broken by *input order*.
- **Float accumulation** — `sum()` over differently-ordered float lists can differ in the last bits; `to_dict()` rounds to 4 dp which masks this, so diff the rounded dicts, not raw floats.

**Licenses:** "resolver output is a pure function of its inputs, twice." Does NOT license "the end-to-end answer is deterministic" (retrieval embeddings and LLM verbalization sit above it), nor "deterministic across machines/Python versions" (untested).

## Recipe 2 — Entropy analysis (why ~0.97 was inevitable)

**When:** anyone proposes moving `ambiguity_entropy` (default 0.75, `constraint_resolver.py:27`) or asks why nearly everything trips the entropy gate.

**The algebra.** With n candidate scores all near a common value s — write them s(1+δᵢ) — normalized entropy is, to second order:

```
H/H_max ≈ 1 − (Σ δᵢ²) / (2 · n · ln2 · log₂n)
```

Bunched scores ⇒ tiny δᵢ ⇒ H/H_max pinned near 1. Check: `[0.31, 0.30, 0.29, 0.28]` has δ ≈ ±0.051, ±0.017 → formula gives 1 − 0.00573/11.09 = 0.99948; exact computation gives **0.99948**. Inverting the exact formula (equal losers): to get H/H_max **below 0.75**, the winner needs ≥ **64.5%** of total confidence mass with n=4 candidates, ≥ **69.7%** with n=3 (computed 2026-07-10).

**Worked example from a committed trace** (`backend/tests/resolver_eval_results.json`, scenario REF-01, run 2026-06-15): recorded `all_admissible` confidences `[0.2883, 0.2159, 0.1409]`, recorded `entropy: 0.9636`. By hand: total 0.6451 → p = [0.4469, 0.3347, 0.2184] → H = 1.5273 → H/log₂3 = **0.9636**. Winner's mass share is 0.447 — far below the 0.697 needed, so entropy > 0.75 was *structurally guaranteed*, not a scenario quirk. Across all 40 recorded scenarios: entropy min 0.8779, mean 0.9705 ("~0.97"), max 0.9956; 29 scenarios had 4 candidates, 11 had 3. Skill-path confidences are bunched by construction: `retrieval_score × action_confidence × condition_multiplier` (`constraint_resolver.py:456-461`) lands everything in roughly 0.14–0.32.

Every recorded entropy is exactly reproducible from its `all_admissible` list (0 mismatches at 4 dp, verified 2026-07-10) — which is what makes Recipe 3 trustworthy.

**Why anything passes at all:** ambiguity needs BOTH high entropy AND a small top-2 relative gap — `is_ambiguous = (entropy > 0.75 and score_diff < 0.10) or det_ambiguous` (`constraint_resolver.py:484-495`). REF-01 passed with entropy 0.9636 because gap = (0.2883−0.2159)/0.2883 = 0.251 ≥ 0.10.

**Licenses:** "entropy is uninformative as an ambiguity signal while scores are bunched; tuning the 0.75 threshold cannot separate these distributions." Does NOT license "entropy is useless" (it would discriminate if score spreads widened) or any specific replacement rule — test those via Recipe 3.

## Recipe 3 — Offline replay (test hypotheses with zero LLM calls)

**When:** before proposing ANY scoring/gating change. The committed JSONs contain full traces; most gating hypotheses can be evaluated against all 40 scenarios in seconds, offline.

**Steps**
1. State the proposed rule as a function of *recorded* fields only (`all_admissible` confidences, `entropy`, `is_ambiguous`, `expected_action`, retrieval-trace components).
2. Recompute the rule per scenario; report **predicted flips** (scenarios whose ambiguity/action verdict changes) and whether each flip moves toward or away from `expected_action`.
3. Only if flips look favorable, request a live eval run per `kernl-change-control`.

Verified snippet (OFFLINE; save outside the repo, e.g. your scratch dir, and run from repo root):

```python
import json, math

def entropy(scores):
    total = sum(scores)
    if not scores or total <= 0: return 1.0
    p = [s / total for s in scores]
    h = -sum(x * math.log2(x) for x in p if x > 0)
    hmax = math.log2(len(p)) if len(p) > 1 else 1.0
    return h / hmax if hmax > 0 else 1.0

runs = json.load(open("backend/tests/resolver_eval_results.json"))["results"]
flips = []
for r in runs:
    scores = sorted((a["confidence"] for a in r["all_admissible"]), reverse=True)
    gap = (scores[0] - scores[1]) / max(scores[0], 0.001) if len(scores) >= 2 else 1.0
    proposed = entropy(scores) > 0.75 and gap < 0.25      # <- hypothesis under test
    if proposed != r["is_ambiguous"]:
        flips.append((r["id"], r["is_ambiguous"], proposed, r["expected_action"]))
print(f"{len(flips)} predicted flips / {len(runs)} scenarios")
for f in flips: print(" ", f)
```

**Worked example** (run 2026-07-10): raising the score-diff gate from 0.10 to 0.25 predicts **11/40 flips** — 10 currently-decided scenarios (REF-03, REF-05, CS-03, ENG-02, REF-ADV-01, CS-ADV-01, COND-04, COND-06, COND-07, COND-08) become ambiguous (all have non-ambiguous expected actions → predicted regressions, including currently-passing COND-06/07/08), and DET-02 stops being ambiguous (expected `ambiguous` → also a regression). Conclusion licensed: **reject the 0.25 gate without spending a single LLM call.**

**Licenses:** "under the recorded score distributions, rule X flips exactly these scenarios." Does NOT license end-to-end accuracy claims — a rule change that alters *retrieval or confidence computation itself* invalidates the recorded scores, and the LLM verbalization layer above the resolver can still mangle a correct primary action. Recorded traces are from 2026-06-15/16 code; a live confirmation run is still required before merge (see `kernl-change-control`).

## Recipe 4 — Ablation methodology

**When:** attributing accuracy to retrieval signals, or evaluating a weight change.

**The harness mode:** `python -m backend.tests.eval_harness --ablation` runs the full 40-scenario eval once per config in `ABLATION_CONFIGS` (`eval_harness.py:566-598`) and writes `backend/tests/eval_ablation_results.json` (not currently committed). It is a LIVE run (5 × 40 gateway-backed scenarios) — clear it first per `kernl-change-control`. Note: two docstrings say "4 configs" (`eval_harness.py:8`, `:892`) but there are **5** (as of 2026-07-10):

| Config | semantic | metadata | keyword | severity | condition |
|---|---|---|---|---|---|
| `A_semantic_only` | 1.00 | 0 | 0 | 0 | — |
| `B_semantic_metadata` | 0.70 | 0.30 | 0 | 0 | — |
| `C_semantic_keywords` | 0.70 | 0 | 0.20 | 0.10 | — |
| `D_full_hybrid` | 0.50 | 0.20 | 0.20 | 0.10 | — |
| `E_with_conditions` | 0.45 | 0.20 | 0.15 | 0.10 | 0.10 |

`E` equals the runtime defaults (`brain_agent.py:22-28` and `last_compiled_brain.json` → `metadata_json.retrieval_weights`).

**How to read an ablation table:** one row per config, columns strict% / relaxed% / avg hybrid score / avg op-confidence. Attribute a signal's contribution by comparing adjacent configs that differ in that signal *only* (A→B isolates metadata; D→E isolates conditions). That is the point of one-variable-at-a-time: change two weights at once and the delta is unattributable. Note A→C and C→D change more than one weight — only some pairs are clean isolations.

**The overfitting trap:** 40 scenarios means one scenario = 2.5 points, and binomial noise is large — at p≈0.5, the standard error is √(0.5·0.5/40) ≈ **7.9 points**. A 5-point "improvement" from weight tuning on the same 40 scenarios you report is indistinguishable from noise and is likely memorizing the eval. Mitigations this repo uses/expects:
- Report **per-family deltas** (the harness prints BREAKDOWN BY SOURCE per source doc; family prefixes REF/CS/ENG/HR/PRICE/DET/COND/ADV) — a real retrieval improvement moves several families, not one.
- **Hold out the DET family** (6 scenarios) from any tuning decision: they test the ambiguity *gate*, and tuning weights to un-ambiguate them defeats their purpose.
- The harness's own anti-overfitting notes: `eval_harness.py:239`, `:563-565`, `:895-897`.

**Known metric bug (as of 2026-07-10):** the harness counts adversarial scenarios with `r["id"].startswith("ADV-")` (`eval_harness.py:754`) but the IDs are `ENG-ADV-01` style, so `scenario_counts.adversarial` is 0 in saved results. Don't conclude "no adversarial scenarios ran" from that field.

**Licenses:** "signal X's weight moved strict/relaxed by Δ on this 40-item set." Does NOT license "signal X helps in general" (n=40, one company, one document corpus).

## Recipe 5 — Hybrid-score decomposition (blame a wrong retrieval)

**When:** a scenario retrieved the wrong skill, or the right skill won for the wrong reason.

**The formula** (`brain_agent.py:389-405`): `final_score = 0.45·semantic + op_s + specificity_bonus`, where `op_s = 0.20·metadata + 0.15·keyword + 0.10·severity + 0.10·condition`, the recorded `operational_confidence = op_s / 0.55` (denominator = sum of the four operational weights), and `specificity_bonus = (specificity_level/5) × 0.02` (`brain_agent.py:396-397`; level 2 ⇒ 0.008). So from a recorded trace you can reconstruct:

```
final_score = 0.45·semantic_confidence + 0.55·operational_confidence + specificity_bonus
```

**Steps:** pull the scenario's `retrieval_trace` from `eval_results_baseline.json`; verify the identity above (sanity check that you read the right fields); then compare semantic vs operational contribution, and top vs `runner_up_scores`, to name the culprit signal.

**Worked example — REF-04** (baseline run 2026-06-16; expected `deny` for a lifetime-deal refund, got `ambiguous`): top skill `refund_policy_matrix`, `semantic_confidence 0.4353`, `operational_confidence 0.0727`, `final_score 0.2439`. Check: 0.45×0.4353 + 0.55×0.0727 + 0.008 = 0.1959 + 0.0400 + 0.0080 = **0.2439** ✓. Blame table:

| Signal | Contribution | Reading |
|---|---|---|
| semantic | 0.1959 (80% of final) | carried the match alone |
| operational (meta+kw+sev+cond) | 0.0400 | near-dead; `why_matched` lists only "Specificity level 2 preferred" — **no condition matched**, because the brain's refund conditions key on `days_since_purchase`/`refund_amount`/`tenure_months` and REF-04's context is `{plan_type: lifetime_deal, days_since_purchase: 30}` — there is no `plan_type == lifetime_deal` condition (see Recipe 7) |
| specificity bonus | 0.008 | noise |

Diagnosis: semantic similarity dominated with zero condition support; final score 0.2439 was so low that downstream confidences bunched → entropy ambiguity (Recipe 2). The fix class is *add the missing typed condition*, not *re-weight semantic*. Same pattern in REF-03 (expected `escalate`, got `approve`: 0.45×0.4597 + 0.55×0.1636 + 0.008 = 0.3049 ✓).

**Caveat:** the committed baseline trace stores the full component breakdown (`metadata_score`, `keyword_score`, `severity_score`, `condition_score`) **only for the runner-up** (`runner_up_scores`); for the top skill you get the semantic/operational split plus the `why_matched` string (`eval_harness.py:710-722` selects the subset; `brain_agent.py:423-483` builds the full trace). For future runs, extend the harness to record `rt["components"]` wholesale before doing fine-grained blame.

**Licenses:** "for this scenario, signal S contributed X of the final score." Does NOT license counterfactuals ("with condition_score 1.0 it would have won") unless you recompute the counterfactual score for BOTH the top skill and all rivals.

## Recipe 6 — Boundary analysis for typed conditions

**When:** adding/reviewing any numeric condition, or investigating COND-family failures.

**Three evaluators, two semantics (as of 2026-07-10).** This is the sharpest edge in the codebase:

| Evaluator | Missing context field | `>` / `<` at exact boundary |
|---|---|---|
| `condition_eval.evaluate_condition` (`condition_eval.py:24-26`) — used by the graph path (`graph_retriever.py:71`) | returns **True** (condition counts as met) | strict (`60 > 60` → False) |
| `brain_agent._score_cond` (`brain_agent.py:332-377`) — retrieval condition signal | field skipped; all fields missing → score **0.0** | strict |
| `constraint_resolver._compute_condition_adjustment` (`constraint_resolver.py:285-364`) — skill-path confidence multiplier | field skipped ("neutral"); all missing → multiplier **1.0**; else multiplier = 0.5 + 0.5·(matched/evaluated) (`:360`) | **inclusive** — `>` and `<` are patched to match on equality (`constraint_resolver.py:324-331`) |

**Steps**
1. Enumerate boundary cases for each threshold: exact value (`==`), one unit below, one unit above (off-by-one day, exact dollar).
2. Build a truth table per evaluator using the table above.
3. Compare each row against the Rivanly ground-truth expectation (harness COND scenarios, `eval_harness.py:357-430`).

**Worked example — the refund thresholds** (brain conditions `days_since_purchase > 60.0` and `refund_amount > 500.0` in `refund_policy_matrix`, `last_compiled_brain.json`):

| Context | condition_eval (strict) | resolver adjustment (inclusive) | Ground truth wants |
|---|---|---|---|
| `days_since_purchase = 60` vs `> 60` | False | **True** | deny (COND-06: "60 days" is past the cutoff) → inclusive semantics happens to help |
| `refund_amount = 500` vs `> 500` | False | **True** | approve, no escalation (COND-03: "> $500" means 500 exactly does NOT escalate) → inclusive semantics is WRONG here |
| `days_since_purchase = 14` vs `<= 14` | True | True | approve full (COND-01/REF-07) ✓ both |
| field absent entirely | True (met!) | skipped, neutral | — divergent "missing" semantics; a graph policy can pass all conditions purely by the context omitting its fields |

The recorded resolver run confirms the damage: COND-03 failed (got `ambiguous`) and COND-04 failed (got `approve` instead of `get_founder_approval`) in `resolver_eval_results.json` (2026-06-15). The inclusive-`>` patch is a boundary hack that fixes one COND scenario while breaking its mirror — a truth table exposes this in minutes; tuning never will.

**Licenses:** "condition set C decides these enumerated boundary rows correctly/incorrectly under evaluator E." Does NOT license "the scenario will pass" — retrieval must still surface the right skill (Recipe 5), and the LLM layer can still override phrasing.

## Recipe 7 — Coverage audit (conditions vs ground truth)

**When:** asking "does the compiled brain actually encode the policies?" — after any recompile, and before blaming retrieval for a failure.

**Steps**
1. Inventory brain conditions (OFFLINE):
```python
import json
d = json.load(open("backend/tests/last_compiled_brain.json"))
for s in d["skills"]:
    for c in s.get("conditions") or []:
        print(s["id"], c["field"], c["operator"], c["value"])
```
2. Inventory ground-truth thresholds by reading the 8 source docs under `data/sources/rivanly-inc/`.
3. Diff. Every ground-truth threshold with no matching typed condition is a scenario family the runtime can only win by semantic luck.

**Worked example (as of 2026-07-10).** The committed brain has **9 conditions across 4 of 12 skills**: `refund_policy_matrix` (days ≤ 14, days > 60, refund_amount > 500, tenure_months < 3), `discount_authority_matrix` (discount ≤ 10, discount > 30), and `customer_tier == enterprise` on `enterprise_onboarding_requirements`, `p0_bug_enterprise_response`, `enterprise_custom_pricing_route`. Ground-truth numeric thresholds (~a dozen):

| # | Threshold | Source | Typed condition in brain? |
|---|---|---|---|
| 1 | full refund ≤ 14 days (annual) | `notion_refund_sop.md:9-10` | YES |
| 2 | deny > 60 days, any tier | `notion_refund_sop.md:16` | YES |
| 3 | founder if > $500 AND tenure < 3 months (monthly) | `notion_refund_sop.md:13` | YES (both halves) |
| 4 | enterprise refund → AM within 1 hour | `notion_refund_sop.md:11` | partial (tier conditions exist on other skills, not refund) |
| 5 | lifetime deal → deny | `notion_refund_sop.md:12` | **NO** (`plan_type` never appears) — explains REF-04/COND-07 |
| 6 | ≥ 3 churn signals in 30 days → AM call in 24h | `notion_cs_playbook.md:7` | **NO** — explains CS-03/CS-ADV-01 (got `initiate_enterprise_onboarding`) |
| 7 | P1 → resolve within 4 hours | `notion_eng_runbook.md:9` | **NO** (`p1_bug_resolution_sla` has 0 conditions) |
| 8 | SLA breach > 1h → support lead | `notion_eng_runbook.md:13` | **NO** |
| 9 | enterprise SLA breach ≥ 2h → AM + Eng Lead | `notion_eng_runbook.md:14` | **NO** |
| 10 | discount ≤ 10% (support/CS) | `notion_pricing_policy.md:9` | YES |
| 11 | startup discount ≤ 20% (pre-seed/seed, annual, yr 1) | `notion_pricing_policy.md:10` | **NO** — explains PRICE-03/PRICE-ADV-01 |
| 12 | discount > 30% → AE | `notion_pricing_policy.md:11` | YES |
| 13 | 2 consecutive missed-KPI quarters → PIP (+5-day review) | `notion_hr_playbook.md:16-17` | **NO** |
| 14 | vendor invoice ≥ $3,500 → ops lead | `slack_export_ops.json` (david_ops_lead msg) | **NO** (`vendor_invoice_approval` has 0 conditions) |
| 15 | tenure > 2 years bypasses 30-day rule | `slack_export_support.json` (team-lead msg) | **NO** (rule text mentions it; no condition) |

Roughly **9 of ~15** thresholds have no typed condition — and the missing ones line up with the recorded failures (Recipe 5's REF-04, CS-03, PRICE-ADV-01...). That correlation is the audit's payoff: it converts "retrieval is flaky" into "the compiler didn't emit conditions for these rules" (compiler internals → `knowledge-compilation-reference`).

**Licenses:** "the brain lacks machine-checkable encodings for thresholds X, Y, Z." Does NOT license "adding them fixes the scenarios" — that's a hypothesis for Recipes 3/6 and then a gated live run.

## Recipe 8 — Contradiction analysis (verifying the planted conflict was caught)

**When:** validating the contradiction-detection stage after a recompile, or explaining the feature.

**The plant.** The Rivanly corpus deliberately contradicts itself on the refund hard limit: the SOP says **no refunds after 60 days** (`notion_refund_sop.md:16`), while Slack has an agent claiming "SOP says 30 days max" and a team lead approving a 45-day refund because ">2 years tenure bypasses the 30-day rule" (`slack_export_support.json`, first two messages). 60 vs 30 — one of them must be wrong.

**Where contradictions flow (compile pipeline):**
1. Detected by the `detect_contradictions` node (`backend/engine/nodes/detect_contradictions.py`) — an LLM extraction pass over chunks tagged with the `contradictions` domain, emitting `{id, domain, claim_a/source_a, claim_b/source_b, resolution, severity}`.
2. Accumulated into `BrainState.contradictions` — an `Annotated[List[...], operator.add]` field (`backend/engine/state.py:15`), meaning LangGraph *merges* the parallel extraction branches' lists at the fan-in barrier (the node runs in parallel with the other extractors via `Send`, `backend/engine/graph.py:26`, joining at `build_operational_graph`, `graph.py:75`).
3. Fed into skill synthesis, whose prompt instructs "Resolve conflicts: note contradictions in the rationale" (`backend/engine/nodes/synthesize_skills.py:199`, consumed at `:241` and `:276`).

**Verification steps (OFFLINE)**
1. `grep -in "contradiction" backend/tests/last_compiled_brain.json`
2. Confirm the note names both claims and a resolution. In the committed snapshot (as of 2026-07-10, `last_compiled_brain.json:4348`) the `refund_policy_matrix` rationale reads: *"Note: Contradiction exists between SOP (60 days) and internal chat (30 days) regarding hard limits; SOP 60-day limit takes precedence."* — plant caught, both sources characterized, precedence resolved in the SOP's favor.
3. Cross-check behavior: the skill's `rule` text also carries the exception ("bypass 30-day rule for customers with > 2 years tenure"), and scenario SLACK-01 tests it (expected `approve`; it failed as `ambiguous` in the 2026-06-15 resolver run — detection succeeded, *actioning* it did not).

**Licenses:** "the pipeline detected and recorded THIS planted contradiction in THIS compile." Does NOT license "contradiction detection is reliable" (n=1 plant, LLM-dependent stage — re-verify after every recompile; the note lives in free-text rationale, not a structured field the resolver consumes).

---

## Provenance and maintenance

All facts verified against the repo on **2026-07-10**. The eval JSONs are point-in-time artifacts (baseline 2026-06-16, resolver-only 2026-06-15); numbers quoted from them stay true of *those files* but describe superseded code once anything recompiles or re-runs. Re-verify volatile facts:

| Fact | Re-verify with (from repo root; use `py` if `python` absent) |
|---|---|
| 26 unit tests, all passing | `python -m backend.tests.test_constraint_resolver` |
| 40 scenarios in harness | `python -c "from backend.tests.eval_harness import SCENARIOS; print(len(SCENARIOS))"` |
| Thresholds 0.75 / 0.40 / 0.5 / 0.10 | `grep -n -A5 "DEFAULT_THRESHOLDS = " backend/runtime/constraint_resolver.py` |
| Weights 0.45/0.20/0.15/0.10/0.10 | `grep -n -A6 "\"retrieval_weights\"" backend/runtime/brain_agent.py` |
| 5 ablation configs A–E | `grep -n "^    \"[A-E]_" backend/tests/eval_harness.py` |
| Ambiguity rule (entropy AND gap OR det) | `grep -n -B2 -A2 "is_ambiguous = (" backend/runtime/constraint_resolver.py` |
| Inclusive `>`/`<` boundary patch | `grep -n -A3 "operator == \">\"" backend/runtime/constraint_resolver.py` |
| Missing-field → True in condition_eval | `grep -n -A2 "if ctx_val is None" backend/runtime/condition_eval.py` |
| Baseline strict 15.0 / relaxed 52.5 | `python -c "import json;d=json.load(open('backend/tests/eval_results_baseline.json'));print(d['run_timestamp'],d['strict_accuracy_pct'],d['relaxed_accuracy_pct'])"` |
| Resolver-only 62.5%, mean entropy 0.9705 | `python -c "import json;d=json.load(open('backend/tests/resolver_eval_results.json'));e=[r['entropy'] for r in d['results']];print(d['accuracy_pct'],sum(e)/len(e))"` |
| 12 skills / 9 conditions in brain | `python -c "import json;d=json.load(open('backend/tests/last_compiled_brain.json'));print(len(d['skills']),sum(len(s.get('conditions') or []) for s in d['skills']))"` |
| Contradiction note in brain | `grep -in "contradiction" backend/tests/last_compiled_brain.json` |
| resolver_only_eval still import-broken | `grep -n "_compute_hybrid_score\|RETRIEVAL_WEIGHTS" backend/tests/resolver_only_eval.py backend/runtime/brain_agent.py` |
| `--stability` kwarg mismatch | `grep -n "company_id=COMPANY_ID" backend/tests/eval_harness.py; grep -n "def handle_agent_query" backend/runtime/brain_agent.py` |
| ADV-count bug | `grep -n "startswith(\"ADV-\")" backend/tests/eval_harness.py` |
| 60-day SOP rule / 30-day Slack claim | `grep -n "60 days" data/sources/rivanly-inc/notion_refund_sop.md; grep -n "30 day" data/sources/rivanly-inc/slack_export_support.json` |
