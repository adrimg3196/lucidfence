"""El registro declarativo de rutas (lucidfence/saas/routing.py) — SD-1 paso 1.

La interfaz es la superficie de test: todo se ejercita a través del seam
(registro + dispatch), nunca contra la implementación interna. Dos adapters
cruzan el seam: el Handler HTTP real (producción) y el ctx fake de aquí.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import saas_server  # noqa: E402,F401 — importa para registrar las rutas declarativas
from lucidfence.saas import routing  # noqa: E402
from helpers import make_temp_engine  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Las rutas migradas de la cadena `if` al registro, con su capability declarada.
MIGRATED = {
    ("GET", "/api/coverage"): "device:read",
    ("GET", "/api/risk"): "device:read",
    ("GET", "/api/cve"): "device:read",
    ("GET", "/api/pois"): "device:read",
    ("GET", "/api/device-attestation"): "device:read",
    ("GET", "/api/incidents/analytics"): "incident:read",
    ("GET", "/api/fences"): "fence:read",
}


def _ctx(eng, role="viewer", org="org-test", qs=None):
    org_roles = {org: role} if role else {}
    return routing.Ctx(http=None, user={"org_roles": org_roles},
                       org=org, eng=eng, qs=qs or {})


# ---- (1) el registro lista las rutas migradas con método y capability ------

def test_registry_lists_migrated_routes_with_method_and_cap():
    specs = {(s.method, s.path): s.cap for s in saas_server._api_routes.specs()}
    for key, cap in MIGRATED.items():
        assert key in specs, f"falta en el registro: {key}"
        assert specs[key] == cap, f"{key}: cap {specs[key]!r} != {cap!r}"


# ---- (2) invariante de seguridad: toda ruta registrada declara capability --

def test_every_registered_route_declares_a_nonempty_capability():
    specs = saas_server._api_routes.specs()
    assert specs, "el registro del servidor no puede estar vacío"
    for s in specs:
        assert isinstance(s.cap, str) and s.cap.strip(), \
            f"{s.method} {s.path} registrada sin capability"


def test_registering_without_capability_is_rejected():
    reg = routing.RouteRegistry()
    for bad in ("", "   ", None, 0):
        try:
            reg.route("GET", "/x", cap=bad)
            assert False, f"cap={bad!r} debería levantar ValueError"
        except ValueError:
            pass
    # cap es keyword-only y sin default: omitirla ni siquiera compila la llamada.
    try:
        reg.route("GET", "/x")
        assert False, "omitir cap debería levantar TypeError"
    except TypeError:
        pass
    assert reg.specs() == [], "ningún registro inválido debe quedar en la tabla"


def test_duplicate_registration_is_rejected():
    reg = routing.RouteRegistry()
    reg.route("GET", "/x", cap="device:read")(lambda ctx: {})
    try:
        reg.route("GET", "/x", cap="device:read")(lambda ctx: {})
        assert False, "ruta duplicada debería levantar ValueError"
    except ValueError:
        pass


# ---- (3) funcional a través del seam (ctx fake + send capturado) -----------

def test_dispatch_without_permission_returns_canonical_403():
    eng = make_temp_engine()
    sent = []
    handled = saas_server._api_routes.dispatch(
        "GET", "/api/fences", _ctx(eng, role=None),
        send=lambda obj, code=200: sent.append((code, obj)))
    assert handled is True
    assert sent == [(403, {"error": "sin permiso"})], \
        f"403 canónico exacto esperado, got {sent}"


def test_dispatch_with_permission_returns_200_payload():
    eng = make_temp_engine()
    sent = []
    handled = saas_server._api_routes.dispatch(
        "GET", "/api/fences", _ctx(eng, role="viewer"),
        send=lambda obj, code=200: sent.append((code, obj)))
    assert handled is True and len(sent) == 1
    code, payload = sent[0]
    assert code == 200 and isinstance(payload.get("fences"), list), payload


def test_coverage_keeps_stale_after_s_contract_through_the_seam():
    eng = make_temp_engine()
    def call(qs):
        sent = []
        assert saas_server._api_routes.dispatch(
            "GET", "/api/coverage", _ctx(eng, role="viewer", qs=qs),
            send=lambda obj, code=200: sent.append((code, obj)))
        return sent[0]
    code, payload = call({"stale_after_s": ["abc"]})
    assert (code, payload) == (400, {"error": "stale_after_s debe ser entero (segundos)"})
    code, payload = call({"stale_after_s": ["10"]})
    assert (code, payload) == (400, {"error": "stale_after_s fuera de rango (60..2592000)"})
    code, payload = call({})
    assert code == 200 and "resumen" in payload, payload


def test_unregistered_route_falls_through_without_sending():
    eng = make_temp_engine()
    sent = []
    handled = saas_server._api_routes.dispatch(
        "GET", "/api/no-existe", _ctx(eng),
        send=lambda obj, code=200: sent.append((code, obj)))
    assert handled is False and sent == [], \
        "una ruta no registrada debe caer a la cadena legacy sin responder"
    # método distinto sobre ruta registrada: tampoco es del registro
    handled = saas_server._api_routes.dispatch(
        "POST", "/api/coverage", _ctx(eng),
        send=lambda obj, code=200: sent.append((code, obj)))
    assert handled is False and sent == []


# ---- (4) sin duplicación: las migradas ya no viven en la cadena `if` -------

def test_migrated_routes_left_the_if_chain():
    src = open(os.path.join(ROOT, "saas_server.py"), encoding="utf-8").read()
    for path in ("/api/coverage", "/api/risk", "/api/cve",
                 "/api/pois", "/api/incidents/analytics"):
        assert f'route == "{path}"' not in src, \
            f"{path} sigue en la cadena `if` además de en el registro"
    # /api/fences: el GET migró; la única mención restante es la rama POST.
    assert src.count('route == "/api/fences"') == 1, \
        "solo la rama POST de /api/fences debe seguir en la cadena"


if __name__ == "__main__":
    for name in sorted(n for n in dir() if n.startswith("test_")):
        globals()[name]()
    print("PASS")
