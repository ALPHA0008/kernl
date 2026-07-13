---
name: kernl-architecture-contract
description: Load this before changing kernl's pipeline graph, runtime retrieval/resolver, brain JSON shape, or DB schema — or when asking "why is it built this way", "can I add a node/edge", "why does the graph path always approve", "why Annotated operator.add", "is the stack right for scale". Provides the load-bearing design decisions with rationale, the invariants that must hold (compile-time LangGraph shape, runtime decision chain, data and DB contracts), and the known-weak points with blast radius.
---

# kernl Architecture Contract

**What this covers:** the design decisions you must not accidentally break — the layered architecture and its principles, the compile-time LangGraph contract, the runtime decision chain, the brain JSON data contract, the DB contract, the known-weak points, and the one deliberately open architecture question.

**When NOT to use this:**
- How to run/compile/serve → `kernl-run-and-operate`; env setup → `kernl-build-and-env`.
- A bug is happening now → `kernl-debugging-playbook`; past incidents → `kernl-failure-archaeology`.
- Exact extraction/synthesis semantics per node → `knowledge-compilation-reference`; thresholds/weights config surface → `kernl-config-and-flags`.
- Whether a change is allowed and how to gate it → `kernl-change-control`. Evals → `kernl-eval-inversion-campaign` / `kernl-validation-and-qa`. Future-architecture research → `kernl-research-frontier`.

---

## 1. The mental model (read this first)

kernl compiles company documents (SOPs, Slack exports, tickets) into a versioned "brain" — a JSON artifact of executable skills plus an operational graph — and then answers operational questions from the compiled brain, never from raw documents. The architecture is four additive layers (docs/archive/operational-graph-master-plan.md [doc removed 2026-07-13; historical citation]:23-34):

```
LLM verbalizer        <- surface layer: explains decisions in natural language
Constraint resolver   <- deterministic policy engine: picks the action
Graph traversal       <- structured retrieval: entity -> policy edges
Entities + skills     <- all extracted knowledge, confidence-weighted
```

Three principles are load-bearing. Violating any of them is an architecture change, not a refactor (route it through `kernl-change-control`):

| Principle | Meaning | Enforced where |
|---|---|---|
| Each layer is additive | New layers handle what the previous couldn't, and fall back downward. Nothing gets deleted when a layer is added. | docs/archive/operational-graph-master-plan.md [doc removed 2026-07-13; historical citation]:34 |
| LLM explains, never decides | The constraint resolver picks the action deterministically; the LLM only verbalizes it; a guardrail overrides the LLM if it diverges. | backend/runtime/constraint_resolver.py:11-13, backend/runtime/guardrails.py:14 |
| The system must know when it doesn't know | Ambiguity is a first-class output: entropy over admissible actions above a threshold → `action_type="ambiguous"`, escalate to a human. | docs/archive/operational-graph-master-plan.md [doc removed 2026-07-13; historical citation]:906, backend/runtime/constraint_resolver.py:262, :493-494 |

"Deterministic" here means: `graph_retriever.py`, `constraint_resolver.py`, `precedence.py`, `condition_eval.py`, and `guardrails.py` contain **zero LLM calls**. Keep it that way.

---

## 2. Compile-time contract: the LangGraph pipeline

The pipeline is a LangGraph `StateGraph` assembled in `backend/engine/graph.py` (`build_compilation_graph`, line 31). LangGraph is a DAG runner where each node is an async function that receives the shared state dict and returns a partial update. The exact shape (as of 2026-07-07):

```
load_sources
  -> chunk_documents
  -> Send fan-out to 5 parallel extractors:
       extract_decisions | extract_workflows | extract_exceptions |
       detect_contradictions | extract_entities
  -> build_operational_graph        (barrier: waits for all 5)
  -> discover_operational_metadata
  -> synthesize_skills
  -> link_evidence
  -> score_confidence
  -> write_brain
  -> END
```

### Invariants and WHY

