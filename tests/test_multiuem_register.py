"""Registro de providers Multi-UEM desde el dashboard: /api/providers.

Cubre el flujo Admin-value de una flota mixta (Applivery móviles + Fleet
portátiles):
  - un owner con engine:config registra dos UEM con su etiqueta de segmento,
  - GET /api/providers los lista con su segmento y flag configured,
  - ningún secreto (api_key/client_secret/…) se re-emite en el GET,
  - un provider no soportado se rechaza con 400,
  - un rol sin engine:config (api key operator) recibe 403 en POST y DELETE,
  - los providers están aislados por tenant (otra org no ve los del primero),
  - cada alta deja rastro hash-chained (provider.registered) en el audit log.

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


def _owner_cookie(tag):
    suffix = int(time.time() * 1000000) % 1000000000
    _, body, ck = req("POST", "/api/auth/signup", {
        "email": f"{tag}-{suffix}@acme.test", "password": "MuemQa123456",
        "name": "Muem QA", "org_name": f"Muem QA {tag} {suffix}",
    })
    if not body.get("ok"):
        raise RuntimeError(f"signup failed: {body}")
    for part in (ck or "").split(","):
        part = part.strip()
        if part.startswith("gf_session="):
            return "gf_session=" + part.split(";", 1)[0].split("=", 1)[1]
    raise RuntimeError(f"gf_session not found in Set-Cookie: {ck!r}")


def _names(providers):
    return {p.get("name") for p in providers}


def test_register_mixed_fleet_permission_isolation_and_audit():
    ck = _owner_cookie("owner")
    FLEET_SECRET = "fleet-tok-SECRET-abc123"

    # baseline: sin conectores
    st, res, _ = req("GET", "/api/providers", cookie=ck)
    assert st == 200 and res.get("providers") == [], res

    # 1. registrar Applivery para móviles
    st, res, _ = req("POST", "/api/providers", {
        "name": "applivery", "api_key": "appl-tok-123", "segment": "móviles",
    }, cookie=ck)
    assert st == 200 and res.get("ok") and res.get("segment") == "móviles", res

    # 2. registrar Fleet para portátiles (endpoint + token)
    st, res, _ = req("POST", "/api/providers", {
        "name": "fleet", "endpoint": "https://fleet.acme.test",
        "api_key": FLEET_SECRET, "segment": "portátiles",
    }, cookie=ck)
    assert st == 200 and res.get("ok") and res.get("registered") == "fleet", res

    # 3. GET lista ambos con su segmento y configured, SIN filtrar el secreto
    st, res, _ = req("GET", "/api/providers", cookie=ck)
    assert st == 200, res
    provs = res.get("providers") or []
    assert _names(provs) == {"applivery", "fleet"}, provs
    by = {p["name"]: p for p in provs}
    assert by["applivery"].get("segment") == "móviles", by["applivery"]
    assert by["fleet"].get("segment") == "portátiles", by["fleet"]
    assert all(p.get("configured") is True for p in provs), provs
    blob = json.dumps(provs)
    assert FLEET_SECRET not in blob, "el secreto NO debe salir en GET /api/providers"
    assert all("secret" not in p and "api_key" not in p for p in provs), provs

    # 4. provider no soportado -> 400
    st, res, _ = req("POST", "/api/providers", {"name": "no_tal_uem"}, cookie=ck)
    assert st == 400, f"provider no soportado debería ser 400, fue {st}: {res}"

    # 5. sin engine:config -> 403 (api key operator) en POST y DELETE
    st, keyres, _ = req("POST", "/api/api-keys", {"name": "muem-op", "role": "operator"}, cookie=ck)
    assert st == 201 and keyres.get("key"), f"no se pudo crear la api key: {st} {keyres}"
    st, res, _ = req("POST", "/api/providers", {"name": "jamf"}, bearer=keyres["key"])
    assert st == 403, f"operator sin engine:config debería ser 403 en POST, fue {st}: {res}"
    st, res, _ = req("DELETE", "/api/providers/applivery", bearer=keyres["key"])
    assert st == 403, f"operator sin engine:config debería ser 403 en DELETE, fue {st}: {res}"

    # el intento del operador NO borró nada
    st, res, _ = req("GET", "/api/providers", cookie=ck)
    assert _names(res.get("providers") or []) == {"applivery", "fleet"}, res

    # 6. aislamiento por tenant: otra org no ve los providers del primero
    ck2 = _owner_cookie("other")
    st, res, _ = req("GET", "/api/providers", cookie=ck2)
    assert st == 200 and (res.get("providers") or []) == [], f"fuga entre tenants: {res}"

    # 7. rastro hash-chained en el audit log del primer tenant
    st, audit, _ = req("GET", "/api/audit", cookie=ck)
    assert st == 200, audit
    events = audit.get("events") if isinstance(audit, dict) else []
    regs = [e for e in (events or []) if e.get("event") == "provider.registered"]
    assert {e.get("provider") for e in regs} >= {"applivery", "fleet"}, regs
    assert any(e.get("segment") == "portátiles" for e in regs), regs
    assert (audit.get("integrity") or {}).get("ok") is True, audit.get("integrity")

    # cleanup
    req("DELETE", "/api/providers/applivery", cookie=ck)
    req("DELETE", "/api/providers/fleet", cookie=ck)
    print(f"  multi-UEM register OK · {len(regs)} altas auditadas")


if __name__ == "__main__":
    test_register_mixed_fleet_permission_isolation_and_audit()
    print("\nmulti-UEM register test passed")
