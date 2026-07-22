from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lucidfence import GeoFencer, Reporter, Simulator, __version__


def test_sdk_geofencer_circle_and_polygon():
    sdk = GeoFencer()
    sdk.add_circle("hq", 40.0, -3.0, 100)
    sdk.add_polygon("yard", [
        {"lat": 39.9, "lng": -3.1}, {"lat": 39.9, "lng": -2.9},
        {"lat": 40.1, "lng": -2.9}, {"lat": 40.1, "lng": -3.1},
    ])
    result = sdk.evaluate(40.0, -3.0)
    assert result["inside"] is True
    assert result["fence_ids"] == ["hq", "yard"]


def test_sdk_simulator_and_reporter_are_local_and_useful():
    with tempfile.TemporaryDirectory() as td:
        seed = Path(td) / "seed.json"
        seed.write_text(json.dumps({"devices": [{"id": "d1", "name": "Phone", "waypoints": [{"lat": 40.0, "lng": -3.0}]}]}))
        rows = Simulator(seed).tick()
    assert rows[0]["device_id"] == "d1"
    report = Reporter.from_status({"devices": rows, "fences": [], "stats": {}, "recent_events": [], "recent_actions": []})
    assert report["summary"]["fleet_size"] == 1
    assert __version__ == "1.3.1"


def test_python_package_metadata_exists():
    root = Path(__file__).resolve().parents[1]
    text = (root / "pyproject.toml").read_text()
    assert 'name = "lucidfence-local"' in text
    assert 'requires-python = ">=3.11"' in text
