import json
from backend.engine.state import BrainState
from backend.core.llm import llm_call
from backend.core.sse import emit

VALID_OPERATORS = {
    "number": {">", ">=", "<", "<=", "==", "!="},
    "string": {"==", "!=", "in", "not_in"},
    "boolean": {"=="},
}


def _get_valid_sets(metadata: dict) -> tuple:
    vs = metadata.get("valid_sets", {})
    depts = vs.get("departments", ["general"])
    sevs = vs.get("severities", ["general", "P0", "P1", "P2", "policy", "sla"])
    wfs = vs.get("workflow_types", ["general"])
    tiers = vs.get("customer_tiers", ["all"])
    cond_fields = set(vs.get("condition_fields", []))
    return depts, sevs, wfs, tiers, cond_fields


def _get_action_ontology(metadata: dict) -> dict:
    return metadata.get("action_types", {}).get("ontology", {})


def _get_action_types(metadata: dict) -> list:
    return metadata.get("action_types", {}).get("values", [])


def _validate_operational_metadata(op: dict, metadata: dict) -> dict:
    depts, sevs, wfs, tiers, _ = _get_valid_sets(metadata)
    action_types = _get_action_types(metadata)
    ontology = _get_action_ontology(metadata)

    cleaned = {}
    dept = (op.get("department") or "").lower().strip()
    cleaned["department"] = dept if dept in depts else None
    sev = (op.get("severity") or "").strip()
    sev_map = {"critical": "P0", "high": "P1", "medium": "P2", "low": "general"}
    if sev in sev_map:
        sev = sev_map[sev]
    cleaned["severity"] = sev if sev in sevs else None
    wf = (op.get("workflow_type") or "").lower().strip()
    cleaned["workflow_type"] = wf if wf in wfs else None
    tier = (op.get("customer_tier") or "").lower().strip()
    cleaned["customer_tier"] = tier if tier in tiers else None
    cleaned["escalation_required"] = bool(op.get("escalation_required", False))
    action = (
        (op.get("action_type") or "")
        .lower()
        .strip()
        .replace(" ", "_")
        .replace("-", "_")
    )
    cleaned["action_type"] = action if action in action_types else None
    cleaned["specificity_level"] = ontology.get(cleaned.get("action_type"), {}).get(
        "specificity", 2
    )
    kws = op.get("keywords", [])
    cleaned["keywords"] = (
        [str(k).lower() for k in kws[:15]] if isinstance(kws, list) else []
    )
    return cleaned


def _build_metadata_confidence(raw_op: dict, cleaned_op: dict) -> dict:
    fields = ["department", "severity", "workflow_type", "customer_tier", "action_type"]
    confidence = {}
    for f in fields:
        raw_val = raw_op.get(f)
        clean_val = cleaned_op.get(f)
        if raw_val and clean_val:
            confidence[f] = 0.90
        elif raw_val and not clean_val:
            confidence[f] = 0.20
        else:
            confidence[f] = 0.50
    return confidence


def _validate_conditions(raw_conditions: list, metadata: dict) -> list:
    _, _, _, _, cond_fields = _get_valid_sets(metadata)
    if not isinstance(raw_conditions, list):
        return []
    validated = []
    for cond in raw_conditions:
        if not isinstance(cond, dict):
            continue
        field = (cond.get("field") or "").lower().strip()
        operator = (cond.get("operator") or "").strip()
        value = cond.get("value")
        ctype = (cond.get("type") or "").lower().strip()
        if cond_fields and field not in cond_fields:
            continue
        if ctype not in VALID_OPERATORS:
            continue
        if operator not in VALID_OPERATORS[ctype]:
            continue
        if ctype == "number":
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
        elif ctype == "string":
            if operator in ("in", "not_in"):
                if not isinstance(value, list):
                    if isinstance(value, str):
                        value = [v.strip() for v in value.split(",")]
                    else:
                        continue
                value = [str(v).lower().strip() for v in value]
            else:
                value = str(value).lower().strip()
        elif ctype == "boolean":
            if not isinstance(value, bool):
                if isinstance(value, str):
                    value = value.lower().strip() in ("true", "1", "yes")
                else:
                    value = bool(value)
        validated.append(
            {
                "field": field,
                "operator": operator,
                "value": value,
                "type": ctype,
                "source": cond.get("source", "rule"),
            }
        )
    return validated


