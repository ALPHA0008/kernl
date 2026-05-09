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

    print(f"[{job_id}] Node extract_exceptions: processing {len(chunks)} chunks")
    await emit(
        job_id,
        "stage",
        {
            "name": "EXTRACT_EXCEPTIONS",
            "detail": "Extracting exceptions and edge cases...",
        },
    )

    chunk_text = _cap_chunks(chunks)
    user = f"Extract all exceptions, edge cases, constraints, and forbidden actions from this company data:\n\n{chunk_text}"

    results = await safe_llm_json_call(SYSTEM, user, max_tokens=2048)

    print(f"[{job_id}] extract_exceptions: extracted {len(results)} exceptions")
    await emit(
        job_id,
        "stage",
        {
            "name": "EXTRACT_EXCEPTIONS_DONE",
            "detail": f"Found {len(results)} exceptions",
        },
    )
    return {"exception_rules": results}
