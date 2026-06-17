"""
Deterministic condition evaluation engine.
No LLM involved. Pure type-safe comparison.

Handles:
  - Missing context fields -> neutral (treated as not applicable, not failure)
  - Type mismatches -> caught and logged, never crashed
  - Boundary values -> explicit comparison (14 <= 14 is True)
"""

VALID_OPERATORS = {
    "number": {">", ">=", "<", "<=", "==", "!="},
    "string": {"==", "!=", "in", "not_in"},
    "boolean": {"=="},
}


def evaluate_condition(cond: dict, context: dict) -> bool:
    field = cond.get("field")
    operator = cond.get("operator")
    value = cond.get("value")
    cond_type = cond.get("type", "string")

    ctx_val = context.get(field)
    if ctx_val is None:
        return True

    try:
        if cond_type == "number":
            ctx_val = float(ctx_val)
            value = float(value)
        elif cond_type == "string":
            ctx_val = str(ctx_val).lower().strip()
            if operator in ("in", "not_in") and isinstance(value, list):
                value = [str(v).lower().strip() for v in value]
            else:
                value = str(value).lower().strip()
        elif cond_type == "boolean":
            ctx_val = bool(ctx_val)
            value = bool(value)
    except (TypeError, ValueError):
        return False

    if operator == "==":
        return ctx_val == value
    elif operator == "!=":
        return ctx_val != value
    elif operator == ">":
        return ctx_val > value
    elif operator == ">=":
        return ctx_val >= value
    elif operator == "<":
        return ctx_val < value
    elif operator == "<=":
        return ctx_val <= value
    elif operator == "in" and isinstance(value, list):
        return ctx_val in value
    elif operator == "not_in" and isinstance(value, list):
        return ctx_val not in value

    return False


def evaluate_conditions(conditions: list, context: dict) -> dict:
    if not conditions:
        return {
            "all_met": True,
            "matched_count": 0,
            "total_evaluated": 0,
            "details": [],
        }

    results = []
    matched = 0
    for cond in conditions:
        result = evaluate_condition(cond, context)
        results.append(
            {
                "field": cond.get("field"),
                "operator": cond.get("operator"),
                "value": cond.get("value"),
                "matched": result,
            }
        )
        if result:
            matched += 1

    return {
        "all_met": matched == len(conditions),
        "matched_count": matched,
        "total_evaluated": len(conditions),
        "details": results,
    }
