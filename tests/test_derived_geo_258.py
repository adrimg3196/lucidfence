"""Issue #258 — geofencing from a derived state signal, no raw coordinates.

Acceptance criteria exercised:
  * In derived-only mode, raw coordinates fed in are NEVER persisted to storage,
    logs, exports or the cloud_state representation.
  * inside/outside/unknown are evaluated with policy_hash and freshness.
  * A policy_hash change invalidates a previously stored signal (-> unknown).
  * Replay (repeated nonce) or a future timestamp lowers confidence and is VISIBLE.
  * The derived-only mode is opt-in and reports which analyses stop being possible.
  * Evidence export proves the decision without reconstructing a personal route.
"""
from lucidfence.core.derived_geo import (
    DerivedGeoSignal,
    DerivedGeoMode,
    GeoState,
    Confidence,
    policy_hash_of,
    ingest,
    evaluate,
    activation_tradeoffs,
    export_evidence,
    to_cloud_state,
)


def _policy() -> dict:
    return {"fence_id": "hq", "radius_m": 600, "type": "circle"}


def _signal(state="inside", lat=40.4168, lng=-3.7038, nonce="n1", observed_at="2026-08-22T10:00:00Z"):
    return DerivedGeoSignal(
        fence_id="hq", device_id="dev-1", tenant_id="t-a",
        state=state, observed_at=observed_at,
        policy_hash=policy_hash_of(_policy()), source="uem-derived",
        confidence=Confidence.HIGH.value, lat=lat, lng=lng, nonce=nonce,
    )


def test_derived_only_strips_coords_from_storage():
    sig = _signal()
    out = ingest(sig, DerivedGeoMode.DERIVED_ONLY, stored_policy_hash=sig.policy_hash)
    d = out.as_dict()  # default strips raw
    assert "lat" not in d and "lng" not in d
    assert out.lat is None and out.lng is None
    assert out.state == GeoState.INSIDE.value


def test_full_mode_retains_coords():
    sig = _signal()
    out = ingest(sig, DerivedGeoMode.FULL, stored_policy_hash=sig.policy_hash)
    assert out.lat == 40.4168 and out.lng == -3.7038


def test_poison_coords_never_reach_cloud_state_or_export():
    # Feed envenenated coordinates; derived-only must drop them everywhere.
    sig = _signal(lat=99.999, lng=999.999)
    out = ingest(sig, DerivedGeoMode.DERIVED_ONLY, stored_policy_hash=sig.policy_hash)
    cs = to_cloud_state("dev-1", out, DerivedGeoMode.DERIVED_ONLY)
    assert "lat" not in cs and "lng" not in cs
    ev = export_evidence(out)
    assert ev["contains_raw_coordinates"] is False
    assert "lat" not in ev and "lng" not in ev


def test_state_evaluated_with_policy_hash_and_freshness():
    r = evaluate("inside", policy_hash_of(_policy()),
                 policy_hash_of(_policy()), "2026-08-22T10:00:00Z")
    assert r["state"] == GeoState.INSIDE.value
    r2 = evaluate("outside", policy_hash_of(_policy()),
                  policy_hash_of(_policy()), "2026-08-22T10:00:00Z")
    assert r2["state"] == GeoState.OUTSIDE.value


def test_policy_hash_change_invalidates_signal():
    sig = _signal()
    out = ingest(sig, DerivedGeoMode.DERIVED_ONLY,
                 stored_policy_hash=policy_hash_of({"fence_id": "hq", "radius_m": 900}))
    assert out.invalidated_by_policy is True
    assert out.state == GeoState.UNKNOWN.value


def test_replay_lowers_confidence_and_visible():
    sig1 = _signal(nonce="dup")
    sig2 = _signal(nonce="dup")
    seen: set = set()
    out1 = ingest(sig1, DerivedGeoMode.DERIVED_ONLY, stored_policy_hash=sig1.policy_hash, seen_nonces=seen)
    out2 = ingest(sig2, DerivedGeoMode.DERIVED_ONLY, stored_policy_hash=sig2.policy_hash, seen_nonces=seen)
    assert out1.replay_detected is False
    assert out2.replay_detected is True
    assert out2.confidence == Confidence.LOW.value
    assert out2.state == GeoState.UNKNOWN.value


def test_future_timestamp_lowers_confidence():
    sig = _signal(observed_at="2099-01-01T00:00:00Z")
    out = ingest(sig, DerivedGeoMode.DERIVED_ONLY, stored_policy_hash=sig.policy_hash,
                 now=1_000_000.0)
    assert out.future_timestamp is True
    assert out.confidence == Confidence.LOW.value
    assert out.state == GeoState.UNKNOWN.value


def test_derived_only_tradeoffs_surfaced():
    tos = activation_tradeoffs()
    assert len(tos) >= 3
    assert any("historical" in t for t in tos)


def test_evidence_hash_is_stable_and_proves_decision():
    sig = _signal()
    ev1 = export_evidence(ingest(sig, DerivedGeoMode.DERIVED_ONLY, stored_policy_hash=sig.policy_hash))
    sig2 = _signal()
    ev2 = export_evidence(ingest(sig2, DerivedGeoMode.DERIVED_ONLY, stored_policy_hash=sig2.policy_hash))
    assert ev1["evidence_hash"] == ev2["evidence_hash"]
    assert ev1["state"] == "inside" and ev1["policy_hash"]
