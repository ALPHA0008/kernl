"""Ed25519 signing for published bundles.

The arc's V1 architecture list names "Ed25519 signing" alongside the
hash-chained ledger. Content-addressing (bundle_content_hash) already makes a
bundle tamper-EVIDENT: alter one condition and the hash changes. Signing adds
tamper-EVIDENT + AUTHENTICATED: a published bundle carries a signature over its
content hash, so a verifier can confirm the bundle was published by the holder
of Kernl's private signing key -- not merely that its bytes are internally
consistent. That is the difference between "this artifact wasn't corrupted" and
"this artifact is the one Kernl actually blessed."

What is signed: the bundle's content_hash string (e.g. "sha256:abcd..."), which
is itself the sha256 over the canonical bundle content. Signing the hash is
equivalent to signing the content (any content change changes the hash, which
changes what must be signed) and keeps signatures small and stable.

Key management:
  - KERNL_SIGNING_KEY (env): the Ed25519 private key, hex-encoded (64 hex chars
    = 32 raw bytes). Generate one with `python -m backend.bundle.signing`.
  - Unset -> signing is a no-op that returns None. Publishing still works
    (dev/test never need a key), but the record is explicitly UNSIGNED, and
    verify() reports that honestly rather than pretending. This is fail-OPEN
    for availability by design: an unsigned bundle is a weaker artifact, not a
    broken one, and the constitutional guarantees (determinism, ledger,
    citation) do not depend on the signature. Production sets the key; the
    absence is visible, never silent.

Only PUBLISHED bundles are signed -- drafts are proposals, not authority.
"""

from __future__ import annotations

import os
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

SIGNING_KEY_ENV = "KERNL_SIGNING_KEY"
# The signature scheme identifier stored alongside every signature, so a future
# scheme migration is unambiguous rather than a guess.
SCHEME = "ed25519"


def generate_signing_key() -> str:
    """Return a fresh Ed25519 private key as 64 hex chars. Store it as the
    KERNL_SIGNING_KEY secret; never commit it."""
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes_raw()
    return raw.hex()


def _load_private_key() -> Optional[Ed25519PrivateKey]:
    hexkey = os.environ.get(SIGNING_KEY_ENV, "").strip()
    if not hexkey:
        return None
    try:
        raw = bytes.fromhex(hexkey)
    except ValueError as exc:
        raise ValueError(
            f"{SIGNING_KEY_ENV} is not valid hex; expected 64 hex chars"
        ) from exc
    if len(raw) != 32:
        raise ValueError(
            f"{SIGNING_KEY_ENV} decodes to {len(raw)} bytes; Ed25519 needs 32"
        )
    return Ed25519PrivateKey.from_private_bytes(raw)


def public_key_hex() -> Optional[str]:
    """The public key (hex) matching the configured signing key, or None if no
    key is configured. Publish this freely -- verifiers need it."""
    priv = _load_private_key()
    if priv is None:
        return None
    return priv.public_key().public_bytes_raw().hex()


def sign_content_hash(content_hash: str) -> Optional[tuple[str, str]]:
    """Sign a bundle's content_hash. Returns (signature_hex, pubkey_hex), or
    None if no signing key is configured (the bundle is then published
    UNSIGNED -- see module docstring)."""
    priv = _load_private_key()
    if priv is None:
        return None
    signature = priv.sign(content_hash.encode("utf-8"))
    pubkey = priv.public_key().public_bytes_raw().hex()
    return signature.hex(), pubkey


def verify_content_hash(content_hash: str, signature_hex: str, pubkey_hex: str) -> bool:
    """Verify a signature over a content_hash against a public key. Returns True
    iff the signature is valid. Any malformed input or bad signature -> False
    (never raises to the caller)."""
    if not signature_hex or not pubkey_hex:
        return False
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex))
        pub.verify(bytes.fromhex(signature_hex), content_hash.encode("utf-8"))
        return True
    except (InvalidSignature, ValueError):
        return False


if __name__ == "__main__":  # pragma: no cover
    # Convenience: generate a key to put in KERNL_SIGNING_KEY.
    print(generate_signing_key())
