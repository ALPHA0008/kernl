import json
from backend.db.supabase import get_client
from backend.llm import llm_call, get_embedding, cosine_similarity


async def handle_agent_query(company_id: str, scenario: str, context: dict = None, with_brain: bool = True) -> dict:
    """
    Real agent query handler.  No keyword routing, no hardcoded actions.
    Everything flows through: retrieve skills -> build prompt -> call vLLM -> return raw result.
    """
    if not with_brain:
        return await _baseline_query(scenario, context)

    # --- WITH BRAIN ---
    db = get_client()
    if not db:
        return _error_response("Database connection failed.")

    # 1. Fetch latest compiled skills
    res = db.table("skills_files").select("brain_json").eq(
        "company_id", company_id
    ).order("compiled_at", desc=True).limit(1).execute()

    if not res.data:
        return _error_response("No compiled brain found. Please compile first.")

    skills = res.data[0]["brain_json"].get("skills", [])
    if not skills:
        return _error_response("Brain is empty — no skills compiled.")

    # 2. Embed the query and score every skill
    query_text = f"{scenario} {json.dumps(context or {})}"
    query_emb = get_embedding(query_text)

    scored = []
    for i, skill in enumerate(skills):
        skill_text = f"{skill.get('category', '')} {skill.get('rule', '')} {skill.get('rationale', '')}"
        skill_emb = get_embedding(skill_text)
        score = cosine_similarity(query_emb, skill_emb)
        scored.append({"skill": skill, "score": round(score, 4), "index": i})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_results = scored[:5]
    retrieval_scores = [s["score"] for s in top_results]

    # 3. Build skills context for the LLM
    skills_context = ""
    for rank, s in enumerate(top_results):
        sk = s["skill"]
        skills_context += f"\n--- Skill #{rank+1} (retrieval_score: {s['score']}) ---\n"
        skills_context += f"Category: {sk.get('category', 'Unknown')}\n"
        skills_context += f"Rule: {sk.get('rule', '')}\n"
        skills_context += f"Rationale: {sk.get('rationale', '')}\n"
        skills_context += f"Evidence: {json.dumps(sk.get('evidence', []))}\n"
        skills_context += f"Compiled Confidence: {sk.get('confidence', 'unknown')}\n"

    # 4. Prompt the LLM - no example confidence values to bias it
    prompt = """You are the Kernl Brain Agent. You have access to this company's compiled operational skills (retrieved below, ranked by relevance).

Your task:
1. Read the scenario and optional JSON context carefully.
2. Examine the retrieved skills and their retrieval_scores.
3. Determine whether any skill clearly applies to this scenario.
4. If a skill applies, state the specific recommended action from that skill's rule.
5. If NO skill applies, or if the input is nonsensical/gibberish, say so honestly.

CONFIDENCE SCORING - base it on real signals:
- retrieval_score < 0.3 -> scenario is likely unrelated to any skill -> confidence < 0.2
- retrieval_score 0.3-0.5 -> weak match -> confidence 0.2-0.5
- retrieval_score 0.5-0.7 -> moderate match -> confidence 0.5-0.75
- retrieval_score > 0.7 AND rule clearly addresses the scenario -> confidence 0.75-0.95
- Never exceed 0.95 unless the match is exact and unambiguous.
- Gibberish or nonsensical input -> confidence 0.0, recommended_action = "unable to determine"

Respond with ONLY a JSON object (no markdown fences, no text outside the JSON):
{
  "recommended_action": "the specific action to take",
  "rule_applied": "exact rule text from the best matching skill",
  "evidence": ["evidence items from the skill"],
  "skill_matched": "the category of the matched skill",
  "confidence": 0.0,
  "reasoning": "explain why this skill applies and how you chose the confidence level"
}"""

    user_content = f"--- Scenario ---\n{scenario}\n\n--- Additional Context ---\n{json.dumps(context or {})}\n\n--- Retrieved Skills (ranked by relevance) ---\n{skills_context}"

    response_str = await llm_call(prompt, user_content)
    result = _parse_json(response_str)
    result["retrieval_scores"] = retrieval_scores
    return result


async def _baseline_query(scenario: str, context: dict = None) -> dict:
    """Without-brain baseline: LLM answers with zero company context."""
    prompt = """You are a generic AI assistant. You have NO company-specific knowledge or policies.
Answer based only on general industry standards. Be honest about your lack of specific context.
Respond with ONLY a JSON object:
{
  "recommended_action": "your general recommendation",
  "rule_applied": "general industry standard you referenced",
  "evidence": [],
  "skill_matched": "none",
  "confidence": 0.3,
  "retrieval_scores": [],
  "reasoning": "explain your reasoning, noting you lack company-specific context"
}"""
    user_content = f"Scenario: {scenario}\nContext: {json.dumps(context or {})}"
    response_str = await llm_call(prompt, user_content)
    return _parse_json(response_str)


def _parse_json(raw: str) -> dict:
    """Parse LLM response as JSON, stripping markdown fences."""
    try:
        clean = raw.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return json.loads(clean.strip())
    except Exception as e:
        return {
            "recommended_action": "Failed to parse LLM response",
            "rule_applied": "none",
            "evidence": [],
            "skill_matched": "none",
            "confidence": 0.0,
            "retrieval_scores": [],
            "reasoning": f"JSON parse error: {e}. Raw: {raw[:500]}"
        }


def _error_response(msg: str) -> dict:
    return {
        "recommended_action": msg,
        "rule_applied": "none",
        "evidence": [],
        "skill_matched": "none",
        "confidence": 0.0,
        "retrieval_scores": [],
        "reasoning": msg
    }
