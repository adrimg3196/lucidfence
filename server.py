#!/usr/bin/env python3
"""Local HTTP server: serves the dashboard (static/index.html) and a small
JSON API for the engine. Fully local on 127.0.0.1 — nothing leaves your Mac.

Endpoints:
  GET  /api/status                 -> engine status (fences, devices, events, actions, trails)
  GET  /api/run-once               -> trigger one evaluation cycle now
  GET  /api/config                 -> current config
  GET  /api/devices                -> list devices (optional ?state=inside|outside|unknown)
  GET  /api/devices/<id>           -> device detail + trail + recent events/actions
  GET  /api/stats                  -> historical stats (compliance/timeline)
  GET  /api/settings/status        -> token configured? + mode (no secret returned)
  POST /api/settings               -> save credentials (0600) + set mode/dry-run
  POST /api/settings/test          -> validate token against Applivery API (read-only, no secret returned)
  GET  /api/product                -> product intelligence bundle (read-only, local)
  GET  /api/analytics              -> analytics derived from local state
  GET  /api/risk                   -> risk center data
  GET  /api/incidents              -> derived incidents
  GET  /api/policies               -> local policy posture
  GET  /api/report                 -> executive local report
  GET  /                          -> dashboard
"""
from __future__ import annotations

import json
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import config_loader
import core.secrets as secrets
from core.secrets import test_applivery_token
from core.engine import Engine
from core.product import build_product

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        cfg = config_loader.load(ROOT / "config.json")
        _engine = Engine(cfg)
        if cfg.get("autostart", True):
            _engine.start()
    return _engine


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str):
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._route()

    def do_POST(self):
        self._route()

    def _route(self):
        parsed = urlparse(self.path)
        route = parsed.path
        qs = {k: v for k, v in (x.split("=", 1) for x in parsed.query.split("&") if "=" in x)}
        method = self.command
        if route in ("/", "/index.html"):
            self._send_file(STATIC / "index.html", "text/html; charset=utf-8")
            return
        if route == "/api/status":
            self._send_json(get_engine().status())
            return
        if route == "/api/run-once":
            stats = get_engine().run_once()
            self._send_json({"ok": True, "stats": stats})
            return
        if route == "/api/config":
            self._send_json(get_engine().config)
            return
        if route == "/api/stats":
            self._send_json({"stats_history": get_engine().store.stats_history(120)})
            return
        if route in ("/api/product", "/api/analytics", "/api/risk", "/api/incidents", "/api/policies", "/api/report"):
            eng = get_engine()
            st = eng.status()
            st["stats_history"] = eng.store.stats_history(120)
            product = build_product(st)
            if route == "/api/product":
                self._send_json(product)
            elif route == "/api/analytics":
                self._send_json({"generated_at": product.get("generated_at"), "analytics": product.get("analytics", {})})
            elif route == "/api/risk":
                self._send_json({"generated_at": product.get("generated_at"), "summary": product.get("summary", {}), "risk": product.get("risk", []), "insights": product.get("insights", [])})
            elif route == "/api/incidents":
                self._send_json({"generated_at": product.get("generated_at"), "summary": product.get("summary", {}), "incidents": product.get("incidents", [])})
            elif route == "/api/policies":
                self._send_json({"generated_at": product.get("generated_at"), "summary": product.get("summary", {}), "policies": product.get("policies", [])})
            elif route == "/api/report":
                self._send_json({"generated_at": product.get("generated_at"), "report": product.get("report", {})})
            return
        if route == "/api/settings/status":
            st = secrets.status(ROOT)
            eng = get_engine()
            st["mode"] = eng.config.get("mode")
            st["dry_run"] = eng.config.get("dry_run")
            st["masked_key"] = secrets.mask_key(ROOT)
            self._send_json(st)
            return
        if route == "/api/settings" and method == "POST":
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8", "replace") or "{}")
            except Exception:
                self._send_json({"ok": False, "error": "JSON inválido"}, 400)
                return
            api_key = body.get("api_key")
            org_id = body.get("org_id")
            mode = body.get("mode")
            res = secrets.save_credentials(ROOT, api_key, org_id)
            if not res.get("ok"):
                self._send_json({"ok": False, "error": res.get("error", "no se pudo guardar")}, 400)
                return
            eng = get_engine()
            if mode in ("live", "simulation"):
                eng.config["mode"] = mode
            if "dry_run" in body:
                eng.config["dry_run"] = bool(body["dry_run"])
            self._send_json({"ok": True, "configured": res.get("configured"),
                             "mode": eng.config.get("mode"), "dry_run": eng.config.get("dry_run")})
            return
        if route == "/api/settings/test" and method == "POST":
            # Validate the stored/provided token against the real Applivery API.
            # Safe: only does a GET /v1 (read-only). Never returns the key.
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8", "replace") or "{}")
            except Exception:
                body = {}
            key = (body.get("api_key") or "").strip() or secrets.read_key(ROOT)
            if not key:
                self._send_json({"ok": False, "error": "no hay token configurado"}, 400)
                return
            res = test_applivery_token(key)
            self._send_json(res)
            return
        if route == "/api/devices":
            eng = get_engine()
            states = list(eng.store.snapshot().values())
            if "state" in qs:
                states = [s for s in states if s.fence_state == qs["state"]]
            self._send_json([s.to_dict() for s in states])
            return
        if route.startswith("/api/devices/"):
            dev_id = route[len("/api/devices/"):]
            eng = get_engine()
            d = eng.store.get(dev_id)
            if not d:
                self._send_json({"error": "not found"}, 404)
                return
            self._send_json({
                "device": d.to_dict(),
                "trail": eng.store.trail(dev_id, 200),
                "events": [e for e in eng.store.recent_events(200) if e.get("device_id") == dev_id][-20:],
                "actions": [a for a in eng.store.recent_actions(200) if a.get("device_id") == dev_id][-20:],
            })
            return
        if route.startswith("/static/"):
            rel = route[len("/static/"):]
            p = (STATIC / rel).resolve()
            if p.is_relative_to(STATIC):
                ctype = "text/html"
                if p.suffix == ".js":
                    ctype = "application/javascript"
                elif p.suffix == ".css":
                    ctype = "text/css"
                self._send_file(p, ctype)
                return
        self.send_error(404)

    def log_message(self, fmt, *args):
        return  # silence default logging


def main():
    cfg = config_loader.load(ROOT / "config.json")
    host = cfg.get("server", {}).get("host", "127.0.0.1")
    port = int(cfg.get("server", {}).get("port", 8765))
    get_engine()  # start engine loop
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"LucidFence product running at http://{host}:{port}")
    print(f"  mode={cfg.get('mode')} interval={cfg.get('interval_seconds')}s dry_run={cfg.get('dry_run')}")
    print("  Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
        get_engine().stop()


if __name__ == "__main__":
    main()
