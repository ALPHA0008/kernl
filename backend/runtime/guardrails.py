"""
Guardrail: ensures the LLM never overrides the constraint resolver's decision.

The constraint resolver determines the correct action set deterministically.
The LLM is only supposed to verbalize it. This module catches and corrects
cases where the LLM tries to override the resolver.

This module NEVER calls an LLM. It is pure logic.
"""

from backend.runtime.constraint_resolver import ConstraintResult


def guardrail_check(llm_response: dict, resolver_result: ConstraintResult) -> dict:
    if not isinstance(llm_response, dict):
        llm_response = {}

    llm_response["_guardrail_fired"] = False
    llm_response["_guardrail_reason"] = None

    if resolver_result is None:
        return llm_response

    if resolver_result.primary_action is None:
        llm_response["_guardrail_fired"] = True
        llm_response["_guardrail_reason"] = (
            "Resolver was ambiguous; action_type set to 'ambiguous'"
        )
        llm_response["action_type"] = "ambiguous"
        return llm_response

    resolver_action = resolver_result.primary_action.action_type
    llm_action = llm_response.get("action_type", "")

    if not llm_action:
        llm_response["action_type"] = resolver_action
        llm_response["_guardrail_fired"] = True
        llm_response["_guardrail_reason"] = (
            f"LLM returned empty action_type. "
            f"Overridden to resolver's decision: '{resolver_action}'"
        )
        return llm_response

    if llm_action != resolver_action:
        llm_response["action_type"] = resolver_action
        llm_response["_guardrail_fired"] = True
        llm_response["_guardrail_reason"] = (
            f"LLM output '{llm_action}' diverged from constraint "
            f"resolver decision '{resolver_action}'. Overridden."
        )

    return llm_response
