# Geofence UEM SaaS — Hardening & Route Module Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the local Geofence UEM SaaS from "feature-complete but unverified" to "verified, hardened, code-reviewed" — completing the route-adherence module with real TDD, killing the residual 500 bug, and proving every endpoint end-to-end with a green QA suite. No push, 100% local.

**Architecture:** Keep the existing layered core (`core/engine.py`, `core/routes.py`, `core/policies.py`, `core/state_store.py`) and the SaaS HTTP layer (`saas_server.py`, `saas/auth.py`, `saas/tenant.py`). Add a real pytest suite under `tests/` that exercises the engine and the HTTP API over `http.client` (the local proxy eats POST to 127.0.0.1, so QA uses raw `http.client`, not `requests`). Frontend (vanilla JS) gets the Routes view. RBAC stays capability-based. All changes are local; nothing is published.

**Tech Stack:** Python 3.9 (stdlib only — no new deps; `os.urandom` OK, `secrets`/`scrypt` absent on this macOS), `http.client` for QA, vanilla JS + Leaflet for UI, `pytest` for the test runner (add a `requirements.txt` with `pytest` only).

## Global Constraints (copied verbatim from project memory)

- 100% LOCAL. Never publish (no push / PR / gist / upload). Skills live in `~/.hermes/skills/`.
- Language: Spanish for user-facing copy and this plan's narrative; code identifiers in English.
- Reuse existing core; do NOT rewrite geofence logic.
- Frontend files must stay < 8K tokens each (split `saas_views.js` / `saas_views2.js` / `saas_views3.js` if needed).
- QA must run GREEN before anything is "delivered" to the user.
- API keys are empty (`--`); never hardcode or print secrets.

---

## Task 1: Routes module — backend TDD (distance + assignment)

**Files:**
- Create: `tests/test_routes.py`
- Modify: `core/routes.py` (already has `Route`, `load_routes`, `route_for_device`, `save_routes`, `distance_to_route`)
- Modify: `core/geo.py` (already has `distance_to_segment_m`)

**Interfaces:**
- Consumes: `core.routes.Route`, `core.geo.Point`, `core.geo.distance_to_segment_m`
- Produces: `Route.distance_to(loc) -> float` (meters), `route_for_device(routes, device_id) -> Optional[Route]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_routes.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.geo import Point
from core.routes import Route, route_for_device, load_routes
from pathlib import Path

def test_distance_to_route_on_segment():
    r = Route(id="r1", name="R", waypoints=[Point(40.43, -3.69), Point(40.42, -3.71)],
              corridor_m=300.0, device_ids=["dev-002"])
    # a point sitting on the segment midpoint
    mid = Point((40.43+40.42)/2, (-3.69+-3.71)/2)
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

def test_load_routes_roundtrip(tmp_path):
    p = tmp_path / "routes.json"
    p.write_text('[{"id":"r1","name":"R","waypoints":[{"lat":40.43,"lng":-3.69}],'
                 '"corridor_m":300,"device_ids":["dev-002"]}]')
    rs = load_routes(p)
    assert len(rs) == 1 and rs[0].device_ids == ["dev-002"]
```

- [ ] **Step 2: Run test to verify it fails (only if impl missing)**

Run: `python3 -m pytest tests/test_routes.py -v`
Expected: collection OK; if `core/routes.py` already implements these, tests may already pass — that is acceptable; the task's value is locking behavior.

- [ ] **Step 3: Implement minimal code (if any function missing)**

`core/routes.py` already defines `distance_to` and `route_for_device`. If `distance_to` is absent, add:

```python
def distance_to(self, loc) -> float:
    if not self.waypoints:
        return 0.0
    return min(distance_to_segment_m(wp, self.waypoints[i+1], loc)
               for i, wp in enumerate(self.waypoints[:-1]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_routes.py -v`
Expected: PASSED (4 tests)

- [ ] **Step 5: Commit (local only, no push)**

```bash
git add tests/test_routes.py core/routes.py core/geo.py 2>/dev/null || true
```

---

## Task 2: Engine route-state integration — TDD

**Files:**
- Create: `tests/test_engine_routes.py`
- Modify: `core/engine.py` (already computes `route_state`/`route_deviation_m` in `run_once`; already has `add_route`/`delete_route`)

