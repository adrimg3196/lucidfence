"""End-to-end QA for the route module (Task 6 of the hardening plan).

Part A (HTTP): assumes `python3 saas_server.py` is running on 127.0.0.1:8765.
Verifies every route endpoint returns 200, the route_* fields are exposed on
devices, create/delete work for owner, and a viewer is blocked from writes.

Part B (engine, deterministic): drives the Engine directly for 45 cycles and
asserts dev-002 reaches off_route AND a route_exit event fires (no server, no
autostart race).

Run via the runner:  python3 tests/run_tests.py
Run directly:        python3 tests/test_qa_e2e.py
"""
import os
import sys
import http.client
import json
import time as _t
from pathlib import Path

import os as _os
H, P = "127.0.0.1", int(_os.environ.get("LUCIDFENCE_PORT", "8765"))
passed = 0
fails = []


def req(m, p, body=None, h=None):
    c = http.client.HTTPConnection(H, P, timeout=5)
    hh = dict(h or {})
    data = json.dumps(body).encode() if body is not None else None
    if data:
        hh["Content-Type"] = "application/json"
    c.request(m, p, body=data, headers=hh)
    r = c.getresponse()
    b = r.read().decode()
    try:
        return r.status, json.loads(b), r.getheader("Set-Cookie")
    except Exception:
        return r.status, b, r.getheader("Set-Cookie")


def check(cond, msg):
    global passed
    if cond:
        passed += 1
        print("  PASS", msg)
    else:
        fails.append(msg)
        print("  FAIL", msg)


def login(email, pw):
    _, _, ck = req("POST", "/api/auth/login", {"email": email, "password": pw})
    tok = None
    for p in (ck or "").split(","):
        if p.strip().startswith("gf_session="):
            tok = p.strip().split(";")[0].split("=", 1)[1]
    return {"Cookie": f"gf_session={tok}"}


def test_e2e():
    # ============ PART A: HTTP endpoints + RBAC ============
    print("== Part A: HTTP ==")
    h = login("ciso@acme.test", "demo1234")
    for ep in ["/api/routes", "/api/status", "/api/risk", "/api/devices"]:
        st, _, _ = req("GET", ep, h=h)
        check(st == 200, f"GET {ep} -> 200 (owner)")
    _, devs, _ = req("GET", "/api/devices", h=h)
    d2 = [d for d in devs if d.get("device_id") == "dev-002"]
    check(bool(d2) and "route_state" in d2[0], "device exposes route_state field (server /api/devices)")
    check(bool(d2) and "route_deviation_m" in d2[0], "device exposes route_deviation_m field (server /api/devices)")

    # create + delete (owner has route:write)
    _, nr, _ = req("POST", "/api/routes",
                  {"name": "QA Ruta", "waypoints": [{"lat": 40.42, "lng": -3.71},
                   {"lat": 40.43, "lng": -3.69}], "corridor_m": 150, "device_ids": []}, h=h)
    check(nr.get("ok") is True, "POST /api/routes creates route (owner)")
    rid = nr["routes"][-1]["id"]
    _, dl, _ = req("POST", f"/api/routes/{rid}/delete", {}, h=h)
    check(dl.get("ok") is True, "POST /api/routes/<id>/delete accepted (owner)")

    # viewer RBAC (unique email to avoid collision across runs).
    # Owner invites the viewer via the authenticated endpoint (public signup can
    # no longer self-join an existing org).
    vemail = f"viewer{int(_t.time())}@acme.test"
    _, inv, _ = req("POST", "/api/users",
                    {"email": vemail, "name": "V", "role": "viewer"}, h=h)
    check(inv.get("ok") is True, "owner can invite a viewer user")
    vh = login(vemail, inv["temp_password"])
    _, body, _ = req("POST", "/api/routes",
                     {"name": "X", "waypoints": [{"lat": 1, "lng": 1}], "corridor_m": 100}, h=vh)
    check(body.get("error") is not None, "viewer blocked from POST /api/routes (route:write)")

    # ============ PART B: engine determinism (hermetic, no shared state) ============
    # Drives the Engine against a temporary tenant + an isolated, deterministic
    # location source. This avoids the shared `data/` demo fleet, where a
    # fence-outside standing `notify` (fence_id=None) and the route_exit `notify`
    # collide on the same (device, action) dedupe bucket and silently suppress the
    # route_exit action. With no fences configured, the route_exit notify is the
    # only thing that can fire it, so the assertion is deterministic.
    print("== Part B: engine ==")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from helpers import make_temp_engine
    from core.engine import Engine
    from core.routes import Route
    from core.geo import Point
    from core.location_source import LocationReport

    eng = make_temp_engine()

    class _RouteExitSource:
        """dev-002 starts ON route, then goes ~3km OFF route on the 2nd cycle."""
        def __init__(self):
            self.on = True

        def fetch(self):
            if self.on:
                lat, lng = 40.4200, -3.7100   # on the route segment
            else:
                lat, lng = 40.3900, -3.7400   # ~3km off the route
            self.on = False
            return [LocationReport(
                device_id="dev-002", name="Comercial", platform="android",
                status="active", compliant=True, lat=lat, lng=lng,
            )]

    eng.fences = []  # isolate route_exit from any fence-state notify
    eng.source = _RouteExitSource()
    route = Route(
        id="route-centro", name="Ruta Comercial Centro",
        waypoints=[Point(40.4200, -3.7100), Point(40.4201, -3.7101)],
        corridor_m=300, device_ids=["dev-002"],
    )
    # The engine reads `route.actions` (if present) in _fire_route_exit,
    # falling back to a notify when absent. Set it explicitly so the
    # route_exit action path is exercised deterministically.
    route.actions = [{"action": "notify", "params": {
        "channel": "security", "msg": "Desviación de ruta"}}]
    eng.routes = [route]

    off_seen = False
    off_risk = None
    on_risk = None
    for _ in range(90):
        eng.run_once()
        d = [x for x in eng.store.snapshot().values() if x.device_id == "dev-002"]
        if not d:
            continue
        st = d[0].route_state
        # Capture risk in each state on first sighting. The source starts on_route
        # (cycle 0), then goes off_route (cycle 1+) — so on_risk is the
        # pre-transition baseline and off_risk the post-transition value.
        if st == "on_route" and on_risk is None:
            on_risk = d[0].risk_score
        elif st == "off_route":
            off_seen = True
            if off_risk is None:
                off_risk = d[0].risk_score
    check(off_seen, "dev-002 reaches off_route (engine, hermetic)")
    check(on_risk is not None and off_risk is not None, "captured risk in both states")
    if on_risk is not None and off_risk is not None:
        check(off_risk > on_risk, f"off_route raises risk ({off_risk} > {on_risk})")
    # route_exit event is logged on every on_route->off_route transition
    evs = [e for e in eng.store.recent_events(100000)
           if e.get("kind") == "route_exit" and e.get("device_id") == "dev-002"]
    check(len(evs) >= 1, f"route_exit event fired ({len(evs)})")
    if evs:
        check(evs[0].get("route_id") == "route-centro", "route_exit carries correct route_id")
    acts = [a for a in eng.store.recent_actions(100000)
            if a.get("trigger") == "route_exit" and a.get("device_id") == "dev-002"]
    check(len(acts) >= 1, f"route_exit action fired (notify) ({len(acts)})")

    print(f"\n=== e2e: {passed} passed, {len(fails)} failed ===")
    assert not fails, f"{len(fails)} route e2e checks failed: {fails}"


if __name__ == "__main__":
    try:
        test_e2e()
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(1)
    sys.exit(0)
