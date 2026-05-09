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


SYSTEM = """You are a contradiction detection specialist. Your ONLY job is to find CONTRADICTIONS, CONFLICTS, and INCONSISTENCIES across company communications.

Output ONLY a JSON array. No preamble. No explanation. No markdown.
Each item must have exactly these fields:
  - id: short snake_case identifier (e.g., "refund_window_conflict")
  - domain: the operational domain this contradiction affects
  - claim_a: what the first source says
  - source_a: which source file claim_a comes from
  - claim_b: what the second source says
  - source_b: which source file claim_b comes from
  - resolution: which claim takes precedence in practice (based on Slack/ticket behavior vs SOP policy)
  - severity: "high", "medium", or "low"

If you find no contradictions, output: []
Example: [{"id": "refund_window_conflict", "domain": "Customer Support", "claim_a": "30-day refund window", "source_a": "notion_refund_sop.md", "claim_b": "45-day refund approved for loyal customer", "source_b": "slack_export_support.json", "resolution": "Observed behavior (Slack) shows exceptions beyond SOP — default to SOP, escalate exceptions", "severity": "medium"}]"""


async def detect_contradictions(state: BrainState) -> dict:
    job_id = state["job_id"]
    chunks = state.get("all_chunks", [])

    print(f"[{job_id}] Node detect_contradictions: processing {len(chunks)} chunks")
    await emit(
        job_id,
        "stage",
        {
            "name": "DETECT_CONTRADICTIONS",
            "detail": "Detecting cross-source contradictions...",
        },
    )

    chunk_text = _cap_chunks(chunks)
    user = f"Detect contradictions and conflicting instructions across this company data:\n\n{chunk_text}"

    results = await safe_llm_json_call(SYSTEM, user, max_tokens=2048)

    print(f"[{job_id}] detect_contradictions: found {len(results)} contradictions")
    await emit(
        job_id,
        "stage",
        {
            "name": "DETECT_CONTRADICTIONS_DONE",
            "detail": f"Found {len(results)} contradictions",
        },
    )
    return {"contradictions": results}
