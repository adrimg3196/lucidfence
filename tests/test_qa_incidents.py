"""HTTP acceptance tests for incident operations and RBAC.

Assumes the local server is running, matching the existing E2E convention.
"""
import http.client
import json
import time

HOST, PORT = "127.0.0.1", 8765


def req(method, path, body=None, cookie=None):
    c = http.client.HTTPConnection(HOST, PORT, timeout=10)
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    data = json.dumps(body).encode() if body is not None else None
    c.request(method, path, body=data, headers=headers)
    r = c.getresponse()
    raw = r.read().decode("utf-8", "replace")
    set_cookie = r.getheader("Set-Cookie")
    c.close()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {"raw": raw}
    return r.status, payload, set_cookie


def login(email, password):
    status, body, cookie = req("POST", "/api/auth/login", {"email": email, "password": password})
    assert status == 200 and body.get("ok"), body
    return (cookie or "").split(";")[0]


def test_incident_http_lifecycle_and_rbac():
    suffix = int(time.time())
    org_name = f"Incident QA {suffix}"
    owner_email = f"incident-owner-{suffix}@acme.test"
    status, signup, _ = req("POST", "/api/auth/signup", {
        "email": owner_email, "password": "ownerpass123", "name": "Owner",
        "org_name": org_name,
    })
    assert status == 200 and signup.get("ok"), signup
    org_id = signup["org"]["id"]
    from pathlib import Path
    from core.incidents import IncidentStore
    fixture = IncidentStore(Path("data") / "tenants" / org_id / "data")
    fixture.merge([{
        "id": "inc-qa-1", "type": "geofence_exit", "severity": "high",
        "status": "open", "title": "Incidente QA", "device_id": "dev-qa",
        "device_name": "QA Device", "last_seen": "2026-07-10T10:00:00+00:00",
    }])
    fixture.transition("inc-qa-1", "resolved", actor="fixture")
    owner = login(owner_email, "ownerpass123")
    status, body, _ = req("GET", "/api/incidents", cookie=owner)
    assert status == 200, body
    incidents = body.get("incidents") or []
    assert incidents, "simulation fleet should derive at least one incident"
    incident_id = incidents[0]["id"]

    status, updated, _ = req(
        "POST", f"/api/incidents/{incident_id}/transition",
        {"status": "acknowledged", "assignee": "soc@acme.test", "note": "QA triage"}, owner,
    )
    assert status == 200 and updated.get("incident", {}).get("status") == "acknowledged", updated
    assert updated["incident"]["timeline"][-1]["note"] == "QA triage"

    viewer_email = f"incident-viewer-{suffix}@acme.test"
    status, inv, _ = req("POST", "/api/users", {
        "email": viewer_email, "name": "Viewer", "role": "viewer"}, cookie=owner)
    assert status == 200 and inv.get("ok"), inv
    viewer = login(viewer_email, inv["temp_password"])

    status, _, _ = req("GET", "/api/incidents", cookie=viewer)
    assert status == 200
    status, denied, _ = req(
        "POST", f"/api/incidents/{incident_id}/transition", {"status": "resolved"}, viewer,
    )
    assert status == 403 and denied.get("error"), denied

    status, resolved, _ = req(
        "POST", f"/api/incidents/{incident_id}/transition",
        {"status": "resolved", "note": "QA cerrado"}, owner,
    )
    assert status == 200 and resolved["incident"]["status"] == "resolved"


def test_incident_csv_export():
    suffix = int(time.time())
    owner_email = f"export-owner-{suffix}@acme.test"
    status, signup, _ = req("POST", "/api/auth/signup", {
        "email": owner_email, "password": "ownerpass123", "name": "Owner",
        "org_name": f"Export QA {suffix}",
    })
    assert status == 200 and signup.get("ok"), signup
    owner = login(owner_email, "ownerpass123")
    # derive incidents for this org so the export has rows
    req("POST", "/api/run-once", cookie=owner)
    c = http.client.HTTPConnection(HOST, PORT, timeout=10)
    c.request("GET", "/api/incidents/export?format=csv", headers={"Cookie": owner})
    r = c.getresponse()
    raw = r.read().decode("utf-8", "replace")
    c.close()
    assert r.status == 200, raw[:120]
    ct = r.getheader("Content-Type", "")
    assert "text/csv" in ct, ct
    header = raw.splitlines()[0]
    assert "id,title,severity,status" in header, header
    assert len(raw.splitlines()) >= 2, "expected header + >=1 incident row"


def test_incident_analytics_and_webhook_setting():
    suffix = int(time.time())
    owner_email = f"an-{suffix}@acme.test"
    status, signup, _ = req("POST", "/api/auth/signup", {
        "email": owner_email, "password": "ownerpass123", "name": "Owner",
        "org_name": f"Analytics QA {suffix}",
    })
    assert status == 200 and signup.get("ok"), signup
    owner = login(owner_email, "ownerpass123")
    status, body, _ = req("GET", "/api/incidents/analytics", cookie=owner)
    assert status == 200, body
    assert "analytics" in body and "open" in body["analytics"], body
    status, body, _ = req("POST", "/api/settings/incident-webhook",
                          {"url": "https://hooks.slack.com/services/T/B/X"}, owner)
    assert status == 200 and body.get("ok") is True, body
    viewer_email = f"an-viewer-{suffix}@acme.test"
    status, vinv, _ = req("POST", "/api/users", {
        "email": viewer_email, "name": "V", "role": "viewer"}, cookie=owner)
    assert status == 200 and vinv.get("ok"), vinv
    vh = login(viewer_email, vinv["temp_password"])
    status, denied, _ = req("POST", "/api/settings/incident-webhook",
                            {"url": "https://x"}, vh)
    assert status == 403 and denied.get("error"), denied
