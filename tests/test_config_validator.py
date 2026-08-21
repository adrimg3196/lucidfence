"""Tests for config_validator — validates any UEM location_source mapping.

Uses a stub HTTP server (stdlib http.server) so the live fetch path is real
but local. No external network.
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, ".")

from lucidfence.core.config_validator import validate_location_source


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = json.dumps({"data": {"items": [
            {"id": "d1", "displayName": "Laptop", "os": "windows",
             "location": {"lat": 40.0, "lng": -3.0}, "compliance": {"ok": True}},
            {"id": "d2", "displayName": "Phone", "os": "ios",
             "location": {"lat": 41.0, "lng": -4.0}},
            {"id": "d3", "displayName": "NoGPS", "os": "android"},  # no location
        ]}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # silence
        pass


def _start_server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, port


def test_validates_good_mapping():
    srv, port = _start_server()
    try:
        cfg = {
            "url": f"http://127.0.0.1:{port}/devices",
            "items_path": "data.items",
            "fields": {
                "device_id": "id", "name": "displayName", "platform": "os",
                "lat": "location.lat", "lng": "location.lng", "compliant": "compliance.ok",
            },
        }
        rep = validate_location_source(cfg)
        # source returns only devices with resolvable lat/lng (d3 NoGPS dropped)
        assert rep["devices_raw"] == 3
        assert rep["devices_returned"] == 2
        assert rep["devices_with_geo"] == 2
        assert rep["devices_dropped_no_geo"] == 1
        assert rep["fetch_error"] is None
        # every configured path resolves on the geo devices
        assert rep["field_resolution"]["device_id"]["resolved"] == 2
        assert rep["field_resolution"]["lat"]["resolved"] == 2
        assert rep["ok"] is True
    finally:
        srv.shutdown()


def test_reports_bad_mapping():
    srv, port = _start_server()
    try:
        cfg = {
            "url": f"http://127.0.0.1:{port}/devices",
            "items_path": "data.items",
            "fields": {"device_id": "id", "lat": "wrong.path", "lng": "location.lng"},
        }
        rep = validate_location_source(cfg)
        # lat path is wrong -> 0 resolved
        assert rep["field_resolution"]["lat"]["resolved"] == 0
        assert rep["ok"] is False
    finally:
        srv.shutdown()
