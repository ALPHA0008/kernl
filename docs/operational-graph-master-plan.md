# Operational Graph — Master Architecture Plan

**Author:** AI-assisted design
**Date:** 2026-05-28
**Status:** Reviewed — ready for Phase 1 execution

---

## Core Thesis

> Production AI systems reduce LLM freedom over time, not increase it.
> Constraint systems beat freeform generation in production.
> The LLM should explain policy, not decide it.

But also:

> Not everything can be made deterministic.
> The real final boss is operational reliability under ambiguity.
> Skills are not replaced — they are layered upon.

---

## Architecture Philosophy

This plan follows a **hybrid layered architecture**:

```
LLM verbalizer        ← surface layer, explains decisions
Constraint resolver   ← deterministic where possible
Graph traversal       ← structured retrieval for related policies
Entities + skills     ← all extracted knowledge, confidence-weighted
```

Each layer is **additive**. Nothing gets deleted. Every new layer handles scenarios the previous layer couldn't, and falls back when it can't.

---

## Where We Are Now (Phase 0)

### Current Pipeline
```
Source Files → Chunks → [4 parallel LLM extractions]
  → Synthesize Skills → Link Evidence → Score Confidence → Write DB
```

### Current Query Time
```
Query → embed → cosine similarity → top 5 skills → inject into LLM prompt → LLM decides
```

### What Already Exists (seeds of the graph)
These are in the OLD `backend/graph/` and `backend/agent/` code paths, NOT in `backend/engine/`:

1. **Typed conditions** with field/operator/value validation and type coercion
2. **Action ontology** with parent/child hierarchy and specificity levels 1-5
3. **Hybrid scoring** with 5 weighted signals (semantic 0.45, metadata 0.20, keyword 0.15, severity 0.10, condition 0.10)
4. **Heuristic fallback** patterns when skill confidence is low
5. **Runtime condition evaluation** against scalar context values
6. **Shannon entropy** for candidate spread and ambiguity detection
7. **Retrieval trace** with why_matched / why_runner_up_lost

### Current Problem
The codebase has TWO parallel implementations. The `engine/` path has cleaner structure but is MISSING all 7 features above. The deployed Dockerfile targets `main.py` (old path), not `api.py` (new path).

---

## Target Architecture

### Compile Time
```
Source Files
    ↓
Chunk documents
    ↓
[Parallel LLM Extraction]
  • Policies / decisions / rules
  • Workflows and step-by-step processes
  • Exceptions and edge cases
  • Contradictions between sources
  • Entities (Customer, Plan, Invoice, Employee, Vendor, etc.)
  • Relationships (requires, blocks, overrides, escalates_to, depends_on)
  • Authority rules (who can approve what, at what threshold)
    ↓
[Barrier: Build Operational Graph]
  • Entities + relationships → adjacency graph
  • Policies with typed conditions → graph-attached rule nodes
  • Precedence edges extracted via structural patterns + LLM refinement
  • Confidence scoring per node and edge
    ↓
[Existing pipeline: Synthesize → Link Evidence → Score → Write]
  Skills written alongside the graph. Both persist. Neither replaces the other.
```

### Query Time (Dual-Mode Runtime)
```
Query + Context
    ↓
1. Identify entities in query         (entity extraction)
2. Try graph traversal first          (entity → policies → conditions)
   ↓
   If graph confidence ≥ threshold:
     → Graph-resolved action set
   Else:
     → Fall back to skill embedding retrieval
    ↓
3. Constraint resolver (deterministic):
   - Evaluate conditions against context
   - Resolve conflicts by precedence
   - Apply authority rules
   - Detect ambiguity → if entropy too high, flag for human
    ↓
4. LLM verbalizer:
   - Receives resolved action set
   - Explains in natural language
   - Guardrail: if LLM output != resolver decision, OVERRIDE with resolver
    ↓
Output
```

### Key Behavioral Properties

| Property | Current | Target |
|---|---|---|
| LLM role | Decides policy | Explains policy |
| Policy enforcement | Probabilistic (in prompt) | Deterministic (constraints) |
| Decision trace | LLM reasoning text | Graph traversal + condition eval + precedence chain |
| Ambiguity handling | LLM guesses | Shannon entropy → human escalation |
| Retrieval | Cosine similarity on skills | Graph traversal + skill fallback |
| State | Stateless per query | Entity graph persists across queries |

---

## Phase 1: Convergence & Stabilization

**Duration:** 3-5 days
**Goal:** Working end-to-end pipeline on a single codebase. The LLM runs. The pipeline compiles. The brain agent answers questions.

### Why This Is Mandatory
The codebase cannot evolve with two parallel implementations diverging. Every day the `engine/` path lacks features from `graph/` is a day the product cannot ship.

### Tasks

#### 1a. Port synthesize_skills features into engine/nodes/

Copy from `backend/graph/nodes/synthesize_skills.py` into `backend/engine/nodes/synthesize_skills.py`:

| Lines | Feature | Why it matters |
|---|---|---|
| 6-36 | Valid departments, severities, workflow types, customer tiers, canonical condition fields | Prevents silent metadata poisoning at compile time |
| 38-56 | Specificity level map (1-5) | Used for tiebreaker in retrieval — unique moat |
| 59-98 | `_validate_operational_metadata()` | Rejects hallucinated department names, normalizes severity variants |
| 101-120 | `_build_metadata_confidence()` | Per-field confidence — enables confidence-weighted retrieval |
| 123-192 | `_validate_conditions()` | Canonical field validation, operator whitelist, type coercion |
| 195-216 | `_compute_conditions_confidence()` | Conditions confidence — gates condition-based retrieval |
| 252-347 | Extended LLM prompt with operational metadata, typed conditions, extended fields | The prompt that produces the rich skill schema |
| 375-412 | Post-processing: validate, build confidence, attach conditions, extended fields | Converts LLM output into validated graph-ready data |

#### 1b. Port brain agent features into runtime/

Copy from `backend/agent/brain_agent.py` into `backend/runtime/brain_agent.py`:

