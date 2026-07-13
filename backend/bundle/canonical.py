"""Canonical serialization and content addressing for policy bundles.

Contract:
  - `canonical_json(obj)` is deterministic: key order, separators, and unicode
    handling are fixed. Two semantically identical bundles always produce the
    same bytes, independent of construction order.
  - `bundle_content_hash(bundle)` = sha256 over the canonical form of the
    bundle's CONTENT ONLY (schema_version, workflows, policies). Registry
    metadata (company binding, timestamps, status) never affects the hash --
    the same policy content always addresses the same artifact.
  - Floats: finite floats are permitted; integral floats normalize to ints,
    non-integral floats serialize via CPython's shortest-round-trip repr
    (deterministic within CPython, which is the only producer in V1).
    NaN/Infinity are rejected -- they have no canonical JSON form. If this
    format ever becomes a cross-language signed artifact (KIR era), revisit
    with string decimals in a new schema version.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.bundle.schema import Bundle

HASH_PREFIX = "sha256:"


def _normalize(obj: Any) -> Any:
    """Recursively normalize to canonical-safe JSON values."""
    if isinstance(obj, dict):
        return {str(k): _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    if isinstance(obj, bool) or obj is None or isinstance(obj, (str, int)):
        return obj
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            raise ValueError(f"non-finite float {obj!r} has no canonical JSON form")
        if obj.is_integer():
            return int(obj)
        return obj
    raise TypeError(f"non-canonical type in content: {type(obj).__name__}")


def canonical_json(obj: Any) -> str:
    return json.dumps(
        _normalize(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def content_hash(obj: Any) -> str:
    digest = hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
    return HASH_PREFIX + digest


def bundle_content_hash(bundle: Bundle) -> str:
    content = {
        "schema_version": bundle.schema_version,
        "workflows": [w.model_dump(mode="json") for w in bundle.workflows],
        "policies": sorted(
            (p.model_dump(mode="json") for p in bundle.policies),
            key=lambda p: p["id"],
        ),
    }
    return content_hash(content)
