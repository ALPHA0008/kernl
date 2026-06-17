import asyncio, os, sys, json, time, uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv("backend/.env", override=True)

from backend.engine.graph import build_compilation_graph


async def run():
    graph = build_compilation_graph()
    state = {
        "job_id": str(uuid.uuid4()),
        "company_id": "higgsfield",
        "source_files": [],
        "all_chunks": [],
        "raw_decisions": [],
        "workflow_steps": [],
        "exception_rules": [],
        "contradictions": [],
        "extracted_entities": [],
        "extracted_relationships": [],
        "extracted_authority_rules": [],
        "operational_graph": {},
        "operational_metadata": {},
        "draft_skills": [],
        "skills_with_evidence": [],
        "final_skills": [],
        "skills_file": {},
        "brain_version": "",
        "start_time": time.time(),
        "errors": [],
    }
    final = await graph.ainvoke(state)
    skills = final.get("final_skills", [])
    graph_data = final.get("operational_graph", {})
    meta = final.get("operational_metadata", {})
    stats = graph_data.get("stats", {})

    print(f"\n=== HIGGSFIELD COMPILATION ===")
    print(f"Skills: {len(skills)}")
    for s in skills:
        print(f"  - {s.get('id')} ({s.get('confidence')} conf) [{s.get('category')}]")
        print(f"    Rule: {s.get('rule', '')[:120]}")
    print(
        f"\nOperational Graph: {stats.get('entity_count', 0)} entities, {stats.get('edge_count', 0)} edges, {stats.get('authority_count', 0)} authority rules"
    )
    print(f"  Entities: {list(graph_data.get('entities', {}).keys())[:10]}")
    edge_strs = [
        f"{e.get('source_id', '?')}->{e.get('target_id', '?')}"
        for e in graph_data.get("edges", [])[:10]
    ]
    print(f"  Edges: {edge_strs}")
    print(f"  Authority Roles: {list(graph_data.get('authority_rules', {}).keys())}")
    print(
        f"Metadata: {len(meta.get('action_types', []))} action types, {len(meta.get('valid_sets', {}).get('departments', []))} depts"
    )

    out = {"skills": skills, "graph_json": graph_data, "metadata_json": meta}
    out_path = os.path.join(os.path.dirname(__file__), "tests", "higgsfield_brain.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    asyncio.run(run())