| Lines | Feature | Why it matters |
|---|---|---|
| 12-18 | Canonical action types | Shared taxonomy across compile-time and query-time |
| 23-39 | Action ontology with parent/children/specificity | Enables hierarchical action reasoning |
| 44-58 | Heuristic fallback patterns | Catches query signals with no graph match |
| 63-86 | Retrieval weights + thresholds | Tunable hybrid scoring — the differentiating algo |
| 90-154 | `_extract_query_signals()` | Extracts severity, department hints, escalation signals, context values from query |
| 156-173 | `_get_trusted_operational()` | Only uses metadata fields above confidence threshold |
| 175-194 | `_score_metadata_match()` | Department + action_type alignment score |
| 196-209 | `_score_keyword_overlap()` | Token overlap score |
| 211-224 | `_score_severity_weight()` | Severity match + escalation signal score |
| 226-290 | `_score_condition_match()` | Runtime typed condition evaluation — the core of deterministic policy |
| 292-336 | `_compute_hybrid_score()` | Weighted combination of all 5 signals + specificity bonus |
| 339-409 | `_build_retrieval_trace()` | Why_matched / why_runner_up_lost — critical for explainability |
| 416-451 | `_heuristic_candidate_builder()` | Fallback when compiled brain lacks operational metadata |
| 454-463 | `_compute_candidate_entropy()` | Shannon entropy — quantifies ambiguity objectively |
| 466-514 | `_build_admissible_actions()` | Ranks candidates by retrieval_score × action_confidence × specificity |
| 521-694 | Full `handle_agent_query()` | Hybrid scoring loop + LLM prompt with admissible actions + candidate entropy |

#### 1c. Fix LLM client (core/llm.py)

- **Problem:** `core/llm.py` uses vLLM with a 3-second timeout as primary. No vLLM is running. Calls always fail and fall back to HF Router, which uses a different model.
- **Fix:** Use OpenRouter as primary (already configured in `.env` with API key and model `meta-llama/llama-3.3-70b-instruct`). Ollama as optional fallback. Remove vLLM dependency.
- **Why:** The pipeline is dead without a running LLM. OpenRouter is the fastest path to a working system.

#### 1d. Delete old code paths

Remove these directories and files:
- `backend/graph/` (entirely superseded by `engine/`)
- `backend/agent/` (old `brain_agent.py` — ported to `runtime/`)
- `backend/llm.py` (old LLM client — ported to `core/llm.py`)
- `backend/main.py` (old entrypoint — `api.py` is the replacement)
- `backend/db/` (supabase.py exists at `core/db/supabase.py`)
- `backend/models/` (schemas exist at `core/models/schemas.py`)
- `backend/sse.py` (exists at `core/sse.py`)

#### 1e. Fix deployment

- Point Dockerfile at `backend.api:app` instead of `backend.main:app`
- Standardize on port 8081 everywhere:
  - Dockerfile expose 8081
  - frontend/src/lib/api.ts → `http://localhost:8081`
  - scripts/smoke_test.py → port 8081
  - backend/api.py runs on port 8081

#### 1f. Fix test imports

- `backend/test_compile.py` imports from `backend.graph.graph` → change to `backend.engine.graph`
- `backend/tests/eval_harness.py` imports from `backend.agent.brain_agent` → change to `backend.runtime.brain_agent`
- `backend/test_health.py` imports from `backend.llm` → change to `backend.core.llm`

### Acceptance Criteria
- [ ] `engine/nodes/synthesize_skills.py` validates metadata, conditions, and action types
- [ ] `runtime/brain_agent.py` returns hybrid score with retrieval trace (5 signals, specificity bonus, entropy)
- [ ] Pipeline compiles Rivanly Inc. end-to-end via OpenRouter
- [ ] Eval harness runs without errors
- [ ] Dockerfile deploys `backend.api:app`
- [ ] All old code paths deleted

### Verification
```bash
# 1. Start the API
cd backend && uvicorn api:app --port 8081

# 2. Compile Rivanly Inc.
curl -X POST http://localhost:8081/compile \
  -H "Content-Type: application/json" \
  -d '{"company_id": "rivanly-inc"}'

# 3. Check results
curl http://localhost:8081/skills/rivanly-inc

# 4. Run eval harness
python -m backend.tests.eval_harness

# 5. Run smoke test
python scripts/smoke_test.py
```

---

## Phase 2: Typed Operational Entities

**Duration:** 2-3 weeks
**Goal:** Extract structured entities alongside skills. Both coexist in the DB.

### Why Phase 2 Before Graph Retrieval
You cannot traverse a graph that doesn't exist. Entities are the nodes. Phase 2 builds the nodes. Phase 3 builds the edges between them.

### 2a. Define entity model

Create `backend/engine/models/entities.py`:

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class TypedCondition:
    field: str
    operator: str      # >, >=, <, <=, ==, !=, in, not_in
    value: Any
    type: str          # "number", "string", "boolean"
    source: str = "rule"

@dataclass
class OperationalEntity:
    id: str
    entity_type: str   # "customer", "plan", "invoice", "employee", "vendor", "team"
    properties: Dict[str, Any]
    source_files: List[str]
    confidence: float = 0.5    # extraction confidence, not operational confidence
    requires_review: bool = False  # flagged if low confidence extraction

@dataclass
class PolicyNode:
    id: str
    rule_text: str
    category: str
    conditions: List[TypedCondition]
    effect: str        # "approve", "deny", "escalate", "require_approval", "monitor"
    priority: int = 0  # higher = overrides lower
    authority: Optional[str] = None  # who can invoke this
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.5

@dataclass
class RelationshipEdge:
    id: str
    source_id: str
    target_id: str
    relation_type: str   # "requires", "blocks", "overrides", "escalates_to",
                         # "depends_on", "triggers", "has_policy", "reports_to"
    conditions: List[TypedCondition] = field(default_factory=list)
    confidence: float = 0.5
    source: str = ""     # which source document this came from
```

### 2b. New extraction node

Create `backend/engine/nodes/extract_entities.py`:

```python
SYSTEM = """You are a knowledge extraction specialist. Your ONLY job is to extract operational ENTITIES,
their PROPERTIES, and RELATIONSHIPS from company communications.

Output ONLY a JSON object. No preamble. No explanation. No markdown.

ENTITIES are the actors, objects, and concepts in the company's operations:
  - Customer (with properties: tier, plan_type, tenure_months, industry)
  - Plan (with properties: type, billing_cycle, price, max_users)
  - Invoice (with properties: amount, status, due_date)
  - Employee (with properties: role, department, seniority)
  - Vendor (with properties: name, category, payment_terms)
  - Team (with properties: name, lead, members)

RELATIONSHIPS are the connections between entities:
  - Customer HAS_PLAN Plan
  - Plan REQUIRES_APPROVAL_FOR Invoice > $X
  - Employee REPORTS_TO Employee
  - Policy APPLIES_TO Customer (when conditions met)

AUTHORITY RULES define who can do what:
  - role: "founder"
    can_approve: ["refund", "discount", "offer"]
    up_to_amount: null  # no limit
  - role: "support_agent"
    can_approve: ["refund"]
    up_to_amount: 500

CONFIDENCE RULES:
  - Explicit policies (notion_refund_sop.md: "Refunds over $500 require Founder approval")
    → confidence: 0.90
  - Implicit patterns extracted from Slack messages
    → confidence: 0.60
  - Ambiguous or contradictory mentions
    → confidence: 0.30

Example output:
{
  "entities": [
    {
      "id": "customer_annual",
      "entity_type": "customer",
      "properties": {"tier": "annual", "refund_window_days": 14},
      "source_files": ["notion_refund_sop.md"],
      "confidence": 0.90
    }
  ],
  "relationships": [
    {
      "source_id": "policy_refund_annual",
      "target_id": "customer_annual",
      "relation_type": "applies_to",
      "conditions": [
        {"field": "plan_type", "operator": "==", "value": "annual", "type": "string"}
      ],
      "confidence": 0.90,
      "source": "notion_refund_sop.md"
    }
  ],
  "authority_rules": [
    {
      "role": "founder",
      "can_approve": ["refund", "discount", "offer", "hire"],
      "up_to_amount": null,
      "source": "notion_refund_sop.md"
    }
  ]
}"""

