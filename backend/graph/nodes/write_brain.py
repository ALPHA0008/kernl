"""
Node 5: Write the final skills file to the database.
Emits SSE stage: WRITING_DB, then pipeline_complete.
"""
import time
import json
import uuid
import datetime
from backend.graph.state import BrainState
from backend.db.supabase import get_client
from backend.sse import emit


async def write_brain(state: BrainState) -> dict:
    job_id = state.get("job_id")
    company_id = state.get("company_id")
    skills_file = state.get("skills_file", {})
    skills = skills_file.get("skills", [])
    start_time = state.get("start_time", time.time())
    duration_ms = int((time.time() - start_time) * 1000)

    print(f"[{job_id}] Node write_brain started for {company_id}")

    await emit(job_id, "stage", {"name": "WRITING_DB", "detail": f"Persisting {len(skills)} skills"})

    db = get_client()
    if not db:
        await emit(job_id, "pipeline_error", {"error": "Database connection failed"})
        print(f"[{job_id}] Node write_brain failed (no DB client)")
        return {"errors": ["DB connection failed in write_brain"]}

    try:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        version_str = f"v_{int(time.time())}"

        source_hashes = {}
        for f in state.get("source_files", []):
            if "filename" in f and "sha256" in f:
                source_hashes[f["filename"]] = f["sha256"]

        # Mark previous brain as not current
        db.table("skills_files").update(
            {"is_current": False}
        ).eq("company_id", company_id).eq("is_current", True).execute()

        # Insert new brain
        sf_res = db.table("skills_files").insert({
            "company_id": company_id,
            "version": version_str,
            "brain_json": skills_file,
            "source_hashes": source_hashes,
            "is_current": True,
        }).execute()

        sf_id = sf_res.data[0]["id"]

        # Insert individual skills
        for skill in skills:
            db.table("skills").insert({
                "id": skill.get("id", str(uuid.uuid4())[:8]),
                "company_id": company_id,
                "skills_file_id": sf_id,
                "name": skill.get("rule", "Unknown")[:200],
                "domain": skill.get("category", "general"),
                "version": version_str,
                "confidence": float(skill.get("confidence", 0.5)),
                "skill_json": skill,
            }).execute()

        # Update compile run
        db.table("compile_runs").update({
            "status": "complete",
            "completed_at": now_iso,
            "duration_ms": duration_ms,
            "result_version": version_str,
        }).eq("id", job_id).execute()

    except Exception as e:
        print(f"[{job_id}] [write_brain] DB Error: {e}")
        await emit(job_id, "pipeline_error", {"error": str(e)})
        return {"errors": [f"write_brain DB error: {e}"]}

    await emit(job_id, "stage", {
        "name": "DONE",
        "detail": f"Brain {version_str} written: {len(skills)} skills, {len(source_hashes)} sources, {duration_ms}ms",
    })
    await emit(job_id, "pipeline_complete", {
        "status": "success",
        "version": version_str,
        "skills_count": len(skills),
        "source_count": len(source_hashes),
        "duration_ms": duration_ms,
    })

    print(f"[{job_id}] Node write_brain finished successfully (version: {version_str})")
    return {}
