"""Auditor de mínimo privilegio de credenciales UEM (backlog §16).

Dos capas, las mismas garantías que el resto del repo:
- `core/least_privilege.py` (función pura): un token con scopes de escritura en
  modo observe produce el aviso; con scopes mínimos, silencio; y lo desconocido
  no penaliza NI tranquiliza (tercer estado explícito).
- `GET /api/least-privilege` a través del seam real de rutas de `saas_server.py`
  (RouteRegistry): gating engine:config, aislamiento por tenant y la garantía
  dura de que la credencial nunca viaja en la respuesta.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import saas_server  # noqa: E402 — registra las rutas declarativas reales
from helpers import make_temp_engine  # noqa: E402
from lucidfence.core.least_privilege import (  # noqa: E402
    least_privilege_report,
    normalize_declared_scopes,
)
from lucidfence.saas import routing  # noqa: E402
from lucidfence.saas.providers import save_providers  # noqa: E402
from lucidfence.saas.tenant import TenantStore  # noqa: E402

OBSERVE = {"mode": "observe", "live_actions": "all", "allow_wipe": False}
ENFORCE_MSG = {"mode": "enforce", "live_actions": ["message"], "allow_wipe": False}

WRITE_TOKEN = [{"id": "uem.devices.read", "grants": ["read"]},
               {"id": "uem.devices.command", "grants": ["wipe", "lock"]}]
READ_TOKEN = [{"id": "uem.devices.read", "grants": ["read"]}]


# ---------------------------------------------------------------- función pura

def test_write_scopes_in_observe_mode_raise_the_warning():
    # El caso literal del backlog: el token puede wipear y el tenant está en
    # observe, donde no sale NI UNA acción en vivo.
    out = least_privilege_report(
        [{"name": "simulation", "scopes": WRITE_TOKEN}], OBSERVE)
    row = out["providers"][0]
    assert row["veredicto"] == "exceso"
    assert [e["scope"] for e in row["exceso"]] == ["uem.devices.command"]
    exceso = row["exceso"][0]
    assert exceso["grants"] == ["lock", "wipe"]
    assert exceso["severity"] == "critical", "wipe es irreversible"
    assert "observe" in exceso["why"] and "wipe" in exceso["why"]
    # el scope de lectura sobrevive a la recomendación: leer es el producto
    assert row["scopes_recomendados"] == ["uem.devices.read"]
    assert out["resumen"]["providers_con_exceso"] == 1
    assert out["resumen"]["scopes_excesivos"] == 1


def test_minimum_scopes_are_silence():
    out = least_privilege_report(
        [{"name": "simulation", "scopes": READ_TOKEN}], OBSERVE)
    row = out["providers"][0]
    assert row["veredicto"] == "correcto"
    assert row["exceso"] == []
    assert row["scopes_recomendados"] == ["uem.devices.read"]
    assert out["resumen"] == {"providers_total": 1, "providers_auditables": 1,
                              "providers_no_auditables": 0, "providers_con_exceso": 0,
                              "providers_correctos": 1, "scopes_excesivos": 0}


def test_enforce_mode_needs_only_its_live_actions():
    scopes = [{"id": "s-msg", "grants": ["message"]},
              {"id": "s-wipe", "grants": ["wipe"]}]
    out = least_privilege_report([{"name": "intune", "scopes": scopes}], ENFORCE_MSG)
    row = out["providers"][0]
    # message SÍ se usa (está en live_actions) -> no es exceso.
    assert [e["scope"] for e in row["exceso"]] == ["s-wipe"]
    assert "allow_wipe=false" in row["exceso"][0]["why"]
    assert row["scopes_recomendados"] == ["s-msg"]


def test_wipe_stops_being_excess_only_with_the_double_key():
    scopes = [{"id": "s-wipe", "grants": ["wipe"]}]
    enf = {"mode": "enforce", "live_actions": ["wipe"], "allow_wipe": True}
    out = least_privilege_report([{"name": "intune", "scopes": scopes}], enf)
    assert out["providers"][0]["veredicto"] == "correcto"
    # …y con la doble llave cerrada vuelve a sobrar.
    enf_cerrado = dict(enf, allow_wipe=False)
    out2 = least_privilege_report([{"name": "intune", "scopes": scopes}], enf_cerrado)
    assert out2["providers"][0]["veredicto"] == "exceso"


def test_action_the_adapter_cannot_drive_is_excess_even_in_enforce():
    # chromeos declara actions=frozenset(): LucidFence no ejecuta NADA contra
    # él, así que un token con permiso de wipe sobra aunque el tenant enforce.
    scopes = [{"id": "s-wipe", "grants": ["wipe"]}]
    enf = {"mode": "enforce", "live_actions": "all", "allow_wipe": True}
    out = least_privilege_report([{"name": "chromeos", "scopes": scopes}], enf)
    row = out["providers"][0]
    assert row["veredicto"] == "exceso"
    assert "no la ejecuta contra este UEM" in row["exceso"][0]["why"]


def test_unknown_scopes_neither_reassure_nor_penalize():
    # El UEM no expone qué concede el scope: no es "correcto" ni es "exceso".
    out = least_privilege_report(
        [{"name": "jamf", "scopes": ["Privileged.Operations.All"]}], OBSERVE)
    row = out["providers"][0]
    assert row["veredicto"] == "no_auditable"
    assert row["exceso"] == [], "lo desconocido nunca se acusa"
    assert row["scopes_sin_clasificar"][0]["scope"] == "Privileged.Operations.All"
    res = out["resumen"]
    # y sobre todo: no infla el denominador de lo auditado.
    assert res["providers_auditables"] == 0 and res["providers_correctos"] == 0
    assert res["providers_no_auditables"] == 1 and res["providers_con_exceso"] == 0


def test_no_scopes_and_no_credential_are_distinct_honest_reasons():
    out = least_privilege_report([
        {"name": "jamf", "configured": False},
        {"name": "intune", "configured": True},
    ], OBSERVE)
    sin_cred, sin_scopes = out["providers"]
    assert sin_cred["veredicto"] == sin_scopes["veredicto"] == "no_auditable"
    assert "sin credencial configurada" in sin_cred["motivo"]
    assert "no expone los scopes" in sin_scopes["motivo"]
    assert out["resumen"]["providers_auditables"] == 0


def test_proven_excess_survives_an_unclassifiable_scope():
    # Un scope opaco no puede tapar un hallazgo real: el veredicto es exceso y
    # lo no clasificado se sigue listando.
    scopes = [{"id": "s-wipe", "grants": ["wipe"]}, "Opaco.All"]
    out = least_privilege_report([{"name": "jamf", "scopes": scopes}], OBSERVE)
    row = out["providers"][0]
    assert row["veredicto"] == "exceso"
    assert [e["scope"] for e in row["exceso"]] == ["s-wipe"]
    assert [s["scope"] for s in row["scopes_sin_clasificar"]] == ["Opaco.All"]


def test_documented_minimum_permission_travels_as_data():
    out = least_privilege_report(
        [{"name": "fleet", "scopes": READ_TOKEN,
          "min_permission": "Usuario API con rol observer (solo lectura)"}], OBSERVE)
    assert out["providers"][0]["min_permission_documentada"] == \
        "Usuario API con rol observer (solo lectura)"


def test_report_echoes_the_enforcement_it_audited_against():
    out = least_privilege_report([{"name": "simulation", "scopes": READ_TOKEN}], OBSERVE)
    assert out["enforcement"] == {"mode": "observe", "live_actions": "all",
                                  "allow_wipe": False}


def test_normalize_declared_scopes_keeps_only_auditable_shape():
    assert normalize_declared_scopes([{"id": "a", "grants": ["read"]}]) == \
        [{"id": "a", "grants": ["read"]}]
    # sin id no hay scope; sin grants el scope existe pero no dice qué concede
    assert normalize_declared_scopes([{"grants": ["wipe"]}]) == []
    assert normalize_declared_scopes([{"id": "b"}]) == [{"id": "b"}]
    for basura in (None, "read", 7, [1, 2], [None]):
        assert normalize_declared_scopes(basura) == [], basura


# ---------------------------------------------------- endpoint a través del seam

def _ctx(eng, role="owner", org="org-lp", qs=None):
    org_roles = {org: role} if role else {}
    return routing.Ctx(http=None, user={"org_roles": org_roles},
                       org=org, eng=eng, qs=qs or {})


def _dispatch(eng, role="owner", org="org-lp"):
    sent = []
    handled = saas_server._api_routes.dispatch(
        "GET", "/api/least-privilege", _ctx(eng, role=role, org=org),
        send=lambda obj, code=200: sent.append((code, obj)))
    assert handled is True
    return sent[0]


def _with_registry(providers, fn):
    """Corre `fn(org_id)` con un TenantStore temporal que tiene esos providers."""
    with tempfile.TemporaryDirectory(prefix="lf-lp-") as td:
        ts = TenantStore(Path(td))
        org = ts.create(name="lp-org", owner_id="owner-lp")
        save_providers(ts.data_dir(org.id), providers)
        old = saas_server._tenants
        saas_server._tenants = ts
        try:
            return fn(org.id)
        finally:
            saas_server._tenants = old


def test_endpoint_warns_about_a_write_token_in_observe_mode():
    eng = make_temp_engine()
    assert eng.enforcement_status()["mode"] == "observe"
    code, payload = _with_registry(
        [{"name": "simulation", "segment": "portátiles", "scopes": WRITE_TOKEN}],
        lambda org: _dispatch(eng, org=org))
    assert code == 200
    row = payload["providers"][0]
    assert row["provider"] == "simulation" and row["veredicto"] == "exceso"
    assert row["exceso"][0]["severity"] == "critical"
    assert payload["enforcement"]["mode"] == "observe"


def test_endpoint_never_leaks_the_credential():
    eng = make_temp_engine()
    provider = {"name": "intune", "scopes": WRITE_TOKEN, "secret": "s3cr3t-lp",
                "client_secret": "otro-s3cr3t", "tenant_id": "t-1"}
    code, payload = _with_registry([provider], lambda org: _dispatch(eng, org=org))
    assert code == 200
    assert "s3cr3t" not in repr(payload), "la credencial jamás viaja en la respuesta"
    assert "otro-s3cr3t" not in repr(payload)


def test_endpoint_without_engine_config_returns_canonical_403():
    eng = make_temp_engine()
    # viewer puede leer dispositivos (device:read) pero NO configurar el engine:
    # la postura de credenciales solo la ve quien puede recortar el token.
    for role in ("viewer", "operator", None):
        assert _dispatch(eng, role=role) == (403, {"error": "sin permiso"}), role


def test_endpoint_is_tenant_scoped():
    eng = make_temp_engine()
    with tempfile.TemporaryDirectory(prefix="lf-lp-iso-") as td:
        ts = TenantStore(Path(td))
        org_a = ts.create(name="lp-a", owner_id="owner-a")
        org_b = ts.create(name="lp-b", owner_id="owner-b")
        save_providers(ts.data_dir(org_a.id), [{"name": "intune", "scopes": WRITE_TOKEN}])
        save_providers(ts.data_dir(org_b.id), [{"name": "jamf", "scopes": READ_TOKEN}])
        old = saas_server._tenants
        saas_server._tenants = ts
        try:
            code_a, pay_a = _dispatch(eng, org=org_a.id)
            code_b, pay_b = _dispatch(eng, org=org_b.id)
        finally:
            saas_server._tenants = old
    assert code_a == 200 and code_b == 200
    assert [r["provider"] for r in pay_a["providers"]] == ["intune"]
    assert [r["provider"] for r in pay_b["providers"]] == ["jamf"]
    assert pay_a["resumen"]["providers_con_exceso"] == 1
    assert pay_b["resumen"]["providers_con_exceso"] == 0


def test_endpoint_reports_zero_excess_without_claiming_all_is_well():
    # Registro sin scopes declarados: 0 excesos, pero 0 auditables — el
    # denominador impide leerlo como "todo correcto".
    eng = make_temp_engine()
    code, payload = _with_registry([{"name": "jamf", "secret": "x" * 12}],
                                   lambda org: _dispatch(eng, org=org))
    assert code == 200
    res = payload["resumen"]
    assert res["providers_con_exceso"] == 0
    assert res["providers_auditables"] == 0 and res["providers_no_auditables"] == 1
    assert payload["providers"][0]["veredicto"] == "no_auditable"


if __name__ == "__main__":
    for name in sorted(n for n in dir() if n.startswith("test_")):
        globals()[name]()
    print("PASS")


def test_declared_scopes_do_not_leak_through_the_providers_listing():
    """El veredicto está tras `engine:config` porque delata qué tokens pueden
    wipear. De los NOMBRES de scope ese veredicto se deriva trivialmente, así
    que GET /api/providers (sin cap propia, visible a viewer) no puede
    servirlos: sería el mismo dato por la puerta de atrás. Regresión de la
    fuga que introdujo esta misma feature al persistir `scopes`.
    """
    import saas_server as srv
    crudo = {"name": "intune", "scopes": WRITE_TOKEN, "secret": "s3cr3t-lp",
             "segment": "portátiles"}
    enmascarado = srv._masked_provider(crudo)
    assert "scopes" not in enmascarado, enmascarado
    assert "s3cr3t-lp" not in repr(enmascarado)
    # Y lo que sí debe seguir viajando no se rompe:
    assert enmascarado["name"] == "intune"
    assert enmascarado["segment"] == "portátiles"
    assert enmascarado["configured"] is True