USER = """Extract all entities, relationships, and authority rules from this company data:
{content}"""
```

The extraction prompt is designed to produce **confidence-tagged output** so the system can distinguish between explicit policies and inferred patterns.

### 2c. Extend BrainState

```python
class BrainState(TypedDict):
    # ... all existing fields stay ...
    
    # New fields (parallel extraction)
    extracted_entities: Annotated[List[Dict[str, Any]], operator.add]
    extracted_relationships: Annotated[List[Dict[str, Any]], operator.add]
    extracted_authority_rules: Annotated[List[Dict[str, Any]], operator.add]
    
    # Built by new barrier node
    operational_graph: Dict[str, Any]  # {
                                       #   "entities": {...},
                                       #   "policies": {...},
                                       #   "edges": [...],
                                       #   "authority_rules": [...]
                                       # }
```

### 2d. Extend graph routing

The extraction fan-out grows from 4 to 7 parallel branches:

```python
def route_to_extraction(state: BrainState) -> list[Send]:
    return [
        Send("extract_decisions", dict(state)),
        Send("extract_workflows", dict(state)),
        Send("extract_exceptions", dict(state)),
        Send("detect_contradictions", dict(state)),
        Send("extract_entities", dict(state)),        # NEW
        Send("extract_relationships", dict(state)),   # NEW
        Send("extract_authority", dict(state)),       # NEW
    ]
```

A new barrier node `build_operational_graph` runs after ALL extraction nodes complete:

```mermaid
extract_decisions ─┐
extract_workflows ─┤
extract_exceptions ─┤
detect_contradictions ─┤
extract_entities ──────┤──→ build_operational_graph → synthesize_skills → ...
extract_relationships ─┤
extract_authority ─────┘
```

`build_operational_graph` does:
1. Merges entities by `id` (deduplication with max-confidence wins)
2. Validates relationship edges (both source and target exist)
3. Builds in-memory adjacency index
4. Links policy nodes to entities via `has_policy` edges
5. Runs structural precedence detection (see Phase 3 for details)
6. Stores result in `state["operational_graph"]`
7. Tags low-confidence entities with `requires_review: true`

### 2e. Extend DB schema

```sql
-- These tables live alongside existing skills_files and skills tables

CREATE TABLE operational_entities (
  id TEXT NOT NULL,
  company_id TEXT REFERENCES companies(id),
  skills_file_id UUID REFERENCES skills_files(id),
  entity_type TEXT NOT NULL,
  properties JSONB NOT NULL,
  confidence FLOAT NOT NULL DEFAULT 0.5,
  requires_review BOOLEAN DEFAULT false,
  PRIMARY KEY (id, company_id, skills_file_id)
);

CREATE TABLE relationship_edges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id TEXT REFERENCES companies(id),
  skills_file_id UUID REFERENCES skills_files(id),
  source_entity_id TEXT NOT NULL,
  target_entity_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  conditions JSONB DEFAULT '[]'::jsonb,
  confidence FLOAT NOT NULL DEFAULT 0.5,
  source TEXT
);

-- Add graph_json column to the existing skills_files table
ALTER TABLE skills_files ADD COLUMN graph_json JSONB DEFAULT '{}'::jsonb;
```

### 2f. No regression check

The existing skills pipeline is **untouched**. Entities and relationships are extracted in parallel, not as a replacement. The eval harness should produce the same accuracy as Phase 1.

### Acceptance Criteria
- [ ] `extract_entities` node runs in parallel with decision/workflow/exception extraction
- [ ] Entities are stored in `operational_entities` table
- [ ] Relationships stored in `relationship_edges` table
- [ ] `graph_json` populated in `skills_files`
- [ ] Low-confidence entities flagged with `requires_review`
- [ ] Eval accuracy matches Phase 1 (no regression)

---

## Phase 3: Graph-Assisted Retrieval

**Duration:** 3-4 weeks
**Goal:** The runtime uses graph traversal as the primary retrieval path. Skills remain as fallback.

### Why This Phase Is Worth Doing Early
The condition evaluation engine already exists in `agent/brain_agent.py` (lines 226-290). The entity data exists after Phase 2. The cost of building graph-assisted retrieval is low because the logic is already written — it just needs to be extracted into a standalone module and wired to the graph instead of the in-memory skill list.

### 3a. Standalone condition evaluator

Extract from `backend/agent/brain_agent.py:226-290` into `backend/runtime/condition_eval.py`:

```python
"""
Deterministic condition evaluation engine.
No LLM involved. Pure type-safe comparison.

Handles:
  - Missing context fields → neutral (treated as not applicable, not failure)
  - Type mismatches → caught and logged, never crashed
  - Boundary values → explicit comparison (14 <= 14 is True)
"""

VALID_OPERATORS = {
    "number": {">", ">=", "<", "<=", "==", "!="},
    "string": {"==", "!=", "in", "not_in"},
    "boolean": {"=="},
}


