from fastapi import (
    FastAPI,
    BackgroundTasks,
    HTTPException,
    UploadFile,
    File,
    Form,
    Depends,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import os
import uuid
import time
import json
import hashlib
import shutil
import asyncio
import traceback
import datetime

from backend.engine.graph import build_compilation_graph
from backend.core.sse import event_bus, emit
from backend.core.db.supabase import (
    get_client,
    get_brain_by_version,
    import_skills_file,
)
from backend.core.llm import check_vllm_health, llm_call, safe_llm_json_call
from backend.core.models.schemas import (
    CompileRequest,
    AgentHandleRequest,
    AgentQueryRequest,
    SkillsImportRequest,
)

from backend.v1_api import router as v1_router

app = FastAPI(title="Kernl API", version="2.1.0")
app.include_router(v1_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_ROOT = os.path.join(BASE_DIR, "data", "sources")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Health
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.get("/health")
async def health_check():
    vllm = await check_vllm_health()
    db = get_client()
    return {
        "status": "ok",
        "vllm": vllm,
        "database": "connected" if db else "not configured",
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Source file management
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _company_sources_dir(company_id: str) -> str:
    return os.path.join(SOURCES_ROOT, company_id)


@app.post("/sources/upload")
async def upload_source(company_id: str = Form(...), file: UploadFile = File(...)):
    dest_dir = _company_sources_dir(company_id)
    os.makedirs(dest_dir, exist_ok=True)

    content = await file.read()
    filepath = os.path.join(dest_dir, file.filename)
    with open(filepath, "wb") as f:
        f.write(content)

    file_hash = hashlib.sha256(content).hexdigest()

    db = get_client()
    if db:
        try:
            db.table("source_files").insert(
                {
                    "company_id": company_id,
                    "filename": file.filename,
                    "sha256": file_hash,
                    "storage_path": f"data/sources/{company_id}/{file.filename}",
                }
            ).execute()
        except Exception as e:
            print(f"[upload] DB record error: {e}")

    return {"filename": file.filename, "sha256": file_hash, "status": "uploaded"}


@app.get("/sources/{company_id}")
async def list_sources(company_id: str):
    src_dir = _company_sources_dir(company_id)
    if not os.path.isdir(src_dir):
        return {"files": []}
    files = []
    for fn in sorted(os.listdir(src_dir)):
        fp = os.path.join(src_dir, fn)
        if os.path.isfile(fp):
            with open(fp, "rb") as f:
                content = f.read()
            files.append(
                {
                    "filename": fn,
                    "size_bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
    return {"files": files, "company_id": company_id}


@app.delete("/sources/{company_id}/{filename}")
async def delete_source(company_id: str, filename: str):
    filepath = os.path.join(_company_sources_dir(company_id), filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    os.remove(filepath)

    db = get_client()
    if db:
        try:
            db.table("source_files").delete().eq("company_id", company_id).eq(
                "filename", filename
            ).execute()
        except Exception as e:
            print(f"[delete] DB cleanup error: {e}")

    return {"status": "deleted", "filename": filename}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Compilation pipeline
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


async def run_compilation_graph(job_id: str, company_id: str):
    initial_state = {
        "job_id": job_id,
        "company_id": company_id,
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
        "draft_skills": [],
        "skills_with_evidence": [],
        "final_skills": [],
        "skills_file": {},
        "brain_version": "",
        "start_time": time.time(),
        "errors": [],
    }

    graph = build_compilation_graph()

    await emit(job_id, "pipeline_start", {"company_id": company_id})
    try:
        await asyncio.wait_for(graph.ainvoke(initial_state), timeout=600.0)
    except Exception as e:
        err_msg = str(e)
        if isinstance(e, asyncio.TimeoutError):
            err_msg = "Pipeline execution timed out after 600 seconds."

        trace = traceback.format_exc()
        print(f"Graph execution failed for {job_id}:\n{trace}")

        await emit(job_id, "pipeline_error", {"error": err_msg, "traceback": trace})
        db = get_client()
        if db:
            try:
                db.table("compile_runs").update(
                    {
                        "status": "error",
                        "completed_at": datetime.datetime.now(
                            datetime.timezone.utc
                        ).isoformat(),
                        "error_detail": err_msg,
                    }
                ).eq("id", job_id).execute()
            except Exception as db_e:
                print(f"Failed to update compile_runs with error status: {db_e}")


@app.post("/compile")
@app.post("/compile/run")
async def compile_brain(req: CompileRequest, background_tasks: BackgroundTasks):
    src_dir = _company_sources_dir(req.company_id)
    if not os.path.isdir(src_dir) or not os.listdir(src_dir):
        raise HTTPException(
            status_code=400,
            detail=f"No source files found at data/sources/{req.company_id}/. Upload files first.",
        )

    job_id = str(uuid.uuid4())
    db = get_client()

    if db:
        try:
            db.table("compile_runs").insert(
                {
                    "id": job_id,
                    "company_id": req.company_id,
                    "status": "running",
                }
            ).execute()
        except Exception as e:
            print(f"Error creating run: {e}")

    background_tasks.add_task(run_compilation_graph, job_id, req.company_id)
    return {"job_id": job_id, "status": "started"}


@app.get("/compile/{job_id}/stream")
async def compile_stream(job_id: str):
    return StreamingResponse(
        event_bus.event_generator(job_id),
        media_type="text/event-stream",
    )


@app.get("/compile/{job_id}/status")
async def compile_status(job_id: str):
    db = get_client()
    if not db:
        return {"status": "unknown", "error_detail": "No DB"}
    res = db.table("compile_runs").select("*").eq("id", job_id).execute()
    if not res.data:
        return {"status": "not_found"}
    return res.data[0]


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Agent query
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# RETIRED (Step 6, 2026-07-13): the legacy free-text agent endpoints are gone.
# They cannot be proxied honestly -- mapping prose scenarios to typed facts is
# a review-time responsibility, not a runtime guess. Decisions now go through
# the deterministic, ledgered path: POST /v1/decisions/evaluate (typed facts,
# API key required). handle_agent_query remains importable for the legacy
# eval harness only.
_RETIREMENT = {
    "error": "gone",
    "detail": (
        "This endpoint is retired. Use POST /v1/decisions/evaluate with typed "
        "facts and an X-API-Key header. Free-text scenarios are not evaluated "
        "at runtime; policy review maps prose to typed facts."
    ),
}


@app.post("/agent/handle", status_code=410)
async def agent_handle_endpoint(_req: AgentHandleRequest):
    return _RETIREMENT


@app.post("/agent/query", status_code=410)
async def agent_query_endpoint(_req: AgentQueryRequest):
    return _RETIREMENT


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Skills & brain versions
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.get("/skills")
async def get_skills_legacy(company_id: str):
    db = get_client()
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    res = (
        db.table("skills_files")
        .select("brain_json")
        .eq("company_id", company_id)
        .order("compiled_at", desc=True)
        .limit(1)
        .execute()
    )
    if not res.data:
        return {"skills": []}
    return res.data[0]["brain_json"]


@app.get("/skills/{company_id}")
async def get_skills(company_id: str):
    db = get_client()
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")

    res = (
        db.table("skills_files")
        .select("*")
        .eq("company_id", company_id)
        .eq("is_current", True)
        .execute()
    )

    if not res.data:
        return {"skills": [], "version": None, "compiled_at": None}

    brain = res.data[0]
    skills = brain["brain_json"].get("skills", [])
    return {
        "skills": skills,
        "version": brain["version"],
        "compiled_at": brain["compiled_at"],
        "source_hashes": brain.get("source_hashes", {}),
        "brain_id": brain["id"],
    }


@app.get("/brain/versions/{company_id}")
async def list_brain_versions(company_id: str):
    db = get_client()
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")

    res = (
        db.table("skills_files")
        .select("id, version, compiled_at, is_current, source_hashes")
        .eq("company_id", company_id)
        .order("compiled_at", desc=True)
        .execute()
    )

    versions = []
    for row in res.data:
        full = (
            db.table("skills_files").select("brain_json").eq("id", row["id"]).execute()
        )
        skill_count = 0
        if full.data:
            skill_count = len(full.data[0]["brain_json"].get("skills", []))
        versions.append(
            {
                "id": row["id"],
                "version": row["version"],
                "compiled_at": row["compiled_at"],
                "is_current": row["is_current"],
                "source_count": len(row.get("source_hashes", {})),
                "skill_count": skill_count,
            }
        )

    return {"versions": versions, "company_id": company_id}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Phase 4 â€” Skills Marketplace
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@app.get("/skills/{company_id}/download")
async def download_skills(company_id: str):
    db = get_client()
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    res = (
        db.table("skills_files")
        .select("*")
        .eq("company_id", company_id)
        .eq("is_current", True)
        .execute()
    )
    if not res.data:
        raise HTTPException(
            status_code=404, detail="No skills file found for this company"
        )
    brain = res.data[0]
    return StreamingResponse(
        iter([json.dumps(brain["brain_json"], indent=2)]),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="skills_{company_id}_{brain["version"]}.json"'
        },
    )


@app.post("/skills/import")
async def import_skills(req: SkillsImportRequest):
    db = get_client()
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    if not req.skills:
        raise HTTPException(status_code=400, detail="No skills provided in payload")
    skills_file = import_skills_file(
        req.company_id, req.skills, req.version, req.source_label
    )
    if not skills_file:
        raise HTTPException(status_code=500, detail="Failed to import skills")
    return {
        "status": "imported",
        "company_id": req.company_id,
        "version": req.version,
        "skill_count": len(req.skills),
        "skills_file_id": skills_file["id"],
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Semantic Diff Engine
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.get("/diff/{v1}/{v2}")
async def semantic_diff(v1: str, v2: str, company_id: str):
    db = get_client()
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")

    brain_v1 = get_brain_by_version(company_id, v1)
    brain_v2 = get_brain_by_version(company_id, v2)

    if not brain_v1 or not brain_v2:
        raise HTTPException(
            status_code=404, detail="One or both brain versions not found"
        )

    skills_v1 = {
        s.get("id", f"idx_{i}"): s
        for i, s in enumerate(brain_v1["brain_json"].get("skills", []))
    }
    skills_v2 = {
        s.get("id", f"idx_{i}"): s
        for i, s in enumerate(brain_v2["brain_json"].get("skills", []))
    }

    ids_v1 = set(skills_v1.keys())
    ids_v2 = set(skills_v2.keys())

    added_ids = ids_v2 - ids_v1
    deleted_ids = ids_v1 - ids_v2
    common_ids = ids_v1 & ids_v2

    added = [
        {"id": sid, "name": skills_v2[sid].get("rule", "")[:100]}
        for sid in sorted(added_ids)
    ]
    deleted = [
        {"id": sid, "name": skills_v1[sid].get("rule", "")[:100]}
        for sid in sorted(deleted_ids)
    ]

    modified = []
    confidence_shifts = []

    for sid in sorted(common_ids):
        s1, s2 = skills_v1[sid], skills_v2[sid]
        for field in ("rule", "rationale"):
            v1_val = str(s1.get(field, ""))
            v2_val = str(s2.get(field, ""))
            if v1_val != v2_val:
                modified.append(
                    {
                        "id": sid,
                        "field": field,
                        "old_value": v1_val[:200],
                        "new_value": v2_val[:200],
                    }
                )

        c1 = float(s1.get("confidence", 0))
        c2 = float(s2.get("confidence", 0))
        if abs(c1 - c2) > 0.01:
            confidence_shifts.append(
                {
                    "id": sid,
                    "old_confidence": c1,
                    "new_confidence": c2,
                    "reason": "Confidence recalculated based on source evidence and contradictions",
                }
            )

    return {
        "v1_version": v1,
        "v2_version": v2,
        "added": added,
        "deleted": deleted,
        "modified": modified,
        "confidence_shifts": confidence_shifts,
        "summary": {
            "v1_skills": len(skills_v1),
            "v2_skills": len(skills_v2),
            "added_count": len(added),
            "deleted_count": len(deleted),
            "modified_count": len(modified),
            "confidence_shift_count": len(confidence_shifts),
        },
    }
