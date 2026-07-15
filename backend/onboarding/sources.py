"""Source snapshots + evidence grounding.

A source snapshot is the frozen text of an uploaded document, content-addressed.
Evidence spans cite INTO a snapshot by (source_id, source_version, span). The
grounding verifier is the constitutional gate (CLAUDE.md rule 2): a span is only
a valid citation if its bytes EXACTLY match the stored source at those offsets.
This is the same check seed_rivanly.py performs by hand -- here it is the
runtime contract for onboarding, so no policy publishes on an unverified span.
"""

from __future__ import annotations

import hashlib
from typing import Optional, Protocol

from pydantic import BaseModel, ConfigDict

from backend.bundle.schema import Evidence


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class SourceSnapshot(BaseModel):
    """Immutable frozen document. content_hash is what an Evidence.source_version
    references; the bytes are what a span is verified against."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    company_id: str
    filename: str
    content_hash: str
    content: str
    byte_length: int
    created_at: str = ""


def make_snapshot(company_id: str, filename: str, content: str) -> SourceSnapshot:
    content_hash = _sha256(content)
    # content-addressed id: stable for identical bytes, so re-upload dedups
    source_id = "src_" + content_hash[7:19]
    return SourceSnapshot(
        source_id=source_id,
        company_id=company_id,
        filename=filename,
        content_hash=content_hash,
        content=content,
        byte_length=len(content.encode("utf-8")),
    )


class GroundingError(ValueError):
    """The selected span does not match the source bytes -- not a valid citation."""


def ground_evidence(
    snapshot: SourceSnapshot,
    span_start: int,
    span_end: int,
    excerpt: str,
) -> Evidence:
    """Verify that `excerpt` is EXACTLY the text at [span_start, span_end) in the
    snapshot, and mint a verified Evidence citation. Raises GroundingError on any
    mismatch -- the reviewer's selection must be the real bytes, never a
    paraphrase and never fabricated offsets."""
    text = snapshot.content
    if span_start < 0 or span_end > len(text) or span_start >= span_end:
        raise GroundingError(
            f"span [{span_start}, {span_end}) is out of range for source "
            f"of length {len(text)}"
        )
    actual = text[span_start:span_end]
    if actual != excerpt:
        raise GroundingError(
            "selected span does not match the source text: the highlighted "
            "excerpt must be the exact bytes at those offsets"
        )
    if not excerpt.strip():
        raise GroundingError("evidence excerpt is empty")
    return Evidence(
        source_id=snapshot.source_id,
        source_version=snapshot.content_hash,
        span_start=span_start,
        span_end=span_end,
        excerpt=excerpt,
    )


class SourceStore(Protocol):
    def add(self, snapshot: SourceSnapshot) -> SourceSnapshot: ...
    def get(self, company_id: str, source_id: str) -> Optional[SourceSnapshot]: ...
    def list(self, company_id: str) -> list[SourceSnapshot]: ...


class InMemorySourceStore:
    """Reference implementation + tested contract for the Postgres adapter."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], SourceSnapshot] = {}

    def add(self, snapshot: SourceSnapshot) -> SourceSnapshot:
        key = (snapshot.company_id, snapshot.source_id)
        # content-addressed: identical bytes dedup to the same snapshot
        if key in self._rows:
            return self._rows[key]
        stored = snapshot.model_copy(
            update={"created_at": snapshot.created_at or _now()}
        )
        self._rows[key] = stored
        return stored

    def get(self, company_id: str, source_id: str) -> Optional[SourceSnapshot]:
        return self._rows.get((company_id, source_id))

    def list(self, company_id: str) -> list[SourceSnapshot]:
        rows = [s for (cid, _), s in self._rows.items() if cid == company_id]
        return sorted(rows, key=lambda s: s.created_at, reverse=True)


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
