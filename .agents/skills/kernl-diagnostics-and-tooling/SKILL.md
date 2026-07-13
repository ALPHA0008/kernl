---
name: kernl-diagnostics-and-tooling
description: Load this when you need to READ a kernl trace or eval artifact instead of guessing — interpreting retrieval_trace / constraint_result / _guardrail_fired fields, explaining why a scenario failed or came out "ambiguous", auditing a compiled brain before an eval run, or triaging eval_results_*.json. Provides field-by-field interpretation guides, healthy-vs-pathological trace examples, an interpretation-heuristics table, and three ready-to-run stdlib scripts (brain_audit.py, eval_failures.py, trace_summary.py) that work offline on the committed JSON artifacts.
---

# kernl Diagnostics and Tooling

**What this covers:** the project's measuring instruments — the retrieval trace, the constraint-resolver result, the guardrail flag, and the eval JSON artifacts — with field-by-field interpretation guides, plus three shipped scripts that turn those artifacts into answers without touching the LLM, the DB, or the network.

**When NOT to use this:**
- Actually *running* the eval or deciding what counts as evidence → `kernl-validation-and-qa` (the eval spends real GPU time on a shared live gateway — never run it casually).
- The campaign to fix what these instruments measure (strict 15% vs resolver 62.5%) → `kernl-eval-inversion-campaign`.
- Step-by-step bug hunting from a symptom → `kernl-debugging-playbook`. Historical root causes → `kernl-failure-archaeology`.
- What the numbers *should* be / statistical method → `kernl-proof-and-analysis-toolkit`. Changing thresholds/weights → `kernl-config-and-flags`, gated by `kernl-change-control`.
- How the pipeline is supposed to work → `kernl-architecture-contract`, `knowledge-compilation-reference`.

Jargon, defined once (all as of 2026-07-10):
- **Compiled brain** — the JSON a compile run produces: `{skills, graph_json, metadata_json, meta}`. Committed snapshot: `backend/tests/last_compiled_brain.json` (12 skills, company `rivanly-inc`).
- **Skill** — one compiled policy record (id, rule text, keywords, typed `conditions`, an `operational` metadata block, per-field confidences). Not to be confused with these onboarding skill files.
- **Hybrid retrieval** — query-time skill ranking: weighted sum of semantic (embedding cosine) + metadata + keyword + severity + condition scores plus a specificity bonus (`_hybrid`, backend/runtime/brain_agent.py:380).
- **Constraint resolver** — the deterministic decision layer that picks an action or declares "ambiguous" without an LLM (backend/runtime/constraint_resolver.py).
- **Entropy** — the resolver's ambiguity measure: Shannon entropy of the candidate-action confidence distribution, normalized to 0..1 by log2(n) (`compute_entropy`, backend/runtime/constraint_resolver.py:102-112). 0 = one clear winner, 1 = perfectly bunched. Empty or all-zero candidate lists return 1.0.
- **Guardrail** — pure-logic post-check that forces the LLM's `action_type` to match the resolver's decision (backend/runtime/guardrails.py:14-52).
- **Eval harness** — the 40-scenario offline benchmark (`backend/tests/eval_harness.py`); its artifacts are the JSON files this skill teaches you to read.

---

## 1. Where the measurements live

| Instrument | Produced by | Where you see it |
|---|---|---|
| `retrieval_trace` (full, with `components` + `matched_conditions`) | `_trace`, backend/runtime/brain_agent.py:423-483; attached at :790 | Live API response of `POST /agent/handle` / `POST /agent/query` (backend/api.py:251,259) — live-gateway calls, see `kernl-run-and-operate` before touching |
| `retrieval_trace` (flattened) | eval harness copies a subset (backend/tests/eval_harness.py:710-722) | Per-scenario records in `backend/tests/eval_results_baseline.json` and `eval_results_partial.json` |
| `constraint_result` | `ConstraintResult.to_dict`, backend/runtime/constraint_resolver.py:85-99; attached at brain_agent.py:808 | Live API response only — the eval harness does NOT save it |
| `_guardrail_fired` / `_guardrail_reason` | `guardrail_check`, backend/runtime/guardrails.py:14; applied at brain_agent.py:787 | Live API response only — not persisted in eval JSON |
| Eval summary + per-scenario records | `run_eval`, backend/tests/eval_harness.py:601-886 | `eval_results_baseline.json` (summary + results), `eval_results_partial.json` (written after *each* scenario, eval_harness.py:727-735 — your live progress bar during a run) |