| Invariant | Where | Why |
|---|---|---|
| Fan-out uses the `Send` API via `route_to_extraction` (a conditional edge), never plain edges from `chunk_documents` to each extractor | backend/engine/graph.py:21-28, :60-70 | `Send("node", state)` schedules a node with an explicit state payload; it is LangGraph's mechanism for dynamic parallel dispatch. |
| Each extractor has a direct edge to `build_operational_graph`, which acts as the **barrier** (join point) | backend/engine/graph.py:72-76 | LangGraph fires a node once all its incoming parallel branches complete — the shared successor *is* the join. If parallel nodes instead each had an edge to different downstream nodes, or the join were skipped, the successor would fire multiple times (once per completed branch) and re-run with partial state. `build_operational_graph` also defensively no-ops if the graph is already built (backend/engine/nodes/build_operational_graph.py:10-12). |
| Every state field written by parallel nodes is declared `Annotated[List[...], operator.add]` | backend/engine/state.py:8, :12-19, :32 | The annotation is a LangGraph *reducer*: when two branches return the same key, LangGraph merges with `operator.add` (list concat) instead of last-write-wins. Without it, `extract_decisions` and `extract_entities` writing `errors` concurrently would overwrite each other. Fields written by exactly one node (e.g. `all_chunks`, `operational_graph`) are plain types. Do not remove a reducer from any field a fan-out node writes. |
| All nodes are `async def` | every file in backend/engine/nodes/ | LangGraph runs parallel branches on the asyncio loop; a sync node blocks the loop and serializes the "parallel" extractors. LLM concurrency is bounded by `asyncio.Semaphore(4)` (backend/core/llm.py:16). |
| The graph is compiled **without a checkpointer**: `workflow.compile()` | backend/engine/graph.py:85 | This is a known gap, not a design choice — see weak point W7 below. The `MemorySaver` claim in CLAUDE.md ("State checkpointing: MemorySaver") is stale; `grep -rn MemorySaver backend/` returns nothing (as of 2026-07-07). |

Adding a node = adding to this contract. State keys it writes need a reducer decision; its position relative to the barrier matters; it must be async. Gate it via `kernl-change-control`.

---

## 3. Runtime contract: the decision chain

Query entry point: `handle_agent_query` in backend/runtime/brain_agent.py:635, served at `POST /agent/handle` (backend/api.py:251) and `POST /agent/query` (backend/api.py:259). The chain, in order:

1. **Load brain** — newest `skills_files.brain_json` from Supabase (`_load_db`, brain_agent.py:607); on any DB failure, fall back to the local file `backend/tests/last_compiled_brain.json` (`_LOCAL_BRAIN`, brain_agent.py:602-604, `_load_file` :627). Runtime config comes from the brain's `metadata_json` with hardcoded fallback `_MD` (brain_agent.py:8-38).
2. **Graph retrieval first** — `retrieve_from_graph` (backend/runtime/graph_retriever.py:32): match context values to graph entities, follow `has_policy` edges, evaluate typed conditions, return policies with `graph_confidence = min(0.5 + 0.1 * n_resolved, 0.95)` (graph_retriever.py:100). The graph path is "used" when `success` and `graph_confidence >= graph_fallback_threshold` (0.5) — checked in brain_agent.py:648-650 and again in `resolve` (constraint_resolver.py:543-548).
3. **Skill hybrid scoring in parallel** — every skill scored as `semantic*0.45 + metadata*0.20 + keyword*0.15 + severity*0.10 + condition*0.10 + specificity bonus` (`_hybrid`, brain_agent.py:380-420; weights from `metadata_json.retrieval_weights`). Per-field metadata is only *trusted* if its `metadata_confidence` ≥ 0.60; conditions only if `conditions_confidence` ≥ 0.60 (`_get_trusted_op`, brain_agent.py:263-283). Top-5 skills yield admissible action candidates (`_admissible`, brain_agent.py:554-599).
4. **Constraint resolver decides** — `resolve` (backend/runtime/constraint_resolver.py:524): graph path if the gate passes (`_resolve_via_graph`, :194), else skill path (`_resolve_via_skills`, :423). It evaluates typed conditions, applies precedence (backend/runtime/precedence.py:71 `resolve_conflicts`) and authority rules, computes normalized entropy over candidate confidences (`compute_entropy`, constraint_resolver.py:102), and declares ambiguity when entropy > `ambiguity_entropy` (0.75) — on the skill path additionally gated by `score_differential_threshold` (0.10) and vague-phrasing signals (constraint_resolver.py:490-494). Ambiguous → `primary_action = None`.
5. **LLM verbalizes** — the prompt embeds the resolver's decision and says "Your ONLY job is to explain it... Do NOT override the action" (brain_agent.py:748-765).
6. **Guardrail overrides divergence** — `guardrail_check` (backend/runtime/guardrails.py:14, called at brain_agent.py:787): if the LLM's `action_type` differs from the resolver's, it is overwritten with the resolver's and `_guardrail_fired=true` is set (guardrails.py:44-50); if the resolver was ambiguous, `action_type` is forced to `"ambiguous"` (guardrails.py:24-30).

