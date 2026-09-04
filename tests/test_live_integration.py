"""Integration test: Applivery live integration (contract reconciled 2026-07-09).

Reconciled contract (VERIFIED live 2026-07-09 against api.applivery.io):
  - Route: GET /v1/organizations/{org}/mdm/devices  (plural "organizations" + "mdm").
    PROVEN: /orgs/ -> 404; /organizations/{org}/devices -> 404; the correct path
    is /organizations/{org}/mdm/devices (returns 200 with data.items). The
    applivery_learn MCP contract is STALE (documents /orgs/{org}/devices).
  - Auth: `Authorization: Bearer <key>` (service-account). PROVEN: the live API
    recognizes Bearer (401 "Invalid Token" = token read & validated). X-Api-Token
    is a different API (gives "No auth token").
  - Pagination via `Link: rel="next"` header (and/or data.nextCursor).
  - Any upstream rejection (401/403/404) is captured as `integration_error`
    and never raises (dashboard never 500s).

Run:  python3 tests/test_live_integration.py
"""
import json
import os
import sys
import threading
import atexit
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler, HTTPServer
from lucidfence.core.engine import Engine
from lucidfence.core.config_loader import load as load_config
from lucidfence.core.actions import LiveAdapter
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, ".env")
# Preserve the operator's real .env (may hold a live Applivery token + workspace).
# Tests rewrite .env with mock values; restore an original or remove the generated
# mock file at process exit so no worktree remains polluted.
_ENV_EXISTED = os.path.exists(ENV_PATH)
_ENV_BACKUP = ENV_PATH + ".bak" if _ENV_EXISTED else None
if _ENV_BACKUP:
    shutil.copy2(ENV_PATH, _ENV_BACKUP)


def _restore_env():
    if _ENV_BACKUP and os.path.exists(_ENV_BACKUP):
        shutil.move(_ENV_BACKUP, ENV_PATH)
        try:
            os.chmod(ENV_PATH, 0o600)
        except OSError:
            pass
    elif not _ENV_EXISTED and os.path.exists(ENV_PATH):
        os.remove(ENV_PATH)


atexit.register(_restore_env)
_MOCK = None
_MOCK_PORT = None


class MockHandler(BaseHTTPRequestHandler):
    last_command_body = None

    def log_message(self, *a):
        pass

    def _valid(self):
        # Accept either auth header (mirrors the dual-header production client).
        return (
            self.headers.get("X-Api-Token") == "valid-token"
            or self.headers.get("Authorization") == "Bearer valid-token"
        )

    def _send(self, code, payload, link=""):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        if link:
            self.send_header("Link", link)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._valid():
            self._send(401, {"status": False, "error": {"code": 4002, "message": "No auth token"}})
            return
        if self.path.startswith("/v1/organizations/") and "/mdm/devices" in self.path:
            if "page=2" in self.path:
                self._send(200, {"items": []})
                return
            self._send(
                200,
                {"items": [
                    {"id": "dev-1001", "name": "Field Tablet A", "platform": "android",
                     "status": "active", "is_compliant": True,
                     "last_location": {"latitude": 40.42, "longitude": -3.71, "accuracy": 12}},
                    {"id": "dev-1002", "name": "Delivery Phone B", "platform": "android",
                     "status": "active", "is_compliant": True,
                     "last_location": {"latitude": 40.43, "longitude": -3.69, "accuracy": 20}},
                ]},
                link=(
                    f'<http://127.0.0.1:{getattr(self.server, "server_port")}/v1/organizations/'
                    'org-test/mdm/devices?page=2>; rel="next"'
                ),
            )
            return
        self._send(404, {"status": False, "error": {"code": 1002, "message": "Route not found"}})

    def do_POST(self):
        if not self._valid():
            self._send(401, {"status": False, "error": {"code": 4002, "message": "No auth token"}})
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            MockHandler.last_command_body = json.loads(raw.decode() or "{}")
        except Exception:
            MockHandler.last_command_body = {}
        self._send(200, {"status": True, "command_id": "cmd-xyz"})


