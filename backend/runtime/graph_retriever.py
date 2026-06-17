"""
Graph-based policy retrieval.

Strategy:
1. Extract entity types from the query context
2. Look up the entity in the operational graph
3. Traverse edges to find applicable policy nodes
4. Evaluate policy conditions against the query context
5. Rank applicable policies by: condition match rate x confidence x priority
6. If graph has insufficient data -> return empty (triggers skill fallback)

This module NEVER calls an LLM. It is deterministic.
"""


def identify_query_entities(context: dict, graph: dict) -> list:
    entities = []
    if not context:
        return entities
    for field, value in context.items():
        entity_id = str(value).lower().replace(" ", "_")
        if entity_id in graph.get("entities", {}):
            entities.append(entity_id)
            continue
        for eid, entity in graph.get("entities", {}).items():
            if entity.get("entity_type") == field.lower().replace("_", ""):
                if entity.get("properties", {}).get("type") == str(value).lower():
                    entities.append(eid)
    return entities


def retrieve_from_graph(query_text: str, context: dict, graph: dict) -> dict:
    steps = []
    entities = identify_query_entities(context, graph)
    steps.append(f"Identified entities: {entities}")

    if not entities:
        return {
            "success": False,
            "policies": [],
            "condition_results": [],
            "graph_confidence": 0.0,
            "reasoning_steps": steps + ["No entities found in graph"],
        }

    applicable = []
    for edge in graph.get("edges", []):
        if (
            edge.get("source_id") in entities
            and edge.get("relation_type") == "has_policy"
        ):
            policy = graph.get("policies", {}).get(edge.get("target_id"))
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

    from backend.runtime.condition_eval import evaluate_conditions

    matched = []
    for policy in applicable:
        cond_result = evaluate_conditions(policy.get("conditions", []), context)
        matched.append(
            {
                "policy": policy,
                "condition_result": cond_result,
            }
        )

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
