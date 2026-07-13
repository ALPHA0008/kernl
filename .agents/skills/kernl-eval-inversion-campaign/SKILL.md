---
name: kernl-eval-inversion-campaign
description: Load this when working on kernl's eval accuracy problem — runtime strict accuracy 15.0% vs resolver-only 62.5%, "false ambiguity", label collapse (schedule/refund/notify instead of canonical actions), missing skill conditions, or any task phrased as "improve the eval numbers", "fix strict accuracy", "why does the runtime answer ambiguous", or "close the resolver/runtime gap". Provides a decision-gated, phase-by-phase campaign: restore broken instrumentation, build a failure taxonomy, then apply ranked fixes (label fidelity, ambiguity gate, condition enforcement, graph effect bug, tier precedence) with offline verification obligations before any LLM run.
---

# kernl Eval Inversion Campaign

**What this covers:** the executable campaign to fix kernl's hardest live problem — the full runtime scores 15.0% strict accuracy while the deterministic resolver alone scored 62.5% on the same 40 scenarios. Numbered phases with gates: expected observation → what to do if you see something else. Includes the verified root-cause map and a ranked solution menu.

**When NOT to use this:**
- Whether a change may merge, and which gate it must pass → `kernl-change-control` (gating lives there; nothing here overrides it).
- How baselines are certified / pass-fail semantics → `kernl-validation-and-qa`.
- Trace-reading and diagnostic scripts → `kernl-diagnostics-and-tooling`. General bug hunting → `kernl-debugging-playbook`.
- Pipeline internals and the retrieval/entropy math derivations → `knowledge-compilation-reference`. Thresholds as config → `kernl-config-and-flags`.
- Starting the backend or compiling a brain → `kernl-run-and-operate` / `kernl-build-and-env`. Past incidents → `kernl-failure-archaeology`. Statistical analysis method → `kernl-proof-and-analysis-toolkit`.

Jargon, defined once (see `kernl-change-control` and `knowledge-compilation-reference` for depth):
- **Brain** — compiled policy JSON. Runtime fallback copy: `backend/tests/last_compiled_brain.json` (12 skills for demo company Rivanly Inc.).
- **Resolver** — `backend/runtime/constraint_resolver.py`, the deterministic (no-LLM) layer that picks one action from candidates.
- **Runtime / full eval** — `python -m backend.tests.eval_harness`: 40 scenarios through the whole stack (retrieval → resolver → LLM verbalizer → guardrail). ~40+ shared-gateway LLM calls per run.
- **Resolver-only eval** — `python -m backend.tests.resolver_only_eval`: same 40 scenarios, retrieval + resolver only, no gateway calls (embeddings are computed locally by a MiniLM model, `backend/core/llm.py:28-53`).
- **Strict / relaxed** — strict = `action_type` exactly equals the expected canonical label (`check_action_strict`, `backend/tests/eval_harness.py:509`); relaxed = semantic match via alias table (`:521`).
- **DET scenarios** — DET-01..06, the 6 scenarios whose *correct* answer is `ambiguous`.
- **False ambiguity** — a definite scenario (expected ≠ ambiguous) answered `ambiguous`.

---

## 0. The problem and the targets

Committed baselines (all committed in `2ca7f83`, as of 2026-07-10):

| Metric | Committed value | File |
|---|---|---|
| Runtime strict | **15.0%** (6/40) | `backend/tests/eval_results_baseline.json` (run 2026-06-16) |
| Runtime relaxed | 52.5% (21/40) | same |
| Resolver-only strict | **62.5%** (25/40) | `backend/tests/resolver_eval_results.json` (run 2026-06-15) |
| DET strict | 5/6 (DET-04 failed) | computed from baseline JSON |
| False ambiguity | 11/34 definite scenarios answered `ambiguous` | computed from baseline JSON |

The inversion: adding the LLM verbalizer + current compiled brain on top of the resolver *cut accuracy by 47.5 points*. Success criteria, in order — measured ONLY by the harness numbers, never judged by eye:

