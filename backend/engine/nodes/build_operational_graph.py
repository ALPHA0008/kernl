from backend.engine.state import BrainState
from backend.core.sse import emit
from backend.engine.models.entities import AUTHORITY_LEVEL


async def build_operational_graph(state: BrainState) -> dict:
    job_id = state["job_id"]
    company_id = state["company_id"]

    if state.get("operational_graph"):
        print(f"[{job_id}] build_operational_graph: already built, skipping")
        return {}

    print(
        f"[{job_id}] Node build_operational_graph: building graph from extracted entities"
    )
    await emit(
        job_id,
        "stage",
        {
            "name": "BUILD_GRAPH",
            "detail": "Building operational graph from extracted entities...",
        },
    )

    raw_entities = state.get("extracted_entities", [])
    raw_relationships = state.get("extracted_relationships", [])
    raw_authority_rules = state.get("extracted_authority_rules", [])

    entities = {}
    for e in raw_entities:
        eid = e.get("id", "")
        if not eid:
            continue
        if eid in entities:
            existing_conf = entities[eid].get("confidence", 0)
            new_conf = e.get("confidence", 0)
            if new_conf > existing_conf:
                entities[eid] = e
        else:
            entities[eid] = e

    entity_ids = set(entities.keys())

    edges = []
    for r in raw_relationships:
        if r.get("source_id") in entity_ids and r.get("target_id") in entity_ids:
            edges.append(r)

    authority_index = {}
    for rule in raw_authority_rules:
        role = rule.get("role", "").lower().strip()
        if role:
            authority_index[role] = {
                "can_approve": rule.get("can_approve", []),
                "up_to_amount": rule.get("up_to_amount"),
                "requires_secondary": rule.get("requires_secondary"),
                "source": rule.get("source", ""),
            }

    policies_from_decisions = []
    for d in state.get("raw_decisions", []):
        policies_from_decisions.append(
            {
                "id": d.get("id", ""),
                "rule_text": d.get("rule", ""),
                "category": d.get("category", ""),
                "rationale": d.get("rationale", ""),
                "effect": "approve",
                "priority": 0,
                "conditions": [],
                "evidence": d.get("evidence", []),
                "confidence": 0.7,
            }
        )

    for e in raw_entities:
        if e.get("confidence", 1.0) < 0.4:
            e["requires_review"] = True

    low_conf_entities = [eid for eid, e in entities.items() if e.get("requires_review")]
    if low_conf_entities:
        print(
            f"[{job_id}] build_operational_graph: flagged {len(low_conf_entities)} low-confidence entities for review: {low_conf_entities}"
        )

    operational_graph = {
        "entities": entities,
        "edges": edges,
        "authority_rules": authority_index,
        "policies": {p["id"]: p for p in policies_from_decisions if p["id"]},
        "entity_ids": list(entity_ids),
        "stats": {
            "entity_count": len(entities),
            "edge_count": len(edges),
            "authority_count": len(authority_index),
            "policy_count": len(policies_from_decisions),
            "flagged_for_review": len(low_conf_entities),
        },
    }

    print(
        f"[{job_id}] build_operational_graph: graph built — {len(entities)} entities, {len(edges)} edges, {len(authority_index)} authority rules"
    )
    await emit(
        job_id,
        "stage",
        {
            "name": "BUILD_GRAPH_DONE",
            "detail": f"Graph: {len(entities)} entities, {len(edges)} edges, {len(authority_index)} authority rules",
        },
    )

    return {"operational_graph": operational_graph}