Never add code that lets LLM output feed back into the resolver's choice. The dependency is one-way: resolver → LLM → guardrail.

---

## 4. Data contract: `brain_json`

Assembled by `write_brain` (backend/engine/nodes/write_brain.py:41-53). Top-level shape:

```json
{
  "skills":        [ ...12 skill objects... ],
  "graph_json":    { "entities": {}, "edges": [], "authority_rules": {},
                     "policies": {}, "entity_ids": [], "stats": {} },
  "metadata_json": { "action_types": {"values": [], "ontology": {}},
                     "valid_sets": {}, "heuristic_patterns": {},
                     "authority_levels": {}, "retrieval_weights": {},
                     "thresholds": {} },
  "meta":          { "company_id", "compiled_at", "total_skills",
                     "duration_ms", "entity_count", "edge_count" }
}
```

**Each skill carries** (built in backend/engine/nodes/synthesize_skills.py): `id`, `category`, `rule`, `rationale`, `evidence`, `source_files`, `confidence`, plus:
- `operational` — department / severity / action_type / workflow_type / customer_tier / escalation_required / specificity_level / keywords, validated against `metadata_json.valid_sets` (synthesize_skills.py:31-64).
- `metadata_confidence` — per-field trust score: 0.90 if the LLM's value survived validation, 0.20 if it was rejected, 0.50 if absent (synthesize_skills.py:67-79). The runtime nulls any field below 0.60.
- `conditions` — typed conditions `{field, operator, value, type, source}` with operator whitelists per type (synthesize_skills.py:6-10, :82-130); `conditions_confidence` from the survival ratio of raw→validated conditions (synthesize_skills.py:133-145).
- `embedding_vector` — 384-dim, from `sentence-transformers/all-MiniLM-L6-v2`, precomputed at write time (write_brain.py:30-36, model at backend/core/llm.py:32-35).

**`metadata_json` is the runtime's real config surface.** The brain agent and resolver read `valid_sets`, the action ontology, `retrieval_weights`, and `thresholds` from the loaded brain, not from code (brain_agent.py:41-49, constraint_resolver.py:34-43). It is produced by `discover_operational_metadata` (backend/engine/nodes/discover_operational_metadata.py): valid sets, action types, ontology, heuristic patterns, and authority levels are *discovered from the extracted data*; note the nuance that `retrieval_weights` and `thresholds` values are currently fixed constants stamped into `metadata_json` at compile time (discover_operational_metadata.py:77-93) — the runtime treats them as data either way. To retune the runtime, change what compile writes (or the brain JSON), not runtime constants. Details in `kernl-config-and-flags`.

Reference brain (as of the 2026-06-15 compile, `backend/tests/last_compiled_brain.json`): 12 skills, 15 entities, 4 edges, 21 graph policies, 5 authority rules, compile duration 291,170 ms.

---

## 5. DB contract

Schema: `backend/schema.sql` — **7 tables** (as of 2026-07-07): `companies`, `skills_files`, `skills`, `source_files`, `compile_runs`, `operational_entities`, `relationship_edges`.

| Invariant | Where | Why |
|---|---|---|
| Exactly one current brain per company: partial unique index `idx_skills_files_current ON skills_files(company_id) WHERE is_current = true` | backend/schema.sql:23 | `write_brain` flips old current to false then inserts the new row with `is_current=true` (write_brain.py:73-89); the index makes a race a constraint violation instead of two currents. |
| Brains are versioned, never mutated | write_brain.py:66 (`v_<unix-ts>` version), new `skills_files` row per compile | Enables diffing versions and rollback by flipping `is_current`. |
| Brain agent survives DB loss via local-file fallback | brain_agent.py:602-604, :640 | Query-time reads fall back to `backend/tests/last_compiled_brain.json` — the runtime never needs raw sources or a live DB to answer. |
| `skills`, `operational_entities`, `relationship_edges` rows are keyed to a `skills_file_id` | schema.sql:28, :68, :78 | Relational mirrors of the brain for querying; the JSON blob in `skills_files.brain_json` remains the source of truth the runtime loads. |

Caveat you will trip on: `_load_db` selects the **newest by `compiled_at`**, not `is_current = true` (brain_agent.py:613-618) — normally identical, but they diverge after a manual rollback. Also CLAUDE.md calls `compile_runs` append-only, yet `write_brain` updates the run row's status (write_brain.py:146-153) — treat CLAUDE.md as aspirational there. See `kernl-debugging-playbook` before "fixing" either.

