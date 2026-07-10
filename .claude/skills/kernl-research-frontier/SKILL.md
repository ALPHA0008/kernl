---
name: kernl-research-frontier
description: Load this when deciding how kernl can advance beyond its current compiler-plus-resolver prototype: proposing a research direction, evaluating whether to keep the current stack or replace a component, planning a roadmap experiment, or making a state-of-the-art claim. Provides repo-grounded, falsifiable frontier bets with the current limitation, kernl-specific asset, first three local steps, evidence milestone, and explicit stop condition.
---

# kernl Research Frontier

Use this skill to choose experiments that could make kernl materially better at compiling operational knowledge into trustworthy actions. Treat every item below as an **open research bet**, not a capability claim. The repository proves only the dated artifacts and implementation details it contains.

Do not use this skill to fix the current eval regression. Use `kernl-eval-inversion-campaign`. Do not use it to choose a threshold or interpret a trace; use `kernl-proof-and-analysis-toolkit` and `kernl-diagnostics-and-tooling`. Route every experiment through `kernl-research-methodology` and `kernl-change-control`.

## What “beyond state of the art” means here

The intended frontier is staged, not a single benchmark score:

1. **Reliability:** deterministic policy decisions must outperform free-form LLM decisions under conflicting, incomplete, and boundary-sensitive company knowledge.
2. **Enterprise scale:** compilation must preserve source/version/evidence lineage as documents, companies, and policy changes grow.
3. **Complexity:** query-time reasoning must resolve conditions, exceptions, authority, temporal validity, and contradictions without making policy decisions opaque.
4. **Adoption:** results must be reproducible from source hash → compiled brain → trace → evaluated decision.

Do not compare to external systems without a controlled, cited study. The local `graphiti.md` is copied third-party reference material, not evidence that Kernl uses Graphiti or has temporal-graph capabilities.

## Decision table

| Frontier bet | Current repo limitation | Kernl-specific asset | First measurable milestone |
|---|---|---|---|
| A. Faithful deterministic action interface | Runtime strict accuracy is 15.0% in the committed baseline while resolver-only is 62.5%; action labels and ambiguity dominate. | A resolver, guardrail, 40-scenario harness, and canonical actions already exist. | Full runtime meets the pre-registered resolver-parity slice without creating new false auto-actions. |
| B. Typed, precedence-aware compilation | The committed brain has 7/12 skills with no typed conditions; graph policies are constructed with `effect: approve` and empty conditions. | Extraction, metadata discovery, resolver condition evaluation, and source evidence are already separate layers. | Every certified scenario’s decisive policy has a typed condition/effect/authority representation that passes coverage audit. |
| C. Provenance-preserving contradiction and time model | Rivanly contains Slack-vs-SOP conflicts, but the operational graph has no validity windows and cannot represent policy supersession over time. | Evidence links, source hashes, versioned skills files, and contradiction extraction node exist. | A conflict query returns the selected source, precedence reason, validity interval, and an explicit unresolved state when evidence is insufficient. |
| D. Retrieval calibrated to abstain for the right reason | Graph retrieval needs `has_policy` edges; committed graph has none. Skill retrieval’s confidence and entropy do not yet establish calibrated decision risk. | Retrieval trace components, metadata thresholds, resolver entropy, and frozen eval artifacts. | Risk/coverage curve shows automatic actions meet a pre-declared precision bar and abstentions are explainable. |
| E. Enterprise-scale incremental recompilation | Compile writes a whole current brain; source hashes exist but no verified selective recompilation or change-impact graph is implemented. | Source-file hashes, versions, chunks, entities, and graph structure are persisted or emitted. | Changing one source recompiles only the affected policy neighborhood and produces a reviewable semantic diff. |

## Bet A — Faithful deterministic action interface

**Why current approaches fail here.** Free-form generation naturally prefers readable verbs such as “schedule” or “refund,” while `eval_harness.py` evaluates canonical action labels exactly. An LLM that explains a decision but changes its action label damages deterministic evaluation; an over-eager ambiguity gate can hide a valid resolver result.

