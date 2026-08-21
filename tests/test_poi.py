"""Tests for the POI (Points of Interest) service."""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.poi import POI, POIService

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _service_with(pois: list[POI]) -> POIService:
    svc = POIService()
    for poi in pois:
        svc.add_poi(poi)
    return svc


def test_poi_load_from_flat_json() -> None:
    data = [
        {"id": "a", "name": "Alpha", "lat": 40.418, "lng": -3.705,
         "category": "office", "tags": ["hq"], "metadata": {"floor": 3}},
        {"id": "b", "name": "Beta", "lat": 40.42, "lng": -3.70},
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        path = f.name
    try:
        svc = POIService()
        svc.load_from_json(path)
        assert len(svc.all()) == 2
        alpha = svc.get_poi("a")
        assert alpha is not None and alpha.category == "office"
        assert alpha.tags == ["hq"] and alpha.metadata == {"floor": 3}
    finally:
        os.unlink(path)


def test_poi_load_from_geojson_feature_collection() -> None:
    # The bundled seed (data/pois.json) is GeoJSON: the loader must accept it.
    svc = POIService()
    svc.load_from_json(os.path.join(ROOT, "data", "pois.json"))
    pois = svc.all()
    assert len(pois) >= 1
    # GeoJSON coordinates are [lng, lat]; verify they were not swapped.
    first = svc.get_poi("poi_school_001")
    assert first is not None
    assert 35 < first.lat < 45 and -5 < first.lng < 0
    assert first.category == "school"


def test_poi_load_from_csv() -> None:
    csv_body = (
        "id,name,lat,lng,category,tags,metadata\n"
        'p1,Uno,40.0,-3.0,shop,food|open24h,"{""wifi"": true}"\n'
        "p2,Dos,41.0,-3.5,park,,\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write(csv_body)
        path = f.name
    try:
        svc = POIService()
        svc.load_from_csv(path)
        assert len(svc.all()) == 2
        p1 = svc.get_poi("p1")
        assert p1 is not None and p1.tags == ["food", "open24h"]
        assert p1.metadata == {"wifi": True}
    finally:
        os.unlink(path)


def test_poi_search_nearby_orders_by_distance_and_respects_radius() -> None:
    svc = _service_with([
        POI(id="near", name="Near", lat=40.4180, lng=-3.7050),
        POI(id="mid", name="Mid", lat=40.4200, lng=-3.7050),
        POI(id="far", name="Far", lat=41.0000, lng=-3.7050),
    ])
    results = svc.search_nearby(40.4180, -3.7050, radius_m=5000)
    ids = [poi.id for poi, _dist in results]
    assert ids == ["near", "mid"]  # "far" is ~65 km away, outside the radius
    assert results[0][1] < results[1][1]


def test_poi_search_nearby_limit_and_empty() -> None:
    assert POIService().search_nearby(0.0, 0.0, radius_m=100) == []
    svc = _service_with([
        POI(id=f"p{i}", name=f"P{i}", lat=40.418 + i * 0.0001, lng=-3.705)
        for i in range(10)
    ])
    results = svc.search_nearby(40.418, -3.705, radius_m=10_000, limit=3)
    assert len(results) == 3


def test_poi_get_unknown_returns_none() -> None:
    assert _service_with([POI(id="x", name="X", lat=0.0, lng=0.0)]).get_poi("nope") is None


def test_poi_to_dict_roundtrip() -> None:
    poi = POI(id="d", name="Dict", lat=1.5, lng=-2.5, category="cat",
              tags=["t"], metadata={"k": "v"})
    assert poi.to_dict() == {
        "id": "d", "name": "Dict", "lat": 1.5, "lng": -2.5,
        "category": "cat", "tags": ["t"], "metadata": {"k": "v"},
    }
