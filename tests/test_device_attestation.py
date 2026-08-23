"""Tests del paquete lucidfence/core/attest/ (spike t_44445e00).

Cubre los 3 verifiers (Apple/Android/Windows) sobre blobs mock REALMENTE
firmados, el NonceCache (single-use/TTL/replay), la reconciliación sin
auto-fusión (C4), y la red line #110: el producto NUNCA muestra "Verified"
salvo state == VERIFIED.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography import x509

from lucidfence.core.attest import (
    AttestationState,
    DeviceAttestation,
    NonceCache,
    Provider,
    Reconciliation,
    verify_attestation,
    verify_apple_attestation,
    verify_android_attestation,
    reconcile_identity,
)
from lucidfence.core.attest import _fixtures as fx

NOW = dt.datetime(2026, 8, 23, 12, 0, 0, tzinfo=dt.timezone.utc)
NONCE = "0123456789abcdef0123456789abcdef"   # 32 hex chars = 128-bit


def _cache():
    c = NonceCache()
    c.issue  # touch to ensure attribute exists
    return c


# --------------------------------------------------------------------------
# Apple MDA
# --------------------------------------------------------------------------
def test_apple_verified_with_vendored_root_and_nonce():
    cache = NonceCache()
    issued = cache.issue("dev-apple")
    blob, root = fx.build_apple_blob(issued, device_serial="ABC123")
    res = verify_apple_attestation(blob, issued, roots=[root], cache=cache,
                                   expected_device_id="dev-apple", now=NOW)
    assert res.verification_result is AttestationState.VERIFIED, res.error
    assert res.to_evidence()["trusted"] is True
    assert any("chain:ok" in e for e in res.evidence_refs)
    assert any("nonce:bound" in e for e in res.evidence_refs)


def test_apple_unknown_without_root_configured():
    cache = NonceCache()
    issued = cache.issue()
    blob, _root = fx.build_apple_blob(issued)
    res = verify_apple_attestation(blob, issued, roots=[], cache=cache, now=NOW)
    assert res.verification_result is AttestationState.UNKNOWN
    assert res.error == "no_trusted_root_configured"


def test_apple_rejected_on_nonce_binding_mismatch():
    cache = NonceCache()
    issued = cache.issue("dev-apple")      # nonce bound into the blob
    other = cache.issue("dev-apple")       # a *different* valid (cached) nonce
    blob, root = fx.build_apple_blob(issued)
    # Present `other` (which passes the single-use gate) but differs from the
    # nonce embedded in the blob -> binding mismatch -> REJECTED.
    res = verify_apple_attestation(blob, other, roots=[root], cache=cache,
                                   expected_device_id="dev-apple", now=NOW)
    assert res.verification_result is AttestationState.REJECTED


def test_apple_replay_is_rejected():
    cache = NonceCache()
    issued = cache.issue("dev-apple")
    blob, root = fx.build_apple_blob(issued)
    first = verify_apple_attestation(blob, issued, roots=[root], cache=cache,
                                     expected_device_id="dev-apple", now=NOW)
    assert first.verification_result is AttestationState.VERIFIED
    # Reuse the same nonce -> replay.
    second = verify_apple_attestation(blob, issued, roots=[root], cache=cache,
                                      expected_device_id="dev-apple", now=NOW)
    assert second.verification_result is AttestationState.REJECTED
    assert any("nonce:replay" in e for e in second.evidence_refs)


# --------------------------------------------------------------------------
# Android Key Attestation
# --------------------------------------------------------------------------
def test_android_verified_with_keydescription_challenge():
    cache = NonceCache()
    issued = cache.issue()
    blob, root = fx.build_android_blob(issued, device_serial="ANDROID99")
    res = verify_android_attestation(blob, issued, roots=[root], cache=cache, now=NOW)
    assert res.verification_result is AttestationState.VERIFIED, res.error
    assert res.to_evidence()["trusted"] is True


def test_android_rejected_when_challenge_mismatch():
    cache = NonceCache()
    issued = cache.issue("dev-android")    # nonce bound into the blob
    other = cache.issue("dev-android")     # a *different* valid (cached) nonce
    blob, root = fx.build_android_blob(issued)
    res = verify_android_attestation(blob, other, roots=[root], cache=cache,
                                     expected_device_id="dev-android", now=NOW)
    assert res.verification_result is AttestationState.REJECTED
    assert "attestationChallenge" in (res.error or "")


def test_android_unknown_without_root():
    cache = NonceCache()
    issued = cache.issue()
    blob, _root = fx.build_android_blob(issued)
    res = verify_android_attestation(blob, issued, roots=[], cache=cache, now=NOW)
    assert res.verification_result is AttestationState.UNKNOWN


# --------------------------------------------------------------------------
# Windows TPM quote
# --------------------------------------------------------------------------
def test_windows_verified_with_aik_chain_and_quote_signature():
    cache = NonceCache()
    issued = cache.issue()
    aik_der, quote, sig, root = fx.build_windows_quote(issued)
    res = verify_attestation(
        "windows", b"", issued, roots=[root], cache=cache, now=NOW,
        aik_cert_der=aik_der, signed_quote=quote, signature=sig)
    assert res.verification_result is AttestationState.VERIFIED, res.error
    assert res.to_evidence()["trusted"] is True
    # C8: authenticity, never health judgement.
    assert res.parsed_claims.get("health_judged") is False


def test_windows_rejected_on_bad_quote_signature():
    cache = NonceCache()
    issued = cache.issue()
    aik_der, quote, sig, root = fx.build_windows_quote(issued)
    bad_sig = bytes((b + 1) % 256 for b in sig)
    res = verify_attestation(
        "windows", b"", issued, roots=[root], cache=cache, now=NOW,
        aik_cert_der=aik_der, signed_quote=quote, signature=bad_sig)
    assert res.verification_result is AttestationState.REJECTED


def test_windows_rejected_on_extradata_nonce_mismatch():
    cache = NonceCache()
    issued = cache.issue()
    aik_der, quote, sig, root = fx.build_windows_quote(issued)
    # A second quote bound to a DIFFERENT nonce than the one we issue.
    _other_aik, quote2, sig2, _r2 = fx.build_windows_quote("cafebabe" * 4)
    res = verify_attestation(
        "windows", b"", issued, roots=[root], cache=cache, now=NOW,
        aik_cert_der=aik_der, signed_quote=quote2, signature=sig2)
    assert res.verification_result is AttestationState.REJECTED


# --------------------------------------------------------------------------
# NonceCache unit behaviour
# --------------------------------------------------------------------------
def test_nonce_single_use_and_replay():
    c = NonceCache()
    n = c.issue("d1")
    ok, why = c.consume(n, "d1")
    assert ok and why == "ok"
    ok2, why2 = c.consume(n, "d1")
    assert not ok2 and why2 == "replay"


def test_nonce_unknown_is_not_found():
    c = NonceCache()
    ok, why = c.consume("does-not-exist")
    assert not ok and why == "not_found"


def test_nonce_device_mismatch_is_unverified():
    c = NonceCache()
    n = c.issue("d1")
    ok, why = c.consume(n, "d2")
    assert not ok and why == "device_mismatch"


def test_nonce_expires_after_ttl():
    state = {"t": 1_000_000.0}
    def clock():
        return state["t"]
    c = NonceCache(ttl_seconds=1, clock=clock)
    n = c.issue()
    # Advance the injected clock beyond the TTL (no real sleep) BEFORE consuming.
    state["t"] += 10
    ok, why = c.consume(n)
    assert not ok and why == "expired"


# --------------------------------------------------------------------------
# Reconciliation without auto-fusion (C4)
# --------------------------------------------------------------------------
def test_reconcile_strong_link_is_not_autofused():
    rec = reconcile_identity(
        method="device-attestation",
        candidate_ids=["ABC123", "abc-123", "unknown-id"],
        known_device_ids={"ABC123"},
    )
    assert isinstance(rec, Reconciliation)
    assert rec.auto_fused is False           # red line C4
    assert "ABC123" in rec.linked_ids
    assert rec.confidence == 1.0


def test_reconcile_weak_candidate_only_is_probabilistic():
    rec = reconcile_identity(
        method="device-attestation",
        candidate_ids=["weak-only-1", "weak-only-2"],
        known_device_ids={"SOME-OTHER"},
    )
    assert rec.auto_fused is False
    assert rec.linked_ids == []              # never auto-merged
    assert rec.confidence < 1.0
    assert set(rec.candidate_ids) == {"WEAKONLY1", "WEAKONLY2"}


# --------------------------------------------------------------------------
# RED LINE #110: never render "Verified" unless state == VERIFIED
# --------------------------------------------------------------------------
def test_render_gate_never_trusted_for_non_verified():
    """La regla de producto: 'Verified' SOLO si state == VERIFIED.
    Cualquier otro estado NUNCA se renderiza como confiable."""
    non_trusted = [
        AttestationState.UNVERIFIED,
        AttestationState.UNKNOWN,
        AttestationState.REJECTED,
    ]
    for st in non_trusted:
        assert st.is_trusted is False
        # El consumidor (Risk Engine / UI) debe usar is_trusted, no el enum value.
        label = "Verified" if st.is_trusted else "Trust not asserted"
        assert label == "Trust not asserted"

    assert AttestationState.VERIFIED.is_trusted is True
    assert ("Verified" if AttestationState.VERIFIED.is_trusted else "x") == "Verified"


def test_evidence_trusted_flag_matches_state():
    for st in AttestationState:
        da = DeviceAttestation(provider=Provider.APPLE, raw_blob=b"",
                               verification_result=st)
        assert da.to_evidence()["trusted"] is st.is_trusted


if __name__ == "__main__":
    import traceback
    fns = sorted((k, v) for k, v in globals().items()
                 if k.startswith("test_") and callable(v))
    passed = failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS {name}")
            passed += 1
        except Exception:
            print(f"FAIL {name}")
            traceback.print_exc()
            failed += 1
    print(f"\n=== {passed} passed, {failed} failed ===")
    raise SystemExit(1 if failed else 0)
