from __future__ import annotations

import http.client
import importlib.util
import json
import os
import re
import tempfile
from pathlib import Path

import loop_improve

ROOT = Path(__file__).resolve().parents[1]


def _request(method: str, path: str, body=None, cookie: str = ""):
    connection = http.client.HTTPConnection("127.0.0.1", 8765, timeout=10)
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    payload = json.dumps(body).encode() if body is not None else None
    connection.request(method, path, payload, headers)
    response = connection.getresponse()
    raw = response.read().decode("utf-8", "replace")
    set_cookie = response.getheader("Set-Cookie") or ""
    connection.close()
    return response.status, json.loads(raw) if raw else {}, set_cookie


def _cookie_header(set_cookie: str) -> str:
    pairs = re.findall(r"(gf_(?:session|org)=[^;,\s]+)", set_cookie)
    return "; ".join(pairs)


def test_roadmap_is_not_public_and_owner_can_read_without_mutating_it():
    status, _, _ = _request("GET", "/api/roadmap")
    assert status == 401
    status, _, _ = _request("PATCH", "/api/roadmap", {"feature_id": "F1.1", "field": "status", "value": "blocked"})
    assert status == 401

    status, login, cookies = _request("POST", "/api/auth/login", {"email": "ciso@acme.test", "password": "demo1234"})
    assert status == 200 and login.get("ok")
    cookie = _cookie_header(cookies)
    status, roadmap, _ = _request("GET", "/api/roadmap", cookie=cookie)
    assert status == 200 and roadmap["progress"]["done"] == 18
    status, _, _ = _request("PATCH", "/api/roadmap", {"feature_id": "DOES-NOT-EXIST", "field": "status", "value": "done"}, cookie=cookie)
    assert status in (400, 404)


def test_versioned_api_openapi_and_deprecation_contract():
    connection = http.client.HTTPConnection("127.0.0.1", 8765, timeout=10)
    connection.request("GET", "/api/v1/openapi.json")
    response = connection.getresponse()
    schema = json.loads(response.read())
    headers = dict(response.getheaders())
    connection.close()
    assert response.status == 200 and schema["openapi"] == "3.1.0"
    assert headers.get("X-API-Version") == "v1"
    assert headers.get("Deprecation") == "true" and "Sunset" in headers

    connection = http.client.HTTPConnection("127.0.0.1", 8765, timeout=10)
    connection.request("GET", "/api/v2/openapi.json")
    response = connection.getresponse(); schema = json.loads(response.read())
    headers = dict(response.getheaders()); connection.close()
    assert response.status == 200 and schema["info"]["version"] == "2.1.0"
    assert headers.get("X-API-Version") == "v2" and "Deprecation" not in headers


def test_runner_treats_nonzero_and_string_system_exit_as_failures():
    spec = importlib.util.spec_from_file_location("honest_runner", ROOT / "tests" / "run_tests.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._system_exit_code(SystemExit()) == 0
    assert module._system_exit_code(SystemExit(0)) == 0
    assert module._system_exit_code(SystemExit(1)) == 1
    assert module._system_exit_code(SystemExit("failed")) == 1


def test_loop_dry_run_does_not_write_history():
    old_history, old_cli = loop_improve._HISTORY, loop_improve._CLI
    with tempfile.TemporaryDirectory() as td:
        loop_improve._HISTORY = Path(td) / "history.jsonl"
        loop_improve._CLI = ""
        try:
            assert loop_improve.run_loop(feature_id="F1.1", max_iter=1, dry_run=True) == 0
            assert not loop_improve._HISTORY.exists()
        finally:
            loop_improve._HISTORY, loop_improve._CLI = old_history, old_cli


def test_zero_fleet_offline_map_accessibility_and_monitor_contracts():
    app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "health-monitor.yml").read_text(encoding="utf-8")
    assert "const total = devs.length;" in app
    assert "const compPct = total ?" in app
    assert "basemaps.cartocdn.com" not in app
    assert 'p[0]!=null&&p[1]!=null' in app
    assert '<main class="main"' in html
    assert 'role="dialog" aria-modal="true"' in html
    assert 'id="toasts" role="status" aria-live="polite"' in html
    assert "prefers-reduced-motion" in html
    assert "schedule:" not in workflow
    assert "required: true" in workflow


def test_doctor_validates_installation_even_when_runtime_is_stopped():
    import subprocess
    result = subprocess.run([str(ROOT / "bin" / "lucidfence"), "doctor", "--port", "65534", "--json"],
                            cwd=ROOT, capture_output=True, text=True, timeout=30)
    report = json.loads(result.stdout)
    assert result.returncode == 0 and report["ok"] is True
    assert report["warnings"] == 1
    assert any(item["name"] == "roadmap" and item["ok"] for item in report["checks"])
