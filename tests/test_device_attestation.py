"""Neutral device attestation envelope for Apple, Android and Windows.

Run directly: python3 tests/test_device_attestation.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from lucidfence.core.device_attestation import (  # noqa: E402
    AttestationError,
    attestation_report,
    envelope_from_dict,
    envelope_from_json,
    normalize_attestation,
)
from lucidfence.core.location_source import LocationReport  # noqa: E402
from lucidfence.core.state_store import DeviceState  # noqa: E402
from lucidfence.saas import routing  # noqa: E402
from helpers import make_temp_engine  # noqa: E402
import saas_server  # noqa: E402,F401


def _fixture(source):
    common = {
        "hardware_backed": True,
        "managed": True,
        "os_integrity": True,
    }
    if source == "apple":
        return {
            "device_udid": "apple-device-1",
            "managed_device_attestation": {
                "issued_at": "2026-09-02T10:00:00Z",
                "expires_at": "2026-09-02T10:15:00Z",
                "nonce": "nonce-apple-001",
                "verifier": "apple-managed-device-attestation",
                "signature_status": "verified",
                "certificate_chain_hash": "a" * 64,
                "claims": dict(common, secure_enclave=True, os_version="17.6"),
            },
        }
    if source == "android":
        return {
            "device_id": "android-device-1",
            "device_trust": {
                "evaluationTime": "2026-09-02T10:00:00Z",
                "expirationTime": "2026-09-02T10:15:00Z",
                "nonce": "nonce-android-001",
                "verifier": "android-enterprise-device-trust",
                "signature_status": "verified",
                "verdict_hash": "b" * 64,
                "claims": dict(common, play_protect=True, os_version="14"),
            },
        }
    if source == "windows":
        return {
            "device_id": "windows-device-1",
            "health_attestation": {
                "issued_at": "2026-09-02T10:00:00Z",
                "expires_at": "2026-09-02T10:15:00Z",
                "nonce": "nonce-windows-001",
                "verifier": "windows-device-health-attestation",
                "signature_status": "verified",
                "report_hash": "c" * 64,
                "claims": dict(common, secure_boot=True, bitlocker=True),
            },
        }
    raise AssertionError(source)


def test_three_vendor_fixtures_share_neutral_contract_without_losing_differences():
    envelopes = [
        normalize_attestation(src, _fixture(src), observed_at="2026-09-02T10:01:00Z")
        for src in ("apple", "android", "windows")
    ]
    keys = [set(e.to_dict()) for e in envelopes]
    assert keys[0] == keys[1] == keys[2]
    assert [e.source for e in envelopes] == ["apple", "android", "windows"]
    assert [e.subject for e in envelopes] == ["apple-device-1", "android-device-1", "windows-device-1"]
    assert all(e.claims["hardware_backed"]["status"] == "asserted" for e in envelopes)
    assert envelopes[0].provenance["raw_claims"]["secure_enclave"] is True
    assert envelopes[1].provenance["raw_claims"]["play_protect"] is True
    assert envelopes[2].provenance["raw_claims"]["secure_boot"] is True


def test_absent_claim_is_unknown_and_not_false_by_default():
    raw = _fixture("android")
    del raw["device_trust"]["claims"]["managed"]
    envelope = normalize_attestation("android", raw, observed_at="2026-09-02T10:01:00Z")
    assert envelope.claims["managed"] == {
        "status": "unknown",
        "value": None,
        "reason": "claim absent in android attestation payload",
    }
    assert envelope.claims["managed"]["value"] is not False


def test_validation_rejects_impossible_timestamps_ambiguous_types_and_bad_hashes():
    impossible = _fixture("apple")
    impossible["managed_device_attestation"]["issued_at"] = "2026-09-02T10:20:00Z"
    try:
        normalize_attestation("apple", impossible, observed_at="2026-09-02T10:01:00Z")
    except AttestationError as exc:
        assert "issued_at after observed_at" in str(exc)
    else:
        raise AssertionError("impossible timestamp accepted")

    ambiguous = _fixture("android")
    ambiguous["device_trust"]["claims"]["managed"] = "false"
    try:
        normalize_attestation("android", ambiguous, observed_at="2026-09-02T10:01:00Z")
    except AttestationError as exc:
        assert "ambiguous boolean claim" in str(exc)
    else:
        raise AssertionError("ambiguous boolean string accepted")

    bad_hash = _fixture("windows")
    bad_hash["health_attestation"]["report_hash"] = "not-a-sha256"
    try:
        normalize_attestation("windows", bad_hash, observed_at="2026-09-02T10:01:00Z")
    except AttestationError as exc:
        assert "raw_hash" in str(exc)
    else:
        raise AssertionError("bad raw_hash accepted")


def test_serialization_is_deterministic_and_old_device_state_data_stays_compatible():
    envelope = normalize_attestation("apple", _fixture("apple"), observed_at="2026-09-02T10:01:00Z")
    encoded_a = envelope.to_json()
    encoded_b = envelope_from_json(encoded_a).to_json()
    assert encoded_a == encoded_b
    assert list(json.loads(encoded_a).keys()) == sorted(json.loads(encoded_a).keys())

    legacy = envelope.to_dict()
    legacy.pop("model_version")
    assert envelope_from_dict(legacy).model_version == "1.0"

    old_device = DeviceState(device_id="old-1", name="Old", platform="ios").to_dict()
    assert "attestation" in old_device
    assert old_device["attestation"] is None


def test_read_only_report_explains_provenance_without_boolean_collapse():
    devices = [
        DeviceState(
            device_id="d1",
            name="iPhone",
            platform="ios",
            attestation=normalize_attestation(
                "apple", _fixture("apple"), observed_at="2026-09-02T10:01:00Z"
            ).to_dict(),
        ).to_dict()
    ]
    report = attestation_report(devices)
    assert report["total"] == 1
    assert report["attestations"][0]["source"] == "apple"
    assert report["attestations"][0]["explanation"]
    assert report["attestations"][0]["claims"]["encryption"]["status"] == "unknown"
    assert report["attestations"][0]["claims"]["encryption"]["value"] is None


def test_read_only_api_route_serves_persisted_neutral_envelopes():
    eng = make_temp_engine()
    eng.store.upsert(DeviceState(
        device_id="d-api",
        name="API iPhone",
        platform="ios",
        attestation=normalize_attestation(
            "apple", _fixture("apple"), observed_at="2026-09-02T10:01:00Z"
        ).to_dict(),
    ))
    sent = []
    ctx = routing.Ctx(
        http=None,
        user={"org_roles": {"org-test": "viewer"}},
        org="org-test",
        eng=eng,
        qs={},
    )
    handled = saas_server._api_routes.dispatch(
        "GET", "/api/device-attestation", ctx,
        send=lambda obj, code=200: sent.append((code, obj)),
    )
    assert handled is True
    code, payload = sent[0]
    assert code == 200
    assert payload["total"] == 1
    assert payload["attestations"][0]["device_id"] == "d-api"
    assert payload["attestations"][0]["signature_status"] == "verified"


def test_expired_before_observed_attestation_is_rejected():
    raw = _fixture("apple")
    raw["managed_device_attestation"]["expires_at"] = "2026-09-02T10:00:30Z"
    try:
        normalize_attestation("apple", raw, observed_at="2026-09-02T10:01:00Z")
    except AttestationError as exc:
        assert "expires_at before observed_at" in str(exc)
    else:
        raise AssertionError("expired-before-observed attestation accepted")


def test_conflicting_vendor_claim_aliases_are_rejected():
    raw = _fixture("windows")
    raw["health_attestation"]["claims"]["hardware_backed"] = True
    raw["health_attestation"]["claims"]["secure_boot"] = False
    try:
        normalize_attestation("windows", raw, observed_at="2026-09-02T10:01:00Z")
    except AttestationError as exc:
        assert "conflicting aliases" in str(exc)
    else:
        raise AssertionError("conflicting vendor aliases accepted")


def test_read_only_report_skips_malformed_attestation_without_hiding_valid_rows():
    valid = normalize_attestation("apple", _fixture("apple"), observed_at="2026-09-02T10:01:00Z")
    report = attestation_report([
        DeviceState(device_id="valid", name="Valid", platform="ios", attestation=valid.to_dict()).to_dict(),
        DeviceState(device_id="bad", name="Bad", platform="windows", attestation={"source": "windows"}).to_dict(),
    ])
    assert report["total"] == 1
    assert report["attestations"][0]["device_id"] == "valid"
    assert report["invalid"] == 1


def test_engine_run_once_preserves_persisted_attestation_when_report_omits_it():
    eng = make_temp_engine()
    envelope = normalize_attestation("apple", _fixture("apple"), observed_at="2026-09-02T10:01:00Z")
    eng.store.upsert(DeviceState(
        device_id="d-cycle",
        name="Cycle iPhone",
        platform="ios",
        attestation=envelope.to_dict(),
    ))
    eng.source = type("Source", (), {"fetch": lambda self: [
        LocationReport(
            device_id="d-cycle",
            name="Cycle iPhone",
            platform="ios",
            lat=40.0,
            lng=-3.0,
            status="active",
            compliant=True,
        )
    ]})()
    stored_before = eng.store.get("d-cycle")
    assert stored_before is not None
    assert stored_before.attestation is not None
    eng.run_once()
    stored_after = eng.store.get("d-cycle")
    assert stored_after is not None
    assert stored_after.attestation == envelope.to_dict()


if __name__ == "__main__":
    test_three_vendor_fixtures_share_neutral_contract_without_losing_differences()
    test_absent_claim_is_unknown_and_not_false_by_default()
    test_validation_rejects_impossible_timestamps_ambiguous_types_and_bad_hashes()
    test_serialization_is_deterministic_and_old_device_state_data_stays_compatible()
    test_read_only_report_explains_provenance_without_boolean_collapse()
    test_read_only_api_route_serves_persisted_neutral_envelopes()
    test_expired_before_observed_attestation_is_rejected()
    test_conflicting_vendor_claim_aliases_are_rejected()
    test_read_only_report_skips_malformed_attestation_without_hiding_valid_rows()
    test_engine_run_once_preserves_persisted_attestation_when_report_omits_it()
    print("device-attestation tests passed")
