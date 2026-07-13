"""Bundle registry + lifecycle: draft -> published -> retired.

Rules enforced here (constitutional -- CLAUDE.md rules 3 and 5):
  - Bundles are immutable: a row is written once; activation moves a pointer.
  - Exactly one published (active) bundle per company.
  - PUBLISH IS REPLAY-GATED: a draft may only be published if an acknowledged
    replay run exists for exactly its content hash.
  - Publishing identical content to the active bundle is a no-op.
  - Rollback = activating a previously published bundle (a pointer move).
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Protocol

from pydantic import BaseModel, ConfigDict

from backend.bundle.canonical import bundle_content_hash
from backend.bundle.schema import Bundle
from backend.replay.engine import ReplayRunStore


class BundleStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class BundleRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_id: str
    company_id: str
    content_hash: str
    status: BundleStatus
    bundle: Bundle
    created_at: str
    created_by: str
    published_at: Optional[str] = None
    published_by: Optional[str] = None
    replay_run_id: Optional[str] = None  # the run that gated this publish


class BundleStore(Protocol):
    def add(self, record: BundleRecord) -> BundleRecord: ...
    def get(self, company_id: str, record_id: str) -> Optional[BundleRecord]: ...
    def by_hash(self, company_id: str, content_hash: str) -> Optional[BundleRecord]: ...
    def active(self, company_id: str) -> Optional[BundleRecord]: ...
    def set_active(self, company_id: str, record_id: str) -> BundleRecord: ...
    def update(self, record: BundleRecord) -> BundleRecord: ...
    def list(self, company_id: str) -> list[BundleRecord]: ...


class InMemoryBundleStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[tuple[str, str], BundleRecord] = {}
        self._active: dict[str, str] = {}

    def add(self, record: BundleRecord) -> BundleRecord:
        with self._lock:
            self._rows[(record.company_id, record.record_id)] = record
            return record

    def get(self, company_id: str, record_id: str) -> Optional[BundleRecord]:
        return self._rows.get((company_id, record_id))

    def by_hash(self, company_id: str, content_hash: str) -> Optional[BundleRecord]:
        for (cid, _), r in self._rows.items():
            if cid == company_id and r.content_hash == content_hash:
                return r
        return None

    def active(self, company_id: str) -> Optional[BundleRecord]:
        rid = self._active.get(company_id)
        return self._rows.get((company_id, rid)) if rid else None

    def set_active(self, company_id: str, record_id: str) -> BundleRecord:
        with self._lock:
            record = self._rows[(company_id, record_id)]
            self._active[company_id] = record_id
            return record

    def update(self, record: BundleRecord) -> BundleRecord:
        with self._lock:
            self._rows[(record.company_id, record.record_id)] = record
            return record

    def list(self, company_id: str) -> list[BundleRecord]:
        rows = [r for (cid, _), r in self._rows.items() if cid == company_id]
        rows.sort(key=lambda r: r.created_at, reverse=True)
        return rows


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class PublishGateError(RuntimeError):
    """Publish blocked: no acknowledged replay run for this exact draft."""


class BundleLifecycle:
    def __init__(self, store: BundleStore, replay_runs: ReplayRunStore) -> None:
        self._store = store
        self._replays = replay_runs

    def save_draft(self, company_id: str, bundle: Bundle, created_by: str) -> BundleRecord:
        content = bundle_content_hash(bundle)
        existing = self._store.by_hash(company_id, content)
        if existing is not None:
            return existing  # identical content already registered
        record = BundleRecord(
            record_id=str(uuid.uuid4()),
            company_id=company_id,
            content_hash=content,
            status=BundleStatus.DRAFT,
            bundle=bundle,
            created_at=_now_iso(),
            created_by=created_by,
        )
        return self._store.add(record)

    def publish(self, company_id: str, record_id: str, published_by: str) -> BundleRecord:
        record = self._store.get(company_id, record_id)
        if record is None:
            raise KeyError(f"unknown bundle record {record_id!r}")
        active = self._store.active(company_id)
        if active is not None and active.content_hash == record.content_hash:
            return active  # identical content already live: no-op

        gate = self._replays.latest_acknowledged_for(company_id, record.content_hash)
        if gate is None:
            raise PublishGateError(
                f"no acknowledged replay run for draft {record.content_hash}; "
                "run and acknowledge a replay before publishing"
            )

        published = record.model_copy(
            update={
                "status": BundleStatus.PUBLISHED,
                "published_at": _now_iso(),
                "published_by": published_by,
                "replay_run_id": gate.run_id,
            }
        )
        self._store.update(published)
        if active is not None:
            self._store.update(active.model_copy(update={"status": BundleStatus.RETIRED}))
        self._store.set_active(company_id, published.record_id)
        return published

    def activate(self, company_id: str, record_id: str) -> BundleRecord:
        """Rollback/forward: point the company at a previously PUBLISHED bundle.
        Only bundles that have passed a publish gate before are eligible."""
        record = self._store.get(company_id, record_id)
        if record is None:
            raise KeyError(f"unknown bundle record {record_id!r}")
        if record.published_at is None:
            raise PublishGateError(
                "cannot activate a bundle that was never published; publish it first"
            )
        current = self._store.active(company_id)
        if current is not None and current.record_id != record.record_id:
            self._store.update(current.model_copy(update={"status": BundleStatus.RETIRED}))
        restored = record.model_copy(update={"status": BundleStatus.PUBLISHED})
        self._store.update(restored)
        return self._store.set_active(company_id, record_id)

    def active_bundle(self, company_id: str) -> Optional[BundleRecord]:
        return self._store.active(company_id)
