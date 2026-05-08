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
    if not supabase: return None
    res = supabase.table("skills_files").select("*").eq("company_id", company_id).eq("is_current", True).execute()
    if res.data:
        return res.data[0]
    return None

def save_skills_file(data: dict):
    if not supabase: return None
    res = supabase.table("skills_files").insert(data).execute()
    return res.data

def save_compile_run(data: dict):
    if not supabase: return None
    res = supabase.table("compile_runs").insert(data).execute()
    return res.data

def update_compile_run(run_id: str, data: dict):
    if not supabase: return None
    res = supabase.table("compile_runs").update(data).eq("id", run_id).execute()
    return res.data

def get_source_hashes(company_id: str):
    if not supabase: return {}
    # Get the latest current brain
    brain = get_current_brain(company_id)
    if brain:
        return brain.get("source_hashes", {})
    return {}

def save_source_file(data: dict):
    if not supabase: return None
    res = supabase.table("source_files").insert(data).execute()
    return res.data

def get_skills_by_brain_id(brain_id: str):
    if not supabase: return []
    res = supabase.table("skills").select("*").eq("skills_file_id", brain_id).execute()
    return res.data

def insert_skills(data: list):
    if not supabase: return None
    res = supabase.table("skills").insert(data).execute()
    return res.data
