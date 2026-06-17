from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


VALID_ENTITY_TYPES = {
    "customer",
    "plan",
    "invoice",
    "employee",
    "vendor",
    "team",
    "role",
    "department",
    "product",
    "sla",
    "service",
    "environment",
    "incident",
    "feature",
    "contract",
    "event",
    "notification",
}

VALID_RELATION_TYPES = {
    "requires",
    "blocks",
    "overrides",
    "escalates_to",
    "depends_on",
    "triggers",
    "has_policy",
    "reports_to",
    "approves",
    "notifies",
    "assigns",
    "applies_to",
    "owns",
    "manages",
    "impacts",
    "resolves",
}

VALID_EFFECTS = {
    "approve",
    "deny",
    "escalate",
    "require_approval",
    "monitor",
    "ambiguous",
    "approve_prorated",
    "page_on_call",
    "resolve_within_4_hours",
    "initiate_pip",
    "initiate_enterprise_onboarding",
    "get_founder_approval",
    "route_to_ops_lead",
    "notify_am_and_eng_lead",
    "send_incident_template",
    "schedule_am_call",
    "approve_20_percent_startup_discount",
    "suspend",
    "cancel",
    "review",
    "investigate",
    "schedule",
    "notify",
    "report",
    "validate",
    "delegate",
}

AUTHORITY_LEVEL = {
    "founder": 5,
    "ceo": 5,
    "cfo": 4,
    "cto": 4,
    "vp": 4,
    "vice_president": 4,
    "principal": 4,
    "director": 3,
    "head": 3,
    "manager": 3,
    "lead": 3,
    "account_executive": 2,
    "account_manager": 2,
    "engineer": 2,
    "support_lead": 2,
    "support_agent": 1,
    "ops_lead": 3,
    "admin": 1,
    "specialist": 2,
    "analyst": 2,
    "coordinator": 1,
    "consultant": 2,
    "supervisor": 3,
    "team_lead": 3,
    "intern": 0,
    "default": 1,
}

DEFAULT_AUTHORITY_LEVEL = 1


def get_authority_level(role: str) -> int:
    return AUTHORITY_LEVEL.get(role.lower().strip(), DEFAULT_AUTHORITY_LEVEL)


@dataclass
class TypedCondition:
    field: str
    operator: str
    value: Any
    type: str = "string"
    source: str = "rule"

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "operator": self.operator,
            "value": self.value,
            "type": self.type,
            "source": self.source,
        }


@dataclass
class OperationalEntity:
    id: str
    entity_type: str
    properties: Dict[str, Any]
    source_files: List[str]
    confidence: float = 0.5
    requires_review: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "properties": self.properties,
            "source_files": self.source_files,
            "confidence": self.confidence,
            "requires_review": self.requires_review,
        }


@dataclass
class RelationshipEdge:
    id: str
    source_id: str
    target_id: str
    relation_type: str
    conditions: List[TypedCondition] = field(default_factory=list)
    confidence: float = 0.5
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "conditions": [c.to_dict() for c in self.conditions],
            "confidence": self.confidence,
            "source": self.source,
        }


def validate_entity(entity: dict) -> bool:
    if not isinstance(entity.get("id"), str) or not entity["id"].strip():
        return False
    if entity.get("entity_type") not in VALID_ENTITY_TYPES:
        return False
    return True


def validate_relationship(rel: dict, known_entity_ids: set) -> bool:
    if rel.get("relation_type") not in VALID_RELATION_TYPES:
        return False
    if rel.get("source_id") not in known_entity_ids:
        return False
    if rel.get("target_id") not in known_entity_ids:
        return False
    return True


def validate_authority_rule(rule: dict) -> bool:
    if not isinstance(rule.get("role"), str):
        return False
    if not isinstance(rule.get("can_approve"), list):
        return False
    return True
