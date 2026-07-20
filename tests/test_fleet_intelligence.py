from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

from core.product import build_analytics, build_product


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)


def _history(*minutes, total=5):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "ts": (base + timedelta(minutes=minute)).isoformat(),
            "devices_total": total,
            "inside": max(0, total - 1),
            "outside": 1,
            "unknown": 0,
            "non_compliant": 1,
        }
        for minute in minutes
    ]


def test_fleet_intelligence_explains_history_quality_and_trends():
    history = _history(0, 15, 75, 90)
    trails = [
        {"device_id": "d1", "ts": "2026-01-01T00:00:00Z", "fence_state": "inside", "lat": 1, "lng": 1},
        {"device_id": "d1", "ts": "2026-01-01T00:10:00Z", "fence_state": "outside", "lat": 2, "lng": 2},
        {"device_id": "d1", "ts": "2026-01-01T00:20:00Z", "fence_state": "outside", "lat": 3, "lng": 3},
        {"device_id": "d1", "ts": "2026-01-01T00:30:00Z", "fence_state": "inside", "lat": 4, "lng": 4},
        {"device_id": "d2", "ts": "2026-01-01T00:00:00Z", "fence_state": "inside", "lat": 1, "lng": 1},
    ]
    result = build_analytics([], [], [], history, trails=trails,
                             now=datetime(2026, 1, 1, 1, 35, tzinfo=timezone.utc),
                             expected_interval_seconds=900)
    intel = result["fleet_intelligence"]

    assert intel["history_points"] == 4
    assert intel["history_span_hours"] == 1.5
    assert intel["median_interval_seconds"] == 900
    assert intel["gap_threshold_seconds"] == 1800
    assert intel["gap_count"] == 1
    assert intel["freshness_seconds"] == 300
    assert intel["outside_peak"] == 1
    assert intel["geofence_transitions"] == 2
    assert intel["top_transition_device"] == {"device_id": "d1", "transitions": 2}
    assert 0 <= intel["signal_quality_score"] < 100
    assert intel["quality_components"]["gps_coverage_percent"] == 100
    assert intel["evidence"]["method"] == "observed-local-history"


def test_expected_cadence_detects_outage_instead_of_learning_it_as_normal():
    intel = build_analytics([], [], [], _history(0, 60), now=NOW,
                            expected_interval_seconds=900)["fleet_intelligence"]
    assert intel["median_interval_seconds"] == 3600
    assert intel["gap_threshold_seconds"] == 1800
    assert intel["gap_count"] == 1
    assert intel["quality_components"]["continuity_percent"] == 0


def test_interval_equal_to_gap_threshold_is_not_a_gap():
    intel = build_analytics([], [], [], _history(0, 30), now=NOW,
                            expected_interval_seconds=900)["fleet_intelligence"]
    assert intel["gap_threshold_seconds"] == 1800
    assert intel["gap_count"] == 0


def test_one_unique_timestamp_is_insufficient_and_schema_is_stable():
    for history in (_history(0), _history(0, 0)):
        intel = build_analytics([], [], [], history, now=NOW)["fleet_intelligence"]
        assert intel["status"] == "insufficient_data"
        assert intel["quality_components"]["continuity_percent"] == 0
        assert intel["compliance_delta_points"] is None
        assert "gap_threshold_seconds" in intel
        assert "quality_formula" in intel["evidence"]


def test_future_timestamp_is_rejected_and_reported_as_clock_skew():
    history = _history(60, 90)
    history.append({**_history(180)[0], "ts": "2099-01-01T00:00:00Z"})
    intel = build_analytics([], [], [], history, now=NOW,
                            expected_interval_seconds=900)["fleet_intelligence"]
    assert intel["status"] == "ready"
    assert intel["history_points"] == 2
    assert intel["invalid_timestamp_count"] == 1
    assert intel["clock_skew_detected"] is True
    assert intel["freshness_seconds"] == 1800
    assert any("reloj" in item.lower() for item in intel["recommendations"])


