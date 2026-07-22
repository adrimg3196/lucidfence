from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.predictive import forecast_movements
from core.product import build_analytics


def _ts(seconds: int) -> str:
    return (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)).isoformat()


def test_forecast_detects_projected_geofence_exit_with_evidence():
    trails = [
        {"device_id": "d1", "lat": 40.0, "lng": -2.9999, "fence_state": "inside", "ts": _ts(0)},
        {"device_id": "d1", "lat": 40.0, "lng": -2.9996, "fence_state": "inside", "ts": _ts(60)},
    ]
    fences = [{"id": "hq", "type": "circle", "center": {"lat": 40.0, "lng": -3.0}, "radius_m": 50}]
    result = forecast_movements(trails, fences, expected_interval_seconds=120)
    row = result["forecasts"][0]
    assert result["status"] == "ready"
    assert row["crossing_risk"] is True
    assert row["leaving_fences"] == ["hq"]
    assert row["verified"] is True
    assert row["evidence"]["observations"] == 2


def test_implausible_gps_jump_is_anomaly_not_confident_prediction():
    trails = [
        {"device_id": "d1", "lat": 40.0, "lng": -3.0, "ts": _ts(0)},
        {"device_id": "d1", "lat": 41.0, "lng": -3.0, "ts": _ts(1)},
    ]
    row = forecast_movements(trails, [], 900)["forecasts"][0]
    assert row["anomaly"] is True
    assert row["verified"] is False
    assert row["confidence_percent"] == 0
    assert row["projected"] == {"lat": 41.0, "lng": -3.0}


def test_analytics_exposes_weekly_predictive_summary():
    trails = [
        {"device_id": "d1", "lat": 40.0, "lng": -3.0, "ts": _ts(0)},
        {"device_id": "d1", "lat": 40.0001, "lng": -3.0, "ts": _ts(60)},
    ]
    analytics = build_analytics([], [], [], [], trails=trails, fences=[], expected_interval_seconds=60)
    predictive = analytics["predictive_movement"]
    assert predictive["weekly_summary"]["devices_with_forecast"] == 1
    assert predictive["provenance"] == "local-trails"
