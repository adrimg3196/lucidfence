"""Engine route-state + action-dedup integration tests (hardening plan)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config_loader  # noqa: E402
from saas.tenant import TenantStore  # noqa: E402
from core.engine import Engine  # noqa: E402

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _org_id():
    ts = TenantStore(ROOT / "data")
    return ts.all()[0].id


def _engine():
    org_id = _org_id()
    ts = TenantStore(ROOT / "data")
    tdir = ts.data_dir(org_id)
    cfg = config_loader.load(ROOT / "config.json")
    cfg["data_dir"] = str(tdir)
    return Engine(cfg)


def test_engine_assigns_route_state():
    eng = _engine()
    eng.run_once()
    states = list(eng.store.snapshot().values())
    d2 = [d for d in states if d.device_id == "dev-002"]
    assert d2, "dev-002 missing"
    assert d2[0].route_state in ("on_route", "off_route", "unassigned"), d2[0].route_state
    assert d2[0].route_deviation_m is None or d2[0].route_deviation_m >= 0


def test_add_and_delete_route():
    eng = _engine()
    n0 = len(eng.routes)
    eng.add_route({"name": "T", "waypoints": [{"lat": 40.42, "lng": -3.71}],
                   "corridor_m": 200, "device_ids": []})
    assert len(eng.routes) == n0 + 1
    rid = eng.routes[-1].id
    eng.delete_route(rid)
    assert len(eng.routes) == n0


class _GpslessSource:
    """Stub location source: one device that never reports GPS."""
    def fetch(self):
        from core.location_source import LocationReport
        return [LocationReport(device_id="dev-gpsless", name="No GPS",
                                platform="android", status="active",
                                compliant=True, lat=None, lng=None)]


def test_gpsless_device_does_not_crash():
    """Regression for reviewer CRITICAL: a device with lat/lng None must be
    marked 'unassigned' without raising (no NameError in run_once)."""
    eng = _engine()
    eng.source = _GpslessSource()
    eng.routes = []  # isolate from demo routes
    eng.run_once()  # must not raise
    d = eng.store.get("dev-gpsless")
    assert d is not None, "gps-less device not stored"
    assert d.route_state == "unassigned", d.route_state
    assert d.route_deviation_m is None


class _RouteOnlySource:
    """Stub: one device on a 2-point path, both positions 'outside' any fence
    (no fences configured) — used to prove route_exit fires on a pure route
    transition without any fence-state change."""
    def __init__(self):
        self.on = True
    def fetch(self):
        from core.location_source import LocationReport
        # on-route point vs far-off-route point; both are 'outside' (no fences)
        if self.on:
            lat, lng = 40.4200, -3.7100   # on the route segment
        else:
            lat, lng = 40.3900, -3.7400   # ~3km off the route
        self.on = False
        return [LocationReport(device_id="dev-route", name="Route only",
                                platform="android", status="active",
                                compliant=True, lat=lat, lng=lng)]


def test_route_exit_fires_without_fence_change():
    """Regression for reviewer IMPORTANT #1: route_exit must fire on the
    on_route->off_route transition even when fence_state does NOT change."""
    eng = _engine()
    eng.source = _RouteOnlySource()
    eng.routes = [__import__("core.routes", fromlist=["Route"]).Route(
        id="rt1", name="R", waypoints=[
            __import__("core.geo", fromlist=["Point"]).Point(40.4200, -3.7100),
            __import__("core.geo", fromlist=["Point"]).Point(40.4201, -3.7101),
        ], corridor_m=300, device_ids=["dev-route"])]
    eng.fences = []  # guarantee no fence-state change
    eng.run_once()  # first cycle: on_route (prev None -> no transition)
    on_risk = eng.store.get("dev-route").risk_score
    eng.run_once()  # second cycle: off_route -> route_exit must fire
    off_risk = eng.store.get("dev-route").risk_score
    assert off_risk > on_risk, (on_risk, off_risk)
    evs = [e for e in eng.store.recent_events(50)
           if e.get("kind") == "route_exit" and e.get("device_id") == "dev-route"]
    assert evs, "route_exit did not fire on pure route transition"
    acts = [a for a in eng.store.recent_actions(50)
            if a.get("trigger") == "route_exit" and a.get("device_id") == "dev-route"]
    assert acts, "route_exit action did not fire"


def _always_policies(n=1):
    from core.policies import Policy
    out = []
    for i in range(n):
        out.append(Policy(
            id=f"p{i+1}", name=f"P{i+1}", description=f"dedup {i+1}",
            when=[{"field": "risk_score", "op": "gte", "value": 0}],
            actions=[{"action": "notify", "params": {"msg": f"m{i+1}"}}]))
    return out


def test_standing_action_not_double_fired_per_cycle():
    """P0.2: a single standing condition fires each (device, action) once per
    cycle, not once per matching policy."""
    eng = _engine()
    eng.source = _GpslessSource()
    eng.routes = []
    eng.policies = _always_policies(2)
    eng.run_once()
    fired = [a for a in eng._cycle_actions
             if a.get("device_id") == "dev-gpsless" and a.get("action") == "notify"]
    assert len(fired) == 1, fired


def test_repeated_policy_on_same_fence_is_deduped():
    """P0.2: two policies firing the same (device, action) in the SAME bucket
    collapse to one execution per cycle (no repeated lock/wipe). Both standalone
    policies resolve to fence_id=None, so they share one bucket and dedupe."""
    eng = _engine()
    eng.routes = []
    eng.fences = []
    eng.source = _GpslessSource()
    eng.policies = _always_policies(2)
    eng.run_once()
    fired = [a for a in eng._cycle_actions
             if a.get("device_id") == "dev-gpsless" and a.get("action") == "notify"]
    assert len(fired) == 1, fired
