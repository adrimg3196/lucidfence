from __future__ import annotations

import http.client
import json
import os
import tempfile
import time
from pathlib import Path

from core.api_keys import APIKeyStore, append_audit, verify_audit

HOST, PORT = "127.0.0.1", 8765


def _request(method, path, body=None, cookie="", bearer=""):
    connection = http.client.HTTPConnection(HOST, PORT, timeout=10)
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    connection.request(method, path, json.dumps(body).encode() if body is not None else None, headers)
    response = connection.getresponse()
    raw = response.read().decode("utf-8", "replace")
    cookies = response.getheader("Set-Cookie") or ""
    connection.close()
    return response.status, json.loads(raw) if raw else {}, cookies


def test_api_key_store_hashes_tokens_and_revokes():
    with tempfile.TemporaryDirectory() as td:
        store = APIKeyStore(td)
        token, record = store.create("org-1", "automation", "operator")
        raw = (Path(td) / "_api_keys.json").read_text()
        assert token not in raw
        authenticated = store.authenticate(token)
        assert authenticated is not None and authenticated["org_id"] == "org-1"
        assert store.revoke("org-1", record["id"]) is True
        assert store.authenticate(token) is None
        assert oct((Path(td) / "_api_keys.json").stat().st_mode & 0o777) == "0o600"


def test_audit_log_chain_detects_tampering():
    with tempfile.TemporaryDirectory() as td:
        append_audit(td, {"event": "one", "actor": "u1"})
        append_audit(td, {"event": "two", "actor": "u1"})
        assert verify_audit(td)["ok"] is True
        path = Path(td) / "audit.jsonl"
        path.write_text(path.read_text().replace('"event":"one"', '"event":"evil"', 1))
        assert verify_audit(td)["ok"] is False


def test_api_key_http_auth_rbac_audit_and_revocation():
    suffix = time.time_ns()
    email = f"api-owner-{suffix}@acme.test"
    status, signup, _ = _request("POST", "/api/auth/signup", {"email": email, "password": "ownerpass123", "name": "Owner", "org_name": f"API QA {suffix}"})
    assert status == 200 and signup.get("ok")
    status, login, cookie = _request("POST", "/api/auth/login", {"email": email, "password": "ownerpass123"})
    assert status == 200 and cookie
    status, created, _ = _request("POST", "/api/api-keys", {"name": "CI", "role": "operator"}, cookie=cookie)
    assert status == 201 and created["key"].startswith("lf_")
    token, key_id = created["key"], created["record"]["id"]
    status, fences, _ = _request("GET", "/api/fences", bearer=token)
    assert status == 200 and "fences" in fences
    status, denied, _ = _request("POST", "/api/api-keys", {"name": "escalate"}, bearer=token)
    assert status == 403
    status, audit, _ = _request("GET", "/api/audit", cookie=cookie)
    assert status == 200 and audit["integrity"]["ok"] is True
    assert audit["cef"] and audit["cef"][0].startswith("CEF:0|LucidFence")
    status, _, _ = _request("DELETE", f"/api/api-keys/{key_id}", cookie=cookie)
    assert status == 200
    status, _, _ = _request("GET", "/api/fences", bearer=token)
    assert status == 401