---

## 6. Known-weak points (as of 2026-07-07)

State these plainly in any design discussion. Each is a fact of the current code, not a to-do you may silently fix — changes go through `kernl-change-control`.

| # | What | Where | Blast radius |
|---|---|---|---|
| W1 | **Graph policies are hardcoded `effect: "approve"`, `priority: 0`, `conditions: []`** — every decision copied into the graph becomes an unconditional approve policy (confidence 0.7). The 2026-06-15 brain has 21 policies, all `approve`/priority 0/no conditions. | backend/engine/nodes/build_operational_graph.py:69-73 | **Live correctness hazard.** When the graph path triggers (`graph_confidence >= 0.5`), the resolver trusts it (constraint_resolver.py:543-561) and the answer can only ever be "approve" — a deny-scenario matching graph entities gets approved with a confident trace. Mitigated only by the graph rarely triggering (see W2). Highest-priority hazard in the repo. |
| W2 | **Compiled graph is thin: 4 edges, 15 entities** (2026-06-15 brain), so `has_policy` traversal almost never resolves and nearly all queries take the skill path. | backend/tests/last_compiled_brain.json `graph_json.stats`; edge filtering at build_operational_graph.py:45-48 | The graph layer is effectively dormant; dual-mode is single-mode in practice. Any change that enriches edges *activates W1*. |
| W3 | **Action-ontology specificity is uniformly 2** — discovered action types are single words with no children, so `_compute_specificity` (base 2 + word-count bonus + child bonus) returns 2 for all; the specificity tiebreaker (`specificity_bonus_scale` 0.02) is flat. | backend/engine/nodes/discover_operational_metadata.py:492-498; brain's ontology values | Retrieval ties between generic and specific actions are not broken as designed; ranking rests on the other score components. |
| W4 | **Authority naming schemes are mixed** — the brain's `metadata_json.authority_levels` contains both `founder` and `role_founder`, `role_am`, `role_vp_sales`, etc.; graph `authority_rules` keys are unprefixed (`founder`, `ops_lead`, `support_cs`); runtime lookups are exact-string (`get_authority_level`, backend/engine/models/entities.py:105-106; duplicate table in backend/runtime/precedence.py:16-47). | 2026-06-15 brain metadata_json; entities.py:73-100 | A requester role written in the other scheme silently gets `DEFAULT_AUTHORITY_LEVEL = 1` — wrong escalation targets and approval limits. Also note AUTHORITY_LEVEL is defined twice (entities.py and precedence.py) and can drift. |
| W5 | **Condition coverage is 5/12 skills** in the 2026-06-15 brain; the other 7 have `conditions: []`, so their condition score is always 0 and the resolver cannot condition-gate them. | backend/tests/last_compiled_brain.json | Threshold-style rules ("within 14 days", "over $500") in uncovered skills are enforced only by LLM explanation, which the guardrail does not check numerically. |
| W6 | **Embedding truncation at 128 tokens** — `max_length=128` in the tokenizer call; skill text is `category + rule + rationale`, and long rules are cut before embedding. | backend/core/llm.py:38-41 | Semantic similarity (45% of the hybrid score) is computed on a prefix; details late in a rule never influence retrieval. |
| W7 | **No checkpointing** — `workflow.compile()` with no checkpointer; a mid-pipeline crash loses all extraction work (a full compile is ~291 s on the reference run). CLAUDE.md's "MemorySaver" claim is stale. | backend/engine/graph.py:85 | Compile is all-or-nothing; no resume, no mid-run inspection. Any retry re-pays the full LLM cost (partially offset by the in-process `_content_cache`, backend/core/llm.py:21). |
| W8 | **Silent-empty-list extraction failures** — `safe_llm_json_call` returns `[]` after a failed parse+retry (backend/core/llm.py:191-217), and extractors pass that through (e.g. backend/engine/nodes/extract_decisions.py:46-52). | backend/core/llm.py:217 | A dead LLM gateway or persistent bad JSON yields a *successful* compile with fewer or zero skills — no error row, no failed status. Detect via skill-count drops (`kernl-validation-and-qa`); triage in `kernl-debugging-playbook`. |

Security note (do not skip): a Hugging Face token was committed in git history (commit 22ee2f0, backend/llm.py at that revision). Treat it as **compromised — it must be revoked**; never copy it anywhere. Likewise never paste the `VLLM_API_KEY` default value into docs or chat — refer to it as "see backend/core/llm.py:14". Details in `kernl-config-and-flags`.

---

