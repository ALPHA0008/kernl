"""
Node 4: De-duplicate skills, resolve conflicts, score confidence, enforce schema.
Emits SSE stage: QUALITY_CHECK
"""
import json
from backend.graph.state import BrainState
from backend.llm import llm_call
from backend.sse import emit


async def quality_normalize(state: BrainState) -> dict:
    job_id = state["job_id"]
    raw_skills = state.get("raw_skills", [])

    print(f"[{job_id}] Node quality_normalize started with {len(raw_skills)} raw skills")

    if not raw_skills:
        await emit(job_id, "stage", {"name": "QUALITY_CHECK", "detail": "No skills to normalize"})
        print(f"[{job_id}] Node quality_normalize finished (0 skills)")
        return {"skills_file": {"skills": []}}

    await emit(job_id, "stage", {
        "name": "QUALITY_CHECK",
        "detail": f"Normalizing {len(raw_skills)} raw skills",
    })

    prompt = """You are a quality assurance agent for an operational skills file.

Below is a raw list of skills extracted from company documents. Your job:

1. DEDUPLICATE: merge skills that describe the same rule (keep the most complete version).
2. RESOLVE CONFLICTS: if two skills contradict, keep both but note the conflict in the rationale. Prefer observed behavior (from Slack/tickets) over stated policy (from SOPs) when they conflict.
3. SCORE CONFIDENCE (0.0 to 1.0) for each skill based on:
   - 0.9–1.0: multiple confirming sources, clear unambiguous rule
   - 0.7–0.89: single strong source or multiple weak sources
   - 0.5–0.69: only one source, or some ambiguity
   - 0.3–0.49: weak evidence or significant ambiguity
   - < 0.3: speculative or poorly supported
4. ENFORCE SCHEMA: every skill must have: id, category, rule, rationale, evidence (array), confidence (float).

Return ONLY a JSON object:
{
  "skills": [
    {
      "id": "skill_slug",
      "category": "Domain Name",
      "rule": "The specific rule text",
      "rationale": "Why this rule exists",
      "evidence": ["source reference 1", "source reference 2"],
      "confidence": 0.85
    }
  ]
}"""

    skills_text = json.dumps(raw_skills, indent=2)
    print(f"[{job_id}] Requesting quality normalization...")
    response_str = await llm_call(prompt, skills_text, max_tokens=8192)
    print(f"[{job_id}] Received quality normalization response")

    try:
        clean = response_str.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        data = json.loads(clean.strip())
        final_skills = data.get("skills", raw_skills)
    except Exception as e:
        print(f"[{job_id}] [quality_normalize] Parse error: {e}")
        # Fallback: use raw skills with default confidence
        final_skills = raw_skills
        for sk in final_skills:
            sk.setdefault("confidence", 0.5)

    await emit(job_id, "stage", {
        "name": "QUALITY_CHECK_DONE",
        "detail": f"Final skills count: {len(final_skills)} (from {len(raw_skills)} raw)",
    })

    print(f"[{job_id}] Node quality_normalize finished (final skills: {len(final_skills)})")
    return {"skills_file": {"skills": final_skills}}