**Kernl asset.** `constraint_resolver.py` and `guardrails.py` encode a deliberate separation: deterministic resolver decides; LLM verbalizes. `brain_agent.py` already attaches `constraint_result` and applies a guardrail.

**First three steps in this repository.**

1. Use `kernl-diagnostics-and-tooling/scripts/eval_failures.py` against the committed baseline to freeze the label-collapse, false-ambiguity, and wrong-decision cohorts.
2. Add offline assertions that a non-null resolver `primary_action.action_type` reaches the API response unchanged, including canonical labels for every `CANONICAL_ACTIONS` member.
3. Implement exactly one experimental interface change (for example, structured resolver output passed separately from prose), then run unit tests and the controlled eval.

**You have a result when…** A named cohort’s strict score reaches its pre-registered target, guardrail behavior is observable in the eval record, and vague `DET-*` scenarios remain ambiguous. A higher relaxed score alone is not a result.

**Wrong path fence.** Do not tune retrieval weights to cure a response-serialization or label-interface defect.

## Bet B — Typed, precedence-aware compilation

**Why current approaches fail here.** Semantic retrieval can find a relevant paragraph but cannot by itself prove that `days_since_purchase == 14`, a customer tier, an authority limit, and an exception are all applicable. The current graph builder reduces decisions to empty conditions and an `approve` effect, losing the information the resolver needs.

**Kernl asset.** The code has typed operator validation, deterministic condition evaluation, authority/precedence scoring, and extraction nodes. The Rivanly corpus supplies numeric boundaries, conflicts, escalation paths, and exceptions.

**First three steps in this repository.**

1. Run the brain audit against `backend/tests/last_compiled_brain.json`; list every skill/policy lacking a decisive typed condition, effect, authority, or evidence link.
2. Define a source-grounded policy intermediate representation with `effect`, `conditions`, `authority`, `precedence_edges`, `evidence`, and an explicit `requires_review` state; add pure validators before connecting it to runtime.
3. Replace graph-policy construction only behind an experiment path, then prove boundary behavior with `COND-*` cases and conflicting-source examples.

**You have a result when…** A coverage table maps every certified decision to an executable policy representation, all conditions are validated, and resolver-only correctness improves or holds without a fallback to text-only policy selection.

**Wrong path fence.** Do not invent typed fields from model guesses; ungrounded extraction must be rejected or marked for human review.

## Bet C — Provenance-preserving contradiction and time model

**Why current approaches fail here.** Operational knowledge changes. A static rule store cannot answer whether the 60-day written refund cutoff, a “30 days max” Slack claim, and a loyalty override are concurrent, superseded, or an unresolved contradiction. Graphiti-style temporal concepts in the root reference do not exist in the Kernl graph.

**Kernl asset.** The pipeline has source files, chunks, evidence links, contradiction extraction, source hashes, and brain versions. Those form the minimum substrate for temporal/provenance research without committing to a graph database replacement.

**First three steps in this repository.**

1. Add a synthetic fixture with explicit effective dates, an update, and a contradiction; do not mutate `data/sources/rivanly-inc/`.
2. Extend the compiled representation with source identity, observed/valid interval where explicitly stated, and a relationship status (`active`, `superseded`, `conflicted`, `unknown`).
3. Add an offline query/replay test that produces a selected rule plus the evidence/precedence/time explanation, or explicitly returns unresolved.

**You have a result when…** The same query at two declared times produces different, evidence-cited decisions when source policy changed; an under-specified time returns an ambiguity/escalation rather than fabricated recency.

**Wrong path fence.** Do not adopt Neo4j, Graphiti, or a new database merely to claim a temporal graph. First establish the representation, query semantics, and benchmark on the existing JSON/DB contract.

## Bet D — Calibrated retrieval and abstention

**Why current approaches fail here.** A high normalized entropy can arise simply because candidate confidences are similar; it is not calibrated probability of policy uncertainty. Current graph confidence is partly structural, and no `has_policy` edges are present in the committed graph.

