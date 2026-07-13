---
name: knowledge-compilation-reference
description: Load this when you need the domain theory behind kernl's code — what a compiled "skill" is, how MiniLM embeddings / cosine similarity / the 5-signal hybrid score work, typed-condition semantics, the Shannon-entropy ambiguity gate, precedence/authority math, the many different "confidence" numbers, the LLM guardrail pattern, or the Rivanly Inc. ground-truth policy matrix and its planted contradictions. Triggers - "why is this scenario ambiguous", "what does entropy 0.99 mean", "how is final_score computed", "what does metadata_confidence 0.20 mean", "what is the correct answer for REF-05", "why did a missing context field pass the condition".
---

# Knowledge Compilation Reference — the field's math and concepts as used in this repo

**What this covers:** the theory a mid-level engineer needs to reason about kernl's behavior: the compile-once thesis, the skill artifact schema, embedding retrieval math, hybrid scoring with a hand-verified worked example, typed-condition semantics, normalized Shannon entropy and the ambiguity gate, precedence/authority scoring, the taxonomy of confidence numbers, the LLM guardrail, and the full Rivanly Inc. ground truth.

**When NOT to use this:**
- Design invariants, what you may not break → `kernl-architecture-contract`. Whether a change is allowed → `kernl-change-control`.
- Something is failing right now → `kernl-debugging-playbook`; past incidents → `kernl-failure-archaeology`.
- Running compiles/evals, env setup → `kernl-run-and-operate`, `kernl-build-and-env`; tunable knobs → `kernl-config-and-flags`.
- The eval-inversion fix campaign itself → `kernl-eval-inversion-campaign`; eval mechanics/QA → `kernl-validation-and-qa`; math proofs tooling → `kernl-proof-and-analysis-toolkit`.

All line numbers and numbers below verified against the repo on 2026-07-08.

---

## 1. The knowledge-compilation thesis

**RAG (retrieval-augmented generation)** searches raw documents at query time and lets an LLM synthesize an answer from whatever it finds. **Knowledge compilation** is the opposite bet: run an expensive extraction pipeline ONCE over the raw sources, produce a structured, validated, versioned artifact (the "brain"), and answer every future query by reading only that artifact. AGENTS.md states it directly: "Agents are compilers, not assistants. We don't search raw documents. We compile tribal knowledge into structured, executable logic once. Then we read the compiled output forever." (AGENTS.md:10). Critical rule #3: "Never read raw source files at query time" (AGENTS.md:414).

**What a "skill" is here.** One skill = one compiled operational rule. The committed brain at `backend/tests/last_compiled_brain.json` holds 12 skills for Rivanly Inc. (as of 2026-07-08). Fields, with the pipeline node that produces each:

| Field | Type | Producer | Example (skill `refund_policy_matrix`) |
|---|---|---|---|
| `id` | snake_case string | LLM in `synthesize_skills` | `refund_policy_matrix` |
| `category` | domain string | LLM | `Support` |
| `rule` | actionable rule text | LLM | "Annual plans: full refund within 14 days, prorated after 14 days. ..." |
| `rationale` | why the rule exists | LLM | notes the 60-vs-30-day contradiction and that SOP wins |
| `evidence` | list of source quotes | LLM + `link_evidence` | 6 quotes from `notion_refund_sop.md` |
| `source_files` | list of filenames | LLM | `["notion_refund_sop.md"]` |
| `conditions` | typed conditions (section 4) | LLM, then whitelist-validated in `synthesize_skills` (backend/engine/nodes/synthesize_skills.py:82-130) | `days_since_purchase <= 14.0` etc. |
| `operational` | `{department, severity, action_type, workflow_type, customer_tier, escalation_required, specificity_level}` | LLM, then validated against discovered valid sets (synthesize_skills.py:31-64) | `department=support, action_type=refund` |
| `metadata_confidence` | per-field dict, 0.90/0.20/0.50 | `_build_metadata_confidence` (synthesize_skills.py:67-79) | all 0.90 |
| `conditions_confidence` | one float | `_compute_conditions_confidence` (synthesize_skills.py:133-145) | 0.90 |
| `confidence` | one float per skill | `score_confidence` node (backend/engine/nodes/score_confidence.py:5-28) | 0.90 |
| `keywords` | ≤15 lowercase strings | LLM, validated (synthesize_skills.py:60-63) | `["churn signals", ...]` |
| `embedding_vector` | 384 floats | `write_brain` (backend/engine/nodes/write_brain.py:30-36) | pre-computed |

