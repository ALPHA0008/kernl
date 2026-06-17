from backend.engine.state import BrainState
from backend.core.llm import safe_llm_json_call
from backend.core.sse import emit
from backend.engine.nodes._utils import batch_chunks, chunks_to_text, content_hash

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

    relevant = [c for c in chunks if "contradictions" in c.get("domains", [])]
    print(
        f"[{job_id}] Node detect_contradictions: {len(relevant)}/{len(chunks)} chunks relevant"
    )
    await emit(
        job_id,
        "stage",
        {
            "name": "DETECT_CONTRADICTIONS",
            "detail": f"Detecting contradictions in {len(relevant)} relevant chunks...",
        },
    )

    if not relevant:
        return {"contradictions": []}

    batches = batch_chunks(relevant)
    all_results = []
    for batch in batches:
        batch_text = chunks_to_text(batch)
        key = f"contradictions:{content_hash(batch_text)}"
        results = await safe_llm_json_call(
            SYSTEM,
            f"Detect contradictions and conflicting instructions across this company data:\n\n{batch_text}",
            max_tokens=4096,
            cache_key=key,
        )
        all_results.extend(results)

    print(f"[{job_id}] detect_contradictions: found {len(all_results)} contradictions")
    await emit(
        job_id,
        "stage",
        {
            "name": "DETECT_CONTRADICTIONS_DONE",
            "detail": f"Found {len(all_results)} contradictions",
        },
    )
    return {"contradictions": all_results}
