"""Regression: DELETE /api/org RBAC + último-propietario guardrail (gap #33).

Cubre el ciclo de borrado destructivo de org:
  - admin / operator / viewer -> DELETE /api/org -> 403 (org:delete es owner-only)
  - api_key operator -> DELETE /api/org -> 403 (jamás una api_key)
  - owner que es el ÚNICO propietario -> DELETE /api/org -> 400 (guardarraíl)
  - owner con sesión y >1 owner -> 200 y la org desaparece del store
  - lock-in: /api/members/role sigue siendo solo owner+sesión (403 a api_key y no-owner)

Run: python3 tests/run_tests.py  (arranca saas_server.py en 127.0.0.1:8765)
"""
import http.client
import json
import time

H, P = "127.0.0.1", 8765


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


def _signup_owner():
    suffix = int(time.time() * 1000)
    password = "OrgQa123456"
    email = f"orgqa-{suffix}@acme.test"
    _, body, ck = req("POST", "/api/auth/signup", {
        "email": email, "password": password, "name": "Org QA",
        "org_name": f"Org QA {suffix}"})
    assert body.get("ok"), f"signup failed: {body}"
    session = None
    org = None
    for part in (ck or "").split(","):
        part = part.strip()
        if part.startswith("gf_session="):
            session = "gf_session=" + part.split(";", 1)[0].split("=", 1)[1]
        if part.startswith("gf_org="):
            org = part.split(";", 1)[0].split("=", 1)[1]
    assert session and org, f"cookies faltantes en {ck!r}"
    return email, password, session, org


def _login(email, password):
    _, body, ck = req("POST", "/api/auth/login",
                      {"email": email, "password": password})
    assert body.get("ok"), f"login failed for {email}: {body}"
    for part in (ck or "").split(","):
        part = part.strip()
        if part.startswith("gf_session="):
            return "gf_session=" + part.split(";", 1)[0].split("=", 1)[1]
    raise RuntimeError(f"no session cookie for {email}")


def _tenants_loaded():
    st, h, _ = req("GET", "/api/readyz")
    assert st == 200, f"/api/readyz -> {st}"
    return h.get("tenants_loaded", 0)


def test_delete_org_rbac():
    email, password, owner_ck, org = _signup_owner()

    def create_and_login(role):
        st, res, _ = req("POST", "/api/users",
                         {"email": f"{role}-{email}", "name": role, "role": role},
                         cookie=owner_ck)
        assert st == 200 and res.get("ok"), f"create {role}: {st} {res}"
        return _login(f"{role}-{email}", res["temp_password"])

    admin_ck = create_and_login("admin")
    operator_ck = create_and_login("operator")
    viewer_ck = create_and_login("viewer")

    # api key con rol operator
    st, keyres, _ = req("POST", "/api/api-keys",
                        {"name": "org-operator", "role": "operator"}, cookie=owner_ck)
    assert st == 201 and keyres.get("key"), f"api key: {st} {keyres}"
    api_bearer = keyres["key"]

    before = _tenants_loaded()

    # 1. roles sin org:delete -> 403 con campo capability
    for ck, label in ((admin_ck, "admin"), (operator_ck, "operator"),
                      (viewer_ck, "viewer")):
        st, res, _ = req("DELETE", "/api/org", cookie=ck)
        assert st == 403, f"{label} DELETE /api/org debe ser 403, fue {st}: {res}"
        assert res.get("capability") == "org:delete", f"{label} capability: {res}"
        assert "org" not in str(res.get("org_id", "")), "no debe filtrar datos"

    # 2. api_key jamás puede borrar org -> 403 con capability
    st, res, _ = req("DELETE", "/api/org", bearer=api_bearer)
    assert st == 403, f"api_key DELETE /api/org debe ser 403, fue {st}: {res}"
    assert res.get("capability") == "org:delete", f"api_key capability: {res}"

    # 3. único propietario -> guardarraíl 400, org intacta
    st, res, _ = req("DELETE", "/api/org", cookie=owner_ck)
    assert st == 400, f"único owner DELETE debe ser 400, fue {st}: {res}"
    assert res.get("capability") == "org:delete", f"guardrail capability: {res}"
    assert _tenants_loaded() == before, "la org no debió borrarse con el guardarraíl"

    # 4. lock-in: /api/members/role sigue siendo solo owner+sesión
    st, res, _ = req("POST", "/api/members/role",
                     {"email": f"viewer-{email}", "role": "operator"},
                     bearer=api_bearer)
    assert st == 403, f"api_key members/role debe ser 403: {st} {res}"
    st, res, _ = req("POST", "/api/members/role",
                     {"email": f"viewer-{email}", "role": "operator"},
                     cookie=viewer_ck)
    assert st == 403, f"viewer members/role debe ser 403: {st} {res}"

    # 5. un 2º propietario habilita el borrado: owner+sesión -> 200 y org borrada
    st, res, _ = req("POST", "/api/users",
                     {"email": f"owner2-{email}", "name": "Owner2", "role": "owner"},
                     cookie=owner_ck)
    assert st == 200 and res.get("ok"), f"create 2nd owner: {st} {res}"
    st, res, _ = req("DELETE", "/api/org", cookie=owner_ck)
    assert st == 200 and res.get("ok"), f"owner DELETE debe ser 200, fue {st}: {res}"
    assert res.get("org_id") == org, f"org_id devuelto {res}"
    assert _tenants_loaded() == before - 1, \
        f"la org debió desaparecer: before={before} after={_tenants_loaded()}"

    print(f"  org:delete RBAC OK · 3x403 rol, 1x403 apikey, 1x400 guardarraíl, 200 borrado")


if __name__ == "__main__":
    test_delete_org_rbac()
    print("\norg RBAC test passed")
