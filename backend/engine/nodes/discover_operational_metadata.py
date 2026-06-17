import re
from collections import Counter
from backend.engine.state import BrainState
from backend.core.sse import emit


async def discover_operational_metadata(state: BrainState) -> dict:
    job_id = state["job_id"]
    company_id = state["company_id"]

    print(f"[{job_id}] Node discover_operational_metadata: analyzing extracted data")
    await emit(
        job_id,
        "stage",
        {
            "name": "DISCOVER_METADATA",
            "detail": "Discovering operational metadata from extracted data...",
        },
    )

    graph = state.get("operational_graph", {})
    entities = graph.get("entities", {})
    edges = graph.get("edges", [])
    authority_rules = graph.get("authority_rules", {})

    raw_decisions = state.get("raw_decisions", [])
    workflow_steps = state.get("workflow_steps", [])
    exception_rules = state.get("exception_rules", [])
    contradictions = state.get("contradictions", [])
    extracted_entities = state.get("extracted_entities", [])
    extracted_relationships = state.get("extracted_relationships", [])
    extracted_authority_rules = state.get("extracted_authority_rules", [])

    all_rules = []
    for d in raw_decisions:
        text = " ".join(
            filter(
                None, [d.get("rule", ""), d.get("category", ""), d.get("rationale", "")]
            )
        )
        all_rules.append(text)
    for w in workflow_steps:
        text = " ".join(
            filter(
                None,
                [w.get("step", ""), w.get("workflow_type", ""), w.get("action", "")],
            )
        )
        all_rules.append(text)
    for e in exception_rules:
        text = " ".join(
            filter(
                None,
                [e.get("condition", ""), e.get("action", ""), e.get("rationale", "")],
            )
        )
        all_rules.append(text)

    valid_departments = _collect_departments(
        entities, raw_decisions, workflow_steps, extracted_authority_rules
    )
    valid_severities = _collect_severities(
        raw_decisions, workflow_steps, exception_rules
    )
    valid_workflow_types = _collect_workflow_types(workflow_steps, raw_decisions)
    valid_customer_tiers = _collect_customer_tiers(entities, raw_decisions)
    condition_fields = _collect_condition_fields(raw_decisions, workflow_steps)
    action_types = _collect_action_types(raw_decisions, workflow_steps, all_rules)
    action_ontology = _build_action_ontology(
        action_types, extracted_relationships, extracted_authority_rules, all_rules
    )
    heuristic_patterns = _build_heuristic_patterns(all_rules, action_types)
    authority_levels = _build_authority_levels(
        authority_rules, extracted_authority_rules, extracted_entities
    )

    retrieval_weights = {
        "semantic": 0.45,
        "metadata": 0.20,
        "keyword": 0.15,
        "severity": 0.10,
        "condition": 0.10,
    }

    thresholds = {
        "metadata_confidence": 0.60,
        "conditions_confidence": 0.60,
        "ambiguity_entropy": 0.75,
        "min_confidence_for_auto_action": 0.40,
        "graph_fallback_threshold": 0.5,
        "score_differential_threshold": 0.10,
        "specificity_bonus_scale": 0.02,
    }

    metadata = {
        "action_types": {
            "values": sorted(action_types),
            "ontology": action_ontology,
        },
        "valid_sets": {
            "departments": sorted(valid_departments),
            "severities": sorted(valid_severities),
            "workflow_types": sorted(valid_workflow_types),
            "customer_tiers": sorted(valid_customer_tiers),
            "condition_fields": sorted(condition_fields),
        },
        "heuristic_patterns": heuristic_patterns,
        "authority_levels": authority_levels,
        "retrieval_weights": retrieval_weights,
        "thresholds": thresholds,
    }

    stats = {
        "action_types_found": len(action_types),
        "ontology_depth": max(
            (o.get("specificity", 1) for o in action_ontology.values()), default=0
        ),
        "heuristic_patterns_found": len(heuristic_patterns),
        "authority_levels_found": len(authority_levels),
        "valid_departments": len(valid_departments),
        "valid_severities": len(valid_severities),
        "valid_workflow_types": len(valid_workflow_types),
        "valid_customer_tiers": len(valid_customer_tiers),
        "condition_fields_found": len(condition_fields),
    }

    print(
        f"[{job_id}] discover_operational_metadata: {len(action_types)} action types, "
        f"{len(heuristic_patterns)} heuristic patterns, {len(authority_levels)} authority levels"
    )
    await emit(
        job_id,
        "stage",
        {
            "name": "DISCOVER_METADATA_DONE",
            "detail": f"Discovered {len(action_types)} action types, {len(heuristic_patterns)} patterns, {len(authority_levels)} authority levels",
        },
    )

    return {"operational_metadata": metadata}