Key consequence: **the committed eval artifacts carry the flattened retrieval trace only.** Anything about entropy, guardrails, or per-action condition traces requires a live query. The scripts below work entirely on what IS committed.

---

## 2. Reading `retrieval_trace`

Two shapes exist. Runtime shape (brain_agent.py:444-482):

| Field | Meaning | Healthy | Pathological |
|---|---|---|---|
| `top_skill` | id of the winning skill | matches the policy domain of the query | a neighboring domain's skill (e.g. `discount_authority_matrix` on a refund query) |
| `final_score` | hybrid score = semantic×0.45 + operational components + specificity bonus (weights from `metadata_json.retrieval_weights`) | > ~0.5 | < 0.3 means nothing matched well; baseline average is 0.3316 |
| `components.semantic_confidence` | raw embedding cosine similarity | > 0.6 | < 0.4 = the query text barely resembles the skill text |
| `components.operational_confidence` | normalized metadata+keyword+severity+condition score (brain_agent.py:408) — "did the *structured* signals agree" | > 0.5 | ~0.25 with high semantic = retrieval is running on vibes (embeddings) alone; baseline average is 0.2204 |
| `components.metadata_score` / `keyword_score` / `severity_score` / `condition_score` | the individual operational signals (scorers at brain_agent.py:286,305,318,332) | several non-zero | all 0.0 = no structured signal fired at all |
| `matched_conditions` | list of per-condition eval strings from `_score_cond` | non-empty on condition-bearing queries | empty on a COND-* style query = context keys didn't reach the conditions |
| `why_matched` | human-readable reasons | names a department/keyword/condition match | only "Specificity level 2 preferred" — see heuristics table: with all 12 skills at level 2 this phrase is a no-op |
| `runner_up` | second-ranked skill id | different domain | same domain sibling with tiny gap |
| `why_runner_up_lost.semantic_gap` | top embedding_sim − runner-up embedding_sim | > 0.15 | < 0.05 = semantically indistinguishable |
| `why_runner_up_lost.final_score_gap` | top final − runner-up final | > 0.1 | < 0.05 = ranking is a coin flip; retrieval "won" by noise |
| `why_runner_up_lost.condition_gap` | boolean: top had higher condition_score | True on condition queries | False everywhere = conditions never discriminate |
| `why_runner_up_lost.missing_metadata_match` / `severity_mismatch` / `lower_specificity` | boolean flags for why the runner-up scored lower (brain_agent.py:464-475) | at least one True | all False + tiny gaps = the two skills genuinely tied |
| `why_runner_up_lost.runner_up_scores` | runner-up's semantic/operational/keyword/condition scores | — | use to see *how close* the loser really was |

Eval-artifact shape (flattened, eval_harness.py:710-722): only `top_skill`, `final_score`, `semantic_confidence`, `operational_confidence`, `why_matched`, `runner_up`, `why_runner_up_lost`. No `components`, no `matched_conditions`.

### Real examples from `backend/tests/eval_results_partial.json` (run of 2026-06-16)

**Pathological — REF-01** (expected `approve`, got `ambiguous`; relaxed-pass, strict-fail):

```json
"retrieval_trace": {
  "top_skill": "refund_policy_matrix",
  "final_score": 0.2993,
  "semantic_confidence": 0.4474,
  "operational_confidence": 0.1636,
  "why_matched": "Specificity level 2 preferred. Matched 1/2 explicit conditions",
  "runner_up": "discount_authority_matrix",
  "why_runner_up_lost": { "semantic_gap": 0.2597, "final_score_gap": 0.0668,
    "condition_gap": true, "runner_up_scores": { "condition_score": 0.0, ... } }
}
```

Diagnosis: the RIGHT skill won (`refund_policy_matrix` on a refund query) and even matched a condition — but `final_score` 0.30 and `operational_confidence` 0.16 are so weak that downstream, the resolver's candidate confidences bunched together and it declared ambiguous. Retrieval succeeded; **decision confidence collapsed**. This is the eval-inversion signature (see `kernl-eval-inversion-campaign`).

