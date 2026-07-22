from datetime import datetime, timedelta, timezone
from typing import Any

from core.multiuem import (
    LocationEvidence,
    NormalizedDevice,
    ProviderCapabilities,
    ProviderHealth,
    SyncResult,
    normalize_identity,
)


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def _evidence(
    *,
    lat: Any = 40.42,
    lng: Any = -3.71,
    observed_at: Any = None,
    accuracy_m: Any = 25,
):
    if observed_at is None:
        observed_at = NOW.isoformat()
    return LocationEvidence(lat, lng, observed_at, accuracy_m, "intune", "gps")


def test_identity_placeholders_are_never_usable_after_ascii_normalization():
    for value in (None, "", "N/A", "unknown", "0", " - ", " null ", "un-available"):
        assert normalize_identity(value) is None
    assert normalize_identity(" ab-c 123 ") == "ABC123"


def test_identity_rejects_entire_value_when_any_character_is_non_ascii():
    for value in (
        "Ｎ／Ａ",
        "ｕｎｋｎｏｗｎ",
        "ß",
        "ı",
        "Straße",
        "devıce",
        "ABCé123",
        "ABC—123",
    ):
        assert normalize_identity(value) is None

    assert normalize_identity("SS") == "SS"
    assert normalize_identity("i") == "I"


def test_location_quality_accepts_fresh_precise_evidence():
    assert _evidence().quality(NOW, 900, 200) == (True, "accepted")


def test_location_quality_rejects_invalid_limits_before_evidence():
    invalid_limits: tuple[Any, ...] = (
        None,
        "10",
        True,
        False,
        -1,
        float("nan"),
        float("inf"),
        float("-inf"),
    )
    invalid_evidence = LocationEvidence(True, False, None, True, "jamf", "gps")

    for invalid in invalid_limits:
        assert invalid_evidence.quality(NOW, invalid, 200, 60) == (False, "invalid_limits")
        assert invalid_evidence.quality(NOW, 900, invalid, 60) == (False, "invalid_limits")
        assert invalid_evidence.quality(NOW, 900, 200, invalid) == (False, "invalid_limits")


def test_location_quality_accepts_finite_non_negative_float_limits():
    assert _evidence(accuracy_m=0).quality(NOW, 0.0, 0.0, 0.0) == (True, "accepted")


def test_location_quality_rejects_missing_invalid_and_naive_timestamps():
    for observed_at in (None, 123, "not-a-timestamp", "2026-07-22T12:00:00"):
        evidence = LocationEvidence(40.42, -3.71, observed_at, 25, "jamf", "gps")
        assert evidence.quality(NOW, 900, 200) == (False, "invalid_timestamp")


def test_location_quality_accepts_utc_z_timestamp():
    assert _evidence(observed_at="2026-07-22T12:00:00Z").quality(NOW, 900, 200) == (
        True,
        "accepted",
    )


def test_location_quality_rejects_non_finite_boolean_and_out_of_range_coordinates():
    invalid_latitudes = (float("nan"), float("inf"), float("-inf"), True, False, -90.0001, 90.0001)
    invalid_longitudes = (
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        False,
        -180.0001,
        180.0001,
    )

    for latitude in invalid_latitudes:
        assert _evidence(lat=latitude).quality(NOW, 900, 200) == (
            False,
            "invalid_coordinates",
        )
    for longitude in invalid_longitudes:
        assert _evidence(lng=longitude).quality(NOW, 900, 200) == (
            False,
            "invalid_coordinates",
        )


def test_location_quality_accepts_exact_coordinate_boundaries():
    for latitude, longitude in ((-90, -180), (-90, 180), (90, -180), (90, 180)):
        assert _evidence(lat=latitude, lng=longitude).quality(NOW, 900, 200) == (
            True,
            "accepted",
        )


def test_location_quality_rejects_stale_inaccurate_and_future_evidence():
    cases = [
        (_evidence(observed_at=(NOW - timedelta(seconds=901)).isoformat()), "stale"),
        (_evidence(accuracy_m=201), "inaccurate"),
        (_evidence(observed_at=(NOW + timedelta(seconds=61)).isoformat()), "future"),
    ]
    for evidence, reason in cases:
        assert evidence.quality(NOW, 900, 200) == (False, reason)


def test_location_quality_accepts_exact_age_future_and_accuracy_limits():
    cases = (
        _evidence(observed_at=(NOW - timedelta(seconds=900)).isoformat()),
        _evidence(observed_at=(NOW + timedelta(seconds=60)).isoformat()),
        _evidence(accuracy_m=200),
    )
    for evidence in cases:
        assert evidence.quality(NOW, 900, 200, 60) == (True, "accepted")


def test_location_quality_rejects_non_finite_boolean_and_negative_accuracy():
    for accuracy in (float("nan"), float("inf"), float("-inf"), True, False, -0.01):
        assert _evidence(accuracy_m=accuracy).quality(NOW, 900, 200) == (
            False,
            "invalid_accuracy",
        )


def test_location_quality_accepts_missing_accuracy():
    evidence = LocationEvidence(40.42, -3.71, NOW.isoformat(), None, "jamf", "network")
    assert evidence.quality(NOW, 900, 200) == (True, "accepted")


def test_mutable_model_defaults_are_independent():
    first_device = NormalizedDevice("a", "intune", "1", "One", "ios")
    second_device = NormalizedDevice("b", "jamf", "2", "Two", "android")
    first_device.inventory["owner"] = "alice"
    first_device.provider_refs["intune"] = "1"
    first_device.provenance["name"] = "intune"

    assert second_device.inventory == {}
    assert second_device.provider_refs == {}
    assert second_device.provenance == {}

    first_sync = SyncResult()
    second_sync = SyncResult()
    first_sync.devices.append(first_device)
    first_sync.health["intune"] = ProviderHealth("ok")

    assert second_sync.devices == []
    assert second_sync.health == {}


def test_provider_capability_action_defaults_are_immutable_and_shared_safely():
    first = ProviderCapabilities()
    second = ProviderCapabilities()

    assert first.actions == frozenset()
    assert second.actions == frozenset()
    assert first.actions is second.actions