def _start_mock():
    global _MOCK_PORT
    # allow_reuse_address tolerates TIME_WAIT leftovers if a prior run didn't
    # shut down cleanly (e.g. the runner interrupted mid-test).
    HTTPServer.allow_reuse_address = True
    srv = HTTPServer(("127.0.0.1", 0), MockHandler)
    _MOCK_PORT = int(srv.server_port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _ensure_mock():
    global _MOCK
    if _MOCK is None:
        _MOCK = _start_mock()
    return _MOCK


def _write_env(key, org):
    with open(ENV_PATH, "w") as f:
        f.write(f"APPLIVERY_API_KEY={key}\n")
        f.write(f"APPLIVERY_ORG_ID={org}\n")
    os.environ["APPLIVERY_API_KEY"] = key
    os.environ["APPLIVERY_ORG_ID"] = org


def _engine_for_live():
    assert _MOCK_PORT is not None
    os.environ["APPLIVERY_API_BASE"] = f"http://127.0.0.1:{_MOCK_PORT}/v1"
    cfg = load_config(os.path.join(ROOT, "config.json"))
    cfg["mode"] = "live"
    cfg["dry_run"] = True
    eng = Engine(cfg)
    eng.org_id = cfg.get("applivery", {}).get("org_id")
    return eng


def test_live_rejected_token_is_captured():
    """Applivery rejects the token -> captured, NOT a 500."""
    _ensure_mock()
    os.environ.pop("APPLIVERY_API_KEY", None)
    _write_env("wrong-token", "org-test")
    stats = _engine_for_live().run_once()
    ie = stats.get("integration_error")
    assert ie, f"expected integration_error, got {stats}"
    assert ie.get("http_status") == 401, ie
    print("  [ok] rejected token -> integration_error:", ie)


def test_live_success_uses_organizations_route():
    """Valid token -> devices fetched via /organizations/; never 500."""
    _ensure_mock()
    os.environ.pop("APPLIVERY_API_KEY", None)
    _write_env("valid-token", "org-test")
    stats = _engine_for_live().run_once()
    assert not stats.get("integration_error"), stats.get("integration_error")
    assert stats["devices_total"] == 2, stats
    assert stats["inside"] == 2, stats
    print("  [ok] live success: 2 devices, 2 inside; route /organizations/{org}/devices")


def test_live_missing_org_id_is_captured():
    _ensure_mock()
    os.environ.pop("APPLIVERY_API_KEY", None)
    _write_env("valid-token", "org-test")
    eng = _engine_for_live()
    eng.org_id = ""
    eng.source.org_id = ""
    ie = eng.run_once().get("integration_error")
    assert ie and ie.get("stage") == "config", ie
    print("  [ok] missing org_id captured gracefully:", ie)


def test_live_command_body_shape():
    """LiveAdapter POSTs to /organizations/.../commands with dual auth."""
    _ensure_mock()
    os.environ.pop("APPLIVERY_API_KEY", None)
    assert _MOCK_PORT is not None
    os.environ["APPLIVERY_API_BASE"] = f"http://127.0.0.1:{_MOCK_PORT}/v1"
    _write_env("valid-token", "org-test")
    adapter = LiveAdapter("org-test", "/organizations/{org_id}/mdm/devices/{device_id}/commands")
    result = adapter.execute(
        SimpleNamespace(device_id="dev-1001", name="Tablet A"),
        "lock", {"message": "policy"},
    )
    assert result["ok"], result
    assert result["status_code"] == 200, result
    body = MockHandler.last_command_body
    assert body.get("command") == "lock", body
    assert body.get("params") == {"message": "policy"}, body
    print("  [ok] command body shape:", body)


def test_live_pagination_follows_cursor_beyond_page_two():
    """El cursor debe seguirse más allá de la página 2 sin perder dispositivos.

    Regresión: el separador de la URL de paginación se calculaba sobre `url`
    (que ya llevaba `?cursor=...` tras el primer salto) en vez de sobre `path`,
    produciendo `.../devices&cursor=...` (malformada) desde la página 3 —
    perdiendo en silencio todo dispositivo de esa página en adelante.
    """
    import urllib.request
    from urllib.parse import urlsplit, parse_qs
    from lucidfence.core import location_source as ls

    pages = {
        None: {"status": True, "data": {"items": [
            {"id": "d1", "lastLocation": {"agent": {"latitude": 1.0, "longitude": 2.0}}}],
            "nextCursor": "C2"}},
        "C2": {"status": True, "data": {"items": [
            {"id": "d2", "lastLocation": {"agent": {"latitude": 3.0, "longitude": 4.0}}}],
            "nextCursor": "C3"}},
        "C3": {"status": True, "data": {"items": [
            {"id": "d3", "lastLocation": {"agent": {"latitude": 5.0, "longitude": 6.0}}}],
            "nextCursor": None}},
    }

    class _Resp:
        def __init__(self, body): self._b = body.encode("utf-8"); self.headers = {}
        def read(self): return self._b
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _fake_urlopen(req, timeout=None):
        cur = parse_qs(urlsplit(req.full_url).query).get("cursor", [None])[0]
        # cursor perdido (la URL malformada del bug) -> página vacía, sin d3
        page = pages.get(cur, {"status": True, "data": {"items": [], "nextCursor": None}})
        return _Resp(json.dumps(page))

    real = urllib.request.urlopen
    urllib.request.urlopen = _fake_urlopen
    try:
        src = ls.LiveLocationSource(org_id="org1", api_key="k")
        src._api_base = "https://api.example.test/v1"
        ids = {r.device_id for r in src.fetch()}
    finally:
        urllib.request.urlopen = real

    assert ids == {"d1", "d2", "d3"}, f"dispositivo de la página 3 perdido por la paginación: {sorted(ids)}"
    print("  [ok] pagination follows cursor across 3 pages:", sorted(ids))


if __name__ == "__main__":
    _ensure_mock()
    try:
        test_live_rejected_token_is_captured()
        test_live_success_uses_organizations_route()
        test_live_missing_org_id_is_captured()
        test_live_command_body_shape()
        test_live_pagination_follows_cursor_beyond_page_two()
        print("\nALL LIVE INTEGRATION TESTS PASSED")
    finally:
        if _MOCK:
            _MOCK.shutdown()
        # .env restored automatically via atexit handler.