**Kernl asset.** `_trace` exposes semantic, metadata, keyword, severity, condition, and specificity components. The resolver exposes entropy and score gaps. The eval corpus includes adversarial, deterministic, and boundary scenarios.

**First three steps in this repository.**

1. Build an offline per-scenario dataset from `eval_results_baseline.json`: correctness, action/abstention, entropy, score gap, and trace components.
2. Pre-register an acceptance policy (for example, a precision floor at stated coverage) and evaluate threshold candidates by cohort, not a global accuracy average.
3. Add a calibration/coverage report to diagnostics before modifying ambiguity behavior; only then test one threshold policy under a feature flag.

**You have a result when…** The policy reports a reproducible risk–coverage curve, meets its declared automatic-action precision floor on held-out or adversarial scenarios, and every abstention includes a concrete missing/conflicting evidence reason.

**Wrong path fence.** Do not claim calibrated confidence from a confidence histogram or a single entropy threshold.

## Bet E — Incremental, reviewable enterprise compilation

**Why current approaches fail here.** A whole-brain recompile can be slow and makes it difficult to tell which operational decision changed. `source_hashes` and brain versions are saved, but current code does not establish impact-limited recomputation or semantic change approval.

**Kernl asset.** `write_brain.py` records source hashes, a timestamped version, skills, graph JSON, and metadata JSON. The API has a brain diff endpoint. This is sufficient to prototype an immutable compilation ledger.

**First three steps in this repository.**

1. Create a non-Rivanly synthetic company fixture with independent source files and record its initial compiled artifact.
2. Change one source and measure which chunks, rules, skills, graph entities/edges, and metadata fields differ; extend the diff to report semantic effect/condition/precedence changes rather than raw text only.
3. Implement invalidation as an offline plan first; prove the selectively recomputed artifact equals the full compile artifact before using it for a live company.

**You have a result when…** A one-file change has an audited dependency set, a reviewable semantic diff, and a selective compile that is byte/semantic-equivalent to the full compile under defined normalization.

**Wrong path fence.** Do not let incremental output replace a full compile until equivalence and rollback have been demonstrated.

## Choosing the next bet

Choose A first: the dated 15.0% strict runtime baseline invalidates broader reliability claims. Choose B next because execution fidelity depends on policy representation. Run C and E as fixture-first research tracks; they are foundational for enterprise scope but should not delay repairing the current decision path. Run D only after traces and graph attachment are trustworthy, otherwise it calibrates broken signals.

## Promotion and retirement

- For every candidate, use the hypothesis card in `kernl-research-methodology` before an LLM-backed run.
- Preserve source hashes, brain artifact/version, config, scenario IDs, and raw result JSON.
- Require the change gates in `kernl-change-control` before changing defaults or public claims.
- Add failed/rejected paths to `kernl-failure-archaeology`, including why the evidence falsified them.

## Provenance and maintenance

Facts in this skill were verified against the repository on 2026-07-10. Re-verify before planning work:

| Fact | Command |
|---|---|
| Dated full-runtime and resolver baselines | `python -c "import json; a=json.load(open('backend/tests/eval_results_baseline.json')); b=json.load(open('backend/tests/resolver_eval_results.json')); print(a.get('run_timestamp'), a.get('strict_accuracy_pct'), a.get('relaxed_accuracy_pct')); print(b.get('timestamp'), b.get('accuracy_pct'))"` |
| Graph-policy information loss | `sed -n '61,100p' backend/engine/nodes/build_operational_graph.py` |
| Graph traversal’s required edge | `sed -n '32,108p' backend/runtime/graph_retriever.py` |
| Provenance/version persistence | `sed -n '41,88p' backend/engine/nodes/write_brain.py` |
| Rivanly contradictions and architecture intent | `grep -n "30-day\|60-day\|validity\|temporal" data/sources/rivanly-inc/* docs/operational-graph-master-plan.md` |
| Diagnostics scripts and artifact scope | `Get-ChildItem .claude/skills/kernl-diagnostics-and-tooling/scripts; python .claude/skills/kernl-diagnostics-and-tooling/scripts/brain_audit.py backend/tests/last_compiled_brain.json` |