def test_transition_identity_gps_ranges_and_trail_window_are_enforced():
    trails = [
        {"ts": "2026-01-01T00:10:00Z", "fence_state": "inside", "lat": 1, "lng": 1},
        {"ts": "2026-01-01T00:20:00Z", "fence_state": "outside", "lat": 2, "lng": 2},
        {"device_id": "d1", "ts": "2026-01-01T00:10:00Z", "fence_state": "inside", "lat": 40, "lng": -3},
        {"device_id": "d1", "ts": "2026-01-01T00:20:00Z", "fence_state": "outside", "lat": "x", "lng": 999},
        {"device_id": "d1", "ts": "2026-01-01T00:30:00Z", "fence_state": "inside", "lat": float("nan"), "lng": 1},
        {"device_id": "d1", "ts": "2026-01-01T03:00:00Z", "fence_state": "outside", "lat": 40, "lng": -3},
    ]
    intel = build_analytics([], [], [], _history(0, 30), trails=trails,
                            now=NOW)["fleet_intelligence"]
    assert intel["geofence_transitions"] == 2
    assert intel["top_transition_device"] == {"device_id": "d1", "transitions": 2}
    assert intel["quality_components"]["gps_coverage_percent"] == 60
    assert intel["evidence"]["trail_points_analyzed"] == 5
    assert intel["evidence"]["trail_points_discarded"] == 1


def test_corrupt_counters_are_clamped_in_series_and_intelligence():
    history = [
        {"ts": "2026-01-01T00:00:00Z", "devices_total": "bad", "non_compliant": -9, "outside": -3},
        {"ts": "2026-01-01T00:15:00Z", "devices_total": 2, "non_compliant": 9, "outside": "bad"},
    ]
    analytics = build_analytics([], [], [], history, now=NOW)
    assert [row["compliance_percent"] for row in analytics["compliance_series"]] == [100, 0]
    intel = analytics["fleet_intelligence"]
    assert intel["outside_peak"] == 0
    assert -100 <= intel["compliance_delta_points"] <= 100
    assert intel["invalid_counter_count"] > 0


def test_analysis_has_explicit_volume_limits_and_temporal_depth():
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    history = [
        {"ts": (base + timedelta(minutes=i)).isoformat(), "devices_total": 1,
         "non_compliant": 0, "inside": 1, "outside": 0, "unknown": 0}
        for i in range(5000)
    ]
    intel = build_analytics([], [], [], history, now=base + timedelta(minutes=5001),
                            expected_interval_seconds=60)["fleet_intelligence"]
    assert intel["history_points"] <= 4096
    assert intel["evidence"]["history_points_discarded"] == 904
    assert intel["quality_components"]["history_depth_percent"] == 100


def test_build_product_passes_engine_interval_and_flattens_grouped_trails():
    status = {
        "interval_seconds": 900,
        "stats_history": _history(0, 60, total=1),
        "trails": {"d1": [
            {"ts": "2026-01-01T00:00:00Z", "fence_state": "inside", "lat": 1, "lng": 1},
            {"ts": "2026-01-01T00:10:00Z", "fence_state": "outside", "lat": 2, "lng": 2},
        ]},
    }
    intel = build_product(status)["analytics"]["fleet_intelligence"]
    assert intel["gap_count"] == 1
    assert intel["geofence_transitions"] == 1


def test_intelligence_view_contract_is_accessible_and_responsive():
    app = (ROOT / "static/app.js").read_text(encoding="utf-8")
    dashboard = (ROOT / "static/dashboard.html").read_text(encoding="utf-8")
    assert 'id:"intelligence"' in app
    assert 'a.href = "#"+item.id' in app
    assert 'aria-live="polite"' in app
    assert '<h1 class="view-title">Inteligencia de flota</h1>' in app
    assert 'class="sr-only intel-data-table"' in app
    assert "finiteMetric" in app
    assert 'value===null || value===undefined || value===""' in app
    assert ':focus-visible' in dashboard
    assert '@media(max-width:700px)' in dashboard
    assert 'grid-template-columns:repeat(2,minmax(0,1fr))' in dashboard


def test_versioned_notebook_contains_no_local_telemetry_outputs():
    notebook = json.loads((ROOT / "analysis/fleet_intelligence.ipynb").read_text(encoding="utf-8"))
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") == "code":
            assert cell.get("execution_count") is None
            assert cell.get("outputs") == []
