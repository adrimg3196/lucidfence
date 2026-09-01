"""RBAC gestionable desde el dashboard: GET /api/members + POST /api/members/role.

Cubre el ciclo Admin-value nº3 (RBAC visible y gestionable):
  - un propietario lista los miembros de SU org con su rol y su etiqueta,
  - reasigna el rol de un miembro con permiso y el listado lo refleja,
  - un rol inválido se rechaza con 400,
  - una api key operator (sin user:role) no puede ver ni cambiar roles (403),
  - el guardarraíl del último propietario: no se puede degradar al único owner,
  - el cambio deja rastro member.role.changed en el audit log hash-chained.

Run: python3 tests/run_tests.py  (arranca saas_server.py en 127.0.0.1:8765)
"""
import http.client
import json
import os
import time

H, P = "127.0.0.1", int(os.environ.get("LUCIDFENCE_TEST_PORT", "8765"))


def req(method, path, body=None, cookie=None, bearer=None):
    c = http.client.HTTPConnection(H, P, timeout=10)
    h = {"Content-Type": "application/json"}
    if cookie:
        h["Cookie"] = cookie
    if bearer:
        h["Authorization"] = "Bearer " + bearer
    data = json.dumps(body).encode() if body is not None else None
    c.request(method, path, body=data, headers=h)
    r = c.getresponse()
    raw = r.read().decode("utf-8", "replace")
    try:
        out = json.loads(raw) if raw else {}
    except Exception:
        out = {"raw": raw}
    return r.status, out, r.getheader("Set-Cookie")


def _owner_cookie():
    suffix = int(time.time() * 1000)
    _, body, ck = req("POST", "/api/auth/signup", {
        "email": f"rbacqa-{suffix}@acme.test", "password": "RbacQa123456",
        "name": "RBAC QA", "org_name": f"RBAC QA {suffix}",
    })
    if not body.get("ok"):
        raise RuntimeError(f"signup failed: {body}")
    for part in (ck or "").split(","):
        part = part.strip()
        if part.startswith("gf_session="):
            return "gf_session=" + part.split(";", 1)[0].split("=", 1)[1], suffix
    raise RuntimeError(f"gf_session not found in Set-Cookie: {ck!r}")


def test_members_list_role_change_permission_guardrail_and_audit():
    ck, suffix = _owner_cookie()
    owner_email = f"rbacqa-{suffix}@acme.test"
    member_email = f"rbacmember-{suffix}@acme.test"

    # el propietario da de alta un operador en su org
    st, res, _ = req("POST", "/api/users",
                     {"email": member_email, "name": "Miembro QA", "role": "operator"},
                     cookie=ck)
    assert st == 200 and res.get("ok"), f"alta de miembro -> {st}: {res}"

    # 1. listar miembros: aparecen owner + operador, con rol y etiqueta, sin hashes
    st, listing, _ = req("GET", "/api/members", cookie=ck)
    assert st == 200, f"GET /api/members -> {st}: {listing}"
    members = {m["email"]: m for m in listing.get("members", [])}
    assert owner_email in members and member_email in members, members
    assert members[owner_email]["role"] == "owner", members[owner_email]
    assert members[member_email]["role"] == "operator", members[member_email]
    assert members[member_email]["role_label"] == "Operador", members[member_email]
    for m in listing["members"]:
        assert "pw_hash" not in m and "pw_salt" not in m, f"secreto expuesto: {m}"
    assert any(r["id"] == "operator" and r["caps"] for r in listing.get("roles", [])), listing.get("roles")

    # 2. cambiar rol con permiso: operator -> viewer, y el GET lo refleja
    st, chg, _ = req("POST", "/api/members/role",
                     {"email": member_email, "role": "viewer"}, cookie=ck)
    assert st == 200 and chg.get("ok"), f"cambio de rol -> {st}: {chg}"
    assert chg["member"]["role"] == "viewer" and chg["member"]["role_label"] == "Solo lectura", chg
    st, listing, _ = req("GET", "/api/members", cookie=ck)
    assert {m["email"]: m["role"] for m in listing["members"]}[member_email] == "viewer", listing

    # 3. rol inválido -> 400
    st, res, _ = req("POST", "/api/members/role",
                     {"email": member_email, "role": "superuser"}, cookie=ck)
    assert st == 400, f"rol inválido debería ser 400, fue {st}: {res}"

    # 4. sin user:role -> 403 (api key operator no puede ni ver ni cambiar roles)
    st, keyres, _ = req("POST", "/api/api-keys", {"name": "rbac-operator", "role": "operator"}, cookie=ck)
    assert st == 201 and keyres.get("key"), f"no se pudo crear la api key: {st} {keyres}"
    st, res, _ = req("POST", "/api/members/role",
                     {"email": member_email, "role": "operator"}, bearer=keyres["key"])
    assert st == 403, f"operator sin user:role debería ser 403, fue {st}: {res}"
    st, res, _ = req("GET", "/api/members", bearer=keyres["key"])
    assert st == 403, f"operator sin user:invite no debería listar miembros, fue {st}: {res}"

    # 5. guardarraíl: no se puede degradar al único propietario
    owner_id = members[owner_email]["id"]
    st, res, _ = req("POST", "/api/members/role",
                     {"user_id": owner_id, "role": "operator"}, cookie=ck)
    assert st == 400, f"degradar al último owner debería ser 400, fue {st}: {res}"
    st, listing, _ = req("GET", "/api/members", cookie=ck)
    assert {m["email"]: m["role"] for m in listing["members"]}[owner_email] == "owner", \
        f"el owner NO debía cambiar: {listing}"

    # 6. rastro member.role.changed en el audit log hash-chained
    st, audit, _ = req("GET", "/api/audit", cookie=ck)
    assert st == 200, f"/api/audit -> {st}"
    events = audit.get("events") if isinstance(audit, dict) else []
    changes = [e for e in (events or []) if e.get("event") == "member.role.changed"]
    assert changes, f"falta member.role.changed en la auditoría: {events}"
    assert any(e.get("role") == "viewer" and e.get("target_email") == member_email for e in changes), changes
    assert (audit.get("integrity") or {}).get("ok") is True, audit.get("integrity")
    print(f"  RBAC members OK · {len(changes)} cambios de rol auditados")


if __name__ == "__main__":
    test_members_list_role_change_permission_guardrail_and_audit()
    print("\nmembers RBAC test passed")