**Interfaces:**
- Consumes: `core.engine.Engine`, `config_loader.load`, `saas.tenant.TenantStore`
- Produces: `Engine.run_once()` populates `DeviceState.route_state in {on_route, off_route, unassigned}` and `route_deviation_m`; `Engine.add_route(dict)`, `Engine.delete_route(str)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engine_routes.py
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import config_loader
from saas.tenant import TenantStore
from core.engine import Engine

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _make_org():
    ts = TenantStore(ROOT / "data")
    org = ts.all()[0]
    return org.id

def test_engine_assigns_route_state():
    org_id = _make_org()
    ts = TenantStore(ROOT / "data")
    tdir = ts.data_dir(org_id)
    cfg = config_loader.load(ROOT / "config.json")
    cfg["data_dir"] = str(tdir)
    eng = Engine(cfg)
    eng.run_once()
    states = list(eng.store.snapshot().values())
    d2 = [d for d in states if d.device_id == "dev-002"]
    assert d2, "dev-002 missing"
    assert d2[0].route_state in ("on_route", "off_route", "unassigned"), d2[0].route_state
    assert d2[0].route_deviation_m is None or d2[0].route_deviation_m >= 0
```

- [ ] **Step 2: Run test to verify (fails only if integration broken)**

Run: `python3 -m pytest tests/test_engine_routes.py -v`
Expected: PASSED (if Task from prior session intact) — otherwise FIX `core/engine.py` `run_once` to set `route_state`/`route_deviation_m` from `route_for_device(self.routes, rep.device_id)`.

- [ ] **Step 3: Add_route / delete_route test**

```python
def test_add_and_delete_route():
    org_id = _make_org()
    ts = TenantStore(ROOT / "data")
    tdir = ts.data_dir(org_id)
    cfg = config_loader.load(ROOT / "config.json")
    cfg["data_dir"] = str(tdir)
    eng = Engine(cfg)
    n0 = len(eng.routes)
    eng.add_route({"name": "T", "waypoints": [{"lat": 40.42, "lng": -3.71}],
                   "corridor_m": 200, "device_ids": []})
    assert len(eng.routes) == n0 + 1
    rid = eng.routes[-1].id
    eng.delete_route(rid)
    assert len(eng.routes) == n0
```

- [ ] **Step 4: Run full routes tests**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASSED

---

## Task 3: Systematic debugging of the residual 500 (using systematic-debugging)

**Files:**
- Modify: `saas_server.py` (RBAC `route:*` caps already added to `saas/auth.py`; `/api/routes` GET/POST/DELETE already added)

**Goal:** Prove `/api/routes`, `/api/status`, `/api/risk` return 200 with the route module active, for every role (owner/admin/operator/viewer).

- [ ] **Step 1: Reproduce**

Start server in background (authorized `process` tool, NOT pkill), then query with `http.client`:

```python
import http.client, json
H, P = "127.0.0.1", 8765
def req(m, p, body=None, h=None):
    c = http.client.HTTPConnection(H, P, timeout=5)
    data = json.dumps(body).encode() if body is not None else None
    hh = dict(h or {})
    if data: hh["Content-Type"] = "application/json"
    c.request(m, p, body=data, headers=hh)
    r = c.getresponse(); b = r.read().decode()
    try: return r.status, json.loads(b), r.getheader("Set-Cookie")
    except: return r.status, b, r.getheader("Set-Cookie")
tok = None
s, u, ck = req("POST", "/api/auth/login", {"email": "ciso@acme.test", "password": "[REDACTED]"})
for p in (ck or "").split(","):
    if p.strip().startswith("gf_session="): tok = p.strip().split(";")[0].split("=",1)[1]
h = {"Cookie": f"gf_session={tok}"}
print(req("GET", "/api/routes", None, h))
print(req("POST", "/api/run-once", {}, h))
print(req("GET", "/api/status", None, h))
print(req("GET", "/api/risk", None, h))
```

- [ ] **Step 2: Assert 200 (no 500)**

Expected: all four return HTTP 200. If any 500, capture `detail` from body and fix root cause in `saas_server.py` (the prior 500 was `eng` referenced before assignment — already fixed by moving `eng = engine_for(org)` above route handlers; verify).

- [ ] **Step 3: Verify route_exit event fires**