**Healthy-ish — DET-01** (expected `ambiguous`, got `ambiguous`; strict-pass): `semantic_confidence` 0.6661, `why_matched` starts with `"Department=matched (engineering)"`, `semantic_gap` 0.1683. A structured signal (department) fired and the semantic separation is real. Note: even here `final_score_gap` is only 0.0258 — a coin-flip ranking that happened to land right. For calibration: 14/40 records in this run have `final_score_gap` > 0.1 (max 0.3078, OPS-01), so gaps > 0.1 are attainable and are the healthy bar.

---

## 3. Reading `constraint_result`

Serialized by backend/runtime/constraint_resolver.py:85-99. Live API responses only (brain_agent.py:808).

| Field | Meaning | Interpretation |
|---|---|---|
| `resolution_source` | `"graph"` (policies came from the operational graph path, constraint_resolver.py:280) or `"skill"` (skill-retrieval fallback, :450/:519) | With the committed Rivanly brain this is effectively always `"skill"`: the graph path requires `has_policy` edges (backend/runtime/graph_retriever.py:47-54) and the committed brain has ZERO of them (run `brain_audit.py` to confirm) |
| `primary_action.source` | per-action provenance: `"graph"`, `"skill"`, or `"skill_fallback"` (heuristic candidate injected when retrieval was weak, constraint_resolver.py:467) | `skill_fallback` winning = the answer came from hardcoded severity/pattern heuristics (`_heuristic_cands`, brain_agent.py:486), not from compiled knowledge |
| `entropy` | normalized 0..1 (see jargon) | compare against `ambiguity_entropy` threshold 0.75 (constraint_resolver.py:26-31; overridable via `metadata_json.thresholds`) |
| `is_ambiguous` | graph path: `entropy > 0.75` (:262). Skill path: `(entropy > 0.75 AND relative score_diff < 0.10) OR deterministic ambiguity signals` — "or"-phrasing, vague wording etc. with score_diff < 0.50 (`_detect_ambiguity_signals` :367, combined :490-495) | If True, `primary_action` is `null` and the guardrail will force `action_type: "ambiguous"` |
| `escalation_required` / `escalation_target` | any admissible action needs approval per `authority_rules`; target = highest-authority role whose `can_approve` list contains the action (:504-510, `_find_escalation_target` :183-191) | Roles missing from the authority-levels map silently fall back to level 1 — audit naming with `brain_audit.py` |
| `reasoning_steps` | ordered strings: candidate scoring, entropy, score_diff, det_signals | The single best "why" record; the last line of the skill path shows `entropy=… score_diff=… ambiguous=… det_signals=[…]` |
| `primary_action.condition_trace` | per-condition strings like `"days_since_purchase <= 14 (matched ctx=9)"` or `"…: not in context (neutral)"` (`_compute_condition_adjustment` :285-364) | "not in context (neutral)" everywhere = your context dict keys don't match condition field names |
| `primary_action.precedence_trace` | why this action outranked others (authority/override/specificity bonuses, backend/runtime/precedence.py:71-114) — truncated to 3 entries in `to_dict` | Empty on the skill path unless authority rules fired |
| `all_admissible_actions` | every candidate with confidence | Bunched confidences here ARE the entropy; read this before blaming the threshold |

Missing-context semantics you must know: in BOTH condition evaluators, a condition whose field is absent from the context counts as neutral/pass — `evaluate_condition` returns True (backend/runtime/condition_eval.py:24-26); `_compute_condition_adjustment` skips it. So "all conditions met" can mean "no conditions were actually checked".

---

## 4. `_guardrail_fired` semantics

`guardrail_check` (backend/runtime/guardrails.py:14-52) always sets `_guardrail_fired` (bool) and `_guardrail_reason` (string|null) on the response. Reason taxonomy — the exact strings:

| Trigger | Reason string (prefix) | What it measures |
|---|---|---|
| Resolver had no primary action | `"Resolver was ambiguous; action_type set to 'ambiguous'"` (guardrails.py:26-29) | Forced ambiguity — count these to measure resolver indecision reaching users |
| LLM returned empty `action_type` | `"LLM returned empty action_type. Overridden to resolver's decision: '…'"` (:38-41) | LLM/JSON-parse fragility |
| LLM action ≠ resolver action | `"LLM output '…' diverged from constraint resolver decision '…'. Overridden."` (:47-49) | **Verbalizer disagreement** — the LLM read the same evidence and decided differently |

