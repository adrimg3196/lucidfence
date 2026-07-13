"""Geospatial helpers: distance, point-in-polygon, movement simulation."""
from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_M = 6_371_000.0


@dataclass
class Point:
    lat: float
    lng: float

    def as_tuple(self):
        return (self.lat, self.lng)


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


def destination_point(start: Point, bearing_deg: float, distance_m: float) -> Point:
    """Return the point reached by travelling `distance_m` from `start` along `bearing_deg`."""
    brng = math.radians(bearing_deg)
    dr = distance_m / EARTH_RADIUS_M
    lat1 = math.radians(start.lat)
    lng1 = math.radians(start.lng)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(dr) + math.cos(lat1) * math.sin(dr) * math.cos(brng)
    )
    lng2 = lng1 + math.atan2(
        math.sin(brng) * math.sin(dr) * math.cos(lat1),
        math.cos(dr) - math.sin(lat1) * math.sin(lat2),
    )
    return Point(lat=math.degrees(lat2), lng=math.degrees(lng2))


def point_in_polygon(p: Point, polygon: list[Point]) -> bool:
    """Ray-casting point-in-polygon test."""
    if len(polygon) < 3:
        return False
    inside = False
    n = len(polygon)
    j = n - 1
    xs = [vp.lng for vp in polygon]
    ys = [vp.lat for vp in polygon]
    lat, lng = p.lat, p.lng
    for i in range(n):
        if ((ys[i] > lat) != (ys[j] > lat)) and (
            lng
            < (xs[j] - xs[i]) * (lat - ys[i]) / (ys[j] - ys[i] + 1e-12) + xs[i]
        ):
            inside = not inside
        j = i
    return inside


def clamp_latlng(lat: float, lng: float):
    lat = max(-89.999999, min(89.999999, lat))
    if lng > 180.0:
        lng -= 360.0
    elif lng < -180.0:
        lng += 360.0
    return lat, lng


def distance_to_segment_m(p: Point, a: Point, b: Point) -> float:
    """Minimum great-circle distance (meters) from point p to segment a-b.

    Projects p onto the great-circle segment in a local equirectangular
    approximation (valid for short segments / city scale) and clamps to the
    endpoints, so the result is the true distance to the nearest point on the
    segment, not just to its vertices.
    """
    if a.lat == b.lat and a.lng == b.lng:
        return haversine_m(p, a)
    # local meters frame anchored at a
    mx = (p.lng - a.lng) * 111_320 * math.cos(math.radians(a.lat))
    my = (p.lat - a.lat) * 111_320
    bx = (b.lng - a.lng) * 111_320 * math.cos(math.radians(a.lat))
    by = (b.lat - a.lat) * 111_320
    # project p onto segment
    dot = mx * bx + my * by
    len2 = bx * bx + by * by
    t = max(0.0, min(1.0, dot / len2)) if len2 else 0.0
    proj_x = bx * t
    proj_y = by * t
    dx = mx - proj_x
    dy = my - proj_y
    return math.hypot(dx, dy)
