"""Points of Interest (POI) service for geofencing context enrichment."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lucidfence.core.geo import Point, haversine_m


def _safe_seed_path(path: str | Path) -> Path:
    """Defang path traversal on POI seed files.

    Seeds should be internal/trusted files (bundled data/ seeds, tests),
    which arrive as absolute paths and pass through unchanged (normalized).
    Relative paths are resolved beneath the current working directory while
    preserving safe subdirectories. Paths that escape that trusted base are
    rejected."""
    p = Path(str(path))
    if p.is_absolute():
        return p.resolve()
    base = Path.cwd().resolve()
    resolved = (base / p).resolve()
    if not resolved.is_relative_to(base):
        raise ValueError("relative POI seed path escapes the working directory")
    return resolved


@dataclass
class POI:
    """A Point of Interest."""
    id: str
    name: str
    lat: float
    lng: float
    category: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def distance_to(self, lat: float, lng: float) -> float:
        """Haversine distance in meters to given coordinates."""
        return haversine_m(Point(self.lat, self.lng), Point(lat, lng))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "lat": self.lat, "lng": self.lng,
            "category": self.category, "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }


def _poi_from_flat(item: Dict[str, Any]) -> POI:
    return POI(
        id=str(item.get("id", "")),
        name=str(item.get("name", "")),
        lat=float(item["lat"]),
        lng=float(item["lng"]),
        category=str(item.get("category", "")),
        tags=list(item.get("tags", [])),
        metadata=item.get("metadata", {}) or {},
    )


def _poi_from_geojson_feature(feature: Dict[str, Any]) -> Optional[POI]:
    geometry = feature.get("geometry") or {}
    if geometry.get("type") != "Point":
        return None
    coords = geometry.get("coordinates") or []
    if len(coords) < 2:
        return None
    props = feature.get("properties") or {}
    # GeoJSON coordinates are [lng, lat]
    return POI(
        id=str(props.get("id", "")),
        name=str(props.get("name", "")),
        lat=float(coords[1]),
        lng=float(coords[0]),
        category=str(props.get("category", "")),
        tags=list(props.get("tags", [])),
        metadata=props.get("metadata", {}) or {},
    )


class POIService:
    """Loads and queries POIs."""

    def __init__(self):
        self._pois: List[POI] = []
        self._index_built = False

    def load_from_json(self, path: str | Path) -> None:
        """Load POIs from a JSON file.

        Accepts either a flat list of objects (id, name, lat, lng, category?,
        tags?, metadata?) or a GeoJSON FeatureCollection of Point features
        with those keys under `properties`.
        """
        with open(_safe_seed_path(path), "r", encoding="utf-8") as f:
            data = json.load(f)
        pois: List[POI] = []
        if isinstance(data, dict) and data.get("type") == "FeatureCollection":
            for feature in data.get("features", []):
                poi = _poi_from_geojson_feature(feature)
                if poi is not None:
                    pois.append(poi)
        elif isinstance(data, list):
            pois = [_poi_from_flat(item) for item in data]
        else:
            raise ValueError(f"formato POI no soportado en {path}")
        self._pois = pois
        self._index_built = False

    def load_from_csv(self, path: str | Path) -> None:
        """Load POIs from a CSV file.

        Expected columns: id, name, lat, lng, category, tags (pipe-separated),
        metadata (JSON string).
        """
        self._pois = []
        with open(_safe_seed_path(path), "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tags = []
                if row.get("tags"):
                    tags = [t.strip() for t in row["tags"].split("|") if t.strip()]
                metadata = {}
                if row.get("metadata"):
                    try:
                        metadata = json.loads(row["metadata"])
                    except json.JSONDecodeError:
                        metadata = {"raw": row["metadata"]}
                self._pois.append(
                    POI(
                        id=row.get("id", ""),
                        name=row.get("name", ""),
                        lat=float(row["lat"]),
                        lng=float(row["lng"]),
                        category=row.get("category", ""),
                        tags=tags,
                        metadata=metadata,
                    )
                )
        self._index_built = False

    def add_poi(self, poi: POI) -> None:
        """Add a single POI."""
        self._pois.append(poi)
        self._index_built = False

    def _build_index(self) -> None:
        """Build a simple index for faster lookups."""
        # For small datasets, linear scan is fine. We sort for deterministic order.
        self._pois.sort(key=lambda p: (p.lat, p.lng))
        self._index_built = True

    def search_nearby(
        self, lat: float, lng: float, radius_m: float, limit: int = 5
    ) -> List[Tuple[POI, float]]:
        """Return up to `limit` POIs within `radius_m` meters, sorted by distance."""
        if not self._pois:
            return []
        if not self._index_built:
            self._build_index()

        results: List[Tuple[POI, float]] = []
        for poi in self._pois:
            dist = poi.distance_to(lat, lng)
            if dist <= radius_m:
                results.append((poi, dist))
        results.sort(key=lambda x: x[1])
        return results[:limit]

    def get_poi(self, poi_id: str) -> Optional[POI]:
        """Find a POI by ID."""
        for poi in self._pois:
            if poi.id == poi_id:
                return poi
        return None

    def all(self) -> List[POI]:
        """Return a copy of all POIs."""
        return list(self._pois)