The brain file also carries `graph_json` (entities, edges, `policies`, `authority_rules`, `precedence_edges`) and `metadata_json` (discovered valid sets, retrieval weights, thresholds) — see backend/engine/nodes/write_brain.py:41-53.

---

## 2. Embedding retrieval

**Embedding**: a fixed-length vector representing a text's meaning, so similarity between texts becomes geometry between vectors. kernl uses `sentence-transformers/all-MiniLM-L6-v2` loaded via HuggingFace `AutoModel` (backend/core/llm.py:32-35), which outputs **384-dimensional** vectors (verified: `embedding_vector` in `last_compiled_brain.json` has 384 entries). It runs on CPU, in-process — no external service.

**Truncation**: the tokenizer is called with `max_length=128, truncation=True` (backend/core/llm.py:41). Anything past ~128 tokens of a skill's text is invisible to retrieval. `refund_policy_matrix` packs five refund tiers into one rule; its tail competes for that 128-token budget. Keep this in mind when a rule "should have matched" — the matching part may have been truncated away.

**Mean pooling** (backend/core/llm.py:45-53): the transformer emits one vector per token; the sentence embedding is the attention-mask-weighted average of the token vectors — sum the vectors of real (non-padding) tokens and divide by their count (`torch.clamp(..., min=1e-9)` guards divide-by-zero).

**Cosine similarity**: for vectors a, b: `cos(a,b) = (a·b) / (||a|| * ||b||)` — 1.0 means same direction, 0 unrelated. Implementation (backend/core/llm.py:60-65):

```python
def cosine_similarity(v1, v2) -> float:
    a, b = np.array(v1), np.array(v2)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)
```

At query time the brain agent does the vectorized batch equivalent: `np.dot(se, qv) / (norms of both)` over all skill vectors at once when every skill has a cached `embedding_vector` (backend/runtime/brain_agent.py:657-662).

**One shared embedding space.** Skill text embedded at compile time is `"{category} {rule} {rationale}"` (write_brain.py:30-33; identical fallback at brain_agent.py:666-675). Query text embedded at query time is `f"{scenario} {json.dumps(ctx)}"` (brain_agent.py:652). Both go through the same model and pooling, so cosine similarity between them is meaningful. If you ever change the skill-text recipe, ALL stored vectors are stale until recompile — the query would live in the same space but skills would encode different text.

---

## 3. Hybrid scoring — the 5-signal weighted sum

Pure semantic similarity confuses "talks about refunds" with "is the applicable refund rule". So retrieval score is a weighted sum of five signals plus a specificity bonus, computed in `_hybrid` (backend/runtime/brain_agent.py:380-420). Default weights (brain_agent.py:22-28; produced into every brain by backend/engine/nodes/discover_operational_metadata.py:77-83):

