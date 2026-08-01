"""Tests for GenericHTTPLocationSource — bring-your-own UEM API (multi-UEM goal).

No real network: urllib.request.urlopen is mocked. Verifies field mapping,
${ENV} header expansion, items_path navigation and graceful errors.
"""
from __future__ import annotations

import json
import sys
import os
sys.path.insert(0, ".")

from lucidfence.core.generic_http_source import GenericHTTPLocationSource, _dig, _resolve_env


def _make_source(payload: dict, **over):
    os.environ["VENDOR_TOKEN"] = "seeded-token"
    cfg = {
        "url": "https://vendor.example.com/api/devices",
        "headers": {"Authorization": "Bearer ${VENDOR_TOKEN}"},
        "items_path": "data.items",
        "fields": {
            "device_id": "id", "name": "name", "platform": "os",
            "lat": "loc.lat", "lng": "loc.lng", "compliant": "comp.ok",
        },
    }
    cfg.update(over)
    src = GenericHTTPLocationSource(cfg)
    body = json.dumps(payload).encode()
    import urllib.request
    import urllib.error

    class FakeResp:
        def __init__(self, b): self._b = b
        def read(self): return self._b
        def __enter__(self): return self
        def __exit__(self, *a): return False
    src._raw = body  # stash for the mock
    def fake_urlopen(req, timeout=30):
        assert req.headers.get("Authorization") == "Bearer seeded-token"
        return FakeResp(body)
    src._fake = fake_urlopen
    return src


def test_env_header_expansion():
    os.environ["VENDOR_TOKEN"] = "seeded-token"
    src = GenericHTTPLocationSource({"url": "https://x", "headers": {"X": "Bearer ${VENDOR_TOKEN}"}})
    assert src.headers["X"] == "Bearer seeded-token"
    del os.environ["VENDOR_TOKEN"]


def test_dig_navigation():
    assert _dig({"a": {"b": 1}}, "a.b") == 1
    assert _dig({"a": {"b": 1}}, "a.x") is None
    assert _dig({"a": 1}, "") == {"a": 1}
    assert _dig([{"a": 1}], "0.a") is None  # only dict paths


def test_maps_items_to_reports():
    payload = {"data": {"items": [
        {"id": "d1", "name": "Laptop", "os": "windows", "loc": {"lat": 40.0, "lng": -3.0}, "comp": {"ok": True}},
        {"id": "d2", "name": "Phone", "os": "ios", "loc": {"lat": 41.0, "lng": -4.0}},
    ]}}
    import urllib.request
    src = _make_source(payload)
    import unittest.mock as m
    with m.patch("urllib.request.urlopen", src._fake):
        reps = src.fetch()
    assert len(reps) == 2
    r0 = reps[0]
    assert r0.device_id == "d1" and r0.platform == "windows"
    assert r0.lat == 40.0 and r0.lng == -3.0
    assert r0.compliant is True
    assert r0.location_source == "generic"


def test_skips_device_without_location():
    payload = {"data": {"items": [
        {"id": "d1", "name": "NoGPS", "os": "android"},  # no loc
        {"id": "d2", "name": "Ok", "os": "ios", "loc": {"lat": 1.0, "lng": 2.0}},
    ]}}
    import urllib.request, unittest.mock as m
    src = _make_source(payload)
    with m.patch("urllib.request.urlopen", src._fake):
        reps = src.fetch()
    assert [r.device_id for r in reps] == ["d2"]


def test_empty_url_returns_error_not_crash():
    src = GenericHTTPLocationSource({"url": ""})
    assert src.fetch() == []
    assert src.last_error and src.last_error["stage"] == "config"
