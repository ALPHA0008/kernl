import json

with open("backend/tests/last_compiled_brain.json") as f:
    brain = json.load(f)

skills = brain.get("skills", [])
graph = brain.get("graph_json", {})
meta = brain.get("metadata_json", {})
stats = graph.get("stats", {})

print("=" * 60)
print("COMPILED BRAIN OUTPUT - Rivanly Inc.")
print("=" * 60)

print(f"\nCompiled: {brain.get('meta', {}).get('compiled_at', '?')}")
print(f"Duration: {brain.get('meta', {}).get('duration_ms', 0)}ms")
print(f"Total Skills: {len(skills)}")

print("\n" + "=" * 60)
print("SKILLS")
print("=" * 60)

for s in skills:
    print(f"\n  [{s.get('confidence'):.2f}] {s.get('id')}")
    print(f"         Dept: {s.get('category')}")
    print(f"         Rule: {s.get('rule')[:120]}")
    print(f"         Evidence: {len(s.get('evidence', []))} source(s)")

print("\n" + "=" * 60)
print("OPERATIONAL GRAPH")
print("=" * 60)
print(f"\n  {stats.get('entity_count', 0)} entities")
print(f"  {stats.get('edge_count', 0)} relationships")
print(f"  {stats.get('authority_count', 0)} authority rules")
print(f"  {stats.get('policy_count', 0)} policies")

print("\n  Entities:")
for eid, e in graph.get("entities", {}).items():
    print(f"    {eid} ({e.get('entity_type', '?')})")

print("\n  Edges:")
for edge in graph.get("edges", []):
    print(
        f"    {edge.get('source_id')} --{edge.get('relation_type')}--> {edge.get('target_id')}"
    )

print("\n  Authority Rules:")
for role, rule in graph.get("authority_rules", {}).items():
    print(
        f"    {role}: can_approve={rule.get('can_approve', [])}, up_to={rule.get('up_to_amount')}"
    )

print("\n" + "=" * 60)
print("OPERATIONAL METADATA")
print("=" * 60)
print(f"\n  Action Types ({len(meta.get('action_types', []))}):")
for a in meta.get("action_types", []):
    print(f"    {a.get('action', '?')} (specificity={a.get('specificity', 0)})")

valid_sets = meta.get("valid_sets", {})
print(f"\n  Valid Departments: {valid_sets.get('departments', [])}")
print(f"  Valid Severities: {valid_sets.get('severities', [])}")
print(f"  Valid Customer Tiers: {valid_sets.get('customer_tiers', [])}")
print(f"  Valid Workflow Types: {valid_sets.get('workflow_types', [])}")
print(f"  Condition Fields: {valid_sets.get('condition_fields', [])}")

al = meta.get("authority_levels", [])
print(f"\n  Authority Levels ({len(al)}):")
for a in al[:5]:
    print(f"    {a.get('role', '?')} = level {a.get('level', 0)}")

print()
