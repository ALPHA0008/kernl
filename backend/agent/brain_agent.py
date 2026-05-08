import json
import numpy as np
from backend.db.supabase import get_client
from backend.llm import llm_call, get_embedding


async def handle_agent_query(
    company_id: str, scenario: str, context: dict = None, with_brain: bool = True
) -> dict:
    if not with_brain:
        return await _baseline_query(scenario, context)

    db = get_client()
    if not db:
        return _error_response("Database connection failed.")

    res = (
        db.table("skills_files")
        .select("brain_json")
        .eq("company_id", company_id)
        .order("compiled_at", desc=True)
        .limit(1)
        .execute()
    )

    if not res.data:
        return _error_response("No compiled brain found. Please compile first.")

    skills = res.data[0]["brain_json"].get("skills", [])
    if not skills:
        return _error_response("Brain is empty — no skills compiled.")

    query_text = f"{scenario} {json.dumps(context or {})}"
    query_emb = get_embedding(query_text)

    cached = True
    for s in skills:
        if "embedding_vector" not in s:
            cached = False
            break

    if cached:
        skill_embs = np.array([s["embedding_vector"] for s in skills])
        query_vec = np.array(query_emb)
        norms = np.linalg.norm(skill_embs, axis=1) * np.linalg.norm(query_vec)
        norms[norms == 0] = 1e-10
        scores = np.dot(skill_embs, query_vec) / norms
        top_indices = np.argsort(scores)[-5:][::-1]
        scored = []
        for idx in top_indices:
            scored.append(
                {
                    "skill": skills[idx],
                    "score": round(float(scores[idx]), 4),
                    "index": int(idx),
                }
            )
    else:
        scored = []
        for i, skill in enumerate(skills):
            skill_text = f"{skill.get('category', '')} {skill.get('rule', '')} {skill.get('rationale', '')}"
            skill_emb = get_embedding(skill_text)
            score = float(
                np.dot(query_emb, skill_emb)
                / (np.linalg.norm(query_emb) * np.linalg.norm(skill_emb) + 1e-10)
            )
            scored.append({"skill": skill, "score": round(score, 4), "index": i})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_results = scored[:5]
    retrieval_scores = [s["score"] for s in top_results]

    skills_context = ""
    for rank, s in enumerate(top_results):
        sk = s["skill"]
        skills_context += (
            f"\n--- Skill #{rank + 1} (retrieval_score: {s['score']}) ---\n"
        )
        skills_context += f"Category: {sk.get('category', 'Unknown')}\n"
        skills_context += f"Rule: {sk.get('rule', '')}\n"
        skills_context += f"Rationale: {sk.get('rationale', '')}\n"
        evidence = sk.get("evidence", [])
        if isinstance(evidence, list):
            skills_context += f"Evidence: {json.dumps(evidence[:3])}\n"
        skills_context += f"Compiled Confidence: {sk.get('confidence', 'unknown')}\n"

    prompt = """You are a logical policy reasoning engine. Your ONLY job is to compare scenario parameters against rule thresholds using pure arithmetic, then output the correct action.

CRITICAL LANGUAGE INTERPRETATION RULES:
- "No refunds after X days" means: refunds ARE allowed if the scenario is BEFORE X days. The word "after" creates a threshold at X. Below X = allowed. Above X = denied.
- "Full refund within X days" means: refunds are allowed ONLY if scenario is WITHIN X days. Below X = allowed. Above X = denied.
- "No refunds for X" (without a threshold) is an absolute ban.

ALWAYS compute: does the scenario value fall on the ALLOWED side or the DENIED side of the threshold?

Follow these exact steps:
STEP 1: Extract numeric thresholds from the matched rule (e.g., "60 days" → 60).
STEP 2: Extract the corresponding parameter from the scenario (e.g., days_since_purchase=45).
STEP 3: COMPARE: Write the comparison explicitly (e.g., "45 < 60, so customer is BEFORE the threshold").
STEP 4: DECIDE based solely on the comparison outcome.

Example A:
  Rule: "No refunds after 60 days. If purchase was more than 60 days ago, deny."
  Scenario: days_since_purchase=45
  STEP 1: threshold = 60 days
  STEP 2: scenario = 45 days
  STEP 3: 45 < 60, customer is BEFORE the threshold
  STEP 4: Action = approve (customer qualifies under 60-day limit)

Example B:
  Rule: "Full refund only within 14 days of purchase"
  Scenario: days_since_purchase=45
  STEP 1: threshold = 14 days
  STEP 2: scenario = 45 days
  STEP 3: 45 > 14, customer is AFTER the threshold
  STEP 4: Action = deny (outside the refund window)

Your recommended_action MUST exactly match what the math says. Do not let the emotional tone of the rule ("absolutely no", "no exceptions") override the arithmetic threshold.

confidence:
- retrieval_score < 0.3 → 0.0-0.2 (unrelated)
- 0.3-0.5 → 0.2-0.5 (weak)
- 0.5-0.7 → 0.5-0.75 (moderate)
- > 0.7 and correct match → 0.75-0.95 (strong)
- gibberish → 0.0

Respond with ONLY this JSON:
{
  "recommended_action": "action based on your math comparison",
  "rule_applied": "exact rule text from best matching skill",
  "evidence": ["evidence items"],
  "skill_matched": "skill category",
  "confidence": 0.0,
  "reasoning": "STEP 1: [threshold] STEP 2: [scenario value] STEP 3: [numeric comparison] STEP 4: [action]"
}"""

    user_content = f"--- Scenario ---\n{scenario}\n\n--- Additional Context ---\n{json.dumps(context or {})}\n\n--- Retrieved Skills (ranked by relevance) ---\n{skills_context}"

    response_str = await llm_call(prompt, user_content)
    result = _parse_json(response_str)
    result["retrieval_scores"] = retrieval_scores
    result["cached_embedding"] = cached
    return result


async def _baseline_query(scenario: str, context: dict = None) -> dict:
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
            "reasoning": f"JSON parse error: {e}. Raw: {raw[:500]}",
        }


def _error_response(msg: str) -> dict:
    return {
        "recommended_action": msg,
        "rule_applied": "none",
        "evidence": [],
        "skill_matched": "none",
        "confidence": 0.0,
        "retrieval_scores": [],
        "reasoning": msg,
    }
