import os
import hashlib
from backend.graph.state import BrainState
from backend.sse import emit


def _detect_type(filename: str) -> str:
    fn = filename.lower()
    if fn.endswith(".json"):
        if "slack" in fn:
            return "slack_json"
        if "ticket" in fn or "zendesk" in fn:
            return "tickets_json"
        return "json"
    if fn.endswith(".md"):
        return "notion_md"
    return "unknown"


async def load_sources(state: BrainState) -> dict:
    company_id = state["company_id"]
    job_id = state["job_id"]

    print(f"[{job_id}] Node load_sources started")
    await emit(
        job_id,
        "stage",
        {"name": "LOADING_DOCS", "detail": f"Reading sources for {company_id}"},
    )

    base = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    sources_dir = os.path.join(base, "data", "sources", company_id)

    if not os.path.isdir(sources_dir):
        await emit(
            job_id,
            "pipeline_error",
            {"error": f"No source directory: data/sources/{company_id}/"},
        )
        print(f"[{job_id}] load_sources failed — missing dir: {sources_dir}")
        return {"errors": [f"Missing directory: {sources_dir}"], "source_files": []}

    source_files = []
    for filename in sorted(os.listdir(sources_dir)):
        filepath = os.path.join(sources_dir, filename)
        if not os.path.isfile(filepath):
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        source_files.append(
            {
                "filename": filename,
                "content": content,
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "doc_type": _detect_type(filename),
            }
        )

    print(f"[{job_id}] load_sources finished: {len(source_files)} files")
    await emit(
        job_id,
        "stage",
        {
            "name": "LOADING_DOCS_DONE",
            "detail": f"Loaded {len(source_files)} source files",
        },
    )
    return {"source_files": source_files}
