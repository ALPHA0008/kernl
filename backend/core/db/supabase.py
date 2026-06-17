import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    # We allow the app to start without Supabase for local testing if needed,
    # but actual DB calls will fail if not provided.
    supabase = None


def get_client():
    return supabase


def get_current_brain(company_id: str):
    if not supabase:
        return None
    res = (
        supabase.table("skills_files")
        .select("*")
        .eq("company_id", company_id)
        .eq("is_current", True)
        .execute()
    )
    if res.data:
        return res.data[0]
    return None


def save_skills_file(data: dict):
    if not supabase:
        return None
    res = supabase.table("skills_files").insert(data).execute()
    return res.data


def save_compile_run(data: dict):
    if not supabase:
        return None
    res = supabase.table("compile_runs").insert(data).execute()
    return res.data


def update_compile_run(run_id: str, data: dict):
    if not supabase:
        return None
    res = supabase.table("compile_runs").update(data).eq("id", run_id).execute()
    return res.data


def get_source_hashes(company_id: str):
    if not supabase:
        return {}
    # Get the latest current brain
    brain = get_current_brain(company_id)
    if brain:
        return brain.get("source_hashes", {})
    return {}


def save_source_file(data: dict):
    if not supabase:
        return None
    res = supabase.table("source_files").insert(data).execute()
    return res.data


def get_skills_by_brain_id(brain_id: str):
    if not supabase:
        return []
    res = supabase.table("skills").select("*").eq("skills_file_id", brain_id).execute()
    return res.data


def insert_skills(data: list):
    if not supabase:
        return None
    res = supabase.table("skills").insert(data).execute()
    return res.data


def get_brain_by_version(company_id: str, version: str):
    if not supabase:
        return None
    res = (
        supabase.table("skills_files")
        .select("*")
        .eq("company_id", company_id)
        .eq("version", version)
        .execute()
    )
    if res.data:
        return res.data[0]
    return None


# ─────────────────────────────────────────────
# Phase 3 — Company CRUD
# ─────────────────────────────────────────────


def get_company(company_id: str):
    if not supabase:
        return None
    res = supabase.table("companies").select("*").eq("id", company_id).execute()
    return res.data[0] if res.data else None


def upsert_company(company_id: str, data: dict):
    if not supabase:
        return None
    existing = get_company(company_id)
    if existing:
        data.pop("id", None)
        data.pop("created_at", None)
        res = supabase.table("companies").update(data).eq("id", company_id).execute()
    else:
        data.setdefault("id", company_id)
        res = supabase.table("companies").insert(data).execute()
    return res.data[0] if res.data else None


def get_company_stats(company_id: str):
    if not supabase:
        return {"skill_count": 0, "source_count": 0, "last_compile": None}
    skill_res = (
        supabase.table("skills")
        .select("id", count="exact")
        .eq("company_id", company_id)
        .eq("stale", False)
        .execute()
    )
    source_res = (
        supabase.table("source_files")
        .select("id", count="exact")
        .eq("company_id", company_id)
        .execute()
    )
    compile_res = (
        supabase.table("compile_runs")
        .select("completed_at, result_version")
        .eq("company_id", company_id)
        .eq("status", "complete")
        .order("completed_at", desc=True)
        .limit(1)
        .execute()
    )
    return {
        "skill_count": getattr(skill_res, "count", 0) or len(skill_res.data or []),
        "source_count": getattr(source_res, "count", 0) or len(source_res.data or []),
        "last_compile": compile_res.data[0] if compile_res.data else None,
    }


# ─────────────────────────────────────────────
# Phase 4 — Skills Marketplace
# ─────────────────────────────────────────────


def import_skills_file(
    company_id: str, skills: list, version: str, source_label: str
) -> dict | None:
    if not supabase:
        return None
    supabase.table("skills_files").update({"is_current": False}).eq(
        "company_id", company_id
    ).eq("is_current", True).execute()
    brain_json = {
        "skills": skills,
        "meta": {"imported": True, "source": source_label, "version": version},
    }
    skills_file = {
        "company_id": company_id,
        "version": version,
        "brain_json": brain_json,
        "source_hashes": {},
        "is_current": True,
    }
    skills_file_res = supabase.table("skills_files").insert(skills_file).execute()
    if not skills_file_res.data:
        return None
    sf = skills_file_res.data[0]
    skill_rows = [
        {
            "id": s.get("id", f"imported_{i}"),
            "company_id": company_id,
            "skills_file_id": sf["id"],
            "name": s.get("rule", "")[:255],
            "domain": s.get("category", "Unknown"),
            "version": version,
            "confidence": s.get("confidence", 0.5),
            "skill_json": s,
        }
        for i, s in enumerate(skills)
    ]
    if skill_rows:
        supabase.table("skills").insert(skill_rows).execute()
    return sf
