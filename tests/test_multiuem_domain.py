from datetime import datetime, timedelta, timezone

from core.multiuem import LocationEvidence, normalize_identity


def test_identity_placeholders_are_never_usable():
    for value in (None, "", "N/A", "unknown", "0", " - "):
        assert normalize_identity(value) is None
    assert normalize_identity(" ab-c 123 ") == "ABC123"


def test_location_quality_accepts_fresh_precise_evidence():
    now = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    evidence = LocationEvidence(40.42, -3.71, now.isoformat(), 25, "intune", "gps")
    assert evidence.quality(now, 900, 200) == (True, "accepted")


def test_location_quality_rejects_stale_inaccurate_future_and_invalid_coordinates():
    now = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    cases = [
        (
            LocationEvidence(
                40.42,
                -3.71,
                (now - timedelta(seconds=901)).isoformat(),
                25,
                "jamf",
                "gps",
            ),
            "stale",
        ),
        (LocationEvidence(40.42, -3.71, now.isoformat(), 201, "jamf", "gps"), "inaccurate"),
        (
            LocationEvidence(
                40.42,
                -3.71,
                (now + timedelta(seconds=61)).isoformat(),
                25,
                "jamf",
                "gps",
            ),
            "future",
        ),
        (LocationEvidence(100, -3.71, now.isoformat(), 25, "jamf", "gps"), "invalid_coordinates"),
    ]
    for evidence, reason in cases:
        assert evidence.quality(now, 900, 200) == (False, reason)