Treat the guardrail as an instrument, not just a safety net: **its firing rate is the measured disagreement rate between the deterministic decider and the LLM verbalizer.** A rising divergence-override rate after a prompt or model change means the verbalizer prompt (brain_agent.py:748-765, which explicitly forbids overriding) has drifted. Caveat: the eval harness does not persist `_guardrail_fired`, so today you can only measure the rate on live responses — log it from `POST /agent/handle` output. Persisting it into eval records is an open improvement (route via `kernl-change-control`).

---

## 5. Eval artifacts as instruments

`backend/tests/eval_results_baseline.json` summary fields (built at eval_harness.py:865-885), with the certified 2026-06-16 baseline values:

| Field | Baseline | How it's computed / how to read it |
|---|---|---|
| `strict_accuracy_pct` | 15.0 | `action_type` exactly equals expected label (`check_action_strict` :509). THE determinism metric |
| `relaxed_accuracy_pct` | 52.5 | expected action appears in the raw text / alias table / candidate list (`check_action_relaxed` :521). Semantic understanding metric |
| `rule_hit_rate_pct` | 55.0 | expected fragment substring-matches `rule_applied` (:552). Retrieval-of-the-right-rule metric |
| `condition_accuracy_pct` | 0.0 | **structurally zero — do not read it.** Computed from `retrieval_trace.components.condition_score` (:768-790), but saved records have no `components` key (flattening at :710-722), so numerator and denominator are always 0 |
| `boundary_pass_rate_pct` | 62.5 | strict-or-relaxed pass rate over `COND-*` scenarios only (:760-766) |
| `avg_hybrid_score` | 0.3316 | mean top retrieval score — retrieval strength across the corpus |
| `avg_operational_confidence` | 0.2204 | mean structured-signal strength; the number to move if retrieval runs on embeddings alone |
| `scenario_counts` | det 6 / cond 8 / **adversarial 0** | prefix filters `DET-`/`COND-`/`ADV-` (:752-754). Adversarial reads 0 because the 5 adversarial IDs are `ENG-ADV-01`-style — `startswith("ADV-")` never matches. There ARE adversarial scenarios; the counter is wrong |
| `strict_passed` / `relaxed_passed` / `failed` | 6 / 21 / 19 | `failed` = total − relaxed_passed (relaxed failures, NOT strict) |

Per-scenario records (fields at eval_harness.py:692-724): `id`, `source`, `scenario` (truncated to 80 chars), `expected_action`, `actual_action`, `actual_action_type`, `strict_pass`, `relaxed_pass`, `expected_rule_fragment`, `actual_rule` (120 chars), `rule_pass`, `top_retrieval_score`, `confidence`, `skill_matched`, `reasoning_snippet` (200 chars), flattened `retrieval_trace`. Caveat: **`confidence` is 0 for all 40 records** — the harness reads `response.get("confidence", 0)` (:706) but the runtime never sets a top-level `confidence` key (it sets `action_confidence`, a dict). Ignore the field.

`eval_results_partial.json` is `{"completed": N, "total": N, "results": [...]}` — same records, rewritten after every scenario. Baseline-file governance (when it may be overwritten) lives in `kernl-validation-and-qa`.

---

## 6. Shipped scripts

All three live in `.Codex/skills/kernl-diagnostics-and-tooling/scripts/`, are stdlib-only (`json`, `argparse`, `collections`), need no LLM/DB/network, and accept both the baseline and partial JSON shapes. Run from the repo root; quote paths (the repo path contains a space). On Windows use `py` if `python` is not on PATH. Each was run against the committed artifacts on 2026-07-10; outputs below are real.

### 6a. `brain_audit.py` — compiled-brain quality gate

```
python ".Codex/skills/kernl-diagnostics-and-tooling/scripts/brain_audit.py" "backend/tests/last_compiled_brain.json"
```

Prints skill count, per-skill condition count / `conditions_confidence` / flags, low `metadata_confidence` fields, specificity distribution, graph stats (entities/edges/policies/authority rules, effect distribution, approve-with-no-conditions count), and authority naming inconsistencies. Run it on any freshly compiled brain BEFORE spending eval GPU time. Real output against the committed brain (abridged):

