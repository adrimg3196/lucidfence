"""Route adherence module — the commercial-route deviation detector.

Why this belongs in the product: a field/commercial device is expected to follow
a planned route (a polyline with a tolerance corridor). If it leaves the corridor
— detour, unauthorized stop, or wandering off the assigned path — that is a
signal of its own, distinct from a geofence exit. A UEM does not model "is this
truck on its delivery route?"; we do. This is another composite signal feeding
the Geospatial Risk & Policy Engine, and it is demonstrable today with the
simulated fleet.

Route model:
  - id, name
  - waypoints: list[{"lat","lng"}]  (ordered polyline)
  - corridor_m: tolerance width (device beyond this from ANY segment = off_route)
  - device_ids: which devices are assigned to this route (empty = all)
  - schedule: optional {"start":"HH:MM","end":"HH:MM"} (ignored if absent)
  - color: UI hint
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from core.geo import Point, distance_to_segment_m, haversine_m


@dataclass
class Route:
    id: str
    name: str
    waypoints: list[Point]
    corridor_m: float = 200.0
    device_ids: list[str] = field(default_factory=list)
    schedule: Optional[dict] = None
    color: str = "#3b82f6"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "waypoints": [{"lat": w.lat, "lng": w.lng} for w in self.waypoints],
            "corridor_m": self.corridor_m,
            "device_ids": list(self.device_ids),
            "schedule": self.schedule,
            "color": self.color,
        }

    def distance_to(self, p: Point) -> float:
        """Minimum distance (m) from point p to the route polyline."""
        if not self.waypoints:
            return float("inf")
        best = haversine_m(p, self.waypoints[0])
        for i in range(len(self.waypoints) - 1):
            d = distance_to_segment_m(p, self.waypoints[i], self.waypoints[i + 1])
            if d < best:
                best = d
        # also consider last vertex (covered by loop when >1 segment)
        return best

    def is_on_route(self, p: Point) -> bool:
        if not self.waypoints:
            return True
        return self.distance_to(p) <= self.corridor_m


def load_routes(path: Path) -> list[Route]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return []
    out: list[Route] = []
    for r in raw:
        wps = [Point(lat=float(w["lat"]), lng=float(w["lng"])) for w in r.get("waypoints", [])]
        if not wps:
            # Skip routes with no waypoints: an empty polyline would make
            # distance_to() return inf (every device "off_route") while
            # is_on_route() returns True — inconsistent. add_route already
            # blocks this, but a hand-edited routes.json could sneak it in.
            continue
        out.append(Route(
            id=r.get("id", "route"),
            name=r.get("name", "Route"),
            waypoints=wps,
            corridor_m=float(r.get("corridor_m", 200.0)),
            device_ids=list(r.get("device_ids", [])),
            schedule=r.get("schedule"),
            color=r.get("color", "#3b82f6"),
        ))
    return out


def save_routes(path: Path, routes: list[Route]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([r.to_dict() for r in routes], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def route_for_device(routes: list[Route], device_id: str) -> Optional[Route]:
    """Pick the first route this device is explicitly assigned to.

    If no route lists this device, returns the first route with an empty
    device_ids list (meaning 'applies to all'), else None.
    """
    assigned = [r for r in routes if device_id in r.device_ids]
    if assigned:
        return assigned[0]
    generic = [r for r in routes if not r.device_ids]
    return generic[0] if generic else None