def _collect_departments(
    entities: dict, raw_decisions: list, workflow_steps: list, authority_rules: list
) -> set:
    depts = {"general"}
    for e in entities.values():
        props = e.get("properties", {})
        dept = props.get("department", "")
        if dept:
            depts.add(dept.lower().strip())
        etype = e.get("entity_type", "")
        if etype == "team":
            team_dept = props.get("name", "").lower().strip()
            if team_dept:
                depts.add(team_dept)
    for d in raw_decisions:
        cat = d.get("category", "")
        if cat:
            depts.add(cat.lower().strip().replace(" ", "_"))
        dept = d.get("department", "")
        if dept:
            depts.add(dept.lower().strip().replace(" ", "_"))
    for w in workflow_steps:
        wf_dept = w.get("department", "")
        if wf_dept:
            depts.add(wf_dept.lower().strip().replace(" ", "_"))
    for r in authority_rules:
        role = r.get("role", "").lower().strip()
        if "support" in role:
            depts.add("customer_support")
        elif "eng" in role or "dev" in role:
            depts.add("engineering")
        elif "finance" in role or "rev" in role:
            depts.add("finance")
        elif "hr" in role:
            depts.add("hr")
        elif "ops" in role:
            depts.add("operations")
        elif "success" in role or "account" in role:
            depts.add("customer_success")
    return depts


def _collect_severities(
    raw_decisions: list, workflow_steps: list, exception_rules: list
) -> set:
    sevs = {"general", "policy"}
    for d in raw_decisions:
        sev = d.get("severity", "")
        if sev:
            sevs.add(sev.upper().strip())
    for w in workflow_steps:
        sev = w.get("severity", "")
        if sev:
            sevs.add(sev.upper().strip())
    for e in exception_rules:
        sev = e.get("severity", "")
        if sev:
            sevs.add(sev.upper().strip())
        text = (e.get("condition", "") + " " + e.get("action", "")).lower()
        if "p0" in text or "critical" in text or "outage" in text or "down" in text:
            sevs.add("P0")
        if "p1" in text or "major" in text:
            sevs.add("P1")
        if "p2" in text or "minor" in text:
            sevs.add("P2")
        if "sla" in text:
            sevs.add("sla")
    return sevs


def _collect_workflow_types(workflow_steps: list, raw_decisions: list) -> set:
    wfs = {"general"}
    for w in workflow_steps:
        wt = w.get("workflow_type", "")
        if wt:
            wfs.add(wt.lower().strip())
    for d in raw_decisions:
        text = d.get("rule", "").lower()
        for keyword in [
            "incident",
            "hiring",
            "recruit",
            "refund",
            "discount",
            "onboard",
            "escalat",
            "perform",
            "pip",
            "invoice",
            "billing",
            "churn",
        ]:
            if keyword in text:
                mapped = {
                    "recruit": "hiring",
                    "pip": "performance",
                    "onboard": "onboarding",
                    "escalat": "escalation",
                    "perform": "performance",
                }
                wfs.add(mapped.get(keyword, keyword))
    return wfs


def _collect_customer_tiers(entities: dict, raw_decisions: list) -> set:
    tiers = {"all"}
    for e in entities.values():
        props = e.get("properties", {})
        for val in props.values():
            if isinstance(val, str) and val.lower() in (
                "enterprise",
                "annual",
                "monthly",
                "startup",
                "lifetime",
                "trial",
                "free",
                "pro",
                "business",
                "premium",
            ):
                tiers.add(val.lower())
    for d in raw_decisions:
        text = d.get("rule", "").lower()
        for keyword in [
            "enterprise",
            "annual",
            "monthly",
            "startup",
            "lifetime",
            "trial",
            "free",
            "pro",
            "business",
            "premium",
        ]:
            if keyword in text:
                tiers.add(keyword)
    return tiers