## 7. OPEN question: is this the right stack for enterprise scale?

Status: **open, owner unassigned.** The current base is FastAPI + LangGraph + Supabase (Postgres/JSONB) + an in-memory dict/list operational graph + in-process CPU embeddings. It is neither settled-forever nor known-wrong — it demonstrably compiles and serves the 12-skill Rivanly brain. Do not present it as either in external material (see `kernl-external-positioning`).

Decide with criteria, not taste. The question becomes live when any of these bind:

| Criterion | Question to answer |
|---|---|
| Multi-tenant isolation | Is per-company row scoping in shared tables enough, or do enterprise customers require schema/instance isolation and per-tenant encryption? |
| Incremental compile | Compiles are full-recompute with no checkpointer (W7). At what source volume does "recompile everything per change" break, forcing incremental/persistent pipeline state? |
| Graph size | `graph_json` is one JSONB blob loaded whole into Python dicts per query. At what entity/edge count does that need a real graph store or at least indexed retrieval? |
| Connector volume | 8 local files today (data/sources/rivanly-inc/). Live Slack/Notion/Zendesk connectors imply auth, sync, rate limits, and PII handling the current loader has no story for. |

Candidate alternatives and experiments are tracked in `kernl-research-frontier`; run any evaluation using the methodology in `kernl-research-methodology`. Until decided, additions should stay stack-neutral where cheap (keep deterministic modules pure-Python, keep the brain a serializable artifact).

---

## Provenance and maintenance

Facts verified against the repo on **2026-07-07** (reference brain: `backend/tests/last_compiled_brain.json`, compiled 2026-06-15). Commands are runnable from the repo root in Git Bash; use `py -3` on Windows if `python` is not on PATH.

| Volatile fact | Re-verify with |
|---|---|
| Pipeline node order and edges | `grep -n "add_edge\|add_node\|Send(" backend/engine/graph.py` |
| Compile has no checkpointer | `grep -rn "checkpointer\|MemorySaver" backend/` (expect no hits) |
| Reducer fields in state | `grep -n "operator.add" backend/engine/state.py` |
| Hardcoded approve/priority/conditions in graph policies (W1) | `grep -n "\"effect\"\|\"priority\"\|\"conditions\"" backend/engine/nodes/build_operational_graph.py` |
| Graph gate threshold 0.5 and confidence formula | `grep -n "graph_fallback_threshold" backend/runtime/constraint_resolver.py backend/runtime/brain_agent.py` and `grep -n "0.5 + 0.1" backend/runtime/graph_retriever.py` |
| Retrieval weights / thresholds values | `grep -n -A16 "retrieval_weights = {" backend/engine/nodes/discover_operational_metadata.py` |
| Guardrail override behavior | `grep -n "diverged\|ambiguous" backend/runtime/guardrails.py` |
| Embedding dim 384 / truncation 128 | `grep -n "max_length" backend/core/llm.py`; dim: `py -3 -c "import json;b=json.load(open('backend/tests/last_compiled_brain.json'));print(len(b['skills'][0]['embedding_vector']))"` |
| Brain stats (12 skills, 15 entities, 4 edges, 21 policies, 5/12 conditions, specificity all 2) | `py -3 -c "import json;b=json.load(open('backend/tests/last_compiled_brain.json'));g=b['graph_json'];print(b['meta'],g['stats'],sum(1 for s in b['skills'] if s.get('conditions')),[ (s.get('operational') or {}).get('specificity_level') for s in b['skills']])"` |
| All 21 policies are approve/0/[] (W1 live check) | `py -3 -c "import json;b=json.load(open('backend/tests/last_compiled_brain.json'));p=b['graph_json']['policies'].values();print({x['effect'] for x in p},{x['priority'] for x in p},{len(x['conditions']) for x in p})"` |
| Mixed authority naming (W4) | `py -3 -c "import json;b=json.load(open('backend/tests/last_compiled_brain.json'));print(sorted(b['metadata_json']['authority_levels']))"` |
| 7 DB tables + partial unique index | `grep -n "CREATE TABLE\|CREATE UNIQUE INDEX" backend/schema.sql` |
| Local brain fallback path | `grep -n "_LOCAL_BRAIN" backend/runtime/brain_agent.py` |
| Silent `[]` on extraction failure (W8) | `grep -n "return \[\]" backend/core/llm.py` |
| Agent endpoints | `grep -n "agent/handle\|agent/query" backend/api.py` |
| Leak commit exists (never print its diff contents) | `git log --oneline \| grep 22ee2f0` |
