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

import base64
import binascii
import json
import os
import stat
import tempfile
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
_P256_COMPONENT_BYTES = 32
_P256_JWK_FIELDS = ("d", "x", "y")
_BASE64URL_ALPHABET = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)


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
        normalized, changed = _normalize_p256_jwk(data)
        parsed = jwt.PyJWK.from_dict(normalized)
        if changed:
            # Migrate legacy short components in place without rotating the key.
            # Parse first so malformed or inconsistent material is never written.
            # Commit the public file first and the private file last. If the final
            # replace fails, the still-legacy private file makes the next load
            # retry this idempotent migration.
            _write_public_jwks(normalized, p.parent / "ssf_jwks.json")
            _atomic_write_text(
                p,
                json.dumps(normalized, indent=2, ensure_ascii=False),
                default_mode=0o600,
            )
        return parsed

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
    parsed = jwt.PyJWK.from_dict(jwk)
    _write_public_jwks(jwk, p.parent / "ssf_jwks.json")
    _atomic_write_text(
        p,
        json.dumps(jwk, indent=2, ensure_ascii=False),
        default_mode=0o600,
    )
    return parsed


def _b64url_int(value: int) -> str:
    # RFC 7518: P-256 d/x/y are fixed-width 32-octet sequences. Deriving
    # the length from bit_length() drops leading zero octets and can make a
    # valid EC key intermittently invalid when parsed as JWK.
    raw = value.to_bytes(_P256_COMPONENT_BYTES, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode_p256_component(field: str, encoded: str) -> bytes:
    """Decode one canonical, unpadded Base64url P-256 JWK component."""
    if not encoded or any(char not in _BASE64URL_ALPHABET for char in encoded):
        raise ValueError(
            f"invalid unpadded base64url in P-256 JWK component {field!r}"
        )

    try:
        raw = base64.b64decode(
            encoded + "=" * (-len(encoded) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError) as exc:
        raise ValueError(
            f"invalid unpadded base64url in P-256 JWK component {field!r}"
        ) from exc

    # Reject alternative encodings with non-zero discarded bits. JWK uses the
    # canonical unpadded Base64url representation, so decoding successfully is
    # necessary but not sufficient.
    canonical = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    if canonical != encoded:
        raise ValueError(
            f"invalid unpadded base64url in P-256 JWK component {field!r}"
        )
    return raw


def _normalize_p256_jwk(data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Left-pad legacy short P-256 components without changing key identity."""
    if data.get("kty") != "EC" or data.get("crv") != "P-256":
        return data, False

    normalized = dict(data)
    changed = False
    for field in _P256_JWK_FIELDS:
        encoded = normalized.get(field)
        if not isinstance(encoded, str):
            continue
        raw = _decode_p256_component(field, encoded)
        if len(raw) < _P256_COMPONENT_BYTES:
            padded = raw.rjust(_P256_COMPONENT_BYTES, b"\x00")
            normalized[field] = (
                base64.urlsafe_b64encode(padded).rstrip(b"=").decode("ascii")
            )
            changed = True
    return normalized, changed


def _atomic_write_text(path: Path, text: str, *, default_mode: int) -> None:
    """Atomically replace text after fsyncing a same-directory temporary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        target_mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        target_mode = default_mode

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, target_mode)
        os.replace(temporary_path, path)
    except BaseException:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
        raise


def _write_public_jwks(private_jwk: dict, jwks_path: Path) -> None:
    """Persist the public JWK (no 'd') so a Receiver can verify offline."""
    pub = {k: v for k, v in private_jwk.items() if k != "d"}
    doc = {"keys": [pub]}
    _atomic_write_text(
        jwks_path,
        json.dumps(doc, indent=2, ensure_ascii=False),
        default_mode=0o644,
    )