def evaluate_condition(cond: dict, context: dict) -> bool:
    """
    Evaluate a single typed condition against a context dict.
    Returns True if condition is met, False if not met, True if field missing (neutral).
    """
    field = cond.get("field")
    operator = cond.get("operator")
    value = cond.get("value")
    cond_type = cond.get("type", "string")

    ctx_val = context.get(field)
    if ctx_val is None:
        return True  # Missing field = neutral (don't disqualify)

    try:
        if cond_type == "number":
            ctx_val = float(ctx_val)
            value = float(value)
        elif cond_type == "string":
            ctx_val = str(ctx_val).lower().strip()
            if operator in ("in", "not_in") and isinstance(value, list):
                value = [str(v).lower().strip() for v in value]
            else:
                value = str(value).lower().strip()
        elif cond_type == "boolean":
            ctx_val = bool(ctx_val)
            value = bool(value)
    except (TypeError, ValueError):
        return False  # Type mismatch → condition failed
    
    # Operator dispatch
    if operator == "==":
        return ctx_val == value
    elif operator == "!=":
        return ctx_val != value
    elif operator == ">":
        return ctx_val > value
    elif operator == ">=":
        return ctx_val >= value
    elif operator == "<":
        return ctx_val < value
    elif operator == "<=":
        return ctx_val <= value
    elif operator == "in" and isinstance(value, list):
        return ctx_val in value
    elif operator == "not_in" and isinstance(value, list):
        return ctx_val not in value
    
    return False


def evaluate_conditions(conditions: list, context: dict) -> dict:
    """
    Evaluate all conditions. Returns summary:
    {
        "all_met": bool,
        "matched_count": int,
        "total_evaluated": int,
        "details": [{"field": ..., "operator": ..., "value": ..., "matched": bool}]
    }
    """
    if not conditions:
        return {"all_met": True, "matched_count": 0, "total_evaluated": 0, "details": []}
    
    results = []
    matched = 0
    for cond in conditions:
        result = evaluate_condition(cond, context)
        results.append({
            "field": cond.get("field"),
            "operator": cond.get("operator"),
            "value": cond.get("value"),
            "matched": result,
        })
        if result:
            matched += 1
    
    return {
        "all_met": matched == len(conditions),
        "matched_count": matched,
        "total_evaluated": len(conditions),
        "details": results,
    }
```

### 3b. Graph retriever

Create `backend/runtime/graph_retriever.py`:

```python
"""
Graph-based policy retrieval.

Strategy:
1. Extract entity types from the query context (e.g., plan_type=annual → entity "annual_plan")
2. Look up the entity in the operational graph
3. Traverse edges to find applicable policy nodes
4. Evaluate policy conditions against the query context
5. Rank applicable policies by: condition match rate × confidence × priority
6. If graph has insufficient data → return empty (triggers skill fallback)

This module NEVER calls an LLM. It is deterministic.
"""


def identify_query_entities(context: dict, graph: dict) -> list:
    """Map context fields to graph entity IDs."""
    entities = []
    for field, value in (context or {}).items():
        # Try direct entity match
        entity_id = str(value).lower().replace(" ", "_")
        if entity_id in graph.get("entities", {}):
            entities.append(entity_id)
            continue
        
        # Try type-based match (e.g., "plan_type": "annual" → match entity with type "plan")
        for eid, entity in graph.get("entities", {}).items():
            if entity.get("entity_type") == field.replace("_", ""):
                if entity.get("properties", {}).get("type") == str(value).lower():
                    entities.append(eid)
    
    return entities


def retrieve_from_graph(query_text: str, context: dict, graph: dict) -> dict:
    """
    Main entry point for graph-based retrieval.
    Returns:
    {
        "success": bool,
        "policies": [PolicyNode],
        "condition_results": [dict],
        "graph_confidence": float,  # 0.0-1.0 — how much to trust graph result
        "reasoning_steps": [str]
    }
    """
    steps = []
    entities = identify_query_entities(context, graph)
    steps.append(f"Identified entities: {entities}")
    
    if not entities:
        return {
            "success": False,
            "policies": [],
            "condition_results": [],
            "graph_confidence": 0.0,
            "reasoning_steps": steps + ["No entities found in graph — falling back to skills"],
        }
    
    # Find applicable policies via graph edges
    applicable = []
    for edge in graph.get("edges", []):
        if edge["source_id"] in entities and edge["relation_type"] == "has_policy":
            policy = graph.get("policies", {}).get(edge["target_id"])
            if policy:
                applicable.append(policy)
    
    steps.append(f"Found {len(applicable)} candidate policies via graph edges")
    
    if not applicable:
        return {
            "success": False,
            "policies": [],
            "condition_results": [],
            "graph_confidence": 0.2,
            "reasoning_steps": steps + ["No policies connected to found entities"],
        }
    
    # Evaluate conditions for each policy
    from backend.runtime.condition_eval import evaluate_conditions
    
    matched = []
    for policy in applicable:
        cond_result = evaluate_conditions(policy.get("conditions", []), context)
        matched.append({
            "policy": policy,
            "condition_result": cond_result,
        })
    
    # Filter to policies where all conditions are met (or no conditions)
    resolved = [m for m in matched if m["condition_result"]["all_met"]]
    steps.append(f"{len(resolved)} policies passed condition evaluation")
    
    if not resolved:
        return {
            "success": False,
            "policies": [],
            "condition_results": matched,
            "graph_confidence": 0.3,
            "reasoning_steps": steps + ["Policies found but conditions not met"],
        }
    
    # Sort by priority (highest first), then confidence, then specificity
    resolved.sort(
        key=lambda r: (
            r["policy"].get("priority", 0),
            r["policy"].get("confidence", 0.5),
        ),
        reverse=True,
    )
    
    policies = [r["policy"] for r in resolved]
    graph_confidence = min(0.5 + 0.1 * len(resolved), 0.95)
    
    return {
        "success": True,
        "policies": policies[:5],
        "condition_results": [r["condition_result"] for r in resolved],
        "graph_confidence": graph_confidence,
        "reasoning_steps": steps,
    }
```

### 3c. Precedence resolver

Create `backend/runtime/precedence.py`:

```python
"""
Policy precedence resolution.
Uses a HYBRID approach:
  1. Structural patterns detected at compile time ("except", "unless", "notwithstanding")
  2. LLM-refined edges stored in the graph
  3. Algorithmic rules (specificity, authority level, recency)

The key design principle: LLMs can SUGGEST precedence but never AUTHORITATIVELY DEFINE it.
Runtime always applies algorithmic rules as the final check.
"""

import re

# Structural patterns that imply override relationships
OVERRIDE_PATTERNS = [
    (r"(?i)\bexcept\b", "overrides"),
    (r"(?i)\bnotwithstanding\b", "overrides"),
    (r"(?i)\bregardless of\b", "overrides"),
    (r"(?i)\boverrides?\b", "overrides"),
    (r"(?i)\bsupersedes?\b", "overrides"),
    (r"(?i)\bunless\b", "blocked_by"),
    (r"(?i)\bonly if\b", "requires"),
    (r"(?i)\bmust have\b", "requires"),
]

