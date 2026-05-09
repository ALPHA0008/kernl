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


SYSTEM = """You are a policy extraction specialist. Your ONLY job is to extract DECISIONS, RULES, and POLICIES from company communications.

Output ONLY a JSON array. No preamble. No explanation. No markdown.
Each item must have exactly these fields:
  - id: short snake_case identifier (e.g., "refund_annual_14day")
  - category: operational domain (e.g., "Customer Support", "Engineering", "Finance")
  - rule: the precise, actionable rule text including thresholds, timeframes, approvals
  - rationale: why this rule exists, based on the evidence
  - evidence: array of specific quotes or references from the source text that support this rule
  - source_files: array of filenames this rule came from

If you find no decisions or rules, output: []
Example: [{"id": "refund_annual_14day", "category": "Customer Support", "rule": "Annual plan customers within 14 days of purchase are eligible for full refund", "rationale": "No-questions policy for annual plans within 14 days", "evidence": ["notion_refund_sop.md: Annual plan customers within 14 days..."], "source_files": ["notion_refund_sop.md"]}]"""


async def extract_decisions(state: BrainState) -> dict:
    job_id = state["job_id"]
    chunks = state.get("all_chunks", [])

    print(f"[{job_id}] Node extract_decisions: processing {len(chunks)} chunks")
    await emit(
        job_id,
        "stage",
        {"name": "EXTRACT_DECISIONS", "detail": "Extracting rules and policies..."},
    )

    chunk_text = _cap_chunks(chunks)
    user = f"Extract all decisions, rules, and policies from this company data:\n\n{chunk_text}"

    results = await safe_llm_json_call(SYSTEM, user, max_tokens=2048)

    print(f"[{job_id}] extract_decisions: extracted {len(results)} rules")
    await emit(
        job_id,
        "stage",
        {"name": "EXTRACT_DECISIONS_DONE", "detail": f"Found {len(results)} rules"},
    )
    return {"raw_decisions": results}
