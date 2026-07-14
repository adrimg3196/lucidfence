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

H, P = "127.0.0.1", 8765
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

    # ============ PART B: engine determinism (no server race) ============
    # Hermetic: build an isolated Engine in a tempdir (like the rest of the
    # engine integration tests) so the live data/ tenant dir shared with the
    # auto-started saas_server.py cannot pollute this engine's simulation
    # state. We then inject a DETERMINISTIC location source: dev-002 starts
    # on-route (cycle 0, prev=None -> no transition) and goes off-route on
    # every subsequent cycle, guaranteeing the on_route->off_route transition
    # (and therefore the route_exit event + fallback notify action) fires
    # exactly once, regardless of run order in the full suite.
    print("== Part B: engine ==")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from helpers import make_temp_engine
    from core.location_source import LocationReport
    from core.routes import Point, Route, load_routes, save_routes

    eng = make_temp_engine(cooldown_seconds=0)

    # Load the REAL product route fixture so route_exit carries route-centro.
    repo_routes = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data" / "routes.json"
    seed_routes = load_routes(repo_routes) if repo_routes.exists() else []
    if not any(r.id == "route-centro" for r in seed_routes):
        seed_routes.append(Route(
            id="route-centro", name="Ruta Comercial Centro", corridor_m=300,
            device_ids=["dev-002"], color="#22c55e",
            waypoints=[Point(40.4300, -3.6900), Point(40.4200, -3.7100)],
        ))
    eng.routes = seed_routes
    eng.fence_by_id = {f.id: f for f in eng.fences}  # no fences; pure route test

    on_pt = Point(40.4250, -3.7000)   # midpoint of the route segment
    off_pt = Point(40.3900, -3.7400)  # ~3.5km off the route

    class _DeterministicRouteSource:
        def __init__(self):
            self.i = 0
        def fetch(self):
            if self.i == 0:
                loc = on_pt
            else:
                loc = off_pt
            self.i += 1
            return [LocationReport(
                device_id="dev-002", name="Movil Reparto B7", platform="android",
                status="active", compliant=True, lat=loc.lat, lng=loc.lng,
            )]

    eng.source = _DeterministicRouteSource()
    off_seen = False
    off_risk = None
    on_risk = None
    for _ in range(90):
        eng.run_once()
        d = [x for x in eng.store.snapshot().values() if x.device_id == "dev-002"]
        if not d:
            continue
        st = d[0].route_state
        if st == "off_route":
            off_seen = True
            if off_risk is None:
                off_risk = d[0].risk_score
        elif st == "on_route":
            # Captured at cycle 0 (dev-002 starts on-route). Recorded the first
            # time we see it so we can compare on_route vs off_route risk.
            if on_risk is None:
                on_risk = d[0].risk_score
    check(off_seen, "dev-002 reaches off_route (engine, 90 cycles)")
    check(off_risk is not None and on_risk is not None, "captured risk in both states")
    if off_risk is not None and on_risk is not None:
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
