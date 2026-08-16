"""Regresión de los hallazgos Strix (PR #45) verificados y arreglados por el
loop Centinela. Cada test falla contra el código de antes del fix y pasa
después. PoC descriptiva contra construcciones locales — nunca red real.

Findings cubiertos (los VIVOS; A/B/E se verificaron ya mitigados):
  C (A10 SSRF, alta)  — robo de token vía header Link
  F (A01/A10, media)  — device_id sin escapar en la URL
  G (A03, baja)       — lat/lng sin acotar en geocercas
  H (A03, baja)       — waypoints de ruta sin validar
  D (A10 SSRF, baja)  — esquema de webhook sin validar
"""
from __future__ import annotations

import json
import tempfile
import urllib.error
import unittest.mock as mock
from pathlib import Path

from lucidfence.core.location_source import LiveLocationSource
from lucidfence.core.adapters.fleet import FleetAdapter
from lucidfence.core.fences import Fence, load_fences
from lucidfence.core.routes import load_routes
from lucidfence.core.notifier import _default_http_post

_BASE = "https://api.applivery.io/v1"


# --- Finding C: header Link no puede redirigir el Bearer a otro host --------
def test_link_pagination_only_follows_same_origin():
    # mismo origen → se sigue
    same = LiveLocationSource._next_from_link(
        '<https://api.applivery.io/v1/devices?cursor=2>; rel="next"', _BASE)
    assert same == "https://api.applivery.io/v1/devices?cursor=2"


def test_link_pagination_refuses_foreign_host():
    # host interno / metadata → NO se sigue (no se reenvía el token)
    for evil in (
        '<https://169.254.169.254/latest/meta-data/>; rel="next"',
        '<https://attacker.example/steal>; rel="next"',
        '<http://api.applivery.io/v1/devices>; rel="next"',  # downgrade a http
    ):
        assert LiveLocationSource._next_from_link(evil, _BASE) is None


# --- Finding F: device_id se escapa (quote) antes de ir a la URL ------------
def test_location_source_quotes_device_id():
    src = LiveLocationSource(org_id="acme", api_key="k")
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        raise urllib.error.URLError("stop after capture")

    with mock.patch("urllib.request.urlopen", fake_urlopen):
        src.fetch_one("../../../secret@evil.com")
    url = captured["url"]
    assert "@evil.com" not in url          # no @host injection
    assert "/../" not in url               # no path traversal
    assert "%2F" in url or "%40" in url    # sí escapado


def test_fleet_adapter_quotes_device_id():
    adapter = FleetAdapter(org_id="acme", endpoint_template="https://fleet.example")
    _, url, _ = adapter._build_request("a/../b@evil", "lock", {})
    assert "@evil" not in url and "/../" not in url
    assert "%2F" in url or "%40" in url


# --- Finding G: lat/lng de geocerca acotados y sin NaN ----------------------
def test_fence_rejects_out_of_range_and_nan():
    for bad in (
        {"id": "f", "name": "f", "type": "circle",
         "center": {"lat": 9999, "lng": 0}, "radius_m": 100},
        {"id": "f", "name": "f", "type": "circle",
         "center": {"lat": float("nan"), "lng": 0}, "radius_m": 100},
        {"id": "f", "name": "f", "type": "circle",
         "center": {"lat": 0, "lng": float("inf")}, "radius_m": 100},
    ):
        try:
            Fence.from_raw(bad)
            assert False, f"se esperaba ValueError para {bad['center']}"
        except ValueError:
            pass


def test_fence_accepts_valid_coordinates():
    f = Fence.from_raw({"id": "f", "name": "f", "type": "circle",
                        "center": {"lat": 40.4, "lng": -3.7}, "radius_m": 100})
    assert f.center is not None and f.center.lat == 40.4


# --- Finding H: waypoint malformado descarta la ruta, no aborta el resto ----
def test_route_with_malformed_waypoint_is_skipped_others_load():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "routes.json"
        p.write_text(json.dumps([
            {"id": "bad", "name": "bad",
             "waypoints": [{"lat": 9999, "lng": 0}, {"lat": 1, "lng": 1}]},
            {"id": "good", "name": "good",
             "waypoints": [{"lat": 40.4, "lng": -3.7}, {"lat": 40.5, "lng": -3.6}]},
        ]), encoding="utf-8")
        routes = load_routes(p)
    ids = {r.id for r in routes}
    assert "good" in ids and "bad" not in ids


# --- Finding D: el webhook rechaza esquemas raros y credenciales -------------
def test_webhook_rejects_dangerous_url():
    for bad in (
        "file:///etc/passwd",
        "gopher://127.0.0.1:6379/_",
        "http://user:pass@evil.example/",
        "ftp://host/x",
        "notaurl",
    ):
        res = _default_http_post(bad, {"x": 1})
        assert res["ok"] is False, f"debería rechazar {bad!r}"
        assert "no permitido" in res.get("error", "") or "esquema" in res.get("error", "")
