"""End-to-end QA for the Workflows module (Task 2 of the workflows plan).

Assumes `python3 saas_server.py` is running on 127.0.0.1:8765.
Uses http.client (no proxy). No pytest dependency.
"""
import http.client
import json
import sys
import time
import urllib.parse

import os as _os
HOST, PORT = "127.0.0.1", int(_os.environ.get("LUCIDFENCE_PORT", "8765"))


def req(method, path, body=None, headers=None, cookie=None):
    c = http.client.HTTPConnection(HOST, PORT, timeout=10)
    h = headers or {}
    h["Content-Type"] = "application/json"
    if cookie:
        h["Cookie"] = cookie
    data = json.dumps(body) if body is not None else None
    c.request(method, path, body=data, headers=h)
    r = c.getresponse()
    raw = r.read().decode("utf-8", "replace")
    try:
        out = json.loads(raw) if raw else {}
    except Exception:
        out = {"_raw": raw}
    # capture session cookie for chaining
    setc = r.getheader("Set-Cookie")
    new_cookie = None
    if setc:
        new_cookie = setc.split(";")[0]
    c.close()
    return r.status, out, new_cookie or cookie


def check(cond, msg):
    if cond:
        print(f"  PASS {msg}")
    else:
        print(f"  FAIL {msg}")
        check.failed += 1


check.failed = 0


def _login(email, password):
    _, b, ck = req("POST", "/api/auth/login", {"email": email, "password": password})
    assert b.get("ok"), f"login failed: {b}"
    return ck


def test_workflows_e2e():
    # owner from seed (ciso@acme.test / [REDACTED])
    owner_ck = _login("ciso@acme.test", "demo1234")

    # GET /api/workflows (200 + templates + catalog)
    st, body, _ = req("GET", "/api/workflows", headers={}, cookie=owner_ck)
    check(st == 200, "GET /api/workflows -> 200 (owner)")
    check("templates" in body and len(body["templates"]) >= 5,
          f"workflow templates listed ({len(body.get('templates', []))})")
    check("actions" in body and len(body["actions"]) == 8,
          "applivery action catalog present (8)")
    check("triggers" in body and len(body["triggers"]) == 6,
          "trigger options for UI present (6)")

    # apply a template -> 200 and appears in active
    _, b, _ = req("POST", "/api/workflows/apply",
                   {"template_id": "wf-block-on-route-exit"}, cookie=owner_ck)
    check(b.get("ok") and b.get("policy", {}).get("id") == "pol-wf-block-on-route-exit",
          "apply template -> 200 (owner)")
    active_ids = [a["id"] for a in b.get("active", [])]
    check("pol-wf-block-on-route-exit" in active_ids,
          "applied workflow appears in active list")

    # custom workflow -> 200
    _, b, _ = req("POST", "/api/workflows/custom", {
        "name": "Wipe si rooteado",
        "trigger": "rooted",
        "action": "wipe",
        "severity": "critical",
    }, cookie=owner_ck)
    check(b.get("ok") and b.get("policy", {}).get("source") == "custom",
          "create custom workflow -> 200 (owner)")
    custom_id = b.get("policy", {}).get("id")
    check(custom_id and custom_id.startswith("pol-custom-"),
          f"custom workflow id generated ({custom_id})")

    # validation: bad trigger rejected (400)
    _, b, _ = req("POST", "/api/workflows/custom", {
        "name": "x", "trigger": "bogus", "action": "lock"}, cookie=owner_ck)
    check(b.get("error") is not None, "custom with bad trigger -> 400 (owner)")

    # delete the custom workflow -> 200 and gone from active
    _, b, _ = req("POST", f"/api/workflows/{custom_id}/delete", cookie=owner_ck)
    check(b.get("ok"), "delete custom workflow -> 200 (owner)")
    check(custom_id not in [a["id"] for a in b.get("active", [])],
          "deleted workflow removed from active")

    # RBAC: a viewer cannot write workflows.
    # Secure pattern: the owner INVITES the viewer (public signup can no longer
    # self-join an existing org). Then the viewer logs in with the temp password.
    vemail = f"viewerqa{int(time.time_ns())}@acme.test"
    _, inv, _ = req("POST", "/api/users", {
        "email": vemail, "name": "V", "role": "viewer"}, cookie=owner_ck)
    assert inv.get("ok"), f"viewer invite failed: {inv}"
    vpw = inv.get("temp_password")
    assert vpw, f"expected temp_password from invite: {inv}"
    vck = _login(vemail, vpw)
    _, b, _ = req("POST", "/api/workflows/apply",
                   {"template_id": "wf-block-on-route-exit"}, cookie=vck)
    check(b.get("error") is not None, "viewer blocked from apply (workflow:write)")
    st, b, _ = req("GET", "/api/workflows", headers={}, cookie=vck)
    check(st == 200, "viewer CAN read /api/workflows (workflow:read)")

    assert check.failed == 0, f"{check.failed} workflow e2e checks failed"


if __name__ == "__main__":
    test_workflows_e2e()
    print(f"\n=== workflows e2e: {13 - check.failed} passed, {check.failed} failed ===")
    if check.failed:
        sys.exit(1)
