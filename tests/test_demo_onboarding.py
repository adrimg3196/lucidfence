"""Regression: local-first onboarding must be one click, no cloud signup."""
import http.client
import json
from typing import Any

HOST, PORT = "127.0.0.1", 8765


def req(method, path, body=None, cookie=None):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=10)
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    raw = json.dumps(body).encode("utf-8") if body is not None else None
    conn.request(method, path, body=raw, headers=headers)
    resp = conn.getresponse()
    payload = resp.read().decode("utf-8", "replace")
    set_cookie = "; ".join(v.split(";", 1)[0] for k, v in resp.getheaders() if k.lower() == "set-cookie")
    conn.close()
    data: dict[str, Any]
    try:
        parsed = json.loads(payload) if payload else {}
        data = parsed if isinstance(parsed, dict) else {"raw": parsed}
    except Exception:
        data = {"raw": payload}
    return resp.status, data, set_cookie


def test_demo_auth_opens_local_dashboard_without_signup_fields():
    status, body, set_cookie = req("POST", "/api/auth/demo")
    assert status == 200 and body.get("ok"), body
    assert body.get("user", {}).get("email") == "ciso@acme.test"
    assert body.get("orgs"), body
    cookie = set_cookie
    assert "gf_session=" in cookie, set_cookie

    status, me, _ = req("GET", "/api/auth/me", cookie=cookie)
    assert status == 200, me
    assert me.get("user", {}).get("email") == "ciso@acme.test"
    assert me.get("orgs"), me