AUTHORITY_LEVEL = {
    "founder": 5,
    "ceo": 5,
    "cfo": 4,
    "cto": 4,
    "vp": 4,
    "director": 3,
    "manager": 3,
    "account_executive": 2,
    "account_manager": 2,
    "engineer": 2,
    "support_lead": 2,
    "support_agent": 1,
    "ops_lead": 3,
}


def detect_structural_precedence(rule_text: str) -> list:
    """Extract precedence signals from rule text using regex patterns."""
    signals = []
    for pattern, relation in OVERRIDE_PATTERNS:
        if pattern.search(rule_text):
            signals.append({
                "pattern": pattern.pattern,
                "relation": relation,
                "confidence": 0.6,  # Structural patterns are medium confidence
            })
    return signals


def resolve_conflicts(policies: list, precedence_edges: list, context: dict) -> list:
    """
    Resolve policy conflicts.
    Order of operations:
      1. Explicit precedence edges (from graph, confidence-weighted)
      2. Structural patterns in policy text
      3. Authority level of invoking role
      4. Specificity (more conditions = more specific)
      5. Recency (last updated wins)
    
    Returns policies sorted by effective priority.
    """
    scored = []
    for policy in policies:
        score = policy.get("priority", 0)
        reasons = []
        
        # 1. Explicit precedence edges
        for edge in precedence_edges:
            if edge["target_id"] == policy.get("id") and edge["relation_type"] == "overrides":
                score += edge.get("confidence", 0.5) * 2
                reasons.append(f"Explicit override edge (confidence={edge.get('confidence', 0.5)})")
        
        # 2. Authority level of the actor
        authority = policy.get("authority")
        if authority:
            auth_level = AUTHORITY_LEVEL.get(authority, 0)
            score += auth_level * 0.5
            reasons.append(f"Authority level {auth_level} ({authority})")
        
        # 3. Specificity (number of conditions = higher specificity)
        condition_count = len(policy.get("conditions", []))
        score += condition_count * 0.3
        if condition_count > 0:
            reasons.append(f"Specificity bonus: {condition_count} conditions")
        
        # 4. Confidence
        score += policy.get("confidence", 0.5) * 0.5
        reasons.append(f"Confidence contribution: {policy.get('confidence', 0.5) * 0.5:.2f}")
        
        scored.append({
            "policy": policy,
            "effective_priority": score,
            "reasons": reasons,
        })
    
    scored.sort(key=lambda x: x["effective_priority"], reverse=True)
    return scored
```

### 3d. Dual-mode runtime

Modify `backend/runtime/brain_agent.py` to use the dual-mode pattern:

```python
async def handle_agent_query(company_id, scenario, context=None, with_brain=True):
    # ... load graph from DB ...
    
    # 1. Try graph retrieval first
    graph_result = retrieve_from_graph(scenario, context, graph)
    
    if graph_result["success"] and graph_result["graph_confidence"] >= GRAPH_CONFIDENCE_THRESHOLD:
        # Graph has enough data → use graph-resolved policies
        policies = graph_result["policies"]
        reasoning_trace = graph_result["reasoning_steps"]
    else:
        # Fall back to skill embedding retrieval (existing logic)
        skills = retrieve_skills_by_embedding(scenario, context)
        policies = convert_skills_to_policies(skills)
        reasoning_trace = ["Graph insufficient — fell back to skill embedding retrieval"]
    
    # 2. Apply constraint resolver (shared, works on both graph and skills)
    actions = constraint_resolver.resolve(policies, context)
    
    # 3. Detect ambiguity via Shannon entropy
    if compute_entropy(actions) > AMBIGUITY_THRESHOLD:
        # Flag for human escalation
        ...
    
    # 4. LLM verbalizes (does not decide)
    llm_response = await llm_verbalize(actions, scenario, context)
    
    # 5. Guardrail: verify LLM didn't override resolver
    llm_response = guardrail_check(llm_response, actions)
    
    return llm_response
```

### 3e. Eval criteria

- Graph-assisted retrieval accuracy ≥ skill-only retrieval accuracy
- Boundary scenarios (COND-*) pass at 80%+ strict (up from ~70%)
- Contradiction scenarios (where rules conflict) improve
- No latency regression (graph traversal is O(1) vs O(n) for embedding comparison)

### Acceptance Criteria
- [ ] `condition_eval.py` is standalone, deterministic, tested separately
- [ ] `graph_retriever.py` returns policies without calling LLM
- [ ] `precedence.py` resolves conflicts algorithmically
- [ ] Dual-mode runtime selects graph or skills per query
- [ ] All eval scenarios pass at Phase 1 levels or higher

---

## Phase 4: Constraint Resolver — LLM Explains, Does Not Decide

**Duration:** 4-6 weeks
**Goal:** The graph determines the admissible action set. The LLM only verbalizes it. Guardrails prevent LLM overrides.

### Important Clarification
This phase is NOT about achieving 100% deterministic policy enforcement for every scenario. That is impossible — some operational contexts are inherently ambiguous (HR decisions, customer empathy, undocumented exceptions).

Instead, this phase builds a **bounded hybrid system**:

```
Can the graph resolve this deterministically?
  YES → enforce deterministically, LLM explains
  NO → surface ambiguity with confidence score, escalate to human if needed
```

The system must know when it doesn't know. That is the real capability.

### 4a. Constraint resolver

Create `backend/runtime/constraint_resolver.py`:

```python
"""
Constraint resolver — the core policy engine.

Deterministically resolves admissible actions from:
  - Applicable policies (from graph or skill retrieval)
  - Typed conditions evaluated against context
  - Precedence hierarchy
  - Authority rules

Returns an ACTION SET with:
  - The single best action (if determinable)
  - All admissible actions (if ambiguity exists)
  - Condition evaluation trace
  - Entropy score (quantified ambiguity)
  - Escalation path if human override needed
"""

from dataclasses import dataclass, field
from typing import List, Optional
from backend.runtime.condition_eval import evaluate_conditions
from backend.runtime.precedence import resolve_conflicts, AUTHORITY_LEVEL


@dataclass
class ResolvedAction:
    action_type: str                    # canonical action type
    category: str                       # operational domain
    confidence: float                   # 0.0-1.0
    requires_approval: bool
    escalation_target: Optional[str]
    policy_applied: str                 # rule text
    evidence: List[str]
    condition_trace: List[dict]         # which conditions matched/failed
    precedence_trace: List[str]         # why this policy won over alternatives