```
SKILLS: 12 total
  churn_risk_intervention                  0      0.2    0.8  conditions DROPPED at retrieval (cond_cf<0.60)
  ...
  refund_policy_matrix                     4      0.9    0.9
SPECIFICITY DISTRIBUTION: {2: 12}
GRAPH: 15 entities, 4 edges, 21 policies, 5 authority rules
  effect distribution: {'approve': 21}
  policies with effect=approve AND empty conditions: 21/21
WARNINGS (5):
  [WARN] 7/12 skills have ZERO typed conditions -- condition_score can never fire for them
  [WARN] all skills share ONE specificity_level -- ... meaningless discriminators
  [WARN] EVERY graph policy is effect=approve with no conditions -- the graph path can only ever answer 'approve' ...
  [WARN] only 0 has_policy edges for 21 policies -- unreachable policies can never be retrieved via the graph
  [WARN] authority_levels mixes naming schemes -- role_-prefixed duplicates: ['role_founder', 'role_ops_lead']
```

Every one of those warnings is a real, verified property of the committed brain (as of 2026-07-10) — the graph path is structurally dead (no `has_policy` edges) and graph effects are degenerate (all `approve`).

### 6b. `eval_failures.py` — failure triage by class

```
python ".Codex/skills/kernl-diagnostics-and-tooling/scripts/eval_failures.py" "backend/tests/eval_results_baseline.json"
```

