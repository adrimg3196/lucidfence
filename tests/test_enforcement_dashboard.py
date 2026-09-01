"""Editar la fase de enforcement desde el dashboard: POST /api/settings/enforcement.

Cubre el ciclo completo del backlog Admin-value:
  - un admin (owner de la org) cambia el modo observe<->enforce con permiso,
  - la persistencia se refleja en /api/settings/status tras el reload del engine,
  - un modo inválido se rechaza con 400,
  - un rol sin engine:config (api key operator) se rechaza con 403,
  - el cambio deja rastro hash-chained en el audit log.

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
        "email": f"enfqa-{suffix}@acme.test", "password": "EnfQa123456",
        "name": "Enf QA", "org_name": f"Enf QA {suffix}",
    })
    if not body.get("ok"):
        raise RuntimeError(f"signup failed: {body}")
    for part in (ck or "").split(","):
        part = part.strip()
        if part.startswith("gf_session="):
            return "gf_session=" + part.split(";", 1)[0].split("=", 1)[1]
    raise RuntimeError(f"gf_session not found in Set-Cookie: {ck!r}")


def test_enforcement_toggle_permission_validation_and_audit():
    ck = _owner_cookie()

    # baseline: el tenant arranca en observe (rollout seguro)
    st, status, _ = req("GET", "/api/settings/status", cookie=ck)
    assert st == 200, f"/api/settings/status -> {st}"
    assert status.get("enforcement", {}).get("mode") == "observe", status.get("enforcement")

    # 1. cambio con permiso: observe -> enforce
    st, res, _ = req("POST", "/api/settings/enforcement", {"mode": "enforce"}, cookie=ck)
    assert st == 200, f"enforce -> {st}: {res}"
    assert res.get("ok") is True and res.get("enforcement", {}).get("mode") == "enforce", res

    # 2. la persistencia se refleja tras el reload del engine
    st, status, _ = req("GET", "/api/settings/status", cookie=ck)
    assert st == 200 and status.get("enforcement", {}).get("mode") == "enforce", status.get("enforcement")

    # 3. modo inválido -> 400
    st, res, _ = req("POST", "/api/settings/enforcement", {"mode": "wipe-everything"}, cookie=ck)
    assert st == 400, f"modo inválido debería ser 400, fue {st}: {res}"

    # 4. sin engine:config -> 403 (api key operator no tiene la capability)
    st, keyres, _ = req("POST", "/api/api-keys", {"name": "enf-operator", "role": "operator"}, cookie=ck)
    assert st == 201 and keyres.get("key"), f"no se pudo crear la api key: {st} {keyres}"
    st, res, _ = req("POST", "/api/settings/enforcement", {"mode": "observe"}, bearer=keyres["key"])
    assert st == 403, f"operator sin engine:config debería ser 403, fue {st}: {res}"

    # el intento del operador NO cambió el modo (sigue en enforce)
    st, status, _ = req("GET", "/api/settings/status", cookie=ck)
    assert status.get("enforcement", {}).get("mode") == "enforce", status.get("enforcement")

    # 5. rastro en el audit log hash-chained
    st, audit, _ = req("GET", "/api/audit", cookie=ck)
    assert st == 200, f"/api/audit -> {st}"
    events = audit.get("events") if isinstance(audit, dict) else []
    changes = [e for e in (events or []) if e.get("event") == "enforcement.mode.changed"]
    assert changes, f"falta el evento enforcement.mode.changed en la auditoría: {events}"
    assert any(e.get("mode") == "enforce" for e in changes), changes
    assert (audit.get("integrity") or {}).get("ok") is True, audit.get("integrity")

    # cleanup: dejar el tenant en observe
    req("POST", "/api/settings/enforcement", {"mode": "observe"}, cookie=ck)
    print(f"  enforcement toggle OK · {len(changes)} cambios auditados")


if __name__ == "__main__":
    test_enforcement_toggle_permission_validation_and_audit()
    print("\nenforcement dashboard test passed")