def _collect_condition_fields(raw_decisions: list, workflow_steps: list) -> set:
    fields = set()
    for d in raw_decisions:
        conds = d.get("conditions", [])
        for c in conds:
            f = c.get("field", "")
            if f:
                fields.add(f)
        text = d.get("rule", "") + " " + d.get("rationale", "")
        fields.update(_infer_condition_fields_from_text(text))
    for w in workflow_steps:
        conds = w.get("conditions", [])
        for c in conds:
            f = c.get("field", "")
            if f:
                fields.add(f)
        text = w.get("step", "") + " " + w.get("condition", "")
        fields.update(_infer_condition_fields_from_text(text))
    if not fields:
        fields = {
            "customer_tier",
            "plan_type",
            "days_since_purchase",
            "refund_amount",
            "tenure_months",
            "discount_percent",
            "churn_signals_count",
            "customer_stage",
            "priority",
            "issue_type",
            "amount",
            "quantity",
            "region",
            "industry",
            "company_size",
            "role",
            "department",
        }
    return fields


_CONDITION_FIELD_PATTERNS = [
    (re.compile(r"(?i)(\d+)\s*day"), "days_since_purchase"),
    (re.compile(r"(?i)(\d+)\s*month"), "tenure_months"),
    (re.compile(r"(?i)\$\s*(\d+)"), "refund_amount"),
    (re.compile(r"(?i)(\d+)\s*percent|(\d+)\s*%"), "discount_percent"),
    (re.compile(r"(?i)(\d+)\s*churn"), "churn_signals_count"),
    (re.compile(r"(?i)priority\s*(p[012])"), "priority"),
    (re.compile(r"(?i)enterprise|annual|monthly|startup"), "customer_tier"),
    (re.compile(r"(?i)plan|starter|pro|business"), "plan_type"),
]


def _infer_condition_fields_from_text(text: str) -> set:
    fields = set()
    for pattern, field_name in _CONDITION_FIELD_PATTERNS:
        if pattern.search(text):
            fields.add(field_name)
    return fields


def _collect_action_types(
    raw_decisions: list, workflow_steps: list, all_rules: list
) -> list:
    actions = set()
    action_verbs = {
        "approve",
        "deny",
        "reject",
        "escalate",
        "refund",
        "monitor",
        "review",
        "notify",
        "page",
        "schedule",
        "initiate",
        "resolve",
        "route",
        "assign",
        "delegate",
        "approve_prorated",
        "get_founder_approval",
        "notify_am_and_eng_lead",
        "send_incident_template",
        "resolve_within_4_hours",
        "approve_20_percent_startup_discount",
        "route_to_ops_lead",
        "initiate_enterprise_onboarding",
        "initiate_pip",
        "page_on_call",
        "schedule_am_call",
        "suspend",
        "cancel",
        "close",
        "investigate",
        "document",
        "report",
        "validate",
        "verify",
        "confirm",
        "reject",
        "refund",
        "create_ticket",
        "update_status",
        "follow_up",
        "call",
    }

    for d in raw_decisions:
        action = d.get("action", "") or d.get("action_type", "")
        if action:
            normalized = action.lower().strip().replace(" ", "_").replace("-", "_")
            actions.add(normalized)
        text = d.get("rule", "").lower()
        for verb in action_verbs:
            if verb in text:
                actions.add(verb)

    for w in workflow_steps:
        action = w.get("action", "") or w.get("action_type", "")
        if action:
            normalized = action.lower().strip().replace(" ", "_").replace("-", "_")
            actions.add(normalized)

    for text in all_rules:
        for verb in action_verbs:
            if verb in text.lower():
                actions.add(verb)

    return sorted(
        actions,
        key=lambda x: (
            -len(x)
            if x
            in (
                "get_founder_approval",
                "notify_am_and_eng_lead",
                "send_incident_template",
                "resolve_within_4_hours",
                "approve_20_percent_startup_discount",
                "route_to_ops_lead",
                "initiate_enterprise_onboarding",
                "initiate_pip",
                "page_on_call",
                "schedule_am_call",
                "approve_prorated",
            )
            else len(x)
        ),
    )