Separates strict failures into: **label-collapse** (relaxed-pass strict-fail — the right decision was reachable, the canonical label wasn't), **over-ambiguity** (`action_type == "ambiguous"` with a definite expected action and no relaxed pass), **wrong-decision** (definite but wrong), **error**. Groups by scenario family. Baseline output (abridged):

```
scenarios=40  strict_pass=6 (15.0%)  relaxed_pass=21 (52.5%)
STRICT FAILURES: 34
  label-collapse : 20
  over-ambiguity : 1
  wrong-decision : 13
FAILURES BY FAMILY:
  REF 7/7   COND 7/8   ENG 4/4   ...   DET 1/6
LABEL-COLLAPSE (20):
  [REF-01] expected=approve      got_type=ambiguous    final_score=0.2993 entropy=n/a
  ...
```

Interpretation: 20 of 34 strict failures are label-collapse — most of the strict/relaxed gap is a labeling/normalization problem, not missing knowledge. That is the quantitative core of the eval-inversion story (campaign strategy: `kernl-eval-inversion-campaign`). `entropy=n/a` is expected on committed artifacts (Section 5 caveat); records from a future harness that saves `constraint_result` will show it automatically.

### 6c. `trace_summary.py` — one-scenario deep dive

```
python ".Codex/skills/kernl-diagnostics-and-tooling/scripts/trace_summary.py" "backend/tests/eval_results_partial.json" REF-01
python ".Codex/skills/kernl-diagnostics-and-tooling/scripts/trace_summary.py" "backend/tests/eval_results_baseline.json" --list
```

Pretty-prints every field of one record, nested traces included; handles both the flattened eval trace and the full runtime shape (`components`, `matched_conditions`, `constraint_result`) if you feed it a captured live response wrapped as `[{...}]` or `{"results":[...]}`. `--list` shows all ids with pass flags. Unknown id exits 1 with a hint.

---

## 7. Interpretation heuristics

| Observation | Most likely meaning | First check |
|---|---|---|
| `condition_score` 0.0 across all traces | Conditions were never evaluated at decision time | (1) context keys vs condition `field` names (case/underscore — `_score_cond` needs exact key presence, brain_agent.py:346); (2) condition coverage: `brain_audit.py` — 7/12 committed skills have zero conditions |
| `matched_conditions` empty but the skill HAS conditions | `conditions_confidence < 0.6` gate dropped them (`_get_trusted_op`, brain_agent.py:281-282) | `brain_audit.py` "DROPPED at retrieval" flags |
| Entropy > 0.9 across the board | Bunched candidate confidences, not genuine ambiguity — all candidates score alike because base confidences are `retrieval_score × action_confidence` of uniformly weak retrieval | `all_admissible_actions` confidences; `avg_hybrid_score` (baseline 0.3316) |
| `action_type: "ambiguous"` with a clearly single-policy query | Either bunched entropy (above) or a deterministic ambiguity signal misfire — the word "appropriate"/"or" in the query trips `_detect_ambiguity_signals` (constraint_resolver.py:367-420) | `reasoning_steps` last line: `det_signals=[...]` |
| `why_matched` says only "Specificity level 2 preferred" | No real structured signal fired; the phrase is decorative — all 12 skills are level 2 | `brain_audit.py` specificity distribution |
| `resolution_source` never `"graph"` | Graph path structurally dead: needs `has_policy` edges and `graph_confidence >= 0.5`; committed brain has 0 such edges | `brain_audit.py` graph warnings; backend/runtime/graph_retriever.py:47-54 |
| `operational_confidence` ~0.25 while `semantic_confidence` is decent | Retrieval is riding embeddings only; metadata/keyword/severity scores are ~0 | full-trace `components` on a live call; keyword lists in the brain |
| All condition traces read "not in context (neutral)" | The eval/context dict doesn't carry the fields the conditions test — and neutral counts as PASS (condition_eval.py:24-26), so policies "apply" vacuously | scenario `context` keys vs skill condition fields |
| `summary.condition_accuracy_pct == 0.0` | Not a model result — structural artifact of trace flattening (Section 5) | eval_harness.py:768-790 vs :710-722 |
| Per-record `confidence == 0` everywhere | Structural: harness reads a key the runtime never sets | eval_harness.py:706 |
| `_guardrail_fired` rate jumps after a prompt/model change | Verbalizer disagreement rising — the LLM is fighting the resolver | `_guardrail_reason` distribution on live responses (Section 4) |

---

## Provenance and maintenance

All facts, line numbers, and outputs verified directly against the repo on **2026-07-10** (brain compiled 2026-06-15, baseline eval run 2026-06-16). All three scripts were executed against the committed artifacts on that date; example outputs are unedited excerpts. Re-verify volatile facts before relying on them:

| Fact | Re-verify with (repo root; quote paths) |
|---|---|
| Trace builder `_trace` at brain_agent.py:423; `_hybrid` at :380 | `grep -n "def _trace\|def _hybrid" "backend/runtime/brain_agent.py"` |
| Response assembly: guardrail :787, retrieval_trace :790, constraint_result :808 | `grep -n "guardrail_check(result\|result\[\"retrieval_trace\"\]\|result\[\"constraint_result\"\]" "backend/runtime/brain_agent.py"` |
| Confidence gates `_get_trusted_op` (0.60 thresholds) at brain_agent.py:263 | `grep -n "def _get_trusted_op" "backend/runtime/brain_agent.py"` |
| DEFAULT_THRESHOLDS (ambiguity_entropy 0.75, score_diff 0.10, graph_fallback 0.5) | `grep -n -A5 "DEFAULT_THRESHOLDS" "backend/runtime/constraint_resolver.py"` |
| `compute_entropy` normalization at constraint_resolver.py:102 | `grep -n "def compute_entropy" "backend/runtime/constraint_resolver.py"` |
| Guardrail reason strings at guardrails.py:26-49 | `grep -n "guardrail_reason" "backend/runtime/guardrails.py"` |
| Graph needs `has_policy` edges (graph_retriever.py:47-54) | `grep -n "has_policy" "backend/runtime/graph_retriever.py"` |
| Neutral missing-context conditions (condition_eval.py:24-26) | `grep -n -A2 "ctx_val is None" "backend/runtime/condition_eval.py"` |
| Flattened trace + record fields (eval_harness.py:692-724), partial write (:727-735) | `grep -n "retrieval_trace\|eval_results_partial" "backend/tests/eval_harness.py"` |
| condition_accuracy structural zero (:768-790); scenario_counts prefixes (:752-754); confidence key (:706) | `grep -n "condition_score\|startswith(\"ADV-\")\|response.get(\"confidence\"" "backend/tests/eval_harness.py"` |
| Baseline numbers 15.0 / 52.5 / 55.0 / 0.0 / 62.5 / 0.3316 / 0.2204 | `python -c "import json;d=json.load(open('backend/tests/eval_results_baseline.json'));print({k:v for k,v in d.items() if k!='results'})"` |
| Brain shape: 12 skills, 15 entities, 4 edges, 21 policies, 0 has_policy edges | `python ".Codex/skills/kernl-diagnostics-and-tooling/scripts/brain_audit.py" "backend/tests/last_compiled_brain.json"` |
| Failure-class counts 20 / 1 / 13 | `python ".Codex/skills/kernl-diagnostics-and-tooling/scripts/eval_failures.py" "backend/tests/eval_results_baseline.json"` |
| Agent endpoints api.py:251/:259 | `grep -n "agent/handle\|agent/query" "backend/api.py"` |