| Signal | Weight | Computed by | Value range and rules |
|---|---|---|---|
| semantic | 0.45 | cosine similarity (section 2) | [0,1] typically |
| metadata | 0.20 | `_score_meta` (brain_agent.py:286-302) | +0.50 if skill department ∈ query department hints; +0.20 if trusted `action_type` present; capped 1.0 |
| keyword | 0.15 | `_score_kw` (brain_agent.py:305-315) | `|skill_keywords ∩ query_tokens| / (|skill_keywords| + 1)` |
| severity | 0.10 | `_score_sev` (brain_agent.py:318-329) | 1.0 exact severity match (e.g. P0=P0); 0.5 escalation signals aligned; else 0 |
| condition | 0.10 | `_score_cond` (brain_agent.py:332-377) | matched/evaluated over conditions whose field IS in query context |
| specificity bonus | additive, not weighted | brain_agent.py:396-397 | `(specificity_level / 5) * 0.02` (scale from `thresholds.specificity_bonus_scale`) |

`final_score = 0.45*semantic + 0.20*metadata + 0.15*keyword + 0.10*severity + 0.10*condition + specificity_bonus`. The reported `operational_confidence` is the non-semantic part renormalized: `op_s / 0.55` (denominator = sum of the four operational weights, brain_agent.py:399-405).

**Worked example — REF-01, from the committed eval trace** (backend/tests/eval_results_baseline.json:21-58, run 2026-06-16). Scenario: "Customer on an annual plan is requesting a refund. They purchased 9 days ago." Top skill `refund_policy_matrix`, trace says `final_score: 0.2993`, `semantic_confidence: 0.4474`, why_matched: "Specificity level 2 preferred. Matched 1/2 explicit conditions". Decompose by hand:

| Component | Raw score | × weight | Contribution |
|---|---|---|---|
| semantic | 0.4474 | 0.45 | 0.2013 |
| metadata | 0.20 (action_type present; no department-hint match) | 0.20 | 0.0400 |
| keyword | 0.0 | 0.15 | 0.0000 |
| severity | 0.0 (no severity signal) | 0.10 | 0.0000 |
| condition | 0.5 (1 of 2 evaluable conditions matched) | 0.10 | 0.0500 |
| specificity bonus | level 2 → (2/5)×0.02 | — | 0.0080 |
| **final_score** | | | **0.2993** ✓ |

Cross-check: `operational_confidence = (0.0400+0+0+0.0500)/0.55 = 0.1636` — exactly the committed value. (The baseline trace is flat; the current `_trace` nests these under a `"components"` key, brain_agent.py:444-459. The math is unchanged.)

Note the ceiling: a perfect skill for a query with no severity/department/keyword overlap tops out well below 1.0 — final scores around 0.25-0.35 are NORMAL, not a sign of failure. `avg_hybrid_score` for the whole baseline run is 0.3316 (eval_results_baseline.json:15).

---

## 4. Typed conditions

A **typed condition** is a machine-checkable predicate attached to a skill or graph policy: `{"field": "days_since_purchase", "operator": "<=", "value": 14.0, "type": "number", "source": "rule"}`. The LLM proposes them during synthesis; they are validated deterministically and evaluated deterministically — no LLM at eval time.

**Operator whitelists** (backend/runtime/condition_eval.py:11-15, duplicated at synthesize_skills.py:6-10):

| type | allowed operators |
|---|---|
| number | `>`, `>=`, `<`, `<=`, `==`, `!=` |
| string | `==`, `!=`, `in`, `not_in` |
| boolean | `==` |

Compile-time validation (`_validate_conditions`, synthesize_skills.py:82-130) drops any condition whose field isn't in the discovered `condition_fields` set, whose type isn't whitelisted, whose operator isn't allowed for its type, or whose numeric value won't coerce to float. Survival rate feeds `conditions_confidence` (section 7).

**Missing-context-field-is-neutral.** In `evaluate_condition`, if the query context has no value for the condition's field, the condition returns **True** (condition_eval.py:24-26). Why: conditions are qualifiers ("this rule applies WHEN..."), and an unstated fact is treated as "not applicable", not as a violation — otherwise every terse query would fail every condition and nothing would ever apply. The risk: an underspecified query silently satisfies ALL conditions of a highly specific rule. Ask "can I refund this customer?" with an empty context and `days_since_purchase > 60 → deny` evaluates as fully met. Neutral-on-missing is over-permissive by design; the eval's COND-* scenarios exist to probe exactly this.

