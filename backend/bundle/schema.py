"""Policy IR v1 -- the typed schema every published policy must satisfy.

Design contract (docs/V1_EXECUTION_PLAN.md section 4 step 1; docs/Kernel_arc.md Part 16 V1):
  - A published policy MUST have: an effect, evidence, and either at least one
    typed condition or an explicit unconditional acknowledgement.
  - Conditions are typed; operators are whitelisted per type.
  - Field values in facts and conditions are JSON scalars only.
  - Policies never mutate: a change is a new bundle.

The evaluator's semantics (backend/runtime/evaluator.py) depend on this schema;
changing anything here is an architecture change (see CLAUDE.md).
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1"

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")

# Operator whitelist per value type. Frozen: extending it is an architecture change.
VALID_OPERATORS: dict[str, frozenset[str]] = {
    "number": frozenset({"gt", "gte", "lt", "lte", "eq", "neq"}),
    "string": frozenset({"eq", "neq", "in", "not_in"}),
    "boolean": frozenset({"eq"}),
}

Scalar = Union[str, int, float, bool]


class OutcomeKind(str, Enum):
    """The four decision outcomes. Frozen enum -- shared by compiler drafts,
    runtime decisions, golden cases, and replay. One label scheme, one place."""

    APPROVE = "approve"
    DENY = "deny"
    ROUTE = "route"
    ESCALATE = "escalate"


class Condition(BaseModel):
    """A single typed condition. All of a policy's conditions must hold (AND)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str
    operator: str
    value: Union[Scalar, list[Scalar]]
    value_type: Literal["number", "string", "boolean"]

    @field_validator("field")
    @classmethod
    def _field_snake(cls, v: str) -> str:
        if not SNAKE_CASE.match(v):
            raise ValueError(f"condition field must be snake_case: {v!r}")
        return v

    @model_validator(mode="after")
    def _operator_valid(self) -> "Condition":
        allowed = VALID_OPERATORS[self.value_type]
        if self.operator not in allowed:
            raise ValueError(
                f"operator {self.operator!r} not allowed for type "
                f"{self.value_type!r} (allowed: {sorted(allowed)})"
            )
        list_ops = {"in", "not_in"}
        if self.operator in list_ops and not isinstance(self.value, list):
            raise ValueError(f"operator {self.operator!r} requires a list value")
        if self.operator not in list_ops and isinstance(self.value, list):
            raise ValueError(f"operator {self.operator!r} requires a scalar value")
        if self.value_type == "number":
            vals = self.value if isinstance(self.value, list) else [self.value]
            for v in vals:
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise ValueError(f"number condition has non-numeric value: {v!r}")
        return self


class Evidence(BaseModel):
    """Provenance for a policy. 'No evidence, no publish' is enforced here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str  # e.g. "notion_refund_sop.md"
    source_version: str  # content hash or version tag of the source snapshot
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=0)
    excerpt: str  # the quoted text; must be non-empty

    @model_validator(mode="after")
    def _span_ordered(self) -> "Evidence":
        if self.span_end < self.span_start:
            raise ValueError("span_end must be >= span_start")
        if not self.excerpt.strip():
            raise ValueError("evidence excerpt must be non-empty")
        return self


class Effect(BaseModel):
    """What the policy decides. `action` is the canonical, snake_case action label."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: OutcomeKind
    action: str

    @field_validator("action")
    @classmethod
    def _action_snake(cls, v: str) -> str:
        if not SNAKE_CASE.match(v):
            raise ValueError(f"action must be snake_case: {v!r}")
        return v


class Authority(BaseModel):
    """Whether exercising this policy's effect needs human approval first."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approval_required: bool = False
    approver_role: Optional[str] = None

    @model_validator(mode="after")
    def _role_iff_required(self) -> "Authority":
        if self.approval_required and not self.approver_role:
            raise ValueError("approval_required=True needs approver_role")
        return self


class Policy(BaseModel):
    """One reviewed, evidence-linked decision rule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    workflow: str
    effect: Effect
    priority: int = Field(ge=0, le=1000)
    conditions: tuple[Condition, ...] = ()
    authority: Authority = Authority()
    evidence: tuple[Evidence, ...]
    overrides: tuple[str, ...] = ()  # policy ids this policy defeats when both match
    unconditional_ack: bool = False  # explicit reviewer sign-off for 0 conditions
    rationale: str = ""

    @field_validator("id", "workflow")
    @classmethod
    def _ids_snake(cls, v: str) -> str:
        if not SNAKE_CASE.match(v.replace(".", "_")):
            raise ValueError(f"identifier must be snake_case (dots allowed): {v!r}")
        return v

    @model_validator(mode="after")
    def _publishable_shape(self) -> "Policy":
        if not self.evidence:
            raise ValueError(f"policy {self.id!r}: no evidence, no publish")
        if not self.conditions and not self.unconditional_ack:
            raise ValueError(
                f"policy {self.id!r}: a policy without conditions requires "
                "unconditional_ack=True (explicit reviewer sign-off)"
            )
        if self.id in self.overrides:
            raise ValueError(f"policy {self.id!r} cannot override itself")
        return self

    @property
    def specificity(self) -> int:
        return len(self.conditions)


