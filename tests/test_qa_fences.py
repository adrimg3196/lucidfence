"""HTTP acceptance tests for tenant-isolated geofence CRUD."""
import http.client
import json
import time

import os as _os
HOST = _os.environ.get("LUCIDFENCE_HOST", "127.0.0.1")
PORT = int(_os.environ.get("LUCIDFENCE_PORT", "8765"))


def req(method, path, body=None, cookie=None):
    c = http.client.HTTPConnection(HOST, PORT, timeout=10)
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    data = json.dumps(body).encode() if body is not None else None
    c.request(method, path, body=data, headers=headers)
    r = c.getresponse(); raw = r.read().decode("utf-8", "replace")
    set_cookie = r.getheader("Set-Cookie"); c.close()
    try: payload = json.loads(raw) if raw else {}
    except Exception: payload = {"raw": raw}
    return r.status, payload, set_cookie


def signup(email, password, org_name):
    status, body, cookie = req("POST", "/api/auth/signup", {
        "email": email, "password": password, "name": email, "org_name": org_name,
    })
    assert status == 200 and body.get("ok"), body
    return (cookie or "").split(";")[0], body


def invite_viewer(owner_cookie, email):
    """Owner invites a viewer into their org, returns the viewer's cookie."""
    status, inv, _ = req("POST", "/api/users",
                         {"email": email, "name": email, "role": "viewer"},
                         cookie=owner_cookie)
    assert status == 200 and inv.get("ok"), inv
    status, body, cookie = req("POST", "/api/auth/login",
                               {"email": email, "password": inv["temp_password"]})
    assert status == 200 and body.get("ok"), body
    return (cookie or "").split(";")[0]



def test_geofence_crud_is_tenant_isolated_and_rbac_protected():
    suffix = int(time.time_ns())
    owner, signed = signup(f"fence-owner-{suffix}@test.local", "ownerpass123", f"Fence Org {suffix}")
    payload = {
        "name": "Almacén Norte", "type": "circle",
        "center": {"lat": 40.5001, "lng": -3.7001}, "radius_m": 350,
        "actions": [{"action": "notify", "when": "on_exit", "params": {"msg": "Salida"}}],
    }
    status, created, _ = req("POST", "/api/fences", payload, owner)
    assert status == 200 and created.get("ok"), created
    fence_id = created["fence"]["id"]
    assert any(f["id"] == fence_id for f in created["fences"])

    status, listed, _ = req("GET", "/api/fences", cookie=owner)
    assert status == 200 and any(f["id"] == fence_id for f in listed["fences"]), listed

    viewer = invite_viewer(owner, f"fence-viewer-{suffix}@test.local")
    status, denied, _ = req("POST", "/api/fences", payload, viewer)
    assert status == 403 and denied.get("error"), denied

    other, _ = signup(f"fence-other-{suffix}@test.local", "otherpass123", f"Other Fence Org {suffix}")
    status, other_list, _ = req("GET", "/api/fences", cookie=other)
    assert status == 200 and not any(f["id"] == fence_id for f in other_list["fences"]), other_list

    status, deleted, _ = req("DELETE", f"/api/fences/{fence_id}", cookie=owner)
    assert status == 200 and deleted.get("ok"), deleted
    assert not any(f["id"] == fence_id for f in deleted["fences"])