def _compute_conditions_confidence(
    raw_conditions: list, validated_conditions: list
) -> float:
    if not raw_conditions:
        return 0.50
    total = len(raw_conditions)
    survived = len(validated_conditions)
    if survived == 0:
        return 0.20
    if survived == total:
        return 0.90
    ratio = survived / total
    return round(0.60 + (ratio * 0.30), 2)


def _build_prompt(metadata: dict) -> str:
    depts, sevs, wfs, tiers, cond_fields = _get_valid_sets(metadata)
    action_types = _get_action_types(metadata)
    action_list = (
        ", ".join(action_types) if action_types else "approve, deny, escalate, monitor"
    )

    prompt = f"""You are a Principal Operations Architect. Below are four sets of extractions from company data:

1. DECISIONS & RULES: explicit policies and decision criteria
2. WORKFLOWS: step-by-step processes and procedures
3. EXCEPTIONS: edge cases, constraints, forbidden actions
4. CONTRADICTIONS: conflicts between different sources

Merge these into unified operational skills. For each skill, output ALL of the following fields:

REQUIRED FIELDS:
- id: short snake_case identifier
- category: operational domain name
- rule: the specific, actionable rule text (be precise — include thresholds, timeframes, approvals)
- rationale: why this rule exists (based on evidence)
- evidence: array of specific quotes or references from source data
- source_files: which files this came from

OPERATIONAL METADATA (inside an "operational" object):
- department: one of [{", ".join(depts)}]
- severity: one of [{", ".join(sevs)}]
- action_type: the canonical action this skill leads to — MUST be one of: {action_list}
- workflow_type: one of [{", ".join(wfs)}]
- customer_tier: one of [{", ".join(tiers)}] — use "all" if rule applies to all
- escalation_required: true/false
- keywords: array of 5-10 specific keywords that distinguish this skill from others

TYPED CONDITIONS (inside a "conditions" array):
Extract every numeric threshold, string equality check, or boolean condition that appears in the rule.
Each condition must have:
  - field: MUST be one of [{", ".join(cond_fields)}] if populated by your data, else any relevant field
  - operator: for numbers use >, >=, <, <=, ==, != | for strings use ==, !=, in, not_in | for booleans use ==
  - value: the actual threshold value (number, string, or boolean)
  - type: "number", "string", or "boolean"
  - source: always "rule"

EXTENDED OPERATIONAL FIELDS (alongside the "operational" object):
- actor: who performs this action
- escalation_target: who receives the escalation
- approval_required: true/false
- workflow_stage: where in the workflow this applies
- temporal_constraints: object with "window_days" (number) and "direction" ("within" or "after") if a time window exists, else null

Quality rules:
- Deduplicate: merge skills that describe the same rule (keep the most complete version)
- Resolve conflicts: note contradictions in the rationale
- Do NOT invent rules that aren't supported by the extractions
- Each rule should be specific enough that a human could follow it
- For keywords, prioritize SPECIFIC distinguishing terms
- Extract ALL numeric thresholds you find — do not skip them

Respond with ONLY a JSON object:
{{
  "skills": [
    {{
      "id": "skill_identifier",
      "category": "CategoryName",
      "rule": "The actionable rule text",
      "rationale": "Why this rule exists",
      "evidence": ["source references"],
      "source_files": ["file names"],
      "operational": {{
        "department": "department_name",
        "severity": "severity_level",
        "action_type": "action_name",
        "workflow_type": "workflow_name",
        "customer_tier": "tier_name",
        "escalation_required": false,
        "keywords": ["kw1", "kw2"]
      }},
      "conditions": [],
      "actor": null,
      "escalation_target": null,
      "approval_required": false,
      "workflow_stage": null,
      "temporal_constraints": null
    }}
  ]
}}"""
    return prompt


