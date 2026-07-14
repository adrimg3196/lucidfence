"""Unit tests for the UEM action executor (core/actions.py).

Covers:
  - SimulationAdapter returns a successful simulated result.
  - LiveAdapter.execute with a mocked 404 command endpoint falls back to the
    remediation webhook when one is configured (enterprise delegation pattern),
    and does NOT raise on any failure.
  - LiveAdapter.execute with no webhook configured records a non-delegated
    failure instead of raising.

Run via the runner:  python3 tests/run_tests.py
Run directly:        python3 tests/test_actions.py
"""
import os
import sys
import json
import threading
import http.server
import socketserver
import time as _t

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from core.actions import LiveAdapter, SimulationAdapter, build_adapter

PORT_CMD = 8801
PORT_WH = 8802


class _CmdHandler(http.server.BaseHTTPRequestHandler):
    # Applivery's public REST API does NOT expose remote commands -> 404.
    def do_POST(self):
        body = json.dumps({
            "status": False,
            "error": {"code": 1002, "message": "Route not found"},
        }).encode()
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class _WhHandler(http.server.BaseHTTPRequestHandler):
    received = {}

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(ln) if ln else b"{}"
        _WhHandler.received = json.loads(data.decode() or "{}")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, *a):
        pass


def _start(handler, port):
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


passed = 0
fails = []


def check(cond, msg):
    global passed
    if cond:
        passed += 1
        print("  PASS", msg)
    else:
        fails.append(msg)
        print("  FAIL", msg)


def test_simulation_adapter():
    a = SimulationAdapter()
    r = a.execute(None, "lock", {}, dry_run=False)
    check(r["ok"] is True and r["adapter"] == "simulation", "SimulationAdapter ok")


def test_live_fallback_to_webhook():
    cmd = _start(_CmdHandler, PORT_CMD)
    wh = _start(_WhHandler, PORT_WH)
    _WhHandler.received = {}
    try:
        os.environ["APPLIVERY_API_KEY"] = "fake-key"
        os.environ["APPLIVERY_API_BASE"] = f"http://127.0.0.1:{PORT_CMD}/v1"
        ad = LiveAdapter(
            org_id="org-x",
            endpoint_template="/organizations/{org_id}/mdm/devices/{device_id}/commands",
            webhook_url=f"http://127.0.0.1:{PORT_WH}/hook",
        )

        class Dev:
            device_id = "dev-1"
            name = "Test Phone"
            platform = "android"

        r = ad.execute(Dev(), "lock", {}, dry_run=False)
        check(r["ok"] is False, "live command 404 -> ok=False (no raise)")
        check(r.get("delegated") is True, "remediation delegated to webhook")
        check(r["delegation"].get("webhook_status") == 200, "webhook returned 200")
        check(
            _WhHandler.received.get("action") == "lock"
            and _WhHandler.received.get("device_id") == "dev-1",
            "webhook payload carries action + device_id",
        )
    finally:
        cmd.shutdown()
        wh.shutdown()
        os.environ.pop("APPLIVERY_API_KEY", None)
        os.environ.pop("APPLIVERY_API_BASE", None)


def test_live_no_webhook_no_raise():
    cmd = _start(_CmdHandler, PORT_CMD)
    try:
        os.environ["APPLIVERY_API_KEY"] = "fake-key"
        os.environ["APPLIVERY_API_BASE"] = f"http://127.0.0.1:{PORT_CMD}/v1"
        ad = LiveAdapter(
            org_id="org-x",
            endpoint_template="/organizations/{org_id}/mdm/devices/{device_id}/commands",
            webhook_url="",
        )

        class Dev:
            device_id = "dev-2"
            name = "No Webhook"
            platform = "ios"

        r = ad.execute(Dev(), "wipe", {}, dry_run=False)
        check(r["ok"] is False, "no-webhook path: ok=False (no raise)")
        check(r.get("delegated") is False, "no-webhook path: not delegated")
    finally:
        cmd.shutdown()
        os.environ.pop("APPLIVERY_API_KEY", None)
        os.environ.pop("APPLIVERY_API_BASE", None)


def test_build_adapter():
    a = build_adapter("simulation", "org", "/x")
    check(isinstance(a, SimulationAdapter), "build_adapter(simulation) -> SimulationAdapter")
    b = build_adapter("live", "org", "/x", webhook_url="http://h")
    check(isinstance(b, LiveAdapter), "build_adapter(live) -> LiveAdapter")


if __name__ == "__main__":
    test_simulation_adapter()
    test_live_fallback_to_webhook()
    test_live_no_webhook_no_raise()
    test_build_adapter()
    print(f"\n=== actions: {passed} passed, {len(fails)} failed ===")
    sys.exit(1 if fails else 0)
