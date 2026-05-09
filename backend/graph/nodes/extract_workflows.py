from backend.graph.state import BrainState
from backend.llm import safe_llm_json_call
from backend.sse import emit

MAX_CHUNK_CHARS = 12000


def _cap_chunks(chunks: list[dict]) -> str:
    parts = []
    chars = 0
    for c in chunks:
        text = c.get("text", "")
        if chars + len(text) > MAX_CHUNK_CHARS:
            break
        parts.append(text)
        chars += len(text)
    return "\n\n---\n\n".join(parts)


SYSTEM = """You are a workflow extraction specialist. Your ONLY job is to extract WORKFLOWS, PROCESSES, and SEQUENTIAL STEPS from company communications.

Output ONLY a JSON array. No preamble. No explanation. No markdown.
Each item must have exactly these fields:
  - id: short snake_case identifier (e.g., "bug_triage_workflow")
  - category: operational domain (e.g., "Engineering", "Customer Support")
  - workflow_name: human-readable name for this workflow
  - steps: array of step descriptions in order
  - triggers: what initiates this workflow
  - source_files: array of filenames this came from

If you find no workflows, output: []
Example: [{"id": "bug_triage_workflow", "category": "Engineering", "workflow_name": "Bug Triage", "steps": ["1. Identify severity (P0/P1/P2)", "2. Page on-call for P0", "3. 4hr SLA for P1"], "triggers": ["Bug report filed with severity label"], "source_files": ["notion_eng_runbook.md"]}]"""


async def extract_workflows(state: BrainState) -> dict:
    job_id = state["job_id"]
    chunks = state.get("all_chunks", [])

    print(f"[{job_id}] Node extract_workflows: processing {len(chunks)} chunks")
    await emit(
        job_id,
        "stage",
        {
            "name": "EXTRACT_WORKFLOWS",
            "detail": "Extracting workflows and processes...",
        },
    )

    chunk_text = _cap_chunks(chunks)
    user = f"Extract all workflows, processes, and step-by-step procedures from this company data:\n\n{chunk_text}"

    results = await safe_llm_json_call(SYSTEM, user, max_tokens=2048)

    print(f"[{job_id}] extract_workflows: extracted {len(results)} workflows")
    await emit(
        job_id,
        "stage",
        {"name": "EXTRACT_WORKFLOWS_DONE", "detail": f"Found {len(results)} workflows"},
    )
    return {"workflow_steps": results}
