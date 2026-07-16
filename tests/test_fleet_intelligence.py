from datetime import datetime, timezone

from core.product import build_analytics, build_product


def test_fleet_intelligence_explains_history_quality_and_trends():
    history = [
        {"ts": "2026-01-01T00:00:00Z", "devices_total": 5, "inside": 4, "outside": 1, "unknown": 0, "non_compliant": 0},
        {"ts": "2026-01-01T00:15:00Z", "devices_total": 5, "inside": 3, "outside": 2, "unknown": 0, "non_compliant": 1},
        {"ts": "2026-01-01T01:15:00Z", "devices_total": 5, "inside": 5, "outside": 0, "unknown": 0, "non_compliant": 0},
        {"ts": "2026-01-01T01:30:00Z", "devices_total": 5, "inside": 3, "outside": 2, "unknown": 0, "non_compliant": 1},
    ]
    trails = [
        {"device_id": "d1", "ts": "2026-01-01T00:00:00Z", "fence_state": "inside", "lat": 1, "lng": 1},
        {"device_id": "d1", "ts": "2026-01-01T00:10:00Z", "fence_state": "outside", "lat": 2, "lng": 2},
        {"device_id": "d1", "ts": "2026-01-01T00:20:00Z", "fence_state": "outside", "lat": 3, "lng": 3},
        {"device_id": "d1", "ts": "2026-01-01T00:30:00Z", "fence_state": "inside", "lat": 4, "lng": 4},
        {"device_id": "d2", "ts": "2026-01-01T00:00:00Z", "fence_state": "inside", "lat": 1, "lng": 1},
    ]

    result = build_analytics([], [], [], history, trails=trails,
                             now=datetime(2026, 1, 1, 1, 35, tzinfo=timezone.utc))
    intel = result["fleet_intelligence"]

    assert intel["history_points"] == 4
    assert intel["history_span_hours"] == 1.5
    assert intel["median_interval_seconds"] == 900
    assert intel["gap_count"] == 1
    assert intel["freshness_seconds"] == 300
    assert intel["compliance_delta_points"] == -20
    assert intel["outside_peak"] == 2
    assert intel["geofence_transitions"] == 2
    assert intel["top_transition_device"] == {"device_id": "d1", "transitions": 2}
    assert 0 <= intel["signal_quality_score"] <= 100
    assert intel["signal_quality_score"] < 100  # one observed gap cannot round up to perfect
    assert intel["quality_components"]["gps_coverage_percent"] == 100
    assert intel["evidence"]["method"] == "observed-local-history"


def test_fleet_intelligence_handles_empty_history_without_overclaiming():
    result = build_analytics([], [], [], [], trails=[], now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    intel = result["fleet_intelligence"]
    assert intel["history_points"] == 0
    assert intel["signal_quality_score"] == 0
    assert intel["status"] == "insufficient_data"
    assert intel["recommendations"]


def test_build_product_flattens_engine_trails_grouped_by_device():
    status = {
        "stats_history": [
            {"ts": "2026-01-01T00:00:00Z", "devices_total": 1, "inside": 1, "outside": 0, "unknown": 0, "non_compliant": 0},
            {"ts": "2026-01-01T00:15:00Z", "devices_total": 1, "inside": 0, "outside": 1, "unknown": 0, "non_compliant": 0},
        ],
        "trails": {
            "d1": [
                {"ts": "2026-01-01T00:00:00Z", "fence_state": "inside", "lat": 1, "lng": 1},
                {"ts": "2026-01-01T00:10:00Z", "fence_state": "outside", "lat": 2, "lng": 2},
            ]
        },
    }
    intel = build_product(status)["analytics"]["fleet_intelligence"]
    assert intel["geofence_transitions"] == 1
    assert intel["top_transition_device"] == {"device_id": "d1", "transitions": 1}


def test_intelligence_view_contract_is_wired():
    app = open("static/app.js", encoding="utf-8").read()
    dashboard = open("static/dashboard.html", encoding="utf-8").read()
    assert 'id:"intelligence"' in app
    assert "async function renderIntelligence()" in app
    assert 'api("/api/analytics")' in app
    assert 'id="view-intelligence"' in dashboard
