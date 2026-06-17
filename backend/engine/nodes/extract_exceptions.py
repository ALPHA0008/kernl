from backend.engine.state import BrainState
from backend.core.llm import safe_llm_json_call
from backend.core.sse import emit
from backend.engine.nodes._utils import batch_chunks, chunks_to_text, content_hash

SYSTEM = """You are an exception extraction specialist. Your ONLY job is to extract EXCEPTIONS, EDGE CASES, CONSTRAINTS, CONDITIONAL RULES, and FORBIDDEN ACTIONS from company communications.

Output ONLY a JSON array. No preamble. No explanation. No markdown.
Each item must have exactly these fields:
  - id: short snake_case identifier (e.g., "no_ltd_refunds")
  - category: operational domain
  - condition: the specific condition that triggers this exception
  - action: what happens when this exception applies
  - rationale: why this exception exists
  - source_files: array of filenames this came from

If you find no exceptions, output: []
Example: [{"id": "no_ltd_refunds", "category": "Customer Support", "condition": "Customer has a lifetime deal account", "action": "Never process refunds for lifetime deal accounts", "rationale": "Explicitly stated in refund SOP as forbidden action", "source_files": ["notion_refund_sop.md"]}]"""


async def extract_exceptions(state: BrainState) -> dict:
    job_id = state["job_id"]
    chunks = state.get("all_chunks", [])

    relevant = [c for c in chunks if "exceptions" in c.get("domains", [])]
    print(
        f"[{job_id}] Node extract_exceptions: {len(relevant)}/{len(chunks)} chunks relevant"
    )
    await emit(
        job_id,
        "stage",
        {
            "name": "EXTRACT_EXCEPTIONS",
            "detail": f"Extracting exceptions from {len(relevant)} relevant chunks...",
        },
    )

    if not relevant:
        return {"exception_rules": []}

    batches = batch_chunks(relevant)
    all_results = []
    for batch in batches:
        batch_text = chunks_to_text(batch)
        key = f"exceptions:{content_hash(batch_text)}"
        results = await safe_llm_json_call(
            SYSTEM,
            f"Extract all exceptions, edge cases, constraints, and forbidden actions from this company data:\n\n{batch_text}",
            max_tokens=4096,
            cache_key=key,
        )
        all_results.extend(results)

    print(f"[{job_id}] extract_exceptions: extracted {len(all_results)} exceptions")
    await emit(
        job_id,
        "stage",
        {
            "name": "EXTRACT_EXCEPTIONS_DONE",
            "detail": f"Found {len(all_results)} exceptions",
        },
    )
    return {"exception_rules": all_results}
