from backend.engine.state import BrainState
from backend.core.llm import safe_llm_json_call
from backend.core.sse import emit
from backend.engine.nodes._utils import batch_chunks, chunks_to_text, content_hash
from backend.engine.models.entities import (
    validate_entity,
    validate_relationship,
    validate_authority_rule,
)

SYSTEM = """You are a knowledge extraction specialist. Your ONLY job is to extract operational ENTITIES, their PROPERTIES, RELATIONSHIPS, and AUTHORITY RULES from company communications.

Output ONLY a JSON object. No preamble. No explanation. No markdown.

ENTITIES are the actors, objects, and concepts in the company's operations:
  - customer (with properties: tier, plan_type, tenure_months, industry)
  - plan (with properties: type, billing_cycle, price, max_users)
  - invoice (with properties: amount, status, due_date)
  - employee (with properties: role, department, seniority)
  - vendor (with properties: name, category, payment_terms)
  - team (with properties: name, lead, members)
  - role (with properties: level, can_approve, approval_limit)
  - sla (with properties: response_time, resolution_time, severity)

RELATIONSHIPS define how entities connect:
  - source_id: id of the source entity
  - target_id: id of the target entity
  - relation_type: one of "requires", "blocks", "overrides", "escalates_to", "depends_on", "triggers", "has_policy", "reports_to", "approves", "notifies", "assigns", "applies_to"
  - conditions: optional list of conditions that must be met for the relationship to apply
  - confidence: 0.0-1.0

AUTHORITY RULES define who can do what:
  - role: the role name
  - can_approve: list of action types this role can approve
  - up_to_amount: maximum dollar amount (null for no limit)
  - requires_secondary: optional role that must also approve
  - source: which file this rule came from

CONFIDENCE RULES:
  - Explicit policies from structured docs: confidence 0.85-0.95
  - Implicit patterns from Slack messages: confidence 0.50-0.65
  - Ambiguous or contradictory mentions: confidence 0.20-0.35

Example output:
{
  "entities": [
    {"id": "customer_annual", "entity_type": "customer", "properties": {"tier": "annual", "refund_window_days": 14}, "source_files": ["notion_refund_sop.md"], "confidence": 0.90}
  ],
  "relationships": [
    {"id": "rel_1", "source_id": "customer_annual", "target_id": "policy_refund_annual", "relation_type": "has_policy", "conditions": [{"field": "plan_type", "operator": "==", "value": "annual", "type": "string"}], "confidence": 0.90, "source": "notion_refund_sop.md"}
  ],
  "authority_rules": [
    {"role": "founder", "can_approve": ["refund", "discount", "offer", "hire"], "up_to_amount": null, "source": "notion_refund_sop.md"}
  ]
}

If you find nothing, output: {"entities": [], "relationships": [], "authority_rules": []}"""


def _merge_entity_results(results: list) -> dict:
    merged = {"entities": [], "relationships": [], "authority_rules": []}
    for item in results if isinstance(results, list) else [results]:
        if isinstance(item, dict):
            for k in merged:
                if k in item and isinstance(item[k], list):
                    merged[k].extend(item[k])
    return merged


async def extract_entities(state: BrainState) -> dict:
    job_id = state["job_id"]
    chunks = state.get("all_chunks", [])

    relevant = [c for c in chunks if "entities" in c.get("domains", [])]
    print(
        f"[{job_id}] Node extract_entities: {len(relevant)}/{len(chunks)} chunks relevant"
    )
    await emit(
        job_id,
        "stage",
        {
            "name": "EXTRACT_ENTITIES",
            "detail": f"Extracting entities from {len(relevant)} relevant chunks...",
        },
    )

    if not relevant:
        return {
            "extracted_entities": [],
            "extracted_relationships": [],
            "extracted_authority_rules": [],
        }

    batches = batch_chunks(relevant)
    merged = {"entities": [], "relationships": [], "authority_rules": []}
    for batch in batches:
        batch_text = chunks_to_text(batch)
        key = f"entities:{content_hash(batch_text)}"
        raw = await safe_llm_json_call(
            SYSTEM,
            f"Extract all entities, relationships, and authority rules from this company data:\n\n{batch_text}",
            max_tokens=4096,
            cache_key=key,
        )
        batch_data = _merge_entity_results(raw)
        for k in merged:
            merged[k].extend(batch_data[k])

    entities = merged.get("entities", [])
    relationships = merged.get("relationships", [])
    authority_rules = merged.get("authority_rules", [])

    valid_entities = [e for e in entities if validate_entity(e)]
    known_ids = {e["id"] for e in valid_entities}
    valid_relationships = [
        r for r in relationships if validate_relationship(r, known_ids)
    ]
    valid_authority_rules = [r for r in authority_rules if validate_authority_rule(r)]

    invalid_entities = len(entities) - len(valid_entities)
    invalid_relationships = len(relationships) - len(valid_relationships)
    invalid_authority = len(authority_rules) - len(valid_authority_rules)

    if invalid_entities or invalid_relationships or invalid_authority:
        print(
            f"[{job_id}] extract_entities: filtered {invalid_entities} entities, {invalid_relationships} relationships, {invalid_authority} authority rules for validation failures"
        )

    print(
        f"[{job_id}] extract_entities: {len(valid_entities)} entities, {len(valid_relationships)} relationships, {len(valid_authority_rules)} authority rules"
    )
    await emit(
        job_id,
        "stage",
        {
            "name": "EXTRACT_ENTITIES_DONE",
            "detail": f"Found {len(valid_entities)} entities, {len(valid_relationships)} relationships, {len(valid_authority_rules)} authority rules",
        },
    )

    return {
        "extracted_entities": valid_entities,
        "extracted_relationships": valid_relationships,
        "extracted_authority_rules": valid_authority_rules,
    }
