---
name: kernl-research-methodology
description: Load this when turning a kernl idea, threshold change, retrieval change, prompt change, graph feature, or architecture proposal into an accepted result; when designing an experiment, ablation, or adversarial test; or when deciding whether to promote, retire, or document a candidate. Provides the hypothesis-to-evidence discipline for a zero-context engineer: pre-registered numeric predictions, offline-first experiments, adversarial refutation, and the required promotion record.
---

# kernl Research Methodology

Use this skill to make a claim falsifiable before changing production behavior. A **result** is an explanation that predicts both the successes and failures in a named evaluation slice; it is not a plausible demo, a prettier trace, or one improved aggregate number.

Do not use this to repair a known regression or operate the service. Use `kernl-debugging-playbook` for symptoms, `kernl-eval-inversion-campaign` for the current 15% strict-accuracy campaign, `kernl-proof-and-analysis-toolkit` for the math and offline analyses, and `kernl-change-control` before any behavior-changing edit.

## Non-negotiable research loop

1. **Freeze the question.** Name the exact decision surface: compile extraction, skill retrieval, graph retrieval, deterministic resolver, LLM verbalizer, or guardrail. Do not call an end-to-end answer an explanation of a specific layer.
2. **Create a hypothesis card before executing.** Commit or attach it to the change review; do not tune against an unrecorded result.
3. **Use the cheapest discriminating test first.** Read committed artifacts and run pure-logic tests before calling the shared vLLM gateway or Supabase.
4. **Try to falsify the mechanism.** Assign at least one adversarial example that the mechanism says should not improve.
5. **Classify the outcome.** Adopt, iterate, or retire the hypothesis. Retired hypotheses belong in `kernl-failure-archaeology`.
6. **Route promotion through change control.** A passing experiment flag is never permission to silently change defaults.

## Hypothesis card

Use this template verbatim. A number is required in every prediction.

```markdown
## H-YYYY-MM-DD: <short mechanism claim>
Owner: <name>  |  Status: candidate
Decision surface: <one layer>
Baseline artifact and date: <path, timestamp>

Mechanism: <one causal sentence>
Predictions before running:
1. <named slice> moves from <baseline> to >=/<== <number>.
2. <negative/adversarial slice> remains <=/>= <number>.
3. <trace field> changes from <baseline range> to <predicted range>.

Intervention: <single code/config change; flag/default and rollback>
Controls: <unchanged model, brain version, scenario IDs, seed/repeats>
Falsifier: <observation that disproves this mechanism>
Evidence plan: <offline command, unit test, eval command, manual artifact paths>
Promotion gate: <strict/relaxed/rule-hit plus safety and review requirements>
```

Do not write “accuracy will improve.” For example, predict `COND` strict accuracy separately from the overall number. The committed baseline contains 40 scenarios, so a one-scenario improvement is 2.5 percentage points and must not be presented as a broad result.

## Evidence ladder

| Level | What it establishes | Kernl evidence |
|---|---|---|
| 0: static | The implementation exists; it proves no behavior. | `git diff`, schema and prompt inspection. |
| 1: pure logic | A deterministic rule works for named inputs. | `python -m unittest backend.tests.test_constraint_resolver` (no LLM). |
| 2: frozen artifact | The predicted failure exists in the committed brain/eval output. | `backend/tests/last_compiled_brain.json`, `eval_results_baseline.json`. |
| 3: controlled evaluation | The intervention changes the named outcome under fixed inputs. | `python -m backend.tests.eval_harness`. |
| 4: robustness | It survives boundaries, adversarial cases, and repeated runs. | `--ablation`, repaired stability runner, added adversarial scenarios. |
| 5: promotion | It meets change-control gates, is reversible, and has documented provenance. | review record plus baseline update decision. |

Never claim a product or research advance from levels 0–2. At current recorded performance, the full runtime baseline is 15.0% strict and 52.5% relaxed, while the resolver-only artifact reports 62.5% strict. Those are dated snapshots, not targets or current measurements; re-read the JSON before using them.

## Experiment design that can distinguish causes

### 1. Decompose before intervening

For every failed scenario, capture:

| Layer | Required observation | Likely next skill |
|---|---|---|
| Compiled brain | skill/rule, typed conditions, graph edge/effect, metadata | `kernl-diagnostics-and-tooling` |
| Retrieval | candidate IDs, component scores, score gap, matched conditions | `kernl-proof-and-analysis-toolkit` |
| Resolver | admissible actions, precedence trace, entropy, ambiguity decision | `kernl-eval-inversion-campaign` |
| Verbalizer/guardrail | resolver action, raw LLM `action_type`, guardrail firing | `kernl-eval-inversion-campaign` |

Do not repair label collapse by tuning retrieval weights, or infer a graph win when graph retrieval cannot traverse a `has_policy` edge.

### 2. Hold the comparison fair

Keep all of these fixed unless one is the stated intervention:

- The committed brain file or explicit `skills_files` version.
- Scenario IDs and expected actions from `backend/tests/eval_harness.py`.
- Retrieval weights and metadata thresholds.
- The gateway/model endpoint, source files, and prompt text.
- The acceptance checker: report strict, relaxed, and rule-hit separately.

If a compile is part of the experiment, record source hashes and the generated brain version. `write_brain` marks prior `skills_files` rows non-current before inserting the next one, so a compile is stateful and needs the live-Supabase gate in `kernl-change-control`.

### 3. Design negative tests

A positive test confirms compatibility; a negative test can distinguish mechanisms. Examples:

| Candidate mechanism | Positive prediction | Required negative/refutation test |
|---|---|---|
| Canonical-label prompt fixes verbalizer collapse | Strict labels improve while resolver action is unchanged. | The same prompt must not turn a resolver `deny` into `approve`. |
| Entropy gate over-flags close scores | False-ambiguous cases fall. | Legitimately vague `DET-*` cases must remain ambiguous. |
| More typed conditions improve applicability | Boundary `COND-*` cases improve. | Missing context must retain its documented neutral semantics unless explicitly changed. |
| Graph policy attachment helps | Graph-path cases acquire policies and correct effects. | No graph retrieval may select an unrelated entity/policy edge. |

## Worked example: the eval inversion

### Observation

The dated full-runtime artifact records 6/40 strict successes (15.0%), 21/40 relaxed successes (52.5%), and 17 `ambiguous` outputs. The resolver-only artifact records 25/40 strict successes (62.5%). That gap rejects the simple claim “the resolver alone explains full-runtime failure.”

### Candidate H-1: label fidelity

> When the resolver returns a canonical action, the LLM verbalizer emits a generic action label; `guardrail_check` only replaces mismatches with the resolver’s `action_type`, so the remaining mismatch may originate before or outside the expected response shape.

Pre-register: (a) capture raw LLM action and guardrail field for all 40 scenarios; (b) strict accuracy should converge toward resolver-only accuracy only on cases with a non-null resolver primary action; (c) genuinely ambiguous cases must remain ambiguous. If raw output already exactly matches the resolver but strict still fails, retire H-1 and inspect the harness mapping/response serialization instead.

### Candidate H-2: entropy gate

> Near-equal confidence candidates make normalized Shannon entropy high; the gate calls a case ambiguous even when one policy should win by an explicit rule.

Pre-register the exact false-ambiguity scenario IDs and their pre-change entropy/score gaps. Change one gate parameter under an experiment flag only. A valid result lowers false ambiguity *without* converting vague `DET-*` cases to automatic actions and without lowering rule-hit rate. A gain only on aggregate relaxed accuracy is insufficient.

## From experiment flag to product behavior

1. Add the candidate setting as explicitly experimental; do not overwrite a metadata default to make a result look better.
2. Add or repair the smallest pure test that fails before the change.
3. Run offline artifact analysis and unit tests.
4. Run the controlled eval only after the shared-gateway etiquette is satisfied.
5. Record per-family strict, relaxed, rule-hit, ambiguity count, and any error count. Do not hide categories with zero observations.
6. Ask an adversarial reviewer to attempt a counterexample from the Rivanly contradiction and boundary inventory.
7. Promote only if `kernl-change-control` gates pass. Document the final mechanism, exact config, artifacts, and rollback in the change review.
8. If the hypothesis fails, add a short symptom → evidence → rejected mechanism entry to `kernl-failure-archaeology`; retain the artifact rather than deleting it.

## Stop conditions

Stop and report “inconclusive” when the source brain changed, the gateway/model changed, a baseline was overwritten, the evaluator threw errors, or the test has fewer examples than the predicted effect can resolve. Do not repair the experiment while reading its results; create H-2 for the next intervention.

## Provenance and maintenance

Facts in this skill were verified against the repository on 2026-07-10. Re-verify volatile facts before use:

| Fact | Command |
|---|---|
| Current baseline metrics and timestamp | `python -c "import json; x=json.load(open('backend/tests/eval_results_baseline.json')); print(x.get('run_timestamp'), x.get('strict_accuracy_pct'), x.get('relaxed_accuracy_pct'), x.get('total_scenarios'))"` |
| Resolver-only baseline | `python -c "import json; x=json.load(open('backend/tests/resolver_eval_results.json')); print(x.get('timestamp'), x.get('accuracy_pct'), x.get('total_scenarios'))"` |
| Scenario inventory and checkers | `grep -n "SCENARIOS\|check_action_strict\|check_action_relaxed" backend/tests/eval_harness.py` |
| Current brain version/write behavior | `grep -n "version_str\|is_current\|metadata_json" backend/engine/nodes/write_brain.py backend/schema.sql` |
| Guardrail and resolver response wiring | `grep -n "guardrail_check\|constraint_result\|def handle_agent_query" backend/runtime/brain_agent.py backend/runtime/guardrails.py` |
