import json
from backend.engine.state import BrainState
from backend.core.llm import llm_call
from backend.core.sse import emit


async def link_evidence(state: BrainState) -> dict:
    job_id = state["job_id"]
    draft_skills = state.get("draft_skills", [])
    chunks = state.get("all_chunks", [])

    print(
        f"[{job_id}] Node link_evidence: enriching {len(draft_skills)} skills with evidence"
    )
    await emit(
        job_id,
        "stage",
        {
            "name": "LINKING_EVIDENCE",
            "detail": f"Linking evidence for {len(draft_skills)} skills",
        },
    )

    if not draft_skills:
        return {"skills_with_evidence": []}

    prompt = """You are an evidence linking specialist. Below are draft operational skills and the original source chunks they were extracted from.

For each skill, find the most specific evidence excerpts from the source chunks that support it. Enrich each skill's evidence array with concrete quotes.

Return ONLY a JSON object:
{
  "skills": [
    {
      "id": "skill_id",
      "category": "...",
      "rule": "...",
      "rationale": "...",
      "evidence": ["Exact quote from source that supports this rule"],
      "source_files": ["filename.ext"]
    }
  ]
}

Keep all existing fields intact. Only add or improve the evidence array."""

    chunks_text = "\n\n---\n\n".join([c.get("text", "") for c in chunks[:20]])

    BATCH_SIZE = 5
    enriched = []

    for i in range(0, len(draft_skills), BATCH_SIZE):
        batch = draft_skills[i : i + BATCH_SIZE]
        skills_text = json.dumps({"skills": batch}, indent=2)
        user_content = f"--- Skills (batch {i // BATCH_SIZE + 1}) ---\n{skills_text}\n\n--- Source Chunks ---\n{chunks_text}"

        response_str = await llm_call(prompt, user_content, max_tokens=4096)
        try:
            clean = response_str.strip()
            if clean.startswith("```json"):
                clean = clean[7:]
            elif clean.startswith("```"):
                clean = clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            data = json.loads(clean.strip())
            enriched.extend(data.get("skills", batch))
        except Exception as e:
            print(f"[{job_id}] [link_evidence] Batch parse error: {e}")
            enriched.extend(batch)

    await emit(
        job_id,
        "stage",
        {
            "name": "LINKING_DONE",
            "detail": f"Evidence linked for {len(enriched)} skills",
        },
    )
    print(f"[{job_id}] link_evidence: done")
    return {"skills_with_evidence": enriched}
