"""Security regression tests for scripts/saas_api_op.py (serverless SaaS ops).

Assignee: empresa-security-soc (Security/SOC Bot).

Cubre (según descomposición t_32a3d2b2):
- Rechazo de tenant_id raro (path traversal / inyección de ruta).
- add_fence a un tenant inexistente -> ValueError.
- create_tenant con device sin lat/lng no crashea (usa .get() con fallback).
- Validación de ACTION / firma en main(): en ESTE momento NO EXISTE control de
  autorización ni de firma, por lo que remove_tenant es destructivo y
  desautorizado. Las pruebas de gap se ponen en ROJO a propósito para
  codificar la vulnerabilidad hasta que se implemente el control.

NOTA DE PREMISA (corrección del SOC): el body de la tarea afirmaba que
create_tenant hace `d['lat']/d['lng']` sin `.get()`. Eso YA NO ES CIERTO: el
código actual usa `d.get("lat", fb_lat)` / `d.get("lng", fb_lng)`. Se deja una
prueba de regresión que BLOQUEA volver a un acceso sin .get().

Las pruebas de gap (remove_tenant sin authz, sin firma) DEBEN FALLAR mientras
el control no exista. Cuando el CTO implemente firma HMAC + RBAC por ACTION,
estas pruebas pasarán y la suite volverá a verde.

No arrancan el server: lógica pura, FS mockeado en los límites (mod.BASE = tmp).
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _api_op_module():
    return _load(ROOT / "scripts" / "saas_api_op.py")


def _set_env(**kw):
    for k, v in kw.items():
        os.environ[k] = v


def _clear_env(*keys):
    for k in keys:
        os.environ.pop(k, None)


# --------------------------------------------------------------------------
# Comportamiento SEGURO (debe PASAR hoy)
# --------------------------------------------------------------------------

def test_create_tenant_rechaza_tenant_id_raro():
    """tenant_id con path traversal / inyección debe ser rechazado."""
    mod = _api_op_module()
    for bad in ["a/b", "a;rm", "../x", "a b", "", "a\\b", "../../etc"]:
        try:
            mod._tenant_dir(bad)
            raise AssertionError("tenant_id raro no rechazado: %r" % bad)
        except ValueError:
            pass


def test_add_fence_a_tenant_inexistente_lanza_ValueError():
    """add_fence sobre tenant que no existe debe fallar, no crearlo."""
    mod = _api_op_module()
    tmp = Path(tempfile.mkdtemp())
    mod.BASE = tmp
    try:
        mod.add_fence("no-existe", {"fence": {"id": "f1", "kind": "circle",
                                              "center": {"lat": 1, "lng": 2},
                                              "radius_m": 100}})
        raise AssertionError("add_fence a tenant inexistente no lanzó ValueError")
    except ValueError:
        pass


def test_create_tenant_device_sin_lat_lng_usa_fallback():
    """Regression: create_tenant NUNCA debe indexar d['lat']/d['lng'] sin .get().

    Corrige la premisa de la tarea: el código actual ya usa
    d.get("lat", fb_lat)/d.get("lng", fb_lng). Esta prueba bloquea que se
    reintroduzca el acceso directo (KeyError si falta lat/lng)."""
    mod = _api_op_module()
    tmp = Path(tempfile.mkdtemp())
    mod.BASE = tmp
    # Dispositivo sin lat/lng en absoluto -> debe usar el fallback del centro.
    mod.create_tenant("cliente1", {
        "fleet": [{"id": "d1", "name": "X", "platform": "android"}],
        "fences": [{"id": "hq", "kind": "circle",
                    "center": {"lat": 40.4, "lng": -3.7}, "radius_m": 500}],
    })
    seed = (tmp / "cliente1" / "data" / "fleet_seed.json").read_text(encoding="utf-8")
    data = json.loads(seed)
    assert "waypoints" in data["devices"][0]
    # El waypoint debe haber tomado el fallback del centro de la geocerca.
    wp = data["devices"][0]["waypoints"][0]
    assert wp["lat"] == 40.4 and wp["lng"] == -3.7


def test_create_tenant_sin_fences_usa_fallback_0_0():
    """Sin geocercas, el fallback de coordenadas es (0,0), no crashea."""
    mod = _api_op_module()
    tmp = Path(tempfile.mkdtemp())
    mod.BASE = tmp
    mod.create_tenant("singeo", {"fleet": [{"id": "d1"}], "fences": []})
    seed = json.loads((tmp / "singeo" / "data" / "fleet_seed.json").read_text(encoding="utf-8"))
    wp = seed["devices"][0]["waypoints"][0]
    assert wp["lat"] == 0.0 and wp["lng"] == 0.0


# --------------------------------------------------------------------------
# GAPS DE SEGURIDAD (deben FALLAR hoy -> codifican la vulnerabilidad)
# --------------------------------------------------------------------------

def test_remove_tenant_rechazado_sin_autorizacion_valida():
    """GAP: remove_tenant es destructivo y NO requiere autorización ni firma.

    Simula el intento de borrar un tenant SÓLO por haber seteado las env vars
    del workflow (ACTION/TENANT_ID/PAYLOAD) sin ningún token/firma válido.
    Un SaaS serverless seguro debe RECHAZAR esto. Hoy lo ejecuta -> RED."""
    mod = _api_op_module()
    tmp = Path(tempfile.mkdtemp())
    mod.BASE = tmp
    mod.create_tenant("victim", {"fleet": [{"id": "d1"}], "fences": []})
    tdir = tmp / "victim"
    assert tdir.exists(), "precondición: el tenant debe existir antes del borrado"

    _clear_env("LUCIDFENCE_API_SIGNATURE", "LUCIDFENCE_API_TOKEN",
               "LUCIDFENCE_API_ROLE")
    _set_env(ACTION="remove_tenant", TENANT_ID="victim", PAYLOAD="{}")
    try:
        # Sin autorización válida el control fail-closed debe rechazar y salir
        # con sys.exit(2) (NO exit 0, que enmascararía la denegación como éxito).
        mod.main()
    except SystemExit as exc:
        assert exc.code == 2, f"denegación debe salir con exit(2), salió {exc.code}"
    else:
        raise AssertionError("main() no rechazó la petición sin autorización")
    finally:
        _clear_env("ACTION", "TENANT_ID", "PAYLOAD")

    # Expectativa SEGURA: sin autorización válida, el tenant debe seguir existiendo.
    assert tdir.exists(), (
        "SECURITY GAP: saas_api_op.main() ejecutó remove_tenant SIN NINGÚN "
        "control de autorización ni firma. Cualquiera que pueda setear las env "
        "vars del workflow puede borrar tenants de la vitrina cloud. "
        "Implementar RBAC por ACTION + verificación de firma HMAC."
    )


def test_saas_api_op_no_tiene_verificacion_de_firma():
    """GAP estructural: no existe ninguna función de verificación de firma HMAC.

    Toda operación serverless disparada por workflow_dispatch debe validar una
    firma del solicitante antes de acciones destructivas. Hoy no existe."""
    mod = _api_op_module()
    has_sig = any(
        hasattr(mod, name) for name in
        ("verify_request_signature", "verify_signature", "check_authz",
         "require_authorization", "authorize")
    )
    assert has_sig, (
        "SECURITY GAP: saas_api_op.py no expone ninguna función de "
        "verificación de firma/autorización (verify_request_signature, "
        "check_authz, ...). Remove_tenant y create_tenant corren sin authz."
    )


def test_main_valida_action_con_autorizacion_por_rol():
    """GAP: ACTION se admite si es conocido, pero no se vincula a un rol/authz.

    Un remove_tenant no debería poder ejecutarse solo porque ACTION es una
    cadena conocida; debe requerir un rol con privilegio (p.ej. org:delete)."""
    mod = _api_op_module()
    tmp = Path(tempfile.mkdtemp())
    mod.BASE = tmp
    mod.create_tenant("v2", {"fleet": [{"id": "d1"}], "fences": []})
    tdir = tmp / "v2"
    # Sin rol de privilegio en la env -> debe rechazarse con sys.exit(2).
    _clear_env("LUCIDFENCE_API_ROLE", "LUCIDFENCE_API_SIGNATURE")
    _set_env(ACTION="remove_tenant", TENANT_ID="v2", PAYLOAD="{}",
             LUCIDFENCE_API_ROLE="")  # rol vacío = sin privilegio
    try:
        mod.main()
    except SystemExit as exc:
        assert exc.code == 2, f"denegación por rol debe salir con exit(2), salió {exc.code}"
    else:
        raise AssertionError("main() no rechazó remove_tenant sin rol con privilegio")
    finally:
        _clear_env("ACTION", "TENANT_ID", "PAYLOAD", "LUCIDFENCE_API_ROLE")
    assert tdir.exists(), (
        "SECURITY GAP: remove_tenant se ejecutó sin un rol con privilegio. "
        "Vincular ACTION=remove_tenant a RBAC (p.ej. scope org:delete) firmado."
    )
