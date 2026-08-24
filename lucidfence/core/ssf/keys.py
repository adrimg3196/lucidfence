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
import errno
import json
import os
import shutil
import stat
import subprocess
import sys
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
    requested_path = Path(path) if path else DEFAULT_JWK_PATH
    # Administrator-managed symlinks must keep pointing at the managed key.
    # Atomic replacement therefore targets the referent, never the link inode.
    p = (
        requested_path.resolve(strict=False)
        if requested_path.is_symlink()
        else requested_path
    )
    jwks_path = requested_path.parent / "ssf_jwks.json"
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
            _write_public_jwks(normalized, jwks_path)
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
    _write_public_jwks(jwk, jwks_path)
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
    if path.is_symlink():
        path = path.resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination_stat = path.stat()
    except FileNotFoundError:
        destination_stat = None
    if destination_stat is not None:
        _reject_unreplaceable_file_flags(path, destination_stat)

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
        if destination_stat is None:
            os.chmod(temporary_path, default_mode)
        else:
            _reject_unverifiable_native_acl(path)
            # os.replace installs the temporary inode, so copy access metadata
            # first. Extended attributes include Linux POSIX ACLs and security
            # labels; any mismatch aborts before the destination is replaced.
            if hasattr(os, "chown"):
                os.chown(
                    temporary_path,
                    destination_stat.st_uid,
                    destination_stat.st_gid,
                )
            source_xattrs = _read_xattrs(path)
            if source_xattrs is not None:
                _synchronize_xattrs(temporary_path, source_xattrs, source=path)
            shutil.copystat(path, temporary_path)
            if source_xattrs is not None:
                copied_xattrs = _read_xattrs(temporary_path)
                if copied_xattrs != source_xattrs:
                    raise OSError(
                        errno.EIO,
                        f"cannot preserve extended attributes for {path}",
                    )
            if hasattr(os, "chown"):
                copied_stat = temporary_path.stat()
                if (
                    copied_stat.st_uid != destination_stat.st_uid
                    or copied_stat.st_gid != destination_stat.st_gid
                ):
                    raise PermissionError(
                        f"cannot preserve owner/group for {path}"
                    )
        os.replace(temporary_path, path)
    except BaseException:
        if temporary_path is not None:
            if hasattr(os, "chflags"):
                try:
                    os.chflags(temporary_path, 0)
                except OSError:
                    pass
            try:
                temporary_path.unlink()
            except OSError:
                pass
        raise


def _reject_unreplaceable_file_flags(path: Path, destination_stat: Any) -> None:
    """Reject BSD flags that can block replacement or temporary cleanup."""
    flags = getattr(destination_stat, "st_flags", 0)
    blocking_names = (
        "UF_IMMUTABLE",
        "SF_IMMUTABLE",
        "UF_APPEND",
        "SF_APPEND",
    )
    active = [
        name
        for name in blocking_names
        if flags & getattr(stat, name, 0)
    ]
    if active:
        raise PermissionError(
            f"cannot replace {path}: blocking file flags {', '.join(active)}"
        )


def _reject_unverifiable_native_acl(path: Path) -> None:
    """Abort when a BSD-style ACL cannot be preserved with stdlib metadata APIs."""
    native_acl_platforms = ("darwin", "freebsd", "openbsd", "netbsd")
    if not sys.platform.startswith(native_acl_platforms):
        return
    try:
        inspected_path = path.resolve(strict=True)
        result = subprocess.run(
            ["ls", "-lde", str(inspected_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise PermissionError(
            f"cannot verify native ACL before replacing {path}"
        ) from exc
    lines = result.stdout.splitlines()
    if result.returncode != 0 or not lines or not lines[0].split():
        raise PermissionError(f"cannot verify native ACL before replacing {path}")
    mode = lines[0].split(maxsplit=1)[0]
    # macOS gives the xattr marker ("@") precedence over the ACL marker
    # ("+"). With ``-e``, native ACL entries still follow the listing line,
    # so inspect those entries instead of trusting the mode token alone.
    has_acl_entry = any(
        line.lstrip().partition(":")[0].isdigit() for line in lines[1:]
    )
    if "+" in mode or has_acl_entry:
        raise PermissionError(
            f"cannot safely replace native ACL-protected file {path}"
        )


def _read_xattrs(path: Path) -> dict[str, bytes] | None:
    """Read all extended attributes, or None when the filesystem lacks them."""
    required = ("listxattr", "getxattr")
    if not all(hasattr(os, name) for name in required):
        return None
    unsupported = {errno.EINVAL, errno.ENOTSUP}
    if hasattr(errno, "EOPNOTSUPP"):
        unsupported.add(errno.EOPNOTSUPP)
    try:
        names = os.listxattr(path)
        return {name: os.getxattr(path, name) for name in names}
    except OSError as exc:
        if exc.errno in unsupported:
            return None
        raise OSError(
            exc.errno or errno.EACCES,
            f"cannot inspect extended attributes for {path}",
        ) from exc


def _synchronize_xattrs(
    destination: Path,
    expected: dict[str, bytes],
    *,
    source: Path,
) -> None:
    """Make destination xattrs exactly match source, failing closed."""
    required = ("listxattr", "getxattr", "setxattr", "removexattr")
    if not all(hasattr(os, name) for name in required):
        if expected:
            raise OSError(
                errno.ENOTSUP,
                f"cannot preserve extended attributes for {source}",
            )
        return
    try:
        present = set(os.listxattr(destination))
        for name in present.difference(expected):
            os.removexattr(destination, name)
        for name, value in expected.items():
            os.setxattr(destination, name, value)
    except OSError as exc:
        raise OSError(
            exc.errno or errno.EPERM,
            f"cannot preserve extended attribute for {source}",
        ) from exc


def _write_public_jwks(private_jwk: dict, jwks_path: Path) -> None:
    """Persist the public JWK (no 'd') so a Receiver can verify offline."""
    pub = {k: v for k, v in private_jwk.items() if k != "d"}
    doc = {"keys": [pub]}
    _atomic_write_text(
        jwks_path,
        json.dumps(doc, indent=2, ensure_ascii=False),
        default_mode=0o644,
    )
