"""Tests for the SSF Transmitter (Emisor CAEP/SSF, fase 1).

Runs under the zero-dependency runner: python3 tests/run_tests.py
Hermetic: no network, deterministic evaluate stub, temp signing key.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Ensure repo root is importable when run via tests/run_tests.py
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lucidfence.core.ssf import (  # noqa: E402
    LF_VENDOR_NS,
    CAEP_DEVICE_COMPLIANCE_CHANGE,
    SSFTransmitter,
    build_device_compliance_change,
    compliance_status_from_score,
)
from lucidfence.core.ssf.keys import (  # noqa: E402
    SIGNING_ALG,
    _b64url_int,
    _normalize_p256_jwk,
    load_signing_jwk,
)
from lucidfence.core.oidc import ASYMMETRIC_ALGORITHMS  # noqa: E402

try:
    import jwt  # PyJWT[crypto] (pinned in pyproject)
except Exception:  # pragma: no cover
    jwt = None


def _stub_evaluate(risk_score: int, severity: str, reasons: list[str]):
    def _fn(device, fence_state, ctx):
        return {
            "device_id": device.get("device_id", "dev-1"),
            "risk_score": risk_score,
            "severity": severity,
            "fence_state": fence_state,
            "signals": {},
            "reasons": reasons,
            "provenance": {},
            "verified": True,
        }

    return _fn


def _temp_key():
    d = Path(tempfile.mkdtemp(prefix="ssf-key-"))
    return d / "ssf_sign.json"


def test_p256_jwk_scalar_preserves_fixed_32_byte_width():
    import base64

    encoded = _b64url_int(1)
    raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    assert raw == (b"\x00" * 31) + b"\x01", len(raw)


def test_existing_short_p256_jwk_is_normalized_without_key_rotation():
    if jwt is None:
        raise SystemExit("SKIP: PyJWT[crypto] not installed")

    import base64
    import json

    from cryptography.hazmat.primitives.asymmetric import ec

    def encode_fixed(value: int) -> str:
        raw = value.to_bytes(32, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    key_path = _temp_key()
    numbers = ec.derive_private_key(1, ec.SECP256R1()).private_numbers()
    legacy = {
        "kty": "EC",
        "crv": "P-256",
        "d": "AQ",
        "x": encode_fixed(numbers.public_numbers.x),
        "y": encode_fixed(numbers.public_numbers.y),
        "kid": "legacy-short-p256",
        "alg": "ES256",
        "use": "sig",
    }
    key_path.write_text(json.dumps(legacy), encoding="utf-8")

    loaded = load_signing_jwk(key_path)
    assert loaded.key.private_numbers().private_value == 1

    migrated = json.loads(key_path.read_text(encoding="utf-8"))
    raw_d = base64.urlsafe_b64decode(
        migrated["d"] + "=" * (-len(migrated["d"]) % 4)
    )
    assert raw_d == (b"\x00" * 31) + b"\x01"

    public = json.loads(
        (key_path.parent / "ssf_jwks.json").read_text(encoding="utf-8")
    )["keys"][0]
    assert "d" not in public
    assert public["x"] == migrated["x"]
    assert public["y"] == migrated["y"]


def test_all_legacy_short_p256_components_are_left_padded():
    import base64

    normalized, changed = _normalize_p256_jwk(
        {
            "kty": "EC",
            "crv": "P-256",
            "d": "AQ",
            "x": "Ag",
            "y": "Aw",
        }
    )

    assert changed is True
    for field, final_byte in (("d", 1), ("x", 2), ("y", 3)):
        encoded = normalized[field]
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        assert raw == (b"\x00" * 31) + bytes([final_byte]), field


def test_malformed_p256_base64url_is_rejected_before_parsing():
    malformed_values = ("!!!!AQ", "!!", "AQ==", "A Q", "", "AB")

    for malformed in malformed_values:
        try:
            _normalize_p256_jwk(
                {
                    "kty": "EC",
                    "crv": "P-256",
                    "d": malformed,
                    "x": _b64url_int(2),
                    "y": _b64url_int(3),
                }
            )
        except ValueError as exc:
            assert "invalid unpadded base64url" in str(exc)
            assert "'d'" in str(exc)
        else:
            raise AssertionError(f"malformed base64url accepted: {malformed!r}")


def test_malformed_persisted_jwk_leaves_private_and_public_files_unchanged():
    import json

    from lucidfence.core.ssf import keys as keys_module

    key_path = _temp_key()
    jwks_path = key_path.parent / "ssf_jwks.json"
    malformed = {
        "kty": "EC",
        "crv": "P-256",
        # The old permissive decoder silently discarded "!" and read this as AQ.
        "d": "!!!!AQ",
        "x": _b64url_int(2),
        "y": _b64url_int(3),
        "kid": "malformed-p256",
        "alg": "ES256",
        "use": "sig",
    }
    key_path.write_text(json.dumps(malformed), encoding="utf-8")
    jwks_path.write_text('{"sentinel": true}', encoding="utf-8")
    private_before = key_path.read_bytes()
    public_before = jwks_path.read_bytes()

    class _MustNotParse:
        class PyJWK:
            @staticmethod
            def from_dict(_data):
                raise AssertionError("malformed JWK reached PyJWK parsing")

    real_ensure_jwt = keys_module._ensure_jwt
    keys_module._ensure_jwt = lambda: _MustNotParse
    try:
        try:
            load_signing_jwk(key_path)
        except ValueError as exc:
            assert "invalid unpadded base64url" in str(exc)
        else:
            raise AssertionError("malformed persisted JWK was accepted")
    finally:
        keys_module._ensure_jwt = real_ensure_jwt

    assert key_path.read_bytes() == private_before
    assert jwks_path.read_bytes() == public_before


def test_persisted_jwk_migration_is_atomic_and_retriable():
    import base64
    import json

    from lucidfence.core.ssf import keys as keys_module

    key_path = _temp_key()
    jwks_path = key_path.parent / "ssf_jwks.json"
    legacy = {
        "kty": "EC",
        "crv": "P-256",
        "d": "AQ",
        "x": "Ag",
        "y": "Aw",
        "kid": "legacy-short-p256",
        "alg": "ES256",
        "use": "sig",
    }
    key_path.write_text(json.dumps(legacy), encoding="utf-8")
    jwks_path.write_text('{"sentinel": true}', encoding="utf-8")
    private_before = key_path.read_bytes()

    class _StubJWT:
        class PyJWK:
            @staticmethod
            def from_dict(data):
                return data

    real_ensure_jwt = keys_module._ensure_jwt
    real_os = keys_module.os

    def fail_private_replace(source, destination):
        if Path(destination) == key_path:
            raise OSError("simulated private-key replace failure")
        return real_os.replace(source, destination)

    class _FailPrivateReplaceOS:
        chmod = staticmethod(real_os.chmod)
        fsync = staticmethod(real_os.fsync)
        replace = staticmethod(fail_private_replace)

    keys_module._ensure_jwt = lambda: _StubJWT
    try:
        keys_module.os = _FailPrivateReplaceOS
        try:
            load_signing_jwk(key_path)
        except OSError as exc:
            assert "simulated private-key replace failure" in str(exc)
        else:
            raise AssertionError("migration ignored the private-key write failure")
        finally:
            keys_module.os = real_os

        # Public data commits first, while the private migration remains pending.
        assert key_path.read_bytes() == private_before
        public_after_failure = json.loads(jwks_path.read_text(encoding="utf-8"))
        assert "d" not in public_after_failure["keys"][0]
        assert set(key_path.parent.iterdir()) == {key_path, jwks_path}

        # Because the private file is still legacy, the next load retries safely.
        loaded = load_signing_jwk(key_path)
        assert loaded["kid"] == legacy["kid"]
    finally:
        keys_module.os = real_os
        keys_module._ensure_jwt = real_ensure_jwt

    migrated = json.loads(key_path.read_text(encoding="utf-8"))
    public = json.loads(jwks_path.read_text(encoding="utf-8"))["keys"][0]
    for field in ("d", "x", "y"):
        raw = base64.urlsafe_b64decode(
            migrated[field] + "=" * (-len(migrated[field]) % 4)
        )
        assert len(raw) == 32, field
    assert public == {key: value for key, value in migrated.items() if key != "d"}


def test_key_file_permissions_are_safe_and_preserved():
    if os.name != "posix":
        return

    import json
    import stat

    from lucidfence.core.ssf import keys as keys_module

    key_path = _temp_key()
    jwks_path = key_path.parent / "ssf_jwks.json"

    class _StubJWT:
        class PyJWK:
            @staticmethod
            def from_dict(data):
                return data

    real_ensure_jwt = keys_module._ensure_jwt
    keys_module._ensure_jwt = lambda: _StubJWT
    try:
        generated = load_signing_jwk(key_path)
        assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(jwks_path.stat().st_mode) == 0o644

        # Force a legacy migration and verify both pre-existing modes survive.
        generated["d"] = "AQ"
        key_path.write_text(json.dumps(generated), encoding="utf-8")
        key_path.chmod(0o640)
        jwks_path.chmod(0o664)
        load_signing_jwk(key_path)
    finally:
        keys_module._ensure_jwt = real_ensure_jwt

    assert stat.S_IMODE(key_path.stat().st_mode) == 0o640
    assert stat.S_IMODE(jwks_path.stat().st_mode) == 0o664


def test_build_event_shape():
    ev = build_device_compliance_change(
        "dev-abc",
        risk_score=85,
        severity="critical",
        reasons=["unmanaged os", "no disk encryption"],
        fence_state="observe",
    )
    assert ev["subject"] == {"subject_type": "device", "device_id": "dev-abc"}
    assert ev["compliance_status"] == "non-compliant"
    ext = ev[LF_VENDOR_NS]
    assert ext["risk_score"] == 85
    assert ext["severity"] == "critical"
    assert ext["reasons"] == ["unmanaged os", "no disk encryption"]
    assert ext["fence_state"] == "observe"


def test_risk_mapping():
    assert compliance_status_from_score(85) == "non-compliant"
    assert compliance_status_from_score(71) == "non-compliant"
    assert compliance_status_from_score(70) == "compliant"
    assert compliance_status_from_score(10) == "compliant"


def test_jws_verifies():
    if jwt is None:
        raise SystemExit("SKIP: PyJWT[crypto] not installed")
    key_path = _temp_key()
    jwk = load_signing_jwk(key_path)
    tx = SSFTransmitter(signing_jwk_path=key_path,
                        evaluate_fn=_stub_evaluate(80, "high", ["x"]))
    out = tx.emit_device_risk({"device_id": "dev-1"}, "enforce")
    jws = out["jws"]
    # Decode + verify against the vendored public key.
    claims = jwt.decode(jws, jwk.key, algorithms=list(ASYMMETRIC_ALGORITHMS))
    assert "iss" in claims and "iat" in claims and "jti" in claims
    event = claims["events"][CAEP_DEVICE_COMPLIANCE_CHANGE]
    assert event["subject"]["device_id"] == "dev-1"
    assert event[LF_VENDOR_NS]["risk_score"] == 80
    # Header must carry kid + typ
    hdr = jwt.get_unverified_header(jws)
    assert hdr["kid"] == jwk.key_id
    assert hdr["typ"] == "secevent+jwt"
    assert hdr["alg"] in ASYMMETRIC_ALGORITHMS


def test_no_pii_in_event():
    ev = build_device_compliance_change(
        "dev-1",
        risk_score=40,
        severity="medium",
        reasons=["weak password"],
        fence_state="observe",
    )
    blob = str(ev)
    # No email, no token-like strings, no raw credential material.
    # (A risk *reason* like "weak password" is a classification, not a secret.)
    for forbidden in ["@example.com", "token", "Bearer ", "secret", "api_key"]:
        assert forbidden not in blob, f"potential PII leaked: {forbidden}"
    # The explainability extension carries only non-sensitive fields.
    ext = ev[LF_VENDOR_NS]
    assert set(ext.keys()) == {"risk_score", "severity", "reasons", "fence_state"}


def test_emit_calls_notifier():
    if jwt is None:
        raise SystemExit("SKIP: PyJWT[crypto] not installed")

    calls = []

    class _StubNotifier:
        def notify(self, transition, incident):
            calls.append((transition, incident))
            return True

    kp = _temp_key()
    tx = SSFTransmitter(
        signing_jwk_path=kp,
        notifier=_StubNotifier(),
        evaluate_fn=_stub_evaluate(20, "low", []),
    )
    out = tx.emit_device_risk({"device_id": "dev-9"}, "observe")
    assert out["delivered"] is True
    assert len(calls) == 1
    transition, incident = calls[0]
    assert transition == "caep-device-compliance-change"
    # incident preserved intact (notifier posts it verbatim inside its own body)
    assert "jws" in incident and "event" in incident
    # The JWS actually verifies (end-to-end, not just shaped) — reuse same key.
    claims = jwt.decode(incident["jws"], load_signing_jwk(kp).key,
                        algorithms=list(ASYMMETRIC_ALGORITHMS))
    assert claims["events"][CAEP_DEVICE_COMPLIANCE_CHANGE]["subject"]["device_id"] == "dev-9"


def test_signing_alg_is_es256():
    # Hard contract: we only provision ES256; the gate forbids EdDSA/Ed25519.
    assert SIGNING_ALG == "ES256"
    assert "EdDSA" not in ASYMMETRIC_ALGORITHMS