def _build_action_ontology(
    action_types: list,
    extracted_relationships: list,
    extracted_authority_rules: list,
    all_rules: list,
) -> dict:
    ontology = {}
    action_set = set(action_types)

    parent_map = {}
    for rel in extracted_relationships:
        rtype = rel.get("relation_type", "")
        if rtype in ("escalates_to", "approves", "overrides"):
            source = rel.get("source_id", "").lower().strip()
            target = rel.get("target_id", "").lower().strip()
            if source and target:
                for action in action_set:
                    if action in source or action in target:
                        parent_map[source] = target

    for action in action_types:
        category = _infer_category(action)
        parent = parent_map.get(action)
        children = [a for a in action_types if parent_map.get(a) == action]
        specificity = _compute_specificity(action, len(children))
        ontology[action] = {
            "category": category,
            "parent": parent,
            "specificity": specificity,
            "children": children,
        }

    return ontology


def _infer_category(action: str) -> str:
    if any(t in action for t in ("approve", "deny", "reject", "refund")):
        return "approval"
    if any(t in action for t in ("escalat", "founder", "lead")):
        return "escalation"
    if any(t in action for t in ("page", "incident", "resolve", "p0", "p1")):
        return "incident_response"
    if any(t in action for t in ("onboard", "schedule", "call", "churn", "success")):
        return "customer_success"
    if any(t in action for t in ("pip", "perform", "hire", "recruit")):
        return "hr"
    if any(t in action for t in ("invoice", "billing", "payment", "vendor")):
        return "finance"
    if any(t in action for t in ("monitor", "review", "investigate")):
        return "observation"
    if any(t in action for t in ("notify", "route", "assign")):
        return "communication"
    return "general"


def _compute_specificity(action: str, child_count: int) -> int:
    base = 2
    words = action.split("_")
    base += max(0, len(words) - 1)
    if child_count > 0:
        base += 1
    return min(base, 5)


def _build_heuristic_patterns(all_rules: list, action_types: list) -> dict:
    patterns = {}
    action_set = set(action_types)

    phrase_action_map = {
        "refund": "approve",
        "p0 outage": "page_on_call",
        "production down": "page_on_call",
        "completely down": "page_on_call",
        "notify am": "notify_am_and_eng_lead",
        "performance improvement": "initiate_pip",
        "20 percent": "approve_20_percent_startup_discount",
        "startup discount": "approve_20_percent_startup_discount",
        "4 hours": "resolve_within_4_hours",
        "founder approval": "get_founder_approval",
        "ops lead": "route_to_ops_lead",
        "prorated": "approve_prorated",
        "enterprise onboard": "initiate_enterprise_onboarding",
        "schedule call": "schedule_am_call",
        "eng lead": "notify_am_and_eng_lead",
    }

    for phrase, action in phrase_action_map.items():
        if action in action_set:
            patterns[phrase] = action

    for text in all_rules:
        text_lower = text.lower()
        for action in action_types:
            if action in text_lower:
                words = action.split("_")
                if len(words) >= 2:
                    key = " ".join(words)
                    if key not in patterns:
                        patterns[key] = action

    return patterns


def _build_authority_levels(
    authority_rules: dict,
    extracted_authority_rules: list,
    extracted_entities: list,
) -> dict:
    levels = {}

    standard_hierarchy = [
        ("founder", 5),
        ("ceo", 5),
        ("cfo", 4),
        ("cto", 4),
        ("vp", 4),
        ("director", 3),
        ("manager", 3),
        ("lead", 3),
        ("senior", 2),
        ("engineer", 2),
        ("specialist", 2),
        ("agent", 1),
        ("intern", 0),
    ]

    for role in authority_rules:
        levels[role] = _assign_authority_level(role, standard_hierarchy)

    for rule in extracted_authority_rules:
        role = rule.get("role", "").lower().strip()
        if role and role not in levels:
            levels[role] = _assign_authority_level(role, standard_hierarchy)

    for entity in extracted_entities:
        etype = entity.get("entity_type", "")
        if etype == "role":
            eid = entity.get("id", "").lower().strip()
            if eid and eid not in levels:
                levels[eid] = _assign_authority_level(eid, standard_hierarchy)

    if not levels:
        levels = {"default": 1}

    return levels


def _assign_authority_level(role: str, hierarchy: list) -> int:
    role_lower = role.lower().strip()
    for title, level in hierarchy:
        if title in role_lower:
            return level
    if any(t in role_lower for t in ("support", "help", "cs", "agent")):
        return 1
    if any(t in role_lower for t in ("eng", "dev", "tech", "swe")):
        return 2
    if any(t in role_lower for t in ("manager", "head", "director")):
        return 3
    if any(t in role_lower for t in ("vp", "vice", "chief", "principal")):
        return 4
    return 1