@dataclass
class ConstraintResult:
    primary_action: Optional[ResolvedAction]
    all_admissible_actions: List[ResolvedAction]
    is_ambiguous: bool
    entropy: float
    escalation_required: bool
    escalation_target: Optional[str]
    reasoning_steps: List[str]


AMBIGUITY_ENTROPY_THRESHOLD = 0.75  # Shannon entropy > 0.75 → ambiguous
MIN_CONFIDENCE_FOR_AUTO_ACTION = 0.40


def compute_entropy(actions: List[ResolvedAction]) -> float:
    """Shannon entropy of action confidences. Higher = more ambiguous."""
    if not actions:
        return 1.0
    scores = [a.confidence for a in actions]
    total = sum(scores)
    if total <= 0:
        return 1.0
    probs = [s / total for s in scores]
    import math
    entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    max_entropy = math.log2(len(probs)) if len(probs) > 1 else 1.0
    return entropy / max_entropy if max_entropy > 0 else 1.0


def resolve(policies: list, context: dict, authority_rules: list = None) -> ConstraintResult:
    """
    Main entry point. Given applicable policies and query context,
    determine the correct action set.
    """
    steps = []
    
    # Step 1: Evaluate conditions for each policy
    for policy in policies:
        cond_result = evaluate_conditions(policy.get("conditions", []), context)
        policy["_condition_eval"] = cond_result
    steps.append(f"Evaluated conditions for {len(policies)} policies")
    
    # Step 2: Filter to policies where all conditions met
    applicable = [p for p in policies if p.get("_condition_eval", {}).get("all_met", True)]
    steps.append(f"{len(applicable)} policies passed condition evaluation")
    
    if not applicable:
        return ConstraintResult(
            primary_action=None,
            all_admissible_actions=[],
            is_ambiguous=True,
            entropy=1.0,
            escalation_required=False,
            escalation_target=None,
            reasoning_steps=steps + ["No applicable policies found"],
        )
    
    # Step 3: Resolve conflicts (precedence, authority, specificity)
    resolved = resolve_conflicts(applicable, [], context)
    steps.append(f"Resolved {len(resolved)} policies by precedence")
    
    # Step 4: Apply authority rules
    if authority_rules:
        resolved = _apply_authority_rules(resolved, context.get("requested_by"), authority_rules)
        steps.append("Applied authority rules")
    
    # Step 5: Build action set
    actions = []
    for r in resolved:
        policy = r["policy"]
        effect = policy.get("effect", "ambiguous")
        
        # Map effect to action_type
        action_type = effect
        
        actions.append(ResolvedAction(
            action_type=action_type,
            category=policy.get("category", "general"),
            confidence=r["effective_priority"] / 10.0,  # normalize
            requires_approval=policy.get("requires_approval", False),
            escalation_target=policy.get("escalation_target"),
            policy_applied=policy.get("rule_text", ""),
            evidence=policy.get("evidence", []),
            condition_trace=policy.get("_condition_eval", {}).get("details", []),
            precedence_trace=r.get("reasons", []),
        ))
    
    # Step 6: Detect ambiguity
    entropy = compute_entropy(actions)
    is_ambiguous = entropy > AMBIGUITY_ENTROPY_THRESHOLD
    
    steps.append(f"Computed entropy: {entropy:.3f} ({'ambiguous' if is_ambiguous else 'clear'})")
    
    # Step 7: Determine escalation
    escalation_required = any(a.requires_approval for a in actions)
    escalation_target = None
    if escalation_required:
        # Pick highest-confidence action's escalation target
        for a in actions:
            if a.requires_approval and a.escalation_target:
                escalation_target = a.escalation_target
                break
    
    primary = actions[0] if actions and not is_ambiguous else None
    
    return ConstraintResult(
        primary_action=primary,
        all_admissible_actions=actions,
        is_ambiguous=is_ambiguous,
        entropy=entropy,
        escalation_required=escalation_required,
        escalation_target=escalation_target,
        reasoning_steps=steps,
    )


def _apply_authority_rules(resolved: list, requester_role: str, authority_rules: list) -> list:
    """Filter actions based on whether the requester has authority to perform them."""
    if not requester_role:
        return resolved
    
    requester_level = AUTHORITY_LEVEL.get(requester_role, 0)
    
    filtered = []
    for r in resolved:
        policy = r["policy"]
        required_authority = policy.get("authority")
        required_level = AUTHORITY_LEVEL.get(required_authority, 0)
        
        if requester_level >= required_level:
            filtered.append(r)
        else:
            # Keep but mark as requiring escalation
            policy["requires_approval"] = True
            policy["escalation_target"] = required_authority
            filtered.append(r)
    
    return filtered
```

### 4b. LLM becomes verbalizer

The brain agent prompt changes from:

> "You are a policy reasoning engine. Decide what to do."

To:

> "You are a policy explainer. The constraint engine has already determined the correct action.
> Your ONLY job is to explain it in natural language. Do not override the action.
> 
> Constraint Engine Decision:
> - Action: {action_type}
> - Confidence: {confidence}
> - Conditions met: {condition_trace}
> - Precedence: {precedence_trace}
> 
> Output the following JSON. The action_type MUST match the constraint engine's decision exactly."

### 4c. Guardrails — LLM cannot override

```python
# backend/runtime/guardrails.py

def guardrail_check(llm_response: dict, resolver_result: ConstraintResult) -> dict:
    """
    Verify LLM output matches the constraint resolver's decision.
    If action_type diverges, OVERRIDE with resolver's decision.
    Log the override for monitoring.
    """
    if resolver_result.primary_action is None:
        # Resolver was ambiguous — allow LLM to handle with caveat
        return llm_response
    
    resolver_action = resolver_result.primary_action.action_type
    llm_action = llm_response.get("action_type", "")
    
    if llm_action != resolver_action:
        # LLM tried to override — log and correct
        print(f"[GUARDRAIL] LLM override attempt: LLM said '{llm_action}', "
              f"resolver said '{resolver_action}'. Using resolver decision.")
        
        llm_response["action_type"] = resolver_action
        llm_response["_guardrail_override"] = True
        llm_response["_guardrail_reason"] = (
            f"LLM output '{llm_action}' diverged from constraint "
            f"resolver decision '{resolver_action}'. Overridden."
        )
    
    return llm_response
