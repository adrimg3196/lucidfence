"""Public Python SDK for LucidFence.

The SDK is deliberately local-first: no network calls and no credential loading.
It exposes small, stable primitives over the production geospatial, simulation,
and reporting engines.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from core.geo import Point, haversine_m, point_in_polygon
from core.location_source import SimulationLocationSource
from core.product import build_product

__version__ = "1.3.1"


class GeoFencer:
    """Evaluate points against circle and polygon fences."""

    def __init__(self, fences: list[dict] | None = None):
        self.fences = list(fences or [])

    def add_circle(self, fence_id: str, lat: float, lng: float, radius_m: float, name: str = "") -> dict:
        if not fence_id or radius_m <= 0:
            raise ValueError("fence_id and a positive radius_m are required")
        fence = {"id": fence_id, "name": name or fence_id, "type": "circle",
                 "center": {"lat": float(lat), "lng": float(lng)}, "radius_m": float(radius_m)}
        self.fences.append(fence)
        return fence

    def add_polygon(self, fence_id: str, coordinates: list[dict], name: str = "") -> dict:
        if not fence_id or len(coordinates) < 3:
            raise ValueError("fence_id and at least three coordinates are required")
        points = [{"lat": float(p["lat"]), "lng": float(p["lng"])} for p in coordinates]
        fence = {"id": fence_id, "name": name or fence_id, "type": "polygon", "coordinates": points}
        self.fences.append(fence)
        return fence

    def evaluate(self, lat: float, lng: float) -> dict:
        point = Point(float(lat), float(lng))
        matches = []
        for fence in self.fences:
            if fence.get("type") == "circle":
                center = fence.get("center") or {}
                inside = haversine_m(point, Point(float(center["lat"]), float(center["lng"]))) <= float(fence["radius_m"])
            elif fence.get("type") == "polygon":
                polygon = [Point(float(p["lat"]), float(p["lng"])) for p in fence.get("coordinates") or []]
                inside = point_in_polygon(point, polygon)
            else:
                inside = False
            if inside:
                matches.append(str(fence.get("id") or fence.get("name") or "fence"))
        return {"inside": bool(matches), "fence_ids": matches, "point": {"lat": point.lat, "lng": point.lng}}


class Simulator:
    """Deterministic local fleet simulator backed by a seed JSON file."""

    def __init__(self, seed_path: str | Path, org_id: str = "sdk"):
        self.source = SimulationLocationSource(str(seed_path), org_id=org_id)

    def tick(self) -> list[dict[str, Any]]:
        return [asdict(report) for report in self.source.fetch()]


class Reporter:
    """Build the same explainable product bundle consumed by the dashboard."""

    @staticmethod
    def from_status(status: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(status, dict):
            raise TypeError("status must be a dict")
        return build_product(status)


__all__ = ["GeoFencer", "Simulator", "Reporter", "__version__"]
