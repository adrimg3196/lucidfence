"""Issue #252 — local AI capability inventory (read-only, unknown-safe).

Acceptance criteria exercised:
  * Capability and observed_use are SEPARATE fields and unknown-safe.
  * Fixtures cover: Apple Intelligence allowed/restricted, platform with no
    signal, and stale data.
  * No prompt/response/PII is ever collected (the model carries none).
  * Every signal keeps source + method (auditability).
  * coverage() reports per-platform/per-capability coverage, not a misleading
    fleet-wide percentage.
"""
from lucidfence.core.ai_capability import (
    ingest,
    coverage,
    load_fixture,
    AICapabilityRecord,
    SignalFreshness,
    UNKNOWN,
)


def test_capability_and_observed_use_are_independent_unknown_safe():
    recs = ingest(
        [
            {
                "device_id": "x1",
                "platform": "ios",
                "capability": "apple_intelligence",
                "source": "fixture",
                "method": "mdm_restrictions_profile",
                # declared + allowed, but enabled/observed_use omitted
                "capability_declared": True,
                "allowed_by_policy": True,
            }
        ]
    )
    r = recs[0]
    assert r.capability_declared is True
    assert r.allowed_by_policy is True
    assert r.enabled is None  # unknown, NOT False
    assert r.observed_use is None  # unknown, NOT False
    assert r.as_dict()["freshness"] == SignalFreshness.UNKNOWN.value


def test_apple_intelligence_allowed_fresh():
    recs = load_fixture("apple_intelligence_allowed_fresh")
    r = recs[0]
    assert r.capability_declared is True
    assert r.enabled is True
    assert r.allowed_by_policy is True
    assert r.observed_use is False
    assert r.freshness() == SignalFreshness.FRESH
    # auditability: source + method preserved
    assert r.source == "fixture"
    assert r.method == "mdm_restrictions_profile"


def test_apple_intelligence_restricted_fresh():
    recs = load_fixture("apple_intelligence_restricted_fresh")
    r = recs[0]
    assert r.capability_declared is True  # capability EXISTS
    assert r.allowed_by_policy is False  # but policy DENIES it
    assert r.enabled is False
    # declared-true + allowed-false must stay distinct (no collapse)
    assert r.capability_declared is not r.allowed_by_policy


def test_platform_with_no_signal_is_unknown_not_false():
    recs = load_fixture("platform_no_signal")
    r = recs[0]
    assert r.capability_declared is None
    assert r.enabled is None
    assert r.allowed_by_policy is None
    assert r.observed_use is None
    assert r.freshness() == SignalFreshness.UNKNOWN
    # coverage must count this as unknown, not as a false-negative
    cov = coverage(recs)
    cap = cov["platforms"][0]["capabilities"][0]
    assert cap["devices_unknown"] == 1
    assert cap["coverage_percent"] == 0


def test_stale_data_is_flagged_stale():
    recs = load_fixture("stale_data")
    r = recs[0]
    assert r.freshness() == SignalFreshness.STALE


def test_coverage_is_per_platform_not_fleetwide_percentage():
    # Mix platforms: ios has signal, android has none. A single fleet-wide
    # percentage would be misleading, so coverage() reports per platform.
    recs = load_fixture("apple_intelligence_allowed_fresh") + load_fixture(
        "platform_no_signal"
    )
    cov = coverage(recs)
    by_platform = {p["platform"]: p for p in cov["platforms"]}
    assert set(by_platform) == {"ios", "android"}
    # ios: 1 device, 1 signal -> 100% coverage
    ios_cap = by_platform["ios"]["capabilities"][0]
    assert ios_cap["coverage_percent"] == 100
    # android: 1 device, 0 signal -> 0% coverage (honest blind spot)
    and_cap = by_platform["android"]["capabilities"][0]
    assert and_cap["coverage_percent"] == 0
    assert and_cap["devices_unknown"] == 1


def test_no_pii_fields_exist():
    # Guard against accidental prompt/response/PII collection.
    fields = set(AICapabilityRecord.__dataclass_fields__.keys())
    forbidden = {"prompt", "response", "text", "user", "username", "email", "token"}
    assert forbidden.isdisjoint(fields)
