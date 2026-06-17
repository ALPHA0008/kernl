from backend.engine.state import BrainState
from backend.core.llm import safe_llm_json_call
from backend.core.sse import emit
from backend.engine.nodes._utils import batch_chunks, chunks_to_text, content_hash

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

    relevant = [c for c in chunks if "decisions" in c.get("domains", [])]
    print(
        f"[{job_id}] Node extract_decisions: {len(relevant)}/{len(chunks)} chunks relevant"
    )
    await emit(
        job_id,
        "stage",
        {
            "name": "EXTRACT_DECISIONS",
            "detail": f"Extracting rules from {len(relevant)} relevant chunks...",
        },
    )

    if not relevant:
        return {"raw_decisions": []}

    batches = batch_chunks(relevant)
    all_results = []
    for batch in batches:
        batch_text = chunks_to_text(batch)
        key = f"decisions:{content_hash(batch_text)}"
        results = await safe_llm_json_call(
            SYSTEM,
            f"Extract all decisions, rules, and policies from this company data:\n\n{batch_text}",
            max_tokens=4096,
            cache_key=key,
        )
        all_results.extend(results)

    print(f"[{job_id}] extract_decisions: extracted {len(all_results)} rules")
    await emit(
        job_id,
        "stage",
        {"name": "EXTRACT_DECISIONS_DONE", "detail": f"Found {len(all_results)} rules"},
    )
    return {"raw_decisions": all_results}
