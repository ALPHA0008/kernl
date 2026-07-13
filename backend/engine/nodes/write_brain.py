import time
import json
import uuid
import datetime
from backend.engine.state import BrainState
from backend.bundle.converter import extraction_warnings, skills_to_drafts
from backend.core.db.supabase import get_client
from backend.core.llm import get_embeddings
from backend.core.sse import emit


async def write_brain(state: BrainState) -> dict:
    job_id = state.get("job_id")
    company_id = state.get("company_id")
    final_skills = state.get("final_skills", [])
    start_time = state.get("start_time", time.time())
    duration_ms = int((time.time() - start_time) * 1000)

    print(
        f"[{job_id}] Node write_brain: persisting {len(final_skills)} skills for {company_id}"
    )
    await emit(
        job_id,
        "stage",
        {
            "name": "WRITING_DB",
            "detail": f"Pre-embedding and persisting {len(final_skills)} skills",
        },
    )

    skill_texts = [
        f"{s.get('category', '')} {s.get('rule', '')} {s.get('rationale', '')}"
        for s in final_skills
    ]
    embeddings = get_embeddings(skill_texts)
    for skill, emb in zip(final_skills, embeddings):
        skill["embedding_vector"] = emb

    # Step 6 (V1): extraction output is a PROPOSAL, not authority. Convert
    # skills to reviewable policy drafts and surface silent-extraction
    # failures (W8) as visible warnings instead of quiet successes.
    drafts = skills_to_drafts(final_skills, company_id)
    warnings = extraction_warnings(dict(state))
    if warnings:
        for w in warnings:
            print(f"[{job_id}] WARNING {w}")
        await emit(job_id, "compile_warnings", {"warnings": warnings})
    await emit(
        job_id,
        "stage",
        {
            "name": "DRAFTS_PROPOSED",
            "detail": (
                f"{len(drafts)} policy drafts proposed for review "
                f"({sum(1 for d in drafts if d.publishable)} publishable as-is); "
                "drafts are never runtime authority"
            ),
        },
    )

    operational_graph = state.get("operational_graph", {})
    operational_metadata = state.get("operational_metadata", {})

    skills_file = {
        "skills": final_skills,
        "graph_json": operational_graph,
        "metadata_json": operational_metadata,
        "meta": {
            "company_id": company_id,
            "compiled_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "total_skills": len(final_skills),
            "duration_ms": duration_ms,
            "entity_count": operational_graph.get("stats", {}).get("entity_count", 0),
            "edge_count": operational_graph.get("stats", {}).get("edge_count", 0),
        },
    }

    db = get_client()
    if not db:
        await emit(job_id, "pipeline_error", {"error": "Database connection failed"})
        print(f"[{job_id}] write_brain: no DB client")
        return {
            "errors": ["DB connection failed in write_brain"],
            "skills_file": skills_file,
        }

    try:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        version_str = f"v_{int(time.time())}"

        source_hashes = {}
        for f in state.get("source_files", []):
            if "filename" in f and "sha256" in f:
                source_hashes[f["filename"]] = f["sha256"]

        db.table("skills_files").update({"is_current": False}).eq(
            "company_id", company_id
        ).eq("is_current", True).execute()

        sf_res = (
            db.table("skills_files")
            .insert(
                {
                    "company_id": company_id,
                    "version": version_str,
                    "brain_json": skills_file,
                    "source_hashes": source_hashes,
                    "is_current": True,
                }
            )
            .execute()
        )

        sf_id = sf_res.data[0]["id"]

        skill_rows = []
        for skill in final_skills:
            skill_copy = {k: v for k, v in skill.items() if k != "embedding_vector"}
            skill_rows.append(
                {
                    "id": skill.get("id", str(uuid.uuid4())[:8]),
                    "company_id": company_id,
                    "skills_file_id": sf_id,
                    "name": skill.get("rule", "Unknown")[:200],
                    "domain": skill.get("category", "general"),
                    "version": version_str,
                    "confidence": float(skill.get("confidence", 0.5)),
                    "skill_json": skill_copy,
                }
            )
        if skill_rows:
            db.table("skills").insert(skill_rows).execute()

        entities = state.get("extracted_entities", [])
        if entities and sf_id:
            entity_rows = []
            for ent in entities:
                entity_rows.append(
                    {
                        "id": ent.get("id", ""),
                        "company_id": company_id,
                        "skills_file_id": sf_id,
                        "entity_type": ent.get("entity_type", "unknown"),
                        "properties": ent.get("properties", {}),
                        "confidence": float(ent.get("confidence", 0.5)),
                        "requires_review": ent.get("requires_review", False),
                    }
                )
            db.table("operational_entities").insert(entity_rows).execute()

        relationships = state.get("extracted_relationships", [])
        if relationships and sf_id:
            rel_rows = []
            for rel in relationships:
                rel_rows.append(
                    {
                        "company_id": company_id,
                        "skills_file_id": sf_id,
                        "source_entity_id": rel.get("source_id", ""),
                        "target_entity_id": rel.get("target_id", ""),
                        "relation_type": rel.get("relation_type", "unknown"),
                        "conditions": rel.get("conditions", []),
                        "confidence": float(rel.get("confidence", 0.5)),
                        "source": rel.get("source", ""),
                    }
                )
            db.table("relationship_edges").insert(rel_rows).execute()

        draft_rows = [
            {
                "draft_id": d.draft_id,
                "company_id": company_id,
                "compile_job_id": str(job_id) if job_id else None,
                "source_skill_id": d.source_skill_id,
                "proposed_json": d.proposed_policy,
                "issues_json": list(d.issues),
                "evidence_texts": list(d.evidence_texts),
                "publishable": d.publishable,
                "status": "pending_review",
            }
            for d in drafts
        ]
        if draft_rows:
            try:
                db.table("policy_drafts").insert(draft_rows).execute()
            except Exception as draft_err:  # drafts must never fail the compile
                warnings.append(f"policy_drafts persistence failed: {draft_err}")
                print(f"[{job_id}] WARNING policy_drafts insert failed: {draft_err}")

        db.table("compile_runs").update(
            {
                "status": "complete",
                "completed_at": now_iso,
                "duration_ms": duration_ms,
                "result_version": version_str,
                "warnings": warnings or None,
            }
        ).eq("id", job_id).execute()

    except Exception as e:
        print(f"[{job_id}] [write_brain] DB Error: {e}")
        await emit(job_id, "pipeline_error", {"error": str(e)})
        return {"errors": [f"write_brain DB error: {e}"], "skills_file": skills_file}

    await emit(
        job_id,
        "stage",
        {
            "name": "DONE",
            "detail": f"Brain {version_str} written: {len(final_skills)} skills, {len(source_hashes)} sources, {duration_ms}ms",
        },
    )
    await emit(
        job_id,
        "pipeline_complete",
        {
            "status": "success",
            "version": version_str,
            "skills_count": len(final_skills),
            "source_count": len(source_hashes),
            "duration_ms": duration_ms,
        },
    )

    print(f"[{job_id}] write_brain: done (version: {version_str})")
    return {"skills_file": skills_file, "brain_version": version_str}
