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
    h = login("ciso@acme.test", "[REDACTED]")
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
    print("== Part B: engine ==")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import config_loader
    from pathlib import Path
    from saas.tenant import TenantStore
    from core.engine import Engine

    ROOT = Path(".")
    ts = TenantStore(ROOT / "data")
    org = "org_c40aa88904"
    cfg = config_loader.load(ROOT / "config.json")
    cfg["mode"] = "simulation"  # deterministic even when local .env has a live token
    cfg["dry_run"] = True
    cfg["data_dir"] = str(ts.data_dir(org))
    cfg["sim_seed_path"] = str(ts.data_dir(org) / "fleet_seed.json")
    cfg["routes_path"] = str(ts.data_dir(org) / "routes.json")
    cfg["policies_path"] = str(ts.data_dir(org) / "policies.json")
    cfg["fences_path"] = str(ts.data_dir(org) / "fences.json")
    eng = Engine(cfg)
    off_seen = False
    off_risk = None
    on_risk = None
    prev_state = None
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
        elif st == "on_route" and off_risk is not None and on_risk is None:
            on_risk = d[0].risk_score
        prev_state = st
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