```

### 4d. Eval shift

| Metric | Phase 1-3 | Phase 4 |
|---|---|---|
| LLM action_type accuracy | Primary metric | Secondary (formatting quality) |
| Resolver action accuracy | Not tracked | Primary metric |
| Resolver-vs-LLM agreement | Not tracked | Must be 100% |
| Guardrail override fires | Not tracked | Must be detected, not prevented |
| Ambiguity detection | Not tracked | Must match human judgment on DET-* |
| Boundary correctness | LLM-dependent | Deterministic via resolver |

### 4e. New adversarial scenarios

Add to the eval harness:

```python
# New scenarios for Phase 4
ADV_SCENARIOS_PHASE4 = [
    {
        "id": "RESOLVE-01",
        "scenario": "Customer on annual plan, 9 days since purchase, requesting $700 refund.",
        "context": {"plan_type": "annual", "days_since_purchase": 9, "refund_amount": 700},
        "expected_action": "get_founder_approval",
        "rationale": "Tests multi-condition resolution: annual (full refund) + >$500 (escalate). Precedence: >$500 overrides standard refund."
    },
    {
        "id": "RESOLVE-02",
        "scenario": "Enterprise customer, 5 days since purchase, requesting refund.",
        "context": {"plan_type": "enterprise", "days_since_purchase": 5},
        "expected_action": "escalate",
        "rationale": "Enterprise override: enterprise rules always override standard refund window."
    },
    {
        "id": "RESOLVE-03",
        "scenario": "HR requesting approval for engineer offer with equity package.",
        "context": {"role": "engineer", "stage": "offer", "includes_equity": True},
        "expected_action": "get_founder_approval",
        "rationale": "Dual precedent: engineering offers need founder approval AND offers with equity need founder approval."
    },
    {
        "id": "ENTROPY-01",
        "scenario": "Minor billing issue with no clear priority.",
        "context": {"issue": "billing_question", "amount": 50},
        "expected_action": "ambiguous",
        "rationale": "Intentionally vague — should result in high entropy and 'ambiguous' output."
    },
    {
        "id": "GUARDRAIL-01",
        "scenario": "Customer requesting refund for annual plan, 9 days since purchase, $300.",
        "context": {"plan_type": "annual", "days_since_purchase": 9, "refund_amount": 300},
        "expected_action": "approve",  # Must be approve. If LLM says anything else, guardrail must fire
        "rationale": "Tests guardrail: annual+14days+<$500 = approve. Any other LLM output must be overridden."
    },
]
```

### Acceptance Criteria
- [ ] Constraint resolver produces deterministic action set for unambiguous scenarios
- [ ] Ambiguity detected by entropy (DET-* scenarios produce "ambiguous")
- [ ] Entropy threshold tuned to match human judgment
- [ ] Guardrail overrides LLM when action_type diverges
- [ ] No regression: Phase 3 accuracy maintained or improved
- [ ] Escalation path identified when no clear action exists

---

## Phase 5: Production Hardening (Ongoing)

**Duration:** Ongoing — no fixed timeline
**Goal:** Reliable, observable, maintainable system.

### 5a. Incremental compilation

Currently, the entire pipeline runs on every compile request. As data grows, this becomes expensive and slow.

Instead:
- Track sha256 per source file
- Only re-extract from changed files
- Patch the graph incrementally rather than rebuilding
- Confidence decreases for unchanged policies that reference changed sources

### 5b. Live source connectors

Replace manual file uploads with real-time ingestion:

| Connector | What it ingests | Trigger |
|---|---|---|
| Slack | Messages from specified channels | Webhook on new message |
| Notion | SOP pages, runbooks | Webhook on page update |
| Zendesk | Support tickets | API poll every N minutes |
| Google Docs | Policy documents | Webhook on document change |

### 5c. Feedback loop

The most valuable source of data is what happens AFTER the system makes a recommendation:

```
Query → system recommends action → human acts → outcome logged
  → Successful → increase confidence for matched policies
  → Human overrode → log divergence, flag for review
  → Multiple human overrides → trigger re-extraction for affected sources
```

The feedback loop makes the system improve over time.

### 5d. Multi-model routing

| Task | Recommended Model | Why |
|---|---|---|
| Extraction (decisions, workflows, etc.) | Qwen 2.5 72B or Llama 3 70B | Needs high comprehension |
| Entity extraction | Qwen 2.5 72B | Structured output, needs precision |
| Condition evaluation | None (deterministic code) | Zero cost, guaranteed correct |
| Precedence detection | Regex + small LLM refinement | Mostly structural patterns |
| Constraint resolution | None (deterministic code) | Zero cost, guaranteed correct |
| LLM verbalization | Qwen 2.5 7B or Llama 3 8B | Smallest capable model — just needs language |

### Acceptance Criteria
- [ ] Incremental compile: 10+ source changes compiled in <30 seconds
- [ ] At least one live connector (Slack or Notion) working
- [ ] Feedback loop operational — system improves from corrections
- [ ] Extraction uses cheaper model than verbalization (cost optimization)

---

## Data Model Evolution Summary

### Phase 1
```json
skills_file: {
  "skills": [
    {
      "id": "handle_refund_request",
      "category": "Customer Support",
      "rule": "Approve full refund for annual plans within 14 days",
      "operational": {
        "department": "customer_support",
        "severity": "policy",
        "action_type": "approve",
        "workflow_type": "refund"
      },
      "conditions": [
        {"field": "days_since_purchase", "operator": "<=", "value": 14, "type": "number"},
        {"field": "plan_type", "operator": "==", "value": "annual", "type": "string"}
      ],
      "confidence": 0.85,
      "evidence": [...],
      "embedding_vector": [...]
    }
  ],
  "meta": {...}
}
```

### Phase 2 (adds)
```json
skills_file: {
  "skills": [...],  // unchanged
  "graph_json": {
    "entities": {
      "customer_annual": {
        "entity_type": "customer",
        "properties": {"tier": "annual", "refund_window_days": 14},
        "confidence": 0.9
      },
      "role_founder": {
        "entity_type": "role",
        "properties": {"approval_limit": null},
        "confidence": 0.95
      }
    },
    "policies": {
      "refund_annual_14day": {
        "rule_text": "...",
        "conditions": [...],
        "effect": "approve",
        "entity_id": "customer_annual"
      }
    },
    "edges": [
      {"source_id": "customer_annual", "target_id": "refund_annual_14day",
       "relation_type": "has_policy", "conditions": []}
    ],
    "authority_rules": [
      {"role": "founder", "can_approve": ["refund"], "up_to_amount": null}
    ]
  }
}
```

### Phase 3-4
```json
skills_file: {
  "skills": [...],                      // fallback
  "graph_json": {...},                  // primary retrieval
  "precedence_edges": [...],            // conflict resolution
  "entity_embeddings": {...}            // entity-level semantic search
}
```

---

## Runtime Evolution Summary

```
Phase 1: query → embed → cosine sim → top 5 skills → LLM decides

