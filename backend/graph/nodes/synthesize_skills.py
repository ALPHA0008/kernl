import json
from backend.graph.state import BrainState
from backend.llm import llm_call
from backend.sse import emit


async def synthesize_skills(state: BrainState) -> dict:
    job_id = state["job_id"]
    raw_decisions = state.get("raw_decisions", [])
    workflow_steps = state.get("workflow_steps", [])
    exception_rules = state.get("exception_rules", [])
    contradictions = state.get("contradictions", [])

    total_raw = (
        len(raw_decisions)
        + len(workflow_steps)
        + len(exception_rules)
        + len(contradictions)
    )
    print(
        f"[{job_id}] Node synthesize_skills: merging {len(raw_decisions)} decisions + {len(workflow_steps)} workflows + {len(exception_rules)} exceptions + {len(contradictions)} contradictions"
    )

    await emit(
        job_id,
        "stage",
        {
            "name": "SYNTHESIZING_SKILLS",
            "detail": f"Merging {total_raw} extracted items into cohesive skills",
        },
    )

    if total_raw == 0:
        print(f"[{job_id}] synthesize_skills: no extractions to merge")
        return {"draft_skills": []}

    prompt = """You are a Principal Operations Architect. Below are four sets of extractions from company data:

1. DECISIONS & RULES: explicit policies and decision criteria
2. WORKFLOWS: step-by-step processes and procedures
3. EXCEPTIONS: edge cases, constraints, forbidden actions
4. CONTRADICTIONS: conflicts between different sources

Merge these into unified operational skills. For each skill:
- id: short snake_case identifier
- category: operational domain name
- rule: the specific, actionable rule text (be precise — include thresholds, timeframes, approvals)
- rationale: why this rule exists (based on evidence)
- evidence: array of specific quotes or references from source data
- source_files: which files this came from

Quality rules:
- Deduplicate: merge skills that describe the same rule (keep the most complete version)
- Resolve conflicts: note contradictions in the rationale
- Do NOT invent rules that aren't supported by the extractions
- Each rule should be specific enough that a human could follow it

Respond with ONLY a JSON object:
{
  "skills": [
    {
      "id": "handle_refund_request",
      "category": "Customer Support",
      "rule": "Approve full refund for annual plans within 14 days",
      "rationale": "No-questions policy within 14 days for annual plans",
      "evidence": ["notion_refund_sop.md: Annual plan customers within 14 days..."],
      "source_files": ["notion_refund_sop.md"]
    }
  ]
}"""

    extractions_text = json.dumps(
        {
            "decisions_and_rules": raw_decisions,
            "workflows_and_processes": workflow_steps,
            "exceptions_and_edge_cases": exception_rules,
            "contradictions": contradictions,
        },
        indent=2,
    )

    response_str = await llm_call(prompt, extractions_text, max_tokens=4096)

    try:
        clean = response_str.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        data = json.loads(clean.strip())
        draft = data.get("skills", [])
    except Exception as e:
        print(f"[{job_id}] [synthesize_skills] Parse error: {e}")
        draft = []

    await emit(
        job_id,
        "stage",
        {
            "name": "SYNTHESIZING_DONE",
            "detail": f"Synthesized {len(draft)} skills from {total_raw} extractions",
        },
    )
    print(f"[{job_id}] synthesize_skills: produced {len(draft)} skills")
    return {"draft_skills": draft}
