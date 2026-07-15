"""Tenant provisioning + API keys.

A tenant is a company with at least one API key. Keys are stored HASHED
(sha256) -- the plaintext is shown exactly once, at issue time, and never
retrievable again. Roles match the API's ROLE_RANK (owner/approver/agent).

This makes new tenants first-class and self-serve, replacing the static
KERNL_API_KEYS env var (which still works as a bootstrap/fallback). The V1 API
resolves a request's principal from whichever source has the key.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional, Protocol

from pydantic import BaseModel, ConfigDict

ROLES = ("owner", "approver", "agent")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def generate_key() -> str:
    """A high-entropy opaque key. `kk_` prefix marks it as a Kernl key."""
    return "kk_" + secrets.token_urlsafe(32)


class Tenant(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: str
    name: str
    created_at: str = ""


class ApiKeyRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    key_id: str
    key_hash: str
    company_id: str
    role: str
    created_at: str = ""
    revoked_at: Optional[str] = None


class TenantStore(Protocol):
    def add_tenant(self, tenant: Tenant) -> Tenant: ...
    def get_tenant(self, company_id: str) -> Optional[Tenant]: ...
    def list_tenants(self) -> list[Tenant]: ...
    def add_key(self, record: ApiKeyRecord) -> ApiKeyRecord: ...
    def find_by_hash(self, key_hash: str) -> Optional[ApiKeyRecord]: ...
    def list_keys(self, company_id: str) -> list[ApiKeyRecord]: ...


class InMemoryTenantStore:
    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}
        self._keys: dict[str, ApiKeyRecord] = {}  # key_id -> record
        self._by_hash: dict[str, str] = {}  # key_hash -> key_id

    def add_tenant(self, tenant: Tenant) -> Tenant:
        if tenant.company_id in self._tenants:
            raise ValueError(f"tenant {tenant.company_id!r} already exists")
        stored = tenant.model_copy(update={"created_at": tenant.created_at or _now()})
        self._tenants[tenant.company_id] = stored
        return stored

    def get_tenant(self, company_id: str) -> Optional[Tenant]:
        return self._tenants.get(company_id)

    def list_tenants(self) -> list[Tenant]:
        return sorted(self._tenants.values(), key=lambda t: t.created_at)

    def add_key(self, record: ApiKeyRecord) -> ApiKeyRecord:
        stored = record.model_copy(update={"created_at": record.created_at or _now()})
        self._keys[record.key_id] = stored
        self._by_hash[record.key_hash] = record.key_id
        return stored

    def find_by_hash(self, key_hash: str) -> Optional[ApiKeyRecord]:
        key_id = self._by_hash.get(key_hash)
        if key_id is None:
            return None
        rec = self._keys.get(key_id)
        if rec is None or rec.revoked_at is not None:
            return None
        return rec

    def list_keys(self, company_id: str) -> list[ApiKeyRecord]:
        return [k for k in self._keys.values() if k.company_id == company_id]


class TenantService:
    """Provisions tenants and issues keys. `provision` is the onboarding entry:
    create the company + mint an owner key, returned in plaintext ONCE."""

    def __init__(self, store: TenantStore) -> None:
        self._store = store

    def provision(self, company_id: str, name: str) -> tuple[Tenant, str]:
        tenant = self._store.add_tenant(Tenant(company_id=company_id, name=name))
        _, plaintext = self.issue_key(company_id, role="owner")
        return tenant, plaintext

    def issue_key(self, company_id: str, role: str) -> tuple[ApiKeyRecord, str]:
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}")
        if self._store.get_tenant(company_id) is None:
            raise KeyError(f"unknown tenant {company_id!r}")
        plaintext = generate_key()
        record = ApiKeyRecord(
            key_id="key_" + secrets.token_hex(8),
            key_hash=hash_key(plaintext),
            company_id=company_id,
            role=role,
        )
        return self._store.add_key(record), plaintext

    def resolve(self, plaintext: str) -> Optional[ApiKeyRecord]:
        return self._store.find_by_hash(hash_key(plaintext))