1. Runtime strict ≥ 62.5% (resolver parity), then ≥ 80%.
2. DET strict preserved ≥ 5/6 on every candidate change.
3. Relaxed accuracy never regresses below 52.5%.
4. False ambiguity 11/34 → ≤ 3/34.

---

## Phase 0 — Restore instrumentation (no LLM, no gateway)

Two harness entry points are broken (also catalogued in `kernl-change-control` §1). Fix them first; you cannot run the campaign blind.

### 0.1 Fix `resolver_only_eval.py` imports

`backend/tests/resolver_only_eval.py:20-26` imports four symbols that no longer exist in `backend/runtime/brain_agent.py`. Verified mapping (as of 2026-07-10):

| Old import | Current symbol | Current signature (brain_agent.py line) |
|---|---|---|
| `_load_skills_from_file` | `_load_file` | `_load_file()` → `(brain_dict, err)` — `:627` |
| `_compute_hybrid_score` | `_hybrid` | `_hybrid(sem, skill, qs, wts=None, meta=None)` — `:380` |
| `_build_admissible_actions` | `_admissible` | `_admissible(top_r, qs, meta=None)` — `:554` |
| `RETRIEVAL_WEIGHTS` (module constant, deleted) | `_wts(meta)` | `_wts(meta)` reads `meta["retrieval_weights"]` — `:68` |

The refactor also made everything metadata-driven. To replicate the runtime path you must load the brain's metadata and thread it through — otherwise `_admissible` falls back to the built-in `_MD` defaults (`brain_agent.py:8-38`) whose `action_types.values` is only `["approve","deny","escalate","monitor"]` and will filter out almost every skill candidate. Concretely, in `evaluate_scenario`:

```python
from backend.runtime.brain_agent import (
    _load_file, _load_metadata, _extract_query_signals, _hybrid, _admissible, _wts,
)
...
brain_data, err = _load_file()
meta = _load_metadata(brain_data)                      # brain_agent.py:41
query_signals = _extract_query_signals(scenario["scenario"], scenario.get("context"), meta)  # :193 takes meta now
w = _wts(meta)
...
final_score, components = _hybrid(sem_sim, skill, query_signals, w, meta)
...
admissible_actions, candidate_entropy = _admissible(top_results, query_signals, meta)
...
constraint_result = constraint_resolve(..., metadata=meta)   # resolve() accepts metadata= (constraint_resolver.py:524-532)
```

Everything else in the script (embedding cache path, scoring loop, strict check at `:169-172`, output to `backend/tests/resolver_eval_results.json` at `:228`) still matches the current code — the committed brain's 12 skills all carry a cached 384-dim `embedding_vector`, so no per-skill embedding calls happen.

### 0.2 Fix `--stability` kwargs

`run_stability_test` (`backend/tests/eval_harness.py:970-975`) calls `handle_agent_query(company_id=..., context=...)` but the signature is `handle_agent_query(cid, scenario, ctx=None, with_brain=True, rw=None)` (`backend/runtime/brain_agent.py:635`). Rename the kwargs: `company_id=` → `cid=`, `context=` → `ctx=`. Note the fixed `--stability` run makes 18 gateway LLM calls (3 runs × 6 DET scenarios).

### 0.3 Fix the ADV counter

`backend/tests/eval_harness.py:754`: `r["id"].startswith("ADV-")` never matches — the 5 adversarial IDs are `ENG-ADV-01`, `REF-ADV-01`, `HR-ADV-01`, `CS-ADV-01`, `PRICE-ADV-01`. Change to `"-ADV-" in r["id"]`. (The committed baseline shows `adversarial: 0` for exactly this reason.)

### GATE 0

Run (from repo root, path quoted because it contains a space):

```powershell
cd "D:\Abhijith P\Desktop\Project\kernl"
python -m backend.tests.resolver_only_eval
```

**Expected:** the script completes with no gateway calls, prints per-scenario results, and strict accuracy lands around **62.5% ± a few scenarios**, with canonical labels (`route_to_ops_lead`, `initiate_enterprise_onboarding`, …) appearing in the output.