Phase 2: query → embed → cosine sim → top 5 skills + graph entities → LLM decides

Phase 3: query → graph traversal → resolved policies → LLM decides
         (fallback: skill embedding retrieval when graph sparse)

Phase 4: query → graph traversal → constraint resolver →
           → admissible action set → LLM verbalizes → guardrail verification → output
         (skills remain as supporting context in prompt)

Phase 5: query → incremental graph → constraint resolver →
           → feedback-aware action set → LLM verbalizes → guardrail → log outcome
```

---

## Evaluation Evolution

```python
# Phase 1-2:
strict_accuracy = compare(actual_action_type, expected_action)
relaxed_accuracy = compare(actual_recommended_action, expected_action)

# Phase 3 adds:
graph_retrieval_accuracy = compare(graph_action, expected) >= skill_retrieval_accuracy

# Phase 4:
resolver_accuracy = compare(resolver_action, expected)  # Primary metric
llm_agreement = compare(llm_action, resolver_action)    # Must be 100%
guardrail_fires = count(llm_override_attempts)           # Detect, don't prevent
ambiguity_detection = compare(entropy_flag, human_judgment)  # Phase 4+

# Phase 5 adds:
feedback_improvement_rate = measure(accuracy_over_time)  # Should increase
incremental_compile_time = measure(seconds_per_compile)  # Should decrease
```

---

## Guardrails: When to Stop

| Scenario type | Phase 1 target | Phase 4 target |
|---|---|---|
| Standard (REF, CS, ENG, HR, PRICE) | 90% relaxed | 95% strict |
| Boundary (COND-*, RESOLVE-*) | 70% relaxed | 100% deterministic |
| Adversarial (ADV-*) | 80% relaxed | 90% strict |
| Ambiguity (DET-*, ENTROPY-*) | "ambiguous" output | Matches human judgment |

**If any phase causes regression, stop and stabilize before proceeding.**

The system's most important capability is knowing when it doesn't know. If ambiguity detection is wrong more than 20% of the time, the system is not ready for Phase 4.

---

## Open Questions and Answers

These were discussed and resolved during architecture review:

### 1. Graph database — Neo4j vs pgvector vs in-memory?

**Answer: In-memory dict + JSONB persistence now. Maybe pgvector adjacency later. Probably never Neo4j.**

Rationale:
- The graph for a single company is small (< 10,000 nodes)
- The graph schema is still evolving — you don't know the final structure yet
- Neo4j introduces operational overhead, deployment complexity, and cognitive load with zero benefit at this stage
- pgvector adjacency (storing edges in Postgres with vector search) may become useful at 100+ companies
- Graph databases are a fetishized technology — most production systems never need them

### 2. Entity extraction quality — can LLMs reliably extract entities?

**Answer: No. Use confidence-weighted extraction with tiers.**

- High confidence (≥0.80): Explicit policies from structured docs → auto-accept
- Medium confidence (0.50-0.79): Implicit patterns from Slack/tickets → mark as tentative
- Low confidence (<0.50): Ambiguous or contradictory mentions → require review

The `requires_review` flag in `operational_entities` table enables a human-in-the-loop workflow without blocking the pipeline.

### 3. Precedence encoding — LLM or structural?

**Answer: Hybrid. Structural pattern matching + LLM refinement. Never LLM-alone.**

Structural patterns ("except", "unless", "notwithstanding", "overrides") provide high-precision candidate edges. LLM refines ambiguous cases. Runtime always applies algorithmic checks as the final authority.

LLMs can SUGGEST precedence. They cannot AUTHORITATIVELY DEFINE it. Hallucinated governance is dangerous.

### 4. Multi-company isolation?

**Answer: company_id column is sufficient for now. Do not engineer deep tenancy yet.**

True multi-tenant isolation involves query isolation, cache isolation, embedding isolation, runtime isolation, eval isolation, and logging isolation. Building this before validating the architecture with a single customer is premature optimization.

### 5. Cold start — how many sources before graph is useful?

**Answer: Skills remain as the permanent fallback. Graph is additive, not a replacement.**

The cold start problem is not a transitional issue — it's a permanent architectural feature. The system always uses graph when graph confidence is high enough, and always falls back to skills when it isn't. This dual-mode design makes the cold start problem irrelevant at runtime.

---

## Technology Decisions

| Decision | Phase 1 | Phase 2+ | Rationale |
|---|---|---|---|
| LLM provider | OpenRouter | OpenRouter + fallback | Already configured, works today |
| Model | Llama 3.3 70B | Qwen 2.5 72B + smaller models | Extraction needs size; verbalization doesn't |
| Embedding | all-MiniLM-L6-v2 | all-MiniLM-L6-v2 | Already implemented, fast, CPU-only |
| Graph storage | JSONB in skills_files | JSONB + entity tables | Keeps graph co-located with skills |
| Condition engine | In brain_agent.py | Standalone module | Extract for reuse |
| Precedence | None | Structural patterns + LLM | Safe incremental approach |
| Multi-tenancy | company_id only | company_id + indexes | Premature optimization is the root of evil |
| Frontend | Next.js 16 | Next.js 16 (graph viewer) | Graph visualization in Phase 3 |

---

## Product-Value Timeline

```
Week 1  ─ Phase 1 completes → Working pipeline, skills in DB, brain agent responds
         ─ You can DEMO: "Compile company knowledge, ask questions, get answers"

Month 1 ─ Phase 2 completes → Entities extracted, confidence-tagged
         ─ You can DEMO: "System understands your company structure, not just text"

Month 2 ─ Phase 3 completes → Graph-aware retrieval improves accuracy
         ─ You can DEMO: "Better answers because system reasons about relationships"

Month 3 ─ Phase 4 completes → Deterministic policy enforcement
         ─ You can DEMO: "System makes reliable decisions, knows when it doesn't know"

Quarter 3+ ─ Phase 5 → Live connectors, feedback loop, production hardening
           ─ You can SELL: "Your company's operational brain that gets better over time"
```

---

## Handoff

**Phase 1** → Ready for direct implementation. All code exists in the old paths. Needs porting.

**Phase 2** → Needs architecture review of entity extraction prompt and confidence thresholds. Entity model is designed above — implementation follows Phase 1 convergence.

**Phase 3** → Ready for implementation once Phase 2 entities are in DB. Condition evaluator already exists in old code — needs extraction into standalone module.

**Phase 4** → Needs eval data from Phase 3 to tune entropy thresholds. Do NOT start Phase 4 until Phase 3 data shows where ambiguity actually occurs.

**Phase 5** → Needs product clarification: which live connector first? Slack? Notion? Depends on customer.
