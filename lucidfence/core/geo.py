"""Geospatial helpers: distance, point-in-polygon, segment distance."""
from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_M = 6_371_000.0


@dataclass
class Point:
    lat: float
    lng: float


def valid_coord(value, lo: float, hi: float, label: str) -> float:
    """Parse a coordinate, rejecting NaN/inf and out-of-range values.

    Geofences and route corridors are security controls: a NaN/9999 latitude
    must fail loudly here, never slip into haversine/point-in-polygon as
    undefined behaviour and silently mis-evaluate a watched zone.
    """
    f = float(value)
    if not math.isfinite(f) or not (lo <= f <= hi):
        raise ValueError(f"{label} fuera de rango o no finito: {value!r}")
    return f


def point_from(raw: dict) -> "Point":
    """Build a Point from a {lat, lng} dict with range/NaN validation."""
    return Point(
        lat=valid_coord(raw["lat"], -90.0, 90.0, "lat"),
        lng=valid_coord(raw["lng"], -180.0, 180.0, "lng"),
    )


def haversine_m(a: Point, b: Point) -> float:
    """Great-circle distance in meters between two points."""
    d_lat = math.radians(b.lat - a.lat)
    d_lng = math.radians(b.lng - a.lng)
    x = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(a.lat))
        * math.cos(math.radians(b.lat))
        * math.sin(d_lng / 2) ** 2
    )
    return EARTH_RADIUS_M * 2 * math.asin(min(1.0, math.sqrt(x)))


def _unwrap_lng(lng: float, ref: float) -> float:
    """Longitude equivalent to ``lng`` within 180° of ``ref``.

    Lets planar tests treat a shape straddling the antimeridian (lng 178 ->
    -178) as the 4°-wide shape it is, not as a 356°-wide band.
    """
    return ref + ((lng - ref + 180.0) % 360.0) - 180.0


def point_in_polygon(p: Point, polygon: list[Point]) -> bool:
    """Ray-casting point-in-polygon test (antimeridian-safe for polygons
    narrower than 180° of longitude, i.e. every real fence)."""
    if len(polygon) < 3:
        return False
    inside = False
    n = len(polygon)
    j = n - 1
    ref = polygon[0].lng
    xs = [_unwrap_lng(vp.lng, ref) for vp in polygon]
    ys = [vp.lat for vp in polygon]
    lat, lng = p.lat, _unwrap_lng(p.lng, ref)
    for i in range(n):
        # The parity guard already implies ys[j] != ys[i]: no epsilon needed
        # (an epsilon can zero the denominator or flip its sign for tiny dy).
        if ((ys[i] > lat) != (ys[j] > lat)) and (
            lng < (xs[j] - xs[i]) * (lat - ys[i]) / (ys[j] - ys[i]) + xs[i]
        ):
            inside = not inside
        j = i
    return inside


def _bearing_rad(a: Point, b: Point) -> float:
    """Initial great-circle bearing from a to b, in radians."""
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    d_lng = math.radians(b.lng - a.lng)
    y = math.sin(d_lng) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lng)
    return math.atan2(y, x)


def distance_to_segment_m(p: Point, a: Point, b: Point) -> float:
    """Minimum great-circle distance (meters) from point p to segment a-b.

    Exact spherical cross-track / along-track formulas, so the result holds
    for long segments, high latitudes and segments crossing the antimeridian
    (the previous local equirectangular frame was off by hundreds of meters
    there, comparable to a route corridor). Clamps to the nearest endpoint
    when the perpendicular foot falls outside the segment.
    """
    if a.lat == b.lat and a.lng == b.lng:
        return haversine_m(p, a)
    d_ap = haversine_m(a, p) / EARTH_RADIUS_M  # angular distance a -> p
    if d_ap == 0.0:
        return 0.0
    delta = _bearing_rad(a, p) - _bearing_rad(a, b)
    if math.cos(delta) < 0.0:  # foot of the perpendicular lies before a
        return haversine_m(p, a)
    xt = math.asin(max(-1.0, min(1.0, math.sin(d_ap) * math.sin(delta))))  # cross-track
    cos_xt = math.cos(xt)
    at = math.acos(max(-1.0, min(1.0, math.cos(d_ap) / cos_xt))) if cos_xt else 0.0  # along-track
    if at > haversine_m(a, b) / EARTH_RADIUS_M:  # ... or beyond b
        return haversine_m(p, b)
    return abs(xt) * EARTH_RADIUS_M