**Branches — read carefully, one of these is likely (as of 2026-07-10):**

- **If the emitted labels are generic verbs** (`schedule`, `refund`, `page`, `notify`, `resolve`, `route`) **and strict is well below 62.5%:** your fix is probably NOT wrong. The committed brain (`last_compiled_brain.json`) carries only 13 generic action verbs in `metadata_json.action_types.values`, while the committed resolver results (generated 2026-06-15) show canonical composite labels — meaning the brain that produced 62.5% was recompiled away before commit `2ca7f83` bundled everything on 2026-06-17. This *is* the S1 mechanism showing itself (see Phase 2). Record your run's number as the new resolver-only reference, note the discrepancy in the PR, and continue — Phase 1 re-baselines anyway.
- **If labels are canonical but the score is far off 62.5% (say < 50% or > 75%):** the refactor changed scoring behavior. **STOP.** Do not touch anything else. The pre-refactor scorer was never committed (the `22ee2f0`-era `backend/agent/brain_agent.py` has no hybrid functions at all), so the only behavioral reference is the committed per-scenario records in `resolver_eval_results.json` — each row has `top_scores`, `entropy`, and `all_admissible` with confidences. Diff `_hybrid`'s component outputs against those recorded values scenario by scenario before proceeding.
- **If it crashes on torch/transformers import:** environment problem, not a campaign problem → `kernl-build-and-env`. First-ever run downloads the MiniLM model from Hugging Face.

Also run the free unit suite now to establish it passes before you change anything: `python backend/tests/test_constraint_resolver.py` — expect 26/26 (no LLM).

---

## Phase 1 — Failure taxonomy on fresh data

One full eval run = ~40+ calls to the shared vLLM gateway (client concurrency capped at `Semaphore(4)`, `backend/core/llm.py:16`). Schedule it, don't loop it — gateway etiquette rules are in `kernl-change-control` §2 rule 11.

```powershell
cd "D:\Abhijith P\Desktop\Project\kernl"
python -m backend.tests.eval_harness
```

Two harness quirks (details in `kernl-change-control` §1/§4): the run **overwrites** `backend/tests/eval_results_baseline.json` in place (`eval_harness.py:1003`) — take your delta with `git diff`, then `git restore` unless you are deliberately re-certifying; and the process exits 1 whenever relaxed < 90% (`eval_harness.py:1008-1010`), which at current numbers is always — read the printed numbers, not the exit code.

Split every strict failure into four buckets. `kernl-diagnostics-and-tooling` owns the tooling for this; if its scripts are unavailable, this self-contained snippet reproduces the split from the results JSON:

```python
import json
d = json.load(open("backend/tests/eval_results_baseline.json"))
GENERIC = {"approve","call","deny","escalate","monitor","notify","page",
           "refund","report","resolve","review","route","schedule"}  # committed brain's action_types.values
for r in d["results"]:
    if r["strict_pass"]: continue
    got, exp = r["actual_action_type"], r["expected_action"]
    if r["id"].startswith("DET-"):             bucket = "DET_REGRESSION"
    elif got == "ambiguous":                   bucket = "FALSE_AMBIGUITY"
    elif got in GENERIC and r["relaxed_pass"]: bucket = "LABEL_COLLAPSE"     # right decision, wrong label
    else:                                      bucket = "WRONG_DECISION"     # includes condition-dead cases
    print(f"{r['id']:14s} {bucket:16s} expected={exp:38s} got={got}")
```

