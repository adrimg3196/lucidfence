"""Signing-key management for the SSF Transmitter (local-first, vendored JWK).

Reuses ``lucidfence.core.oidc.ASYMMETRIC_ALGORITHMS`` so we never duplicate the
allowed-algorithm list. The signing algorithm is fixed to **ES256** (EC P-256):
that is the only member of ASYMMETRIC_ALGORITHMS we vendored a key for, and
Ed25519/EdDSA is explicitly NOT in that tuple (oidc.py:36), so it cannot be used.

On first run (no vendored key) we generate an EC P-256 keypair and persist it
locally — no network, no cloud. The public JWK is exposed so a Receiver (fase 2)
can verify, again with no mandatory network endpoint.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lucidfence.core.oidc import ASYMMETRIC_ALGORITHMS

# The signing algorithm is fixed; ES256 is the only one we provision a key for.
SIGNING_ALG = "ES256"
if SIGNING_ALG not in ASYMMETRIC_ALGORITHMS:
    raise RuntimeError(
        f"{SIGNING_ALG} not in ASYMMETRIC_ALGORITHMS; cannot sign SSF SETs"
    )

DEFAULT_KEYS_DIR = Path(__file__).resolve().parent / "keys"
DEFAULT_JWK_PATH = DEFAULT_KEYS_DIR / "ssf_sign.json"
DEFAULT_JWKS_PATH = DEFAULT_KEYS_DIR / "ssf_jwks.json"

_KID = "lucidfence-ssf-es256-1"


def _ensure_jwt() -> Any:
    try:
        import jwt  # PyJWT[crypto]
    except ImportError as exc:  # pragma: no cover - dependency is pinned
        raise RuntimeError(
            "PyJWT[crypto] is required to sign SSF SETs (pyproject pins it)"
        ) from exc
    return jwt


def load_signing_jwk(path: Path | None = None) -> Any:
    """Load (generating + persisting on first run) the vendored ES256 signing JWK.

    Returns a ``jwt.PyJWK`` ready to use with ``jwt.encode(..., algorithm="ES256")``.
    """
    jwt = _ensure_jwt()
    p = Path(path) if path else DEFAULT_JWK_PATH
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("alg") != SIGNING_ALG:
            raise RuntimeError(
                f"vendored SSF key alg is {data.get('alg')!r}, expected {SIGNING_ALG}"
            )
        return jwt.PyJWK.from_dict(data)

    # First run: generate EC P-256 locally (no network).
    from cryptography.hazmat.primitives.asymmetric import ec

    priv = ec.generate_private_key(ec.SECP256R1())
    numbers = priv.private_numbers()
    # Build JWK from the EC private numbers (P-256).
    jwk = {
        "kty": "EC",
        "crv": "P-256",
        "d": _b64url_int(numbers.private_value),
        "x": _b64url_int(numbers.public_numbers.x),
        "y": _b64url_int(numbers.public_numbers.y),
        "kid": _KID,
        "alg": SIGNING_ALG,
        "use": "sig",
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(jwk, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_public_jwks(jwk, p.parent / "ssf_jwks.json")
    return jwt.PyJWK.from_dict(jwk)


def _b64url_int(value: int) -> str:
    # RFC 7518: P-256 d/x/y are fixed-width 32-octet sequences. Deriving
    # the length from bit_length() drops leading zero octets and can make a
    # valid EC key intermittently invalid when parsed as JWK.
    raw = value.to_bytes(32, "big")
    import base64

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _write_public_jwks(private_jwk: dict, jwks_path: Path) -> None:
    """Persist the public JWK (no 'd') so a Receiver can verify offline."""
    pub = {k: v for k, v in private_jwk.items() if k != "d"}
    doc = {"keys": [pub]}
    jwks_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