async def synthesize_skills(state: BrainState) -> dict:
    job_id = state["job_id"]
    raw_decisions = state.get("raw_decisions", [])
    workflow_steps = state.get("workflow_steps", [])
    exception_rules = state.get("exception_rules", [])
    contradictions = state.get("contradictions", [])
    metadata = state.get("operational_metadata", {})

    total_raw = (
        len(raw_decisions)
        + len(workflow_steps)
        + len(exception_rules)
        + len(contradictions)
    )
    print(
        f"[{job_id}] Node synthesize_skills: merging {len(raw_decisions)} decisions + "
        f"{len(workflow_steps)} workflows + {len(exception_rules)} exceptions + "
        f"{len(contradictions)} contradictions"
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

    prompt = _build_prompt(metadata)

    extractions_text = json.dumps(
        {
            "decisions_and_rules": raw_decisions,
            "workflows_and_processes": workflow_steps,
            "exceptions_and_edge_cases": exception_rules,
            "contradictions": contradictions,
        },
        indent=2,
    )

    response_str = await llm_call(prompt, extractions_text, max_tokens=8192)

    def _try_parse(text: str) -> list:
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        data = json.loads(clean.strip())
        return data.get("skills", [])

    raw_skills = []
    try:
        raw_skills = _try_parse(response_str)
    except Exception as e:
        print(f"[{job_id}] [synthesize_skills] Parse error: {e}")
        depts, sevs, wfs, tiers, cond_fields = _get_valid_sets(metadata)
        action_types = _get_action_types(metadata)
        retry_prompt = (
            f"Output ONLY a JSON object with a single key 'skills' containing an array of operational skills. "
            f"Each skill has: id, category, rule, rationale, evidence, source_files, "
            f"operational (department from {depts}, severity from {sevs}, action_type from {action_types}, "
            f"workflow_type from {wfs}, customer_tier from {tiers}, escalation_required, keywords), "
            f"conditions (field, operator, value, type, source). No markdown, no explanation."
        )
        try:
            retry = await llm_call(retry_prompt, extractions_text, max_tokens=8192)
            raw_skills = _try_parse(retry)
        except Exception as e2:
            print(f"[{job_id}] [synthesize_skills] Retry parse error: {e2}")
            raw_skills = []

    draft = []
    for skill in raw_skills:
        raw_op = skill.pop("operational", {}) or {}
        cleaned_op = _validate_operational_metadata(raw_op, metadata)
        metadata_confidence = _build_metadata_confidence(raw_op, cleaned_op)

        raw_conditions = skill.pop("conditions", []) or []
        validated_conditions = _validate_conditions(raw_conditions, metadata)
        conditions_confidence = _compute_conditions_confidence(
            raw_conditions, validated_conditions
        )

        actor = skill.pop("actor", None)
        escalation_target = skill.pop("escalation_target", None)
        approval_required = bool(skill.pop("approval_required", False))
        workflow_stage = skill.pop("workflow_stage", None)
        temporal_constraints = skill.pop("temporal_constraints", None)

        skill["operational"] = cleaned_op
        skill["metadata_confidence"] = metadata_confidence
        skill["conditions"] = validated_conditions
        skill["conditions_confidence"] = conditions_confidence
        skill["actor"] = actor
        skill["escalation_target"] = escalation_target
        skill["approval_required"] = approval_required
        skill["workflow_stage"] = workflow_stage
        skill["temporal_constraints"] = temporal_constraints
        skill["keywords"] = cleaned_op.pop("keywords", [])

        draft.append(skill)

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
