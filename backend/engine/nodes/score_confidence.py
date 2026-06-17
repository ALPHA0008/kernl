from backend.engine.state import BrainState
from backend.core.sse import emit


def _score_confidence(skill: dict, contradictions: list) -> float:
    """Math-based confidence scoring per the CLAUDE.md formula."""
    base = 0.5

    source_count = len(skill.get("evidence", []))
    if source_count >= 3:
        base += 0.25
    elif source_count == 2:
        base += 0.15
    elif source_count == 1:
        base += 0.05

    base += 0.15

    skill_id = skill.get("id", "")
    has_contradiction = any(
        c.get("id", "").startswith(skill_id.split("_")[0])
        or skill_id in str(c.get("domain", ""))
        for c in contradictions
    )
    if not has_contradiction:
        base += 0.10

    return round(min(base, 1.0), 2)


async def score_confidence(state: BrainState) -> dict:
    job_id = state["job_id"]
    skills = state.get("skills_with_evidence", [])
    contradictions = state.get("contradictions", [])

    print(f"[{job_id}] Node score_confidence: scoring {len(skills)} skills")
    await emit(
        job_id,
        "stage",
        {"name": "SCORING_CONFIDENCE", "detail": f"Scoring {len(skills)} skills"},
    )

    final_skills = []
    for skill in skills:
        skill["confidence"] = _score_confidence(skill, contradictions)
        final_skills.append(skill)

    avg_conf = round(
        sum(s.get("confidence", 0) for s in final_skills) / max(len(final_skills), 1), 2
    )

    await emit(
        job_id,
        "stage",
        {
            "name": "SCORING_DONE",
            "detail": f"Average confidence: {avg_conf} across {len(final_skills)} skills",
        },
    )
    print(f"[{job_id}] score_confidence: avg confidence {avg_conf}")
    return {"final_skills": final_skills}
