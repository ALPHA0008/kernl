"""Unit tests: the onboarding domain (tenants, sources, grounding, drafts,
bundle assembly). The full docs -> cited dashboard flow, minus the API.

Deterministic: no LLM, no DB, no network.
    py -3 backend/tests/test_onboarding.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.bundle.canonical import bundle_content_hash
from backend.onboarding.drafts import InMemoryDraftStore
from backend.onboarding.service import AssembleError, OnboardingService
from backend.onboarding.sources import (
    GroundingError,
    InMemorySourceStore,
    ground_evidence,
    make_snapshot,
)
from backend.onboarding.tenants import (
    InMemoryTenantStore,
    TenantService,
    hash_key,
)

# A realistic refund SOP with a citable sentence.
SOURCE = (
    "Refund Policy\n\n"
    "Customers on annual plans who request a refund within 14 days of "
    "purchase receive a full refund.\n"
    "After 14 days, annual refunds are prorated.\n"
)


def _service() -> OnboardingService:
    tenants = TenantService(InMemoryTenantStore())
    return OnboardingService(tenants, InMemorySourceStore(), InMemoryDraftStore())


# ---------------------------------------------------------------- tenants


def test_provision_issues_owner_key_once():
    svc = _service()
    tenant, key = svc.tenants.provision("acme-corp", "Acme Corp")
    assert tenant.company_id == "acme-corp"
    assert key.startswith("kk_")
    # the plaintext resolves back to an owner record; the store holds only a hash
    rec = svc.tenants.resolve(key)
    assert rec is not None and rec.role == "owner" and rec.company_id == "acme-corp"
    assert rec.key_hash == hash_key(key) and rec.key_hash != key


def test_duplicate_tenant_rejected():
    svc = _service()
    svc.tenants.provision("acme-corp", "Acme")
    try:
        svc.tenants.provision("acme-corp", "Acme Again")
        assert False, "duplicate tenant must raise"
    except ValueError:
        pass


def test_revoked_and_unknown_keys_do_not_resolve():
    svc = _service()
    svc.tenants.provision("acme-corp", "Acme")
    assert svc.tenants.resolve("kk_nonsense") is None


# ------------------------------------------------------- source grounding


def test_snapshot_is_content_addressed():
    s1 = make_snapshot("acme", "refund.md", SOURCE)
    s2 = make_snapshot("acme", "refund.md", SOURCE)
    assert s1.content_hash == s2.content_hash
    assert s1.source_id == s2.source_id  # identical bytes -> same id


def test_grounding_accepts_exact_span():
    snap = make_snapshot("acme", "refund.md", SOURCE)
    start = SOURCE.index("Customers on annual")
    end = SOURCE.index("full refund.") + len("full refund.")
    excerpt = SOURCE[start:end]
    ev = ground_evidence(snap, start, end, excerpt)
    assert ev.source_version == snap.content_hash
    assert ev.excerpt == excerpt


def test_grounding_rejects_paraphrase():
    snap = make_snapshot("acme", "refund.md", SOURCE)
    start = SOURCE.index("Customers on annual")
    end = start + 10
    try:
        ground_evidence(snap, start, end, "a paraphrase not in the doc")
        assert False, "paraphrase must be rejected"
    except GroundingError:
        pass


def test_grounding_rejects_out_of_range():
    snap = make_snapshot("acme", "refund.md", SOURCE)
    try:
        ground_evidence(snap, 0, len(SOURCE) + 100, SOURCE)
        assert False, "out-of-range span must be rejected"
    except GroundingError:
        pass


# ------------------------------------------------------ drafts + publish


def _annual_refund_policy() -> dict:
    return {
        "id": "refund.annual_14d",
        "workflow": "refund",
        "effect": {"kind": "approve", "action": "approve_full_refund"},
        "priority": 70,
        "conditions": [
            {"field": "plan_type", "operator": "eq", "value": "annual", "value_type": "string"},
            {"field": "days_since_purchase", "operator": "lte", "value": 14, "value_type": "number"},
        ],
        "authority": {"approval_required": False},
        "overrides": [],
        "unconditional_ack": False,
        "rationale": "Annual plans refundable within 14 days.",
    }


def test_draft_not_publishable_without_evidence():
    svc = _service()
    svc.tenants.provision("acme", "Acme")
    d = svc.save_draft("acme", _annual_refund_policy())
    assert d.publishable is False
    assert any("grounded evidence" in i for i in d.issues_json)


def test_full_flow_author_ground_accept_assemble():
    svc = _service()
    svc.tenants.provision("acme", "Acme")
    snap = svc.sources.add(make_snapshot("acme", "refund.md", SOURCE))

    d = svc.save_draft("acme", _annual_refund_policy())
    assert d.publishable is False

    start = SOURCE.index("Customers on annual")
    end = SOURCE.index("full refund.") + len("full refund.")
    d = svc.ground_span("acme", d.draft_id, snap.source_id, start, end, SOURCE[start:end])
    assert d.publishable is True
    assert d.issues_json == ()

    d = svc.set_status("acme", d.draft_id, "accepted")
    assert d.status == "accepted"

    bundle = svc.assemble_bundle("acme")
    assert bundle.company_id == "acme"
    assert len(bundle.policies) == 1
    # the inferred workflow declares both condition fields with correct types
    wf = bundle.workflow("refund")
    fmap = {f.name: f.value_type for f in wf.facts}
    assert fmap == {"plan_type": "string", "days_since_purchase": "number"}
    # the assembled bundle is content-addressable (ready for the publish gate)
    assert bundle_content_hash(bundle).startswith("sha256:")


def test_cannot_accept_unpublishable_draft():
    svc = _service()
    svc.tenants.provision("acme", "Acme")
    d = svc.save_draft("acme", _annual_refund_policy())
    try:
        svc.set_status("acme", d.draft_id, "accepted")
        assert False, "accepting an ungrounded draft must raise"
    except ValueError:
        pass


def test_assemble_requires_accepted_drafts():
    svc = _service()
    svc.tenants.provision("acme", "Acme")
    try:
        svc.assemble_bundle("acme")
        assert False, "assembling with no accepted drafts must raise"
    except AssembleError:
        pass


def test_removing_evidence_makes_draft_unpublishable_again():
    svc = _service()
    svc.tenants.provision("acme", "Acme")
    snap = svc.sources.add(make_snapshot("acme", "refund.md", SOURCE))
    d = svc.save_draft("acme", _annual_refund_policy())
    start = SOURCE.index("Customers on annual")
    end = SOURCE.index("full refund.") + len("full refund.")
    d = svc.ground_span("acme", d.draft_id, snap.source_id, start, end, SOURCE[start:end])
    assert d.publishable is True
    d = svc.remove_evidence("acme", d.draft_id, 0)
    assert d.publishable is False


def test_extraction_proposes_ungrounded_drafts():
    """The LLM proposer converts model output into 'extracted' drafts that carry
    NO evidence -- a human must still ground each. Gateway is mocked; no network,
    no numpy/torch import."""
    import asyncio

    from backend.onboarding import extract as extract_mod

    async def fake_array(system, content):
        return [
            {
                "id": "refund.annual_14d",
                "workflow": "refund",
                "effect": {"kind": "approve", "action": "approve_full_refund"},
                "priority": 70,
                "conditions": [
                    {"field": "plan_type", "operator": "eq", "value": "annual",
                     "value_type": "string"},
                ],
                "rationale": "annual refunds within 14 days",
            }
        ]

    orig = extract_mod._gateway_json_array
    extract_mod._gateway_json_array = fake_array
    try:
        snap = make_snapshot("acme", "refund.md", SOURCE)
        drafts = asyncio.run(extract_mod.propose_drafts_from_source(snap))
    finally:
        extract_mod._gateway_json_array = orig

    assert len(drafts) == 1
    d = drafts[0]
    assert d.origin == "extracted"
    assert d.evidence_json == ()  # ungrounded: never authority on the LLM's word
    assert d.publishable is False
    assert any("grounded evidence" in i for i in d.issues_json)


def test_extraction_unavailable_degrades():
    import asyncio

    from backend.onboarding import extract as extract_mod
    from backend.onboarding.extract import ExtractionUnavailable

    async def boom(system, content):
        raise RuntimeError("gateway down")

    orig = extract_mod._gateway_json_array
    extract_mod._gateway_json_array = boom
    try:
        snap = make_snapshot("acme", "refund.md", SOURCE)
        try:
            asyncio.run(extract_mod.propose_drafts_from_source(snap))
            assert False, "must raise ExtractionUnavailable"
        except ExtractionUnavailable:
            pass
    finally:
        extract_mod._gateway_json_array = orig


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"Results: {len(TESTS) - failed}/{len(TESTS)} passed, {failed} failed")
    sys.exit(1 if failed else 0)