**Boundary semantics are inclusive-explicit**: `14 <= 14` is True (documented in the module docstring, condition_eval.py:8; REF-07 in the eval expects exactly-14-days → approve). Type coercion happens before comparison: numbers via `float()`, strings lowercased/stripped; a failed coercion returns False (condition_eval.py:28-42).

**There are three condition evaluators — do not conflate them:**

| Evaluator | Where | Missing field | Quirk |
|---|---|---|---|
| `evaluate_condition/s` | condition_eval.py:18-93 | returns True (counts as matched) | canonical; used by graph retrieval |
| `_score_cond` | brain_agent.py:332-377 | skipped (not counted) | retrieval signal only |
| `_compute_condition_adjustment` | constraint_resolver.py:285-364 | skipped, logged "(neutral)" | for `>` and `<`, `ctx == value` ALSO counts as a match (constraint_resolver.py:324-331) — deliberate boundary leniency, but it makes strict inequalities non-strict |

---

## 5. Shannon entropy as the ambiguity measure

**Shannon entropy** of a probability distribution p₁..pₙ is `H = -Σ pᵢ log₂ pᵢ`; it is maximal (`log₂ n`) when all pᵢ are equal. kernl uses **normalized** entropy `H / log₂ n ∈ [0,1]` over the candidate actions' confidences (`compute_entropy`, backend/runtime/constraint_resolver.py:102-112):

```python
probs = [s / total for s in scores]          # normalize confidences to a distribution
entropy = -sum(p * math.log2(p) for p in probs if p > 0)
max_entropy = math.log2(len(probs)) if len(probs) > 1 else 1.0
return entropy / max_entropy
```

Edge cases: no actions → 1.0; total ≤ 0 → 1.0; a single action → 0.0.

**The mathematical heart of the over-ambiguity failure.** Because the scores are normalized by their sum, absolute magnitude cancels: candidates at [0.9, 0.9, 0.9] and [0.05, 0.05, 0.05] both yield entropy exactly 1.0. Entropy measures RELATIVE SPREAD, never correctness or absolute confidence. Derivation: write n candidate scores as sᵢ = s(1+δᵢ) with small δᵢ. Then pᵢ = 1/n + O(δ), and expanding H around the uniform distribution, H = log₂n − O(δ²) — so H/Hmax → 1 as the scores bunch together, at second order (i.e. very fast). Concretely, four candidates at [0.30, 0.28, 0.27, 0.25] give p = [0.273, 0.255, 0.245, 0.227], H ≈ 1.997, H/Hmax ≈ **0.999** — over the 0.75 gate even though the top action may be exactly right. The hybrid scorer (section 3) structurally produces bunched mid-range scores, so multi-candidate resolutions land near entropy 1.0 almost regardless of quality. This is why the committed baseline shows strict accuracy 15.0% but relaxed 52.5% (eval_results_baseline.json:10-11): REF-01 and REF-02 both identify the right rule and still return `action_type: "ambiguous"`. The campaign to fix this lives in `kernl-eval-inversion-campaign`.

**The ambiguity gate** (skill path, constraint_resolver.py:484-495). With defaults `ambiguity_entropy = 0.75` and `score_differential_threshold = 0.10` (constraint_resolver.py:26-31):

```
score_diff = (top_conf - second_conf) / max(top_conf, 0.001)     # RELATIVE gap
det_ambiguous = (any vague-phrasing/or-choice/etc. signal) and score_diff < 0.50
is_ambiguous  = (entropy > 0.75 and score_diff < 0.10) or det_ambiguous
```

