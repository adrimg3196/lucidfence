"""Explainable, local-only movement forecasting for LucidFence.

This is intentionally a deterministic short-horizon extrapolator, not an opaque
ML claim.  It uses the last two valid observations per device, projects one
engine interval, evaluates the projected point against the configured fences,
and carries evidence with every result.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import math
from typing import Any

from core.geo import Point, haversine_m, point_in_polygon

MAX_TRAIL_POINTS = 20_000
MAX_SPEED_KMH = 220.0


def _dt(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _point(row: dict) -> Point | None:
    try:
        lat, lng = float(row.get("lat")), float(row.get("lng"))
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return Point(lat, lng)


def _inside(point: Point, fence: dict) -> bool:
    kind = str(fence.get("type") or "circle")
    if kind == "circle":
        center = fence.get("center") or {}
        try:
            return haversine_m(point, Point(float(center["lat"]), float(center["lng"]))) <= float(fence.get("radius_m") or 0)
        except (KeyError, TypeError, ValueError):
            return False
    if kind == "polygon":
        try:
            polygon = [Point(float(p["lat"]), float(p["lng"])) for p in fence.get("coordinates") or []]
        except (KeyError, TypeError, ValueError):
            return False
        return point_in_polygon(point, polygon)
    return False


def _fence_ids(point: Point, fences: list[dict]) -> list[str]:
    return [str(f.get("id") or f.get("name") or "fence") for f in fences if _inside(point, f)]


def forecast_movements(trails: list[dict], fences: list[dict], expected_interval_seconds: int = 900) -> dict:
    """Forecast one local engine interval with explicit evidence and bounds."""
    interval = max(1, min(86_400, int(expected_interval_seconds or 900)))
    groups: dict[str, list[tuple[datetime, Point, dict]]] = defaultdict(list)
    for row in trails[-MAX_TRAIL_POINTS:]:
        if not isinstance(row, dict):
            continue
        device_id = str(row.get("device_id") or "")
        timestamp, point = _dt(row.get("ts")), _point(row)
        if device_id and timestamp and point:
            groups[device_id].append((timestamp, point, row))

    forecasts = []
    anomaly_count = 0
    crossing_count = 0
    for device_id, points in groups.items():
        points.sort(key=lambda item: item[0])
        if len(points) < 2:
            continue
        previous, latest = points[-2], points[-1]
        observed_seconds = (latest[0] - previous[0]).total_seconds()
        if observed_seconds <= 0:
            continue
        distance = haversine_m(previous[1], latest[1])
        speed_kmh = distance / observed_seconds * 3.6
        anomaly = speed_kmh > MAX_SPEED_KMH
        # Never amplify an implausible GPS jump into a confident forecast.
        scale = 0.0 if anomaly else min(4.0, interval / observed_seconds)
        projected = Point(
            max(-89.999999, min(89.999999, latest[1].lat + (latest[1].lat - previous[1].lat) * scale)),
            ((latest[1].lng + (latest[1].lng - previous[1].lng) * scale + 180) % 360) - 180,
        )
        current_fences = _fence_ids(latest[1], fences)
        projected_fences = _fence_ids(projected, fences)
        leaving = sorted(set(current_fences) - set(projected_fences))
        entering = sorted(set(projected_fences) - set(current_fences))
        crossing = bool(leaving or entering)
        anomaly_count += int(anomaly)
        crossing_count += int(crossing)
        confidence = 0 if anomaly else min(95, 45 + min(40, len(points) * 4))
        forecasts.append({
            "device_id": device_id,
            "forecast_seconds": interval,
            "projected": {"lat": round(projected.lat, 7), "lng": round(projected.lng, 7)},
            "speed_kmh": round(speed_kmh, 1),
            "crossing_risk": crossing,
            "leaving_fences": leaving,
            "entering_fences": entering,
            "anomaly": anomaly,
            "anomaly_reason": "gps_speed_implausible" if anomaly else None,
            "confidence_percent": confidence,
            "verified": not anomaly,
            "evidence": {
                "method": "two-point-linear-extrapolation",
                "observations": len(points),
                "window_start": previous[0].isoformat(),
                "window_end": latest[0].isoformat(),
                "observed_seconds": round(observed_seconds, 3),
                "distance_m": round(distance, 2),
            },
        })

    forecasts.sort(key=lambda row: (not row["crossing_risk"], not row["anomaly"], row["device_id"]))
    return {
        "status": "ready" if forecasts else "insufficient_data",
        "forecast_horizon_seconds": interval,
        "crossing_risk_count": crossing_count,
        "anomaly_count": anomaly_count,
        "devices_analyzed": len(forecasts),
        "forecasts": forecasts,
        "weekly_summary": {
            "observations_analyzed": sum(len(rows) for rows in groups.values()),
            "devices_with_forecast": len(forecasts),
            "potential_crossings": crossing_count,
            "gps_anomalies": anomaly_count,
        },
        "provenance": "local-trails",
        "limitations": "Short-horizon linear forecast; decisions require fresh UEM evidence and human review.",
    }
