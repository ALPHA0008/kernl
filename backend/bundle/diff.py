"""Bundle diff: what publishing a candidate would change vs another bundle.

Pure function over two Bundle objects -- no store access, no side effects.
Used by the Policy Workbench diff view (V1_EXECUTION_PLAN.md section 7,
screen 1: "diff draft bundle vs published"). This is a structural diff over
policy content, distinct from replay (which diffs *decision outcomes* on a
case set); the two are complementary, not substitutes.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.bundle.schema import Bundle, Policy


class PolicyChange(BaseModel):
    """A single policy that differs between the two bundles being compared."""

    model_config = ConfigDict(frozen=True)

    policy_id: str
    workflow: str
    change: str  # "added" | "removed" | "modified"
    before: Policy | None = None
    after: Policy | None = None
    changed_fields: tuple[str, ...] = ()


class BundleDiff(BaseModel):
    model_config = ConfigDict(frozen=True)

    from_hash: str | None  # None if there was nothing to compare against
    to_hash: str
    added: tuple[PolicyChange, ...]
    removed: tuple[PolicyChange, ...]
    modified: tuple[PolicyChange, ...]
    unchanged_count: int

    @property
    def is_empty(self) -> bool:
        return not self.added and not self.removed and not self.modified


_COMPARE_FIELDS = ("effect", "priority", "conditions", "authority", "evidence",
                    "overrides", "unconditional_ack", "rationale", "workflow")


def _changed_fields(before: Policy, after: Policy) -> tuple[str, ...]:
    return tuple(f for f in _COMPARE_FIELDS if getattr(before, f) != getattr(after, f))


def diff_bundles(before: Bundle | None, after: Bundle) -> BundleDiff:
    """Structural diff: which policies were added, removed, or modified going
    from `before` to `after`. `before=None` (no prior bundle, e.g. a tenant's
    first draft) reports every policy in `after` as added."""
    before_map: dict[str, Policy] = {p.id: p for p in before.policies} if before else {}
    after_map: dict[str, Policy] = {p.id: p for p in after.policies}

    added = tuple(
        PolicyChange(policy_id=pid, workflow=p.workflow, change="added", after=p)
        for pid, p in after_map.items() if pid not in before_map
    )
    removed = tuple(
        PolicyChange(policy_id=pid, workflow=p.workflow, change="removed", before=p)
        for pid, p in before_map.items() if pid not in after_map
    )
    modified = tuple(
        PolicyChange(
            policy_id=pid, workflow=after_map[pid].workflow, change="modified",
            before=before_map[pid], after=after_map[pid],
            changed_fields=_changed_fields(before_map[pid], after_map[pid]),
        )
        for pid in after_map
        if pid in before_map and before_map[pid] != after_map[pid]
    )
    unchanged = sum(
        1 for pid in after_map if pid in before_map and before_map[pid] == after_map[pid]
    )

    return BundleDiff(
        from_hash=_hash_or_none(before),
        to_hash=_hash_of(after),
        added=added,
        removed=removed,
        modified=modified,
        unchanged_count=unchanged,
    )


def _hash_of(b: Bundle) -> str:
    from backend.bundle.canonical import bundle_content_hash
    return bundle_content_hash(b)


def _hash_or_none(b: Bundle | None) -> str | None:
    return _hash_of(b) if b is not None else None