class FactSpec(BaseModel):
    """Declares one fact a workflow understands. `default` (if set) is applied
    when the fact is absent from a request -- reviewed data, not code."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    value_type: Literal["number", "string", "boolean"]
    description: str = ""
    default: Optional[Scalar] = None

    @field_validator("name")
    @classmethod
    def _name_snake(cls, v: str) -> str:
        if not SNAKE_CASE.match(v):
            raise ValueError(f"fact name must be snake_case: {v!r}")
        return v

    @model_validator(mode="after")
    def _default_typed(self) -> "FactSpec":
        if self.default is None:
            return self
        ok = {
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "string": lambda v: isinstance(v, str),
            "boolean": lambda v: isinstance(v, bool),
        }[self.value_type](self.default)
        if not ok:
            raise ValueError(
                f"fact {self.name!r}: default {self.default!r} does not match "
                f"declared type {self.value_type!r}"
            )
        return self


class WorkflowSpec(BaseModel):
    """A decision domain (e.g. refund). Owns its fact vocabulary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    facts: tuple[FactSpec, ...]
    description: str = ""

    @model_validator(mode="after")
    def _unique_facts(self) -> "WorkflowSpec":
        names = [f.name for f in self.facts]
        if len(names) != len(set(names)):
            raise ValueError(f"workflow {self.name!r}: duplicate fact names")
        return self

    def fact_map(self) -> dict[str, FactSpec]:
        return {f.name: f for f in self.facts}


class Bundle(BaseModel):
    """The compiled, immutable decision artifact. Content-addressed by
    `bundle_content_hash` over its canonical form (see canonical.py)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = SCHEMA_VERSION
    company_id: str
    workflows: tuple[WorkflowSpec, ...]
    policies: tuple[Policy, ...]

    @model_validator(mode="after")
    def _integrity(self) -> "Bundle":
        wf_names = {w.name for w in self.workflows}
        if len(wf_names) != len(self.workflows):
            raise ValueError("duplicate workflow names")
        pol_ids = [p.id for p in self.policies]
        if len(pol_ids) != len(set(pol_ids)):
            raise ValueError("duplicate policy ids")
        id_set = set(pol_ids)
        for p in self.policies:
            if p.workflow not in wf_names:
                raise ValueError(f"policy {p.id!r}: unknown workflow {p.workflow!r}")
            for target in p.overrides:
                if target not in id_set:
                    raise ValueError(f"policy {p.id!r} overrides unknown policy {target!r}")
            wf = next(w for w in self.workflows if w.name == p.workflow)
            known = set(wf.fact_map())
            for c in p.conditions:
                if c.field not in known:
                    raise ValueError(
                        f"policy {p.id!r}: condition field {c.field!r} not declared "
                        f"in workflow {p.workflow!r} facts"
                    )
                spec = wf.fact_map()[c.field]
                if spec.value_type != c.value_type:
                    raise ValueError(
                        f"policy {p.id!r}: condition on {c.field!r} typed "
                        f"{c.value_type!r} but workflow declares {spec.value_type!r}"
                    )
        # overrides must stay within one workflow and be acyclic
        by_id = {p.id: p for p in self.policies}
        for p in self.policies:
            for target in p.overrides:
                if by_id[target].workflow != p.workflow:
                    raise ValueError(
                        f"policy {p.id!r} overrides {target!r} in a different workflow"
                    )
        _assert_acyclic_overrides(self.policies)
        return self

    def workflow(self, name: str) -> WorkflowSpec:
        for w in self.workflows:
            if w.name == name:
                return w
        raise KeyError(f"unknown workflow: {name!r}")

    def policies_for(self, workflow: str) -> tuple[Policy, ...]:
        return tuple(p for p in self.policies if p.workflow == workflow)


def _assert_acyclic_overrides(policies: tuple[Policy, ...]) -> None:
    graph = {p.id: set(p.overrides) for p in policies}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = dict.fromkeys(graph, WHITE)

    def visit(node: str, stack: list[str]) -> None:
        color[node] = GRAY
        for nxt in graph[node]:
            if color[nxt] == GRAY:
                raise ValueError(f"override cycle: {' -> '.join(stack + [node, nxt])}")
            if color[nxt] == WHITE:
                visit(nxt, stack + [node])
        color[node] = BLACK

    for node in graph:
        if color[node] == WHITE:
            visit(node, [])