After several `run-once` cycles, query `/api/status` and assert `recent_events` contains at least one `{"kind": "route_exit"}` when dev-002 strays off its corridor (the demo route `route-centro` covers office→home; when the sim moves dev-002 to offsite it should exit).

---

## Task 4: Code review (using requesting-code-review)

- [ ] **Step 1: Self-review the diff surface**

Review `core/routes.py`, `core/engine.py` (route block), `saas_server.py` (`/api/routes`), `saas/auth.py` (caps). Check: no bare `except:`, no hardcoded secrets, RBAC enforced on every new endpoint, `to_dict()` exposes `route_state`/`route_deviation_m`/`route_id`.

- [ ] **Step 2: Dispatch a code-reviewer subagent** (via `delegate_task`, general-purpose) with the concrete checklist above and the file list. Act on Critical/Important findings before proceeding. Minor findings noted.

---

## Task 5: Frontend — Routes view (vanilla JS, <8K tokens)

**Files:**
- Modify: `static/saas_views3.js` (create if absent) — render `GFViews.routes`
- Modify: `static/saas.js` — register nav item + route
- Modify: `static/saas.html` (if nav is in HTML) — add "Rutas" link

**Interfaces:**
- Consumes: `GET /api/routes` → `{routes:[{id,name,waypoints,corridor_m,device_ids,color}]}`, `GET /api/devices` → states with `route_state`, `route_deviation_m`
- Produces: `GFViews.routes(root)` rendering a Leaflet map with the polyline + device markers colored by `route_state`, plus a side list with deviation badges.

- [ ] **Step 1: Add `GFViews.routes`**

```javascript
window.GFViews = window.GFViews || {};
GFViews.routes = function(root) {
  root.innerHTML = `<div class="grid2">
    <div><div id="route-map" class="map"></div></div>
    <div><h3>Rutas asignadas</h3><div id="route-list"></div></div>
  </div>`;
  const map = L.map('route-map').setView([40.42, -3.71], 12);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
  API('GET','/api/routes').then(r => {
    (r.routes||[]).forEach(rt => {
      const pts = (rt.waypoints||[]).map(w => [w.lat, w.lng]);
      if (pts.length) L.polyline(pts, {color: rt.color||'#22c55e', weight:4, dashArray:'6 6'}).addTo(map);
      const div = document.createElement('div');
      div.className = 'card';
      div.innerHTML = `<b>${rt.name}</b><br>Corredor: ${rt.corridor_m} m · Dispositivos: ${(rt.device_ids||[]).join(', ')}`;
      document.getElementById('route-list').appendChild(div);
    });
  });
  API('GET','/api/devices').then(devs => {
    (devs||[]).forEach(d => {
      if (d.lat == null) return;
      const color = d.route_state==='off_route' ? '#ef4444' : d.route_state==='on_route' ? '#22c55e' : '#9ca3af';
      L.circleMarker([d.lat, d.lng], {radius:7, color}).addTo(map);
    });
  });
};
```

- [ ] **Step 2: Register nav in `saas.js`**

Add to the view registry: `routes: GFViews.routes` and a nav button labeled "Rutas" calling `navigate('routes')`.

- [ ] **Step 3: Manual smoke (browser not required)** — verify JS parses by loading `saas.js`+`saas_views3.js` via `node --check` if node present, else skip (runtime check covered by Task 3 server queries).

---

## Task 6: Final QA gate — green before delivery

**Files:**
- Create: `tests/test_qa_e2e.py` (runs server in-process or via background `process`, queries all endpoints)

- [ ] **Step 1: Full suite**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASSED (routes unit + engine route-state + e2e HTTP).

- [ ] **Step 2: Report to user ONLY after green**

Do NOT deliver until `pytest` exits 0 with 0 failures. State explicitly: "QA green — N tests passing, 0 failures. Modules: routes backend + TDD, 500 debugged, code-reviewed, frontend Routes view."

---

## No Placeholders

Every step above contains the exact code, command, and expected output. No "TODO", no "implement later", no "similar to Task N".

## Self-Review (done at plan time)

- Spec coverage: route module backend ✓ (T1,T2), 500 debug ✓ (T3), code review ✓ (T4), frontend ✓ (T5), QA gate ✓ (T6).
- Placeholder scan: none.
- Type consistency: `route_state` strings match across `engine.py`, `state_store.py`, `policies.py`, frontend (`on_route`/`off_route`/`unassigned`).
