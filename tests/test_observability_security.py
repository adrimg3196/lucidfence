from __future__ import annotations

import http.client


def _get(path):
    connection = http.client.HTTPConnection("127.0.0.1", 8765, timeout=5)
    connection.request("GET", path)
    response = connection.getresponse()
    body = response.read()
    headers = dict(response.getheaders())
    connection.close()
    return response.status, headers, body


def test_prometheus_metrics_are_live_and_bounded():
    status, headers, body = _get("/metrics")
    text = body.decode()
    assert status == 200
    assert "lucidfence_http_requests_total" in text
    assert "lucidfence_tenants" in text
    assert "lucidfence_engines" in text
    assert headers.get("X-Content-Type-Options") == "nosniff"


def test_static_responses_have_security_headers_without_breaking_dashboard():
    status, headers, body = _get("/static/dashboard.html")
    assert status == 200 and b"Command Center" in body
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert "script-src 'self'" in headers.get("Content-Security-Policy", "")


def test_request_body_cap_and_malformed_length_are_guarded_at_source():
    from pathlib import Path
    server = (Path(__file__).resolve().parents[1] / "saas_server.py").read_text()
    assert "MAX_REQUEST_BODY = 1024 * 1024" in server
    assert "payload demasiado grande" in server
    assert "content_length invalido" in server
    assert '"detail": str(e)' not in server