(Python `and` binds tighter than `or` — that grouping is the actual semantics.) The deterministic signals come from `_detect_ambiguity_signals` (constraint_resolver.py:367-420): `" or "` in the query, vague phrases ("handle this appropriately", "what should", "you decide", "appropriate", ... full list at constraint_resolver.py:377-388), the word "escalate", "exactly N%" boundary wording, and multi-domain keyword overlap. If `is_ambiguous`, `primary_action` is None and the guardrail (section 8) forces `action_type = "ambiguous"`.

**The graph path has NO score-diff escape hatch**: `is_ambiguous = entropy > ambiguity_th` alone (constraint_resolver.py:262-263).

**Two entropies appear in output JSON**: `decision_trace.candidate_entropy` from `_entropy` in brain_agent.py:541-551 (same formula but returns 0.0 for empty/zero input, opposite of the resolver's 1.0) and `constraint_entropy` from the resolver. Same math, different populations of candidates — do not compare them to each other.

---

## 6. Precedence and authority

When multiple policies apply, `resolve_conflicts` (backend/runtime/precedence.py:71-114) ranks them by **effective priority**:

```
effective_priority = policy.priority
                   + Σ edge.confidence × 2      # for each precedence edge with relation_type
                                                #   "overrides" whose target_id == this policy's id
                   + authority_level × 0.5      # from AUTHORITY_LEVEL map, if policy has "authority"
                   + len(conditions) × 0.3      # specificity bonus
                   + policy.confidence × 0.5
```

Downstream the graph path converts it to an action confidence: `min(effective_priority / 10.0, 0.95)` (constraint_resolver.py:236).

**AUTHORITY_LEVEL** (precedence.py:16-43): founder/ceo 5; cfo/cto/vp/vice_president/principal 4; director/head/manager/lead/ops_lead/supervisor/team_lead 3; account_executive/account_manager/engineer/support_lead/specialist/analyst/consultant 2; support_agent/admin/coordinator 1; intern 0; default 1 (`get_authority_level`, precedence.py:46-47). Brain metadata can override/extend it via `merge_with_metadata` (precedence.py:50-54).

**OVERRIDE_PATTERNS** (precedence.py:3-12) are structural regex cues mapping rule wording to precedence relations: `except / notwithstanding / regardless of / overrides / supersedes → "overrides"`, `unless → "blocked_by"`, `only if / must have → "requires"`. Caveat (as of 2026-07-08): the only consumer, `detect_structural_precedence` (precedence.py:57-68), calls `.search()` on the raw pattern STRINGS (never `re.compile`d) — it would raise `AttributeError` if invoked, and nothing in `backend/` calls it. Treat OVERRIDE_PATTERNS as declared-but-inert.

**Reality check against the committed brain**: `graph_json.precedence_edges` is empty, and every one of the 21 graph policies has `priority: 0` and `effect: "approve"` (see `kernl-architecture-contract` for why the graph path therefore "always approves"). So in practice effective priority currently reduces to `conditions×0.3 + confidence×0.5`.

---

## 7. Confidence semantics — they are DIFFERENT numbers

Multiple fields are named "confidence". Each has a different producer, scale, and consumer. Table them; never average or compare across rows.

| Name | Lives on | Producer | Values | Consumed by |
|---|---|---|---|---|
| `metadata_confidence` (per field: department, severity, workflow_type, customer_tier, action_type) | skill | `_build_metadata_confidence` (synthesize_skills.py:67-79) | **0.90** LLM gave a value AND it survived whitelist validation; **0.20** LLM gave a value that was rejected (hallucinated/invalid); **0.50** LLM gave nothing | `_get_trusted_op` (brain_agent.py:263-283): field trusted only if ≥ `metadata_confidence` threshold 0.60 — so only 0.90 fields are used |
| `conditions_confidence` (one float) | skill | `_compute_conditions_confidence` (synthesize_skills.py:133-145) | **0.50** none proposed; **0.20** all proposed conditions rejected; **0.90** all survived; else `0.60 + 0.30×survival_ratio` | same gate at 0.60 — a 0.20 skill has its conditions ignored at retrieval |
| skill `confidence` | skill | `score_confidence` node (score_confidence.py:5-28): base 0.5 + evidence bonus (≥3 sources +0.25, 2 +0.15, 1 +0.05) + 0.15 recency + 0.10 if no contradiction touches it; capped 1.0 | 0.65–1.0 possible (committed brain: 0.7–1.0) | shown to the LLM as "Compiled Confidence" in the prompt (brain_agent.py:721); NOT part of hybrid retrieval score |
| graph policy `confidence` | graph_json policy | `build_operational_graph` (LLM extraction) | committed brain: uniformly 0.7 | precedence ×0.5 term; graph retriever tiebreak (graph_retriever.py:91-97) |
| entity/relationship `confidence` | graph entities/edges | extraction prompts band it: explicit-doc 0.85–0.95, Slack-implicit 0.50–0.65, contradictory 0.20–0.35 (backend/engine/nodes/extract_entities.py:40-42) | 0.0–1.0 | written to DB (write_brain.py:122,140) |
| `semantic_confidence` / `operational_confidence` | retrieval trace | section 3 | cosine / renormalized op score | diagnostics + prompt |
| `action_confidence` | admissible candidate | = `metadata_confidence["action_type"]` (brain_agent.py:568-578) | 0.90/0.20/0.50 | resolver base: `retrieval_score × action_confidence` (constraint_resolver.py:456-458) |
| resolved action `confidence` | ResolvedAction | skill path: base × condition multiplier `0.5 + 0.5×match_rate` (constraint_resolver.py:360, 460-461); graph path: `min(effective_priority/10, 0.95)` | 0–0.95 | entropy input (section 5) and final output |

Also defined but (as of 2026-07-08) never read by any logic: `min_confidence_for_auto_action: 0.40` (constraint_resolver.py:28, brain_agent.py:33, discover_operational_metadata.py:89) — a dead threshold; see `kernl-config-and-flags`.

---

## 8. The guardrail pattern — the LLM is a verbalizer, not a decider

The constraint resolver decides the action deterministically; the LLM only explains it. Two enforcement layers:

1. **Prompt-level**: the system prompt opens "You are a policy explainer. The constraint engine has already determined the correct action. Your ONLY job is to explain it... Do NOT override the action." and pins `action_type` to the resolver's choice inside the required JSON (brain_agent.py:748-765).
2. **Code-level** (`guardrail_check`, backend/runtime/guardrails.py:14-52, applied at brain_agent.py:787): after parsing the LLM JSON — if the resolver was ambiguous, force `action_type="ambiguous"`; if the LLM returned an empty action, substitute the resolver's; if the LLM's action DIFFERS from the resolver's, overwrite it. Every intervention sets `_guardrail_fired: True` with `_guardrail_reason`.

Why override rather than trust: LLM output is nondeterministic, prompt-injectable, and prone to arithmetic slips on thresholds ("no refunds after 60 days" reasoning errors are called out explicitly in the prompt's language-interpretation rules, brain_agent.py:750-753). Determinism requirements (the DET-* eval scenarios) demand that the same query yields the same action every run; only a deterministic decider can promise that. The corollary: if the final answer is wrong, debug the RESOLVER and RETRIEVAL, not the prompt — the LLM cannot rescue a wrong resolver decision, by design.

---

## 9. Rivanly Inc. — the ground truth every eval scenario tests

Rivanly Inc. is the fictional 15-person B2B SaaS demo company. Its entire "tribal knowledge" is 8 synthetic files in `data/sources/rivanly-inc/` (5 Notion markdown docs, 2 Slack exports, 1 Zendesk export — 143 lines total). The 40 eval scenarios (`SCENARIOS`, backend/tests/eval_harness.py:40) are graded against this matrix. Learn it; you cannot judge an eval result without it.

**Policy matrix** (source file → rule):

| Domain | Rule | Expected action label |
|---|---|---|
| Refunds (`notion_refund_sop.md`) | Annual plan, ≤14 days since purchase → full refund (14 exactly counts: REF-07) | `approve` |
| | Annual plan, >14 days → prorated refund of unused months | `approve_prorated` |
| | Enterprise, ANY refund → never process; escalate to Account Manager within 1 hour | `escalate` |
| | Lifetime Deal → always deny | `deny` |
| | Monthly plan, tenure <3 months, amount >$500 → Founder approval | `get_founder_approval` |
| | HARD LIMIT: no refunds after 60 days, any tier | `deny` |
| Discounts (`notion_pricing_policy.md`) | Support/CS may give up to 10% to save a churning customer | `approve` |
| | Pre-seed/seed startup: up to 20% on Annual, first year | `approve_20_percent_startup_discount` |
| | >30% → must go to an Account Executive; support cannot approve | `escalate` |
| | Enterprise custom bundles/volume pricing → route to VP of Sales | (route) |
| Churn (`notion_cs_playbook.md`) | ≥3 churn signals within 30 days → schedule AM call within 24 hours (2 signals → just monitor, CS-03) | `schedule_am_call` / `monitor` |
| | New Enterprise onboarding = kickoff call + custom training + 30-day check-in | `initiate_enterprise_onboarding` |
| SLA/Eng (`notion_eng_runbook.md`) | P0 from Enterprise → page on-call immediately | `page_on_call` |
| | P1 → resolve within 4 hours | `resolve_within_4_hours` |
| | SLA breach >1h → notify support lead; Enterprise breach ≥2h → notify AM AND Eng Lead | `notify_am_and_eng_lead` |
| | Active outage → do not troubleshoot; send incident template + status page link | `send_incident_template` |
| HR (`notion_hr_playbook.md`) | Engineering offer stage → Founder approval before sending offer letter | `get_founder_approval` |
| | KPIs missed 2 consecutive quarters → PIP; then formal review with dept head within 5 business days | `initiate_pip` |
| Vendors (`slack_export_ops.json`) | Software vendor invoice ≥$3,500 → route to ops lead before payment | `route_to_ops_lead` |

**The planted contradictions and Slack-only exceptions** (deliberate — they test whether compilation captures tribal knowledge that overrides documents):

1. **60-day SOP vs "30 days" Slack** — the SOP says no refunds after 60 days (`notion_refund_sop.md`, "Strict Time Limits"), but in `slack_export_support.json` sarah_am says "SOP says 30 days max". The two numbers cannot both be right; the compiled `refund_policy_matrix` rationale records the conflict and resolves "SOP 60-day limit takes precedence".
2. **The undocumented loyalty override** — in the same Slack thread, mike_lead: "For loyal customers over 2 years tenure, we can bypass the 30-day rule. Go ahead and approve the refund for Acme Corp" (4-year customer, 45-day-old charge). This rule exists ONLY in Slack — no SOP mentions it. Eval SLACK-01 expects `approve` for a 4-year-tenure customer at 45 days; a pipeline that only trusts documents fails it.
3. **The outage "close the tickets" addition** — the runbook says send the incident template and link the status page; Slack (mike_lead, 2026-04-01) adds "Just send the incident response template and **close the tickets**." The observed behavior extends the written SOP.
4. **The accepted 12-hour P1 precedent** — `zendesk_tickets.json` TICKET-1045: a P1 for Enterprise resolved "within 12 hours, outside the normal 4-hour SLA but acceptable for this specific complex issue for Enterprise." A precedent that the 4-hour rule bends for complex Enterprise cases — planted to see if ticket history softens a hard rule.

AGENTS.md:429-438 lists the 12 intended skills per department; the committed brain indeed contains 12 skills (ids like `refund_policy_matrix`, `discount_authority_matrix`, `p0_bug_enterprise_response`) and 21 graph policies. The eval baseline against all of this: strict 15.0%, relaxed 52.5%, rule-hit 55.0% (eval_results_baseline.json:10-12) — the gap is the over-ambiguity failure of section 5.

---

## Provenance and maintenance

Facts verified against the working tree on **2026-07-08**. The committed eval trace used in section 3 is `backend/tests/eval_results_baseline.json` (run timestamp 2026-06-16). Do NOT run the pipeline or eval to re-verify — it hits the shared live vLLM gateway and Supabase (see `kernl-run-and-operate`). Re-verify statically, from the repo root (quote paths — the repo path contains a space):

| Volatile fact | Re-verify with |
|---|---|
| Embedding model + 128-token truncation | `grep -n "all-MiniLM-L6-v2\|max_length=128" "backend/core/llm.py"` |
| cosine_similarity implementation | `grep -n "def cosine_similarity" "backend/core/llm.py"` |
| Retrieval weights .45/.20/.15/.10/.10 | `grep -n -A6 "retrieval_weights" "backend/runtime/brain_agent.py" \| head -12` |
| Specificity bonus scale 0.02 | `grep -n "specificity_bonus_scale" "backend/runtime/brain_agent.py" "backend/engine/nodes/discover_operational_metadata.py"` |
| VALID_OPERATORS whitelists | `grep -n -A5 "VALID_OPERATORS" "backend/runtime/condition_eval.py"` |
| Missing-field-returns-True | `grep -n -B1 -A2 "ctx_val is None" "backend/runtime/condition_eval.py"` |
| compute_entropy formula | `grep -n -A11 "def compute_entropy" "backend/runtime/constraint_resolver.py"` |
| Gate thresholds 0.75 / 0.10 | `grep -n -A6 "DEFAULT_THRESHOLDS" "backend/runtime/constraint_resolver.py"` |
| Ambiguity gate expression | `grep -n -A3 "det_ambiguous" "backend/runtime/constraint_resolver.py"` |
| Vague-phrase list | `grep -n -A12 "vague_phrases" "backend/runtime/constraint_resolver.py"` |
| OVERRIDE_PATTERNS + AUTHORITY_LEVEL | `grep -n -A10 "OVERRIDE_PATTERNS\|^AUTHORITY_LEVEL" "backend/runtime/precedence.py"` |
| Effective-priority terms (×2, ×0.5, ×0.3, ×0.5) | `grep -n "score +=" "backend/runtime/precedence.py"` |
| metadata_confidence 0.90/0.20/0.50 | `grep -n -A12 "_build_metadata_confidence" "backend/engine/nodes/synthesize_skills.py"` |
| conditions_confidence bands | `grep -n -A12 "_compute_conditions_confidence" "backend/engine/nodes/synthesize_skills.py"` |
| Skill confidence formula | `grep -n -A23 "_score_confidence" "backend/engine/nodes/score_confidence.py"` |
| Guardrail override logic | `grep -n -A8 "def guardrail_check" "backend/runtime/guardrails.py"` |
| Embedding dim 384 / 12 skills | `grep -c "embedding_vector" "backend/tests/last_compiled_brain.json"` (expect 12); dim via any JSON parse of `skills[0].embedding_vector` |
| REF-01 trace numbers | `grep -n -A20 '"id": "REF-01"' "backend/tests/eval_results_baseline.json"` |
| Baseline accuracy 15.0 / 52.5 | `grep -n "strict_accuracy_pct\|relaxed_accuracy_pct" "backend/tests/eval_results_baseline.json"` |
| Rivanly contradiction texts | `grep -n "bypass the 30-day rule\|close the tickets\|60 days\|12 hours" -r "data/sources/rivanly-inc/"` |
| Eval scenario count (40) | `grep -c '"id":' "backend/tests/eval_harness.py"` minus non-scenario ids; or check `total_scenarios` in the baseline JSON |
