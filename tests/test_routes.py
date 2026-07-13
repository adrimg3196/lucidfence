"""Unit tests for the route-adherence module (Task 1 of the hardening plan)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.geo import Point  # noqa: E402
from core.routes import Route, load_routes, route_for_device  # noqa: E402
from pathlib import Path  # noqa: E402


def test_distance_to_route_on_segment():
    r = Route(id="r1", name="R", waypoints=[Point(40.43, -3.69), Point(40.42, -3.71)],
              corridor_m=300.0, device_ids=["dev-002"])
    mid = Point((40.43 + 40.42) / 2, (-3.69 + -3.71) / 2)
    d = r.distance_to(mid)
    assert d < 50.0, f"expected near 0, got {d}"


def test_distance_to_route_off_corridor():
    r = Route(id="r1", name="R", waypoints=[Point(40.43, -3.69), Point(40.42, -3.71)],
              corridor_m=300.0, device_ids=["dev-002"])
    far = Point(40.50, -3.80)  # ~8 km away
    d = r.distance_to(far)
    assert d > 1000.0, f"expected >1km, got {d}"


def test_route_for_device_finds_assignment():
    r = Route(id="r1", name="R", waypoints=[Point(40.43, -3.69)], corridor_m=300.0,
              device_ids=["dev-002"])
    assert route_for_device([r], "dev-002") is r
    assert route_for_device([r], "dev-999") is None


def test_load_routes_roundtrip():
    import tempfile
    d = tempfile.mkdtemp()
    p = Path(d) / "routes.json"
    p.write_text('[{"id":"r1","name":"R","waypoints":[{"lat":40.43,"lng":-3.69}],'
                 '"corridor_m":300,"device_ids":["dev-002"]}]')
    rs = load_routes(p)
    assert len(rs) == 1 and rs[0].device_ids == ["dev-002"]
