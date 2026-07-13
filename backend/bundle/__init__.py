"""Policy Bundle: the immutable, content-addressed artifact that is the only
runtime decision authority in Kernl V1.

Modules:
    schema     -- Policy IR (pydantic models) and validation rules
    canonical  -- canonical JSON serialization + SHA-256 content addressing
    store      -- storage protocol with in-memory and Supabase implementations
    lifecycle  -- draft -> published -> retired transitions, replay-gated publish
"""

from backend.bundle.schema import (
    Bundle,
    Condition,
    Effect,
    Evidence,
    FactSpec,
    OutcomeKind,
    Policy,
    WorkflowSpec,
)
from backend.bundle.canonical import bundle_content_hash, canonical_json

__all__ = [
    "Bundle",
    "Condition",
    "Effect",
    "Evidence",
    "FactSpec",
    "OutcomeKind",
    "Policy",
    "WorkflowSpec",
    "bundle_content_hash",
    "canonical_json",
]