(The `LABEL_COLLAPSE` heuristic — generic label + relaxed pass — is an approximation; eyeball each row against the scenario's rationale in `eval_harness.py:40-430` before trusting the count. "Condition-dead" = the right skill matched but its numeric threshold was missing or non-discriminating, so the wrong branch won.)

**Committed-baseline pattern** (recomputed from the committed JSON, 2026-07-10): 34 strict failures = **~9 label collapse + 11 false ambiguity + ~13 wrong decision (many condition-dead) + 1 DET regression (DET-04)**.

### GATE 1

**Expected:** your fresh run's taxonomy counts approximately match the committed pattern above. → Proceed to Phase 2 in the ranked order.
**If the mix shifted materially** (e.g., false ambiguity ballooned, or label collapse vanished): the brain or environment has drifted since the committed baseline. Re-baseline first — declare the fresh run the working reference in your notes (formal re-certification rules: `kernl-validation-and-qa`), rerun Phase 0's resolver-only eval for a matching resolver reference, and only then pick levers.

---

## Phase 2 — Solution menu, ranked

Each lever states: the verified mechanism, the fix, the **theory obligation** (what you must predict on paper BEFORE running anything), expected gain, and where to verify. Implementation order is in Phase 3.

### S1 — Label fidelity (biggest strict gain; pure compile/runtime, offline-verifiable)

**Mechanism (CONFIRMED against the committed brain):** the final `action_type` is the resolver's, verbatim. Path: resolver decides → LLM verbalizes → `guardrail_check` overrides any LLM divergence back to the resolver's label (`backend/runtime/guardrails.py:44-50`) → `_norm` passes unknown labels through unchanged (`backend/runtime/brain_agent.py:822-828` — it returns the cleaned string even when it is not in the action-type set). So if the resolver emits `schedule`, the run scores `schedule`.

The resolver's skill path takes each candidate's action from the compiled skill's `operational.action_type`, filtered by membership in the brain's `metadata_json.action_types.values` (`brain_agent.py:566-570`). In the committed brain those values are **13 generic verbs** (`approve, call, deny, escalate, monitor, notify, page, refund, report, resolve, review, route, schedule`) — none of the 11 composite labels in `CANONICAL_ACTIONS` (`eval_harness.py:437-453`) except the 4 simple ones. Sample: `pip_trigger_and_review` → `schedule` (expected `initiate_pip`), `refund_policy_matrix` → `refund` (not even canonical), `eng_offer_approval` → `approve` (expected `get_founder_approval` — note this one is a **semantic inversion**, not mere collapse: "approve" is the opposite of "stop and get founder approval").

**Compile-side root:** `_collect_action_types` (`backend/engine/nodes/discover_operational_metadata.py:345-412`) has the composite labels in its vocabulary (`:365-375`) but matches them by literal substring in rule text — `page_on_call` never literally appears in "page the on-call engineer", so only single verbs survive discovery. `synthesize_skills`' prompt then constrains `action_type` to exactly that discovered list ("MUST be one of: {action_list}", `backend/engine/nodes/synthesize_skills.py:175`), and `_validate_operational_metadata` nulls anything outside it (`:56`). The heuristic fallback candidates in the runtime (`brain_agent.py:502,517-524`) would emit `page_on_call` / `resolve_within_4_hours` only if those are in the action-type set — currently they aren't.

**Fix (two coordinated options — pick and justify):**
1. Compile-side (preferred): make action-type discovery synthesize composite labels (e.g., normalize the `action`/`action_type` fields extractors emit, and/or add composite patterns like "page the on-call" → `page_on_call`), so the synthesis prompt's allowed list contains the composite actions the documents actually describe. Requires one recompile (engine change class → `kernl-change-control`).
2. Runtime ontology mapping: populate `action_types.ontology` children/parents so a generic verb + skill context maps to the composite label at `_admissible`/`_norm` time. Currently every ontology entry has `parent: null, children: [], specificity: 2` — it discriminates nothing.

**Theory obligation:** before any run, write the per-scenario predicted label flips (e.g., "HR-02: `schedule` → `initiate_pip` because `pip_trigger_and_review.operational.action_type` becomes `initiate_pip`"). Check each predicted flip against the committed baseline rows — S1 only converts failures where the *decision* was already right (~9 scenarios). It does nothing for `eng_offer_approval`-style inversions unless the label change also flips the decision semantics.

**Verify:** resolver-only eval (free) — labels change there first; then full eval.

### S2 — Ambiguity gate (fixes the 11 false-ambiguity failures; fully offline-derivable)

**Mechanism:** the skill path declares ambiguity via `is_ambiguous = (entropy > ambiguity_entropy) and (score_diff < score_differential_threshold) or det_ambiguous` (`backend/runtime/constraint_resolver.py:493-495`; thresholds 0.75 / 0.10 from `DEFAULT_THRESHOLDS`, `:26-31`, overridable by brain metadata). `compute_entropy` (`:102-112`) normalizes Shannon entropy of the candidates' confidences by `log2(n)`. Candidate confidences are `retrieval_score × action_confidence × condition_multiplier` (`:456-461`), and retrieval scores bunch in a narrow band — the committed resolver run shows normalized entropy **between 0.88 and 0.99 on all 40 scenarios, passes and failures alike** — always above the 0.75 threshold. So the entropy term is always true, and the gate is effectively decided by `score_diff` (a *relative* margin, `(top − second)/top`, `:484-488`) plus `_detect_ambiguity_signals` (`:367-420`: "or"-choice, vague phrasing, the word "escalate", exact-percent boundary, multi-domain overlap; fires as ambiguous whenever signals exist and `score_diff < 0.50`, `:490-491`). Full derivation of why bunched scores push normalized entropy to 1 → `knowledge-compilation-reference`.

**Candidate fixes, ranked:**
1. Margin logic: evaluate absolute vs relative `score_diff`; a relative margin on scores ~0.35 makes 0.035 absolute separation "decisive" — decide which is defensible and measure.
2. Sharpen candidate scores before entropy (temperature exponent on confidences) so genuinely dominant candidates produce low entropy.
3. Entropy over DISTINCT actions only. `_admissible` already dedups by action name (`brain_agent.py:573-583`), so this mainly matters on the graph path where duplicate `approve` policies inflate the candidate list (see S4).
4. Audit `_detect_ambiguity_signals`: the bare keyword "escalate" fires on legitimate escalation queries (check PRICE-02 in the traces), and `det_ambiguous`'s 0.50 margin is very permissive.

**Theory obligation:** recompute entropy/margins offline from recorded traces — `resolver_eval_results.json` rows carry `all_admissible` with per-candidate confidences, and `eval_results_baseline.json` carries `constraint_entropy` in decision traces. Predict which of the 11 false-ambiguous scenarios flip under your proposed rule, and confirm the 6 DET scenarios do NOT flip, before any live run. Zero LLM calls needed for this analysis.

### S3 — Condition enforcement: 5/12 → 12/12 skills with typed conditions (compile-side; one recompile)

**Mechanism (CONFIRMED):** only 5 of the 12 compiled skills carry conditions (`enterprise_onboarding_requirements`, `p0_bug_enterprise_response`, `discount_authority_matrix`, `enterprise_custom_pricing_route`, `refund_policy_matrix`). The other 7 all have `conditions_confidence = 0.2` — and `_compute_conditions_confidence` (`backend/engine/nodes/synthesize_skills.py:133-145`) assigns 0.2 **only when the LLM DID emit conditions and every one was rejected by validation** (no-conditions-emitted scores 0.5). So this is validation rejection, not extraction miss. The rejector is the field whitelist at `synthesize_skills.py:94`: any condition whose `field` is not in `valid_sets.condition_fields` is dropped. The committed brain's whitelist has only 6 fields: `customer_tier, days_since_purchase, discount_percent, plan_type, refund_amount, tenure_months`. The whitelist itself comes from `_collect_condition_fields` + regex inference (`backend/engine/nodes/discover_operational_metadata.py:284-334`), whose patterns miss the other fields (e.g., `(\d+)\s*churn` does not match "3 or more churn signals"; `priority\s*p[012]` does not match "P1 bugs").

Even if conditions survived, they'd be trust-gated: the runtime drops a skill's conditions when `conditions_confidence < 0.60` (`brain_agent.py:281-283`), and `_score_cond` then returns 0.0 "no conditions in skill" (`:332-338`), so the `condition` retrieval weight (0.10) and the resolver's condition multiplier (`constraint_resolver.py:285-364`, neutral 1.0 when nothing evaluates) discriminate nothing for those 7 skills.

**The exact missing conditions, from ground truth** (never edit these files — `kernl-change-control` rule 10):

| Skill (committed brain) | Missing condition(s) | Ground truth |
|---|---|---|
| `churn_risk_intervention` | `churn_signals_count >= 3` (in 30 days) | `data/sources/rivanly-inc/notion_cs_playbook.md:7` |
| `p1_bug_resolution_sla` | `priority == "P1"` (resolve within 4h) | `notion_eng_runbook.md:9` |
| `sla_breach_notification` | `sla_breach_hours >= 2` + `customer_tier == "enterprise"` | `notion_eng_runbook.md:14` (standard 1h rule: `:13`) |
| `outage_response_protocol` | `active_outage == true` | `notion_eng_runbook.md:17` |
| `eng_offer_approval` | `role == "engineering"` + `stage == "offer"` | `notion_hr_playbook.md:13` |
| `pip_trigger_and_review` | `missed_kpi_quarters >= 2` | `notion_hr_playbook.md:16` |
| `vendor_invoice_approval` | `invoice_amount >= 3500` + `vendor_type == "software"` | `slack_export_ops.json:11` |

**Fix:** widen condition-field discovery (better patterns, and/or harvest field names from the conditions the extractors already emit at `discover_operational_metadata.py:286-291`), or make the whitelist advisory instead of fatal for high-confidence LLM conditions — then recompile and confirm each skill's conditions and `conditions_confidence ≥ 0.6` with `python backend/show_brain.py`. Also align: the eval contexts use exactly the field names above (`eval_harness.py` SCENARIOS), so compiled condition fields must match them verbatim, or `_score_cond`/`_compute_condition_adjustment` will treat them as "not in context" (neutral, `constraint_resolver.py:311-313`).

**Theory obligation:** the table above, plus per-scenario predictions for the condition-dead failures (CS-03, CS-ADV-01, HR-01/HR-02, OPS-01, ENG-04, ENG-02 at minimum).

### S4 — Graph effect fix (cheap safety fix; do FIRST)

**Mechanism (CONFIRMED):** `build_operational_graph` hardcodes every graph policy to `"effect": "approve"`, `"priority": 0`, `"conditions": []` (`backend/engine/nodes/build_operational_graph.py:69-71`). The graph retriever grants `graph_confidence = 0.5 + 0.1 × n_resolved` (`backend/runtime/graph_retriever.py:100`), so a single matched policy scores 0.6 ≥ `graph_fallback_threshold` 0.5 and the resolver takes the graph path (`constraint_resolver.py:543-561`) — which can then only ever answer `approve`. Current exposure is limited only by luck: the committed brain has just 4 edges and the path needs `relation_type == "has_policy"` edges (`graph_retriever.py:47-54`). Check `resolution_source` in your Phase 1 traces to see whether it ever fires.

**Fix, either/both:** (a) derive `effect` from the decision text (deny/escalate/route/notify verbs) at graph build time; (b) gate the graph path OFF by raising `graph_fallback_threshold` to 1.0 until policies carry real effects — a threshold change, so it needs ablation-style evidence per `kernl-change-control` §4.4. **NEVER ship the graph path while all effects are `approve`** — every graph-routed query becomes an approve, which makes strict accuracy *worse* and is an actively dangerous default for a policy engine.

### S5 — Enterprise/tier override + catch-all skills (last; depends on S3)

**Mechanism:** in the committed resolver-only run, `route_to_ops_lead` (vendor-invoice/pricing routing skills) won unrelated queries — REF-03, REF-04, REF-ADV-01, PRICE-ADV-01 all resolved to it — and the enterprise-refund rule (any enterprise refund → escalate to AM, `notion_refund_sop.md:11`) lost to the generic refund matrix on REF-03/REF-ADV-01. These are precedence failures: nothing encodes "enterprise overrides standard". **Fix:** add `customer_tier == "enterprise"` conditions to the escalation skills (needs S3's recompile) — condition count feeds precedence directly (`backend/runtime/precedence.py:95-98` gives +0.3 per condition) — and/or emit real precedence edges (`detect_structural_precedence`, `precedence.py:57-68`). Do this after S3; without typed conditions there is nothing for precedence to grip.

**Rank recap: S4 immediately (safety), then S1 + S2 (pure runtime/compile-label work, offline-verifiable, biggest strict gain), then S3 (one recompile), then S5.**

---

## Phase 3 — Implement, one lever at a time

For EACH lever, in this exact loop:

1. **Write the prediction first**: expected strict/relaxed/false-ambiguity/DET numbers, per-scenario flips, on paper (PR draft or notes). This is the theory obligation from Phase 2 — no prediction, no run.
2. `python backend/tests/test_constraint_resolver.py` → 26/26 (free, seconds).
3. `python -m backend.tests.resolver_only_eval` (free, no gateway) → compare against your prediction.
4. Only if 2–3 match prediction: full eval `python -m backend.tests.eval_harness` (~40 gateway calls — schedule it). Restore baseline JSONs after reading numbers unless re-certifying.
5. **Gate after each lever:**
   - DET strict < 5/6 → **revert that lever**, no exceptions. Diagnose offline before retrying.
   - Relaxed < 52.5% → revert or explain the exact scenarios lost, per family.
   - Numbers moved but not as predicted → your theory is wrong; stop stacking levers on a wrong theory. Back to Phase 2 for that lever.
6. Commit the lever separately with its before/after numbers. Never bundle two levers in one measurement — you lose attribution.

---

## Phase 4 — Promotion

Route the finished change set through `kernl-change-control` (its rules win over anything here):

- PR reports the full table: old/new strict, relaxed, rule-hit, per-source family breakdown (the harness prints it), false-ambiguity count, DET count.
- Any threshold/weight change (e.g., S4's `graph_fallback_threshold`, S2's margin) cites ablation or A/B evidence (`python -m backend.tests.eval_harness --ablation` = 5 configs × 40 scenarios ≈ 200 gateway calls — schedule off-peak).
- Golden baseline updates (`eval_results_baseline.json`, `resolver_eval_results.json`) are explicit, called-out re-certifications with provenance (run date, commit, brain identity) — protocol in `kernl-validation-and-qa`.
- If you recompiled (S1/S3/S5): brain audit via `python backend/show_brain.py` summarized in the PR (12 skills expected, conditions coverage, confidences).

---

## Wrong paths — fenced off

| Do NOT | Why |
|---|---|
| Loosen `check_action_strict` or add entries to `ACTION_ALIASES` to make numbers pass | Metric gaming. Strict exists to measure determinism; softening the ruler measures nothing. Fix the labels the system emits, not the checker. |
| Blindly raise `ambiguity_entropy` (0.75) without the S2 margin analysis | Entropy is ≥ 0.88 on *every* scenario in the committed resolver run; raising the threshold flips false-ambiguity failures into wrong-decision failures and breaks the 5 passing DET scenarios. |
| Edit `data/sources/rivanly-inc/` to match system output | The 8 files are calibrated ground truth; editing them silently re-calibrates every number ever measured (`kernl-change-control` rule 10). |
| Make the verbalizer freeform / weaken `guardrail_check` | The resolver-decides–LLM-explains guardrail architecture is the product thesis (`guardrails.py:1-9`). The guardrail is not the bug — the labels fed into it are. |
| Chase graph coverage (more edges/entities) before S4 | An all-`approve` graph path makes accuracy WORSE with every additional match. Fix or gate the effect first. |
| Judge any fix by eye / single-scenario spot check | Success is the harness numbers, full stop. |

---

## Provenance and maintenance

All facts verified directly against the repo on **2026-07-10** (HEAD `d215501`). Baseline JSONs and brain are as committed in `2ca7f83`. Re-verify volatile facts (repo root, quote the path):

| Fact | Re-verify with |
|---|---|
| Baselines 15.0 / 52.5 / 62.5 | `grep -E "strict_accuracy_pct|relaxed_accuracy_pct" backend/tests/eval_results_baseline.json; grep accuracy_pct backend/tests/resolver_eval_results.json` |
| Broken imports still broken | `grep -n "RETRIEVAL_WEIGHTS\|_load_skills_from_file" backend/runtime/brain_agent.py` (no hits = mapping still needed) |
| Current symbol names/lines | `grep -n "def _load_file\|def _hybrid\|def _admissible\|def _wts\|def _load_metadata\|def _norm\|def handle_agent_query" backend/runtime/brain_agent.py` |
| `--stability` kwarg bug | `grep -n "company_id=" backend/tests/eval_harness.py` |
| ADV counter bug | `grep -n 'startswith("ADV-")' backend/tests/eval_harness.py` |
| 40 scenarios / 6 DET / 8 COND / 5 ADV | `grep -c "\"id\":" backend/tests/eval_harness.py` (counts scenario ids +1 result key); inspect SCENARIOS `backend/tests/eval_harness.py:40-430` |
| 15 canonical actions | `grep -n -A16 "CANONICAL_ACTIONS" backend/tests/eval_harness.py` |
| Brain: 13 generic action types, 12 skills, 5 with conditions | `python -c "import json;b=json.load(open('backend/tests/last_compiled_brain.json'));print(b['metadata_json']['action_types']['values']);print(len(b['skills']));print(sum(1 for s in b['skills'] if s.get('conditions')))"` |
| Condition-field whitelist (6 fields) | `python -c "import json;print(json.load(open('backend/tests/last_compiled_brain.json'))['metadata_json']['valid_sets']['condition_fields'])"` |
| `conditions_confidence` 0.2-means-all-rejected | `grep -n -A12 "_compute_conditions_confidence" backend/engine/nodes/synthesize_skills.py` |
| Whitelist rejection line | `grep -n "field not in cond_fields" backend/engine/nodes/synthesize_skills.py` |
| Prompt constrains action_type | `grep -n "MUST be one of" backend/engine/nodes/synthesize_skills.py` |
| Graph effect hardcode | `grep -n '"effect": "approve"' backend/engine/nodes/build_operational_graph.py` |
| Graph confidence formula + threshold | `grep -n "0.5 + 0.1" backend/runtime/graph_retriever.py; grep -n "graph_fallback_threshold" backend/runtime/constraint_resolver.py` |
| Ambiguity gate logic + thresholds | `grep -n -B2 -A4 "is_ambiguous = " backend/runtime/constraint_resolver.py; grep -n -A6 "DEFAULT_THRESHOLDS" backend/runtime/constraint_resolver.py` |
| Guardrail override / `_norm` passthrough | `grep -n "diverged from constraint" backend/runtime/guardrails.py; grep -n -A7 "def _norm" backend/runtime/brain_agent.py` |
| Precedence condition bonus | `grep -n "condition_count \* 0.3" backend/runtime/precedence.py` |
| Ground-truth thresholds | `grep -n "3 or more\|4 hours\|two consecutive\|60 days\|3,500\|\$500" data/sources/rivanly-inc/*.md data/sources/rivanly-inc/slack_export_ops.json` |
| 26 unit tests | `grep -c "def test_" backend/tests/test_constraint_resolver.py` |
| Gateway semaphore / local embeddings | `grep -n "Semaphore\|all-MiniLM" backend/core/llm.py` |

If any command disagrees with this skill, the repo wins — update this file and re-date the stamp. Known open uncertainty (2026-07-10): the committed `resolver_eval_results.json` (canonical labels) and the committed brain (generic labels) cannot both be products of the same artifacts — Gate 0's first branch handles this; whoever resolves it should record which brain vintage becomes the certified resolver reference.
