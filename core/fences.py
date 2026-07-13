"""Geofence model + evaluation against device locations."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from core.geo import Point, haversine_m, point_in_polygon


@dataclass
class ActionSpec:
    """An action to run when a transition condition is met."""
    action: str  # lock | wipe | message | locate | reboot | clear_passcode | custom
    when: str = "on_enter"  # on_enter | on_exit | on_violation | on_unknown
    params: dict = field(default_factory=dict)
    enabled: bool = True


@dataclass
class Fence:
    id: str
    name: str
    type: str = "circle"  # circle | polygon
    center: Optional[Point] = None
    radius_m: float = 0.0
    coordinates: list = field(default_factory=list)  # list[Point] for polygon
    rules: dict = field(default_factory=dict)
    actions: list = field(default_factory=list)

    @staticmethod
    def from_raw(raw: dict) -> "Fence":
        c = raw.get("center")
        coords = [
            Point(lat=float(p["lat"]), lng=float(p["lng"]))
            for p in raw.get("coordinates", [])
        ]
        actions = [
            ActionSpec(
                action=a.get("action", "message"),
                when=a.get("when", "on_enter"),
                params=a.get("params", {}) or {},
                enabled=a.get("enabled", True),
            )
            for a in raw.get("actions", [])
        ]
        return Fence(
            id=raw["id"],
            name=raw["name"],
            type=raw.get("type", "circle"),
            center=Point(lat=float(c["lat"]), lng=float(c["lng"])) if c else None,
            radius_m=float(raw.get("radius_m", 0)),
            coordinates=coords,
            rules=raw.get("rules", {}) or {},
            actions=actions,
        )

    def contains(self, p: Point) -> bool:
        if self.type == "circle" and self.center is not None:
            return haversine_m(p, self.center) <= self.radius_m
        if self.type == "polygon" and self.coordinates:
            return point_in_polygon(p, self.coordinates)
        return False


def load_fences(path: str) -> list[Fence]:
    text = Path(path).read_text(encoding="utf-8")
    data = json.loads(text)
    raw_list = data.get("fences", data if isinstance(data, list) else [data])
    return [Fence.from_raw(r) for r in raw_list]


def save_fences(path: str | Path, fences: list[Fence]) -> None:
    """Atomically persist geofences in the canonical JSON shape."""
    rows = []
    for f in fences:
        row = {
            "id": f.id,
            "name": f.name,
            "type": f.type,
            "center": ({"lat": f.center.lat, "lng": f.center.lng} if f.center else None),
            "radius_m": f.radius_m,
            "coordinates": [{"lat": p.lat, "lng": p.lng} for p in f.coordinates],
            "rules": f.rules,
            "actions": [
                {"action": a.action, "when": a.when, "params": a.params, "enabled": a.enabled}
                for a in f.actions
            ],
        }
        rows.append(row)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps({"fences": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)


def fence_index(fences: list[Fence]) -> dict:
    return {f.id: f for f in fences}


def validate_fences(fences: list[Fence]) -> list[str]:
    """Return a list of human-readable problems (empty list == all good).

    Local-only sanity checks that catch the most common geofence config
    mistakes before they cause silent mis-evaluation:
      - duplicate ids
      - circle without center/radius
      - polygon with < 3 points or self-intersection
      - action `when` not in the supported set
      - unknown/invalid action names
    """
    problems: list[str] = []
    seen_ids: set[str] = set()
    valid_when = {"on_enter", "on_exit", "on_violation", "on_unknown"}
    valid_actions = {
        "lock", "wipe", "message", "locate", "reboot", "clear_passcode", "notify", "custom"
    }
    for f in fences:
        if f.id in seen_ids:
            problems.append(f"duplicate fence id: {f.id}")
        seen_ids.add(f.id)
        if f.type == "circle":
            if f.center is None:
                problems.append(f"{f.id}: circle fence missing center")
            if not f.radius_m or f.radius_m <= 0:
                problems.append(f"{f.id}: circle fence radius must be > 0")
        elif f.type == "polygon":
            if len(f.coordinates) < 3:
                problems.append(f"{f.id}: polygon needs >= 3 points (has {len(f.coordinates)})")
            elif _polygon_self_intersects(f.coordinates):
                problems.append(f"{f.id}: polygon is self-intersecting (invalid)")
        else:
            problems.append(f"{f.id}: unknown fence type {f.type!r}")
        for a in f.actions:
            if a.when not in valid_when:
                problems.append(f"{f.id}: action {a.action} has invalid 'when'={a.when!r}")
            if a.action not in valid_actions:
                problems.append(f"{f.id}: unknown action {a.action!r}")
    return problems


def _polygon_self_intersects(poly: list[Point]) -> bool:
    """Check segment intersection (ignoring consecutive/closed-edge touches)."""
    n = len(poly)
    if n < 4:
        return False

    def ccw(a: Point, b: Point, c: Point) -> float:
        return (b.lng - a.lng) * (c.lat - a.lat) - (b.lat - a.lat) * (c.lng - a.lng)

    def seg_intersect(p1, p2, p3, p4):
        d1 = ccw(p3, p4, p1)
        d2 = ccw(p3, p4, p2)
        d3 = ccw(p1, p2, p3)
        d4 = ccw(p1, p2, p4)
        if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
            return True
        return False

    # close the ring for the check
    pts = poly + [poly[0]]
    m = len(pts)
    for i in range(m - 1):
        for j in range(i + 1, m - 1):
            # skip edges that share a vertex
            if i == j or abs(i - j) == 1 or (i == 0 and j == m - 2):
                continue
            if seg_intersect(pts[i], pts[i + 1], pts[j], pts[j + 1]):
                return True
    return False
