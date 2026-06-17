import re

OVERRIDE_PATTERNS = [
    (r"(?i)except", "overrides"),
    (r"(?i)notwithstanding", "overrides"),
    (r"(?i)regardless of", "overrides"),
    (r"(?i)overrides?", "overrides"),
    (r"(?i)supersedes?", "overrides"),
    (r"(?i)unless", "blocked_by"),
    (r"(?i)only if", "requires"),
    (r"(?i)must have", "requires"),
]

DEFAULT_AUTHORITY_LEVEL = 1

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


def get_authority_level(role: str) -> int:
    return AUTHORITY_LEVEL.get(role.lower().strip(), DEFAULT_AUTHORITY_LEVEL)


def merge_with_metadata(metadata_authority: dict) -> dict:
    merged = dict(AUTHORITY_LEVEL)
    if metadata_authority:
        merged.update(metadata_authority)
    return merged


def detect_structural_precedence(rule_text: str) -> list:
    signals = []
    for pattern, relation in OVERRIDE_PATTERNS:
        if pattern.search(rule_text):
            signals.append(
                {
                    "pattern": pattern.pattern,
                    "relation": relation,
                    "confidence": 0.6,
                }
            )
    return signals


def resolve_conflicts(policies: list, precedence_edges: list, context: dict, authority_levels: dict = None) -> list:
    if authority_levels is None:
        authority_levels = AUTHORITY_LEVEL
    scored = []
    for policy in policies:
        score = policy.get("priority", 0)
        reasons = []

        for edge in precedence_edges:
            if (
                edge.get("target_id") == policy.get("id")
                and edge.get("relation_type") == "overrides"
            ):
                score += edge.get("confidence", 0.5) * 2
                reasons.append(
                    f"Explicit override edge (confidence={edge.get('confidence', 0.5)})"
                )

        authority = policy.get("authority")
        if authority:
            auth_level = authority_levels.get(authority, DEFAULT_AUTHORITY_LEVEL)
            score += auth_level * 0.5
            reasons.append(f"Authority level {auth_level} ({authority})")

        condition_count = len(policy.get("conditions", []))
        score += condition_count * 0.3
        if condition_count > 0:
            reasons.append(f"Specificity bonus: {condition_count} conditions")

        score += policy.get("confidence", 0.5) * 0.5
        reasons.append(
            f"Confidence contribution: {policy.get('confidence', 0.5) * 0.5:.2f}"
        )

        scored.append(
            {
                "policy": policy,
                "effective_priority": score,
                "reasons": reasons,
            }
        )

    scored.sort(key=lambda x: x["effective_priority"], reverse=True)
    return scored
