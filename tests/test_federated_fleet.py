"""Panel único multi-UEM (backlog §12): la vista federada de la flota.

Dos capas, mismas garantías que el resto del repo:
- `core/federated_fleet.py` (función pura): dos providers con perfiles
  distintos aparecen en UNA lista con origen trazado, riesgo comparable
  (el veredicto del engine, nunca recalculado) y honestidad con lo
  desconocido (null, jamás inventado ni penalizado).
- `GET /api/fleet/federated` a través del seam real de rutas de
  `saas_server.py` (RouteRegistry): gating device:read, filtro por provider,
  aislamiento por tenant.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import saas_server  # noqa: E402 — registra las rutas declarativas reales
from helpers import make_temp_engine  # noqa: E402
from lucidfence.core.federated_fleet import (  # noqa: E402
    build_federated_fleet,
    valid_provider_filter,
)
from lucidfence.core.state_store import DeviceState  # noqa: E402
from lucidfence.saas import routing  # noqa: E402
from lucidfence.saas.providers import save_providers  # noqa: E402
from lucidfence.saas.tenant import TenantStore  # noqa: E402


# ---------------------------------------------------------------- función pura

def _device(device_id, name, platform, refs, **kw):
    d = {"device_id": device_id, "name": name, "platform": platform,
         "provider_refs": refs, "compliant": kw.pop("compliant", True),
         "fence_state": kw.pop("fence_state", "inside"),
         "last_seen": kw.pop("last_seen", "2026-08-25T10:00:00+00:00")}
    d.update(kw)
    return d


def _risk(device_id, score, level, labels):
    return {"device_id": device_id, "score": score, "level": level,
            "factors": [{"points": 0, "label": x, "severity": level} for x in labels]}


PROVIDERS = [{"name": "intune", "segment": "portátiles"},
             {"name": "jamf", "segment": "móviles"}]


def test_two_providers_federate_into_single_fleet_with_traced_origin():
    devices = [
        _device("win-1", "Portátil Ventas", "windows", {"intune": "guid-1"}),
        _device("mac-1", "MacBook Diseño", "macos", {"jamf": "jamf-9"}),
    ]
    risk = [_risk("win-1", 60.0, "high", ["dispositivo no conforme", "fuera de geocerca permitida"]),
            _risk("mac-1", 5.0, "low", [])]
    out = build_federated_fleet(devices, risk, PROVIDERS)
    assert out["total"] == out["fleet_total"] == 2
    by_id = {r["device_id"]: r for r in out["fleet"]}
    assert by_id["win-1"]["provider"] == "intune"
    assert by_id["win-1"]["segment"] == "portátiles"
    assert by_id["mac-1"]["provider"] == "jamf"
    assert by_id["mac-1"]["segment"] == "móviles"
    # riesgo comparable: mismo veredicto (score+nivel) del engine para ambos,
    # en la misma escala, ordenado de mayor a menor.
    assert [r["device_id"] for r in out["fleet"]] == ["win-1", "mac-1"]
    assert by_id["win-1"]["risk"] == {"score": 60.0, "level": "high"}
    assert by_id["mac-1"]["risk"] == {"score": 5.0, "level": "low"}
    counts = {p["name"]: p["devices"] for p in out["providers"]}
    assert counts == {"intune": 1, "jamf": 1}
    assert out["sin_origen"] == 0


def test_risk_is_engine_verdict_verbatim_with_top_reasons():
    devices = [_device("d1", "Uno", "android", {"intune": "x"})]
    labels = ["razón A", "razón B", "razón C", "razón D"]
    out = build_federated_fleet(devices, [_risk("d1", 42.5, "medium", labels)], PROVIDERS)
    row = out["fleet"][0]
    # el panel NO recalcula: score y nivel llegan tal cual del engine y las
    # razones top son las 3 primeras del explain, en su orden.
    assert row["risk"] == {"score": 42.5, "level": "medium"}
    assert row["top_reasons"] == ["razón A", "razón B", "razón C"]


def test_unknown_fields_stay_null_and_never_penalize():
    devices = [
        # sin plataforma, sin provider_refs, sin fila de riesgo del engine
        {"device_id": "ghost-1", "name": "Sin datos", "provider_refs": {}},
        _device("ok-1", "Con señal", "linux", {"intune": "y"}),
    ]
    out = build_federated_fleet(devices, [_risk("ok-1", 10.0, "low", [])], PROVIDERS)
    by_id = {r["device_id"]: r for r in out["fleet"]}
    ghost = by_id["ghost-1"]
    assert ghost["platform"] is None
    assert ghost["provider"] is None and ghost["segment"] is None
    assert ghost["providers"] == []
    # riesgo desconocido = null, jamás un 0/100 inventado…
    assert ghost["risk"] == {"score": None, "level": None}
    assert ghost["top_reasons"] == []
    # …y lo desconocido no compite con señal real: va al final, no penaliza
    # ni asciende en el ranking.
    assert [r["device_id"] for r in out["fleet"]] == ["ok-1", "ghost-1"]
    assert out["sin_origen"] == 1


def test_provider_filter_reduces_fleet_but_keeps_honest_totals():
    devices = [
        _device("win-1", "Uno", "windows", {"intune": "a"}),
        _device("mac-1", "Dos", "macos", {"jamf": "b"}),
    ]
    risk = [_risk("win-1", 30.0, "medium", []), _risk("mac-1", 20.0, "medium", [])]
    out = build_federated_fleet(devices, risk, PROVIDERS, provider="jamf")
    assert [r["device_id"] for r in out["fleet"]] == ["mac-1"]
    assert out["total"] == 1 and out["fleet_total"] == 2
    assert out["filter"] == {"provider": "jamf"}
    # el resumen por provider no cambia con el filtro: sigue contando la flota
    # completa (si cambiara, el chip del filtro mentiría sobre lo que hay).
    counts = {p["name"]: p["devices"] for p in out["providers"]}
    assert counts == {"intune": 1, "jamf": 1}


def test_consolidated_device_traces_every_origin():
    devices = [_device("dual-1", "Doble UEM", "macos",
                       {"jamf": "j-1", "intune": "i-1"})]
    out = build_federated_fleet(devices, [_risk("dual-1", 15.0, "low", [])], PROVIDERS)
    row = out["fleet"][0]
    assert [p["name"] for p in row["providers"]] == ["intune", "jamf"]
    # el filtro por CUALQUIERA de sus orígenes lo encuentra
    for name in ("intune", "jamf"):
        got = build_federated_fleet(devices, [], PROVIDERS, provider=name)
        assert [r["device_id"] for r in got["fleet"]] == ["dual-1"], name


def test_unregistered_origin_is_still_traced_without_inventing_segment():
    # un provider que reportó dispositivos pero ya no está en el registro del
    # tenant: el origen se traza igual (es un hecho), el segmento queda null.
    devices = [_device("x-1", "Huérfano", "linux", {"fleet": "f-1"})]
    out = build_federated_fleet(devices, [], PROVIDERS)
    row = out["fleet"][0]
    assert row["provider"] == "fleet" and row["segment"] is None
    counts = {p["name"]: p["devices"] for p in out["providers"]}
    assert counts.get("fleet") == 1


def test_valid_provider_filter_contract():
    for ok in ("intune", "jamf", "workspace_one", "a1"):
        assert valid_provider_filter(ok), ok
    for bad in ("", "  ", "INTUNE", "1abc", "in tune", "a" * 65, None, 3, "ñu"):
        assert not valid_provider_filter(bad), bad


# ---------------------------------------------------- endpoint a través del seam

def _ctx(eng, role="viewer", org="org-fed", qs=None):
    org_roles = {org: role} if role else {}
    return routing.Ctx(http=None, user={"org_roles": org_roles},
                       org=org, eng=eng, qs=qs or {})


def _dispatch(eng, role="viewer", org="org-fed", qs=None):
    sent = []
    handled = saas_server._api_routes.dispatch(
        "GET", "/api/fleet/federated", _ctx(eng, role=role, org=org, qs=qs),
        send=lambda obj, code=200: sent.append((code, obj)))
    assert handled is True
    return sent[0]


def _seed_two_uem_fleet(eng):
    eng.store.upsert(DeviceState(
        device_id="win-fed", name="Portátil QA", platform="windows",
        compliant=False, fence_state="outside",
        provider_refs={"intune": "guid-win"}))
    eng.store.upsert(DeviceState(
        device_id="mac-fed", name="MacBook QA", platform="macos",
        compliant=True, fence_state="inside",
        provider_refs={"jamf": "jamf-mac"}))


def test_endpoint_federates_two_uems_with_engine_verdict_and_segments():
    eng = make_temp_engine()
    _seed_two_uem_fleet(eng)
    with tempfile.TemporaryDirectory(prefix="lf-fed-") as td:
        ts = TenantStore(Path(td))
        org = ts.create(name="fed-org", owner_id="owner-fed")
        save_providers(ts.data_dir(org.id),
                       [{"name": "intune", "segment": "portátiles", "secret": "s3cr3t"},
                        {"name": "jamf", "segment": "móviles"}])
        old = saas_server._tenants
        saas_server._tenants = ts
        try:
            code, payload = _dispatch(eng, org=org.id)
        finally:
            saas_server._tenants = old
    assert code == 200
    by_id = {r["device_id"]: r for r in payload["fleet"]}
    assert set(by_id) == {"win-fed", "mac-fed"}
    assert by_id["win-fed"]["provider"] == "intune"
    assert by_id["win-fed"]["segment"] == "portátiles"
    assert by_id["mac-fed"]["provider"] == "jamf"
    assert by_id["mac-fed"]["segment"] == "móviles"
    # riesgo comparable: el MISMO engine puntúa ambos perfiles (0..100 + nivel)
    # y el perfil incumplidor/fuera puntúa más alto que el sano/dentro.
    for row in by_id.values():
        assert isinstance(row["risk"]["score"], (int, float))
        assert row["risk"]["level"] in ("low", "medium", "high", "critical")
    assert by_id["win-fed"]["risk"]["score"] > by_id["mac-fed"]["risk"]["score"]
    assert by_id["win-fed"]["top_reasons"], "el explain del engine debe viajar"
    # las credenciales del registro jamás viajan en la respuesta
    assert "s3cr3t" not in repr(payload)


def test_endpoint_provider_filter_works_and_invalid_filter_is_400():
    eng = make_temp_engine()
    _seed_two_uem_fleet(eng)
    code, payload = _dispatch(eng, qs={"provider": ["jamf"]})
    assert code == 200
    assert [r["device_id"] for r in payload["fleet"]] == ["mac-fed"]
    assert payload["fleet_total"] == 2
    code, payload = _dispatch(eng, qs={"provider": ["NO VÁLIDO"]})
    assert code == 400 and "provider" in payload.get("error", "")


def test_endpoint_without_permission_returns_canonical_403():
    eng = make_temp_engine()
    code, payload = _dispatch(eng, role=None)
    assert (code, payload) == (403, {"error": "sin permiso"})


def test_endpoint_is_tenant_scoped():
    eng_a = make_temp_engine(org_name="tenant-a")
    eng_b = make_temp_engine(org_name="tenant-b")
    _seed_two_uem_fleet(eng_a)
    eng_b.store.upsert(DeviceState(
        device_id="only-b", name="Solo B", platform="linux",
        provider_refs={"fleet": "fl-1"}))
    code_a, pay_a = _dispatch(eng_a, org="org-a")
    code_b, pay_b = _dispatch(eng_b, org="org-b")
    assert code_a == 200 and code_b == 200
    ids_a = {r["device_id"] for r in pay_a["fleet"]}
    ids_b = {r["device_id"] for r in pay_b["fleet"]}
    assert ids_a == {"win-fed", "mac-fed"} and ids_b == {"only-b"}
    assert not (ids_a & ids_b), "un tenant no puede ver dispositivos de otro"


if __name__ == "__main__":
    for name in sorted(n for n in dir() if n.startswith("test_")):
        globals()[name]()
    print("PASS")
