"""Points of Interest (POI) service for geofencing context enrichment."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from core.geo import Point, haversine_m


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


class POIService:
    """Loads and queries POIs."""

    def __init__(self):
        self._pois: List[POI] = []
        self._index_built = False

    def load_from_json(self, path: str | Path) -> None:
        """Load POIs from a JSON file.
        Expected format: list of objects with id, name, lat, lng, category?, tags?, metadata?
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._pois = []
        for item in data:
            self._pois.append(
                POI(
                    id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    lat=float(item["lat"]),
                    lng=float(item["lng"]),
                    category=str(item.get("category", "")),
                    tags=list(item.get("tags", [])),
                    metadata=item.get("metadata", {}),
                )
            )
        self._index_built = False

    def load_from_csv(self, path: str | Path) -> None:
        """Load POIs from a CSV file.
        Expected columns: id, name, lat, lng, category, tags (pipe-separated), metadata (JSON string)
        """
        self._pois = []
        with open(path, "r", encoding="utf-8", newline="") as f:
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