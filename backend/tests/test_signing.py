"""Ed25519 bundle signing: primitives + lifecycle integration.

A published bundle is authority. Signing makes it AUTHENTICATED, not merely
tamper-evident: a verifier confirms Kernl actually blessed this exact content
hash, not just that the bytes are internally consistent.

Deterministic: no LLM, no DB, no network.
    py -3 backend/tests/test_signing.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.bundle.lifecycle import (
    BundleLifecycle,
    InMemoryBundleStore,
)
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
from backend.bundle.signing import (
    SIGNING_KEY_ENV,
    generate_signing_key,
    public_key_hex,
    sign_content_hash,
    verify_content_hash,
)
from backend.replay.cases import Expected, GoldenCase, InMemoryCaseStore
from backend.replay.engine import InMemoryReplayRunStore, ReplayEngine


def _bundle() -> Bundle:
    wf = WorkflowSpec(
        name="refund",
        facts=(FactSpec(name="days", value_type="number"),),
    )
    pol = Policy(
        id="refund.ok",
        workflow="refund",
        effect=Effect(kind=OutcomeKind.APPROVE, action="approve_refund"),
        priority=50,
        conditions=(Condition(field="days", operator="lte", value=14, value_type="number"),),
        evidence=(Evidence(source_id="s.md", source_version="sha256:x",
                           span_start=0, span_end=4, excerpt="rule"),),
    )
    return Bundle(company_id="acme", workflows=(wf,), policies=(pol,))


def _publish(store, runs, company_id, bundle, cases=()):
    life = BundleLifecycle(store, runs)
    replay = ReplayEngine(runs)
    draft = life.save_draft(company_id, bundle, created_by="tester")
    run = replay.run(company_id=company_id, cases=list(cases), candidate=bundle)
    replay.acknowledge(company_id, run.run_id, by="tester")
    return life.publish(company_id, draft.record_id, published_by="tester")


# ----------------------------------------------------------------- primitives


def test_no_key_means_unsigned_not_broken():
    os.environ.pop(SIGNING_KEY_ENV, None)
    assert sign_content_hash("sha256:abc") is None
    assert public_key_hex() is None


def test_sign_and_verify_round_trip():
    os.environ[SIGNING_KEY_ENV] = generate_signing_key()
    try:
        signed = sign_content_hash("sha256:abc123")
        assert signed is not None
        sig, pub = signed
        assert verify_content_hash("sha256:abc123", sig, pub) is True
        assert public_key_hex() == pub
    finally:
        os.environ.pop(SIGNING_KEY_ENV, None)


def test_verify_rejects_tamper_and_wrong_key():
    os.environ[SIGNING_KEY_ENV] = generate_signing_key()
    try:
        sig, pub = sign_content_hash("sha256:original")
        # content changed under the same signature
        assert verify_content_hash("sha256:TAMPERED", sig, pub) is False
        # a different key's signature does not verify against pub
        other_key = generate_signing_key()
        os.environ[SIGNING_KEY_ENV] = other_key
        other_sig, other_pub = sign_content_hash("sha256:original")
        assert verify_content_hash("sha256:original", other_sig, pub) is False
        assert other_pub != pub
    finally:
        os.environ.pop(SIGNING_KEY_ENV, None)


def test_malformed_inputs_are_false_never_raise():
    assert verify_content_hash("sha256:x", "", "abcd") is False
    assert verify_content_hash("sha256:x", "notahex!!", "notahex!!") is False
    assert verify_content_hash("sha256:x", "ab", "cd") is False  # wrong lengths


def test_bad_key_env_raises_clearly():
    os.environ[SIGNING_KEY_ENV] = "not-hex"
    try:
        raised = False
        try:
            sign_content_hash("sha256:x")
        except ValueError:
            raised = True
        assert raised, "a malformed KERNL_SIGNING_KEY must raise, not sign silently"
    finally:
        os.environ.pop(SIGNING_KEY_ENV, None)


# -------------------------------------------------------------- lifecycle wire


def test_publish_signs_when_key_present():
    os.environ[SIGNING_KEY_ENV] = generate_signing_key()
    try:
        pub = _publish(InMemoryBundleStore(), InMemoryReplayRunStore(), "acme", _bundle())
        assert pub.is_signed is True
        assert pub.signature_scheme == "ed25519"
        assert pub.verify_signature() is True
    finally:
        os.environ.pop(SIGNING_KEY_ENV, None)


def test_publish_unsigned_when_no_key():
    os.environ.pop(SIGNING_KEY_ENV, None)
    pub = _publish(InMemoryBundleStore(), InMemoryReplayRunStore(), "acme", _bundle())
    assert pub.is_signed is False
    assert pub.verify_signature() is False  # unsigned is not "valid"
    assert pub.signature is None and pub.signing_pubkey is None


def test_tampered_published_record_fails_verification():
    """The whole point: if a stored record's content_hash is altered, its
    signature no longer verifies. verify_signature is computed from the
    content, never trusted as a stored boolean."""
    os.environ[SIGNING_KEY_ENV] = generate_signing_key()
    try:
        pub = _publish(InMemoryBundleStore(), InMemoryReplayRunStore(), "acme", _bundle())
        tampered = pub.model_copy(update={"content_hash": "sha256:forged"})
        assert tampered.is_signed is True          # signature bytes still present
        assert tampered.verify_signature() is False  # but they don't match the hash
    finally:
        os.environ.pop(SIGNING_KEY_ENV, None)


def test_draft_is_never_signed():
    os.environ[SIGNING_KEY_ENV] = generate_signing_key()
    try:
        life = BundleLifecycle(InMemoryBundleStore(), InMemoryReplayRunStore())
        draft = life.save_draft("acme", _bundle(), created_by="tester")
        assert draft.is_signed is False  # only publish signs
    finally:
        os.environ.pop(SIGNING_KEY_ENV, None)


def test_seeded_reference_bundle_verifies_under_signing():
    """A real seed bundle, published through the actual replay gate with a key
    configured, is signed and verifies."""
    from backend.bundle.seed_rivanly import build_bundle, build_golden_cases

    os.environ[SIGNING_KEY_ENV] = generate_signing_key()
    try:
        cases = InMemoryCaseStore()
        for gc in build_golden_cases():
            cases.add(gc)
        pub = _publish(InMemoryBundleStore(), InMemoryReplayRunStore(),
                       "rivanly-inc", build_bundle(), cases.list("rivanly-inc"))
        assert pub.is_signed and pub.verify_signature()
    finally:
        os.environ.pop(SIGNING_KEY_ENV, None)


# keep GoldenCase/Expected imported (used indirectly via seed); silence linters
_ = (GoldenCase, Expected)

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
