"""Enrutado declarativo consistente entre las dos rutas de dispatch (issue #205).

El bug: `Engine._execute_action` ejecutaba SIEMPRE de forma imperativa en la
ruta single-provider (la del dashboard de un tenant normal), mientras la ruta
multi-UEM despachaba por su propio criterio. El MISMO dispositivo Apple recibía
un comando distinto según el camino interno de código.

Lo que se ancla aquí:
  (a) la vía la decide `ddm.declarative_path_for` — capacidad del adapter +
      capacidad del dispositivo + equivalente declarativo modelado + perfil
      aportado; dato desconocido => imperativo (el comportamiento de hoy);
  (b) las DOS rutas dan el mismo veredicto para el mismo caso;
  (c) el enrutado cambia el TRANSPORTE, jamás el gating: wipe con doble llave,
      observe/enforce y `live_actions` se aplican ANTES de elegir vía y siguen
      valiendo igual por las dos;
  (d) el catálogo de conectores expone la capacidad declarativa DERIVADA del
      adapter, no una lista escrita a mano.

Offline: sin credenciales ni red (los adapters usados son mock/registro).

Run via the runner:  python3 tests/run_tests.py
Run directly:        python3 tests/test_declarative_routing.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core import ddm  # noqa: E402
from lucidfence.core.adapters import ADAPTER_REGISTRY  # noqa: E402
from lucidfence.core.adapters.jamf import JamfAdapter  # noqa: E402
from lucidfence.core.multiuem import (  # noqa: E402
    MultiUEMOrchestrator,
    ProviderBinding,
    ProviderCapabilities,
)
from lucidfence.core.state_store import DeviceState  # noqa: E402
from lucidfence.saas.providers import catalog, declarative_support  # noqa: E402
from helpers import make_temp_engine  # noqa: E402

#: Lo mínimo que exige `com.apple.configuration.legacy` para poder construir
#: las declarations: la policy y el perfil https que las transporta.
DDM_PARAMS = {
    "policy": {"id": "pol-geofence"},
    "profile_url": "https://mdm.example.com/profiles/geofence-hq.mobileconfig",
}


class _RecordingAdapter:
    """Adapter falso que captura (action, dry_run) sin tocar red."""

    name = "recording"
    supports_ddm = False

    def __init__(self, supports_ddm: bool = False):
        self.supports_ddm = supports_ddm
        self.calls: list[tuple] = []

    def execute(self, device, action, params, dry_run=False):
        self.calls.append((action, dry_run))
        return {"ok": True, "adapter": self.name, "action": action,
                "device_id": getattr(device, "device_id", ""), "dry_run": dry_run}


def _apple_ddm_device(device_id="dev-mac", refs=None):
    """macOS 14.5: plataforma y versión por encima del mínimo DDM (13.0)."""
    return DeviceState(device_id=device_id, name="MacBook QA", platform="macos",
                       os_version="14.5", fence_state="outside",
                       provider_refs=refs or {})


def _legacy_device(device_id="dev-old"):
    """iOS 12.4: Apple, pero por debajo del mínimo DDM (15.0)."""
    return DeviceState(device_id=device_id, name="iPhone viejo", platform="ios",
                       os_version="12.4", fence_state="outside")


def _unknown_os_device(device_id="dev-unknown"):
    """Apple sin `os_version`: dato desconocido, jamás se adivina capacidad."""
    return DeviceState(device_id=device_id, name="iPad sin readback",
                       platform="ipados", fence_state="outside")


def _engine(adapter, enforcement=None):
    eng = make_temp_engine(
        cooldown_seconds=0,
        extra_config={"enforcement": enforcement} if enforcement else None)
    eng.adapter = adapter
    eng.orchestrator = None
    return eng


def _engine_multiuem(adapter, enforcement=None, provider="jamf"):
    """Mismo engine, pero por la ruta del orquestador multi-UEM.

    El binding reusa el `execute` del MISMO adapter, así que cualquier
    diferencia de comando entre las dos rutas es del enrutado, no del UEM.
    """
    eng = _engine(adapter, enforcement)
    eng.orchestrator = MultiUEMOrchestrator([ProviderBinding(
        name=provider,
        capabilities=ProviderCapabilities(actions=frozenset({
            "lock", "wipe", "message", "locate", "reboot", "clear_passcode",
            "apply_ddm",
        })),
        fetch_devices=lambda: [],
        execute_action=lambda remote_id, action, params, dry_run: adapter.execute(
            {"device_id": remote_id}, action, params, dry_run),
    )])
    return eng


# ---- (a) la decisión pura -------------------------------------------------

def test_declarative_path_needs_the_four_conditions():
    jamf = JamfAdapter()
    dev = _apple_ddm_device()
    assert ddm.declarative_path_for(dev, "lock", jamf, DDM_PARAMS) == "apply_ddm"
    # 1. adapter sin capacidad DDM declarada -> imperativo
    assert ddm.declarative_path_for(dev, "lock", _RecordingAdapter(), DDM_PARAMS) is None
    # 2. acción sin equivalente declarativo modelado (Apple no lo publica)
    for action in ("wipe", "reboot", "clear_passcode", "locate", "message"):
        assert ddm.declarative_path_for(dev, action, jamf, DDM_PARAMS) is None, action
    # 3. dispositivo por debajo del mínimo de OS
    assert ddm.declarative_path_for(_legacy_device(), "lock", jamf, DDM_PARAMS) is None
    # 4. sin el perfil que las declarations transportan
    assert ddm.declarative_path_for(dev, "lock", jamf, {}) is None
    assert ddm.declarative_path_for(dev, "lock", jamf, {"policy": {"id": "p"}}) is None
    # profile_url no https: `com.apple.configuration.legacy` lo prohíbe
    assert ddm.declarative_path_for(
        dev, "lock", jamf, {"policy": {"id": "p"}, "profile_url": "http://x/p"}) is None
    print("  PASS declarative_path_for exige las 4 condiciones")


def test_unknown_data_stays_imperative():
    """Readback-honesto: sin `os_version` no se adivina; se mantiene el hoy."""
    jamf = JamfAdapter()
    assert ddm.declarative_path_for(_unknown_os_device(), "lock", jamf, DDM_PARAMS) is None
    assert ddm.declarative_path_for(None, "lock", jamf, DDM_PARAMS) is None
    print("  PASS dato desconocido => vía imperativa")


def test_no_invented_apple_equivalences():
    """Solo se enruta lo que ddm.py modela de verdad; nada inventado."""
    assert ddm.DECLARATIVE_EQUIVALENTS == {"lock": "apply_ddm"}, ddm.DECLARATIVE_EQUIVALENTS
    print("  PASS sin equivalencias declarativas inventadas")


# ---- (b) las dos rutas, el mismo veredicto --------------------------------

def test_single_provider_routes_declaratively():
    rec = _RecordingAdapter(supports_ddm=True)
    eng = _engine(rec, {"mode": "enforce", "live_actions": ["lock"]})
    res = eng.run_command(_apple_ddm_device(), "lock", DDM_PARAMS)
    assert res["enforcement"] == "declarative", res
    assert res["requested_action"] == "lock", res
    assert res["action"] == "apply_ddm", res
    assert rec.calls == [("apply_ddm", False)], rec.calls
    print("  PASS ruta single-provider enruta declarativamente")


def test_both_paths_agree_on_the_same_device():
    """El bug de #205: mismo dispositivo, misma acción, mismo veredicto de vía."""
    enf = {"mode": "enforce", "live_actions": ["lock"]}
    rec_single = _RecordingAdapter(supports_ddm=True)
    rec_multi = _RecordingAdapter(supports_ddm=True)
    single = _engine(rec_single, enf)
    multi = _engine_multiuem(rec_multi, enf)
    # El adapter del ref lo resuelve el registro: `jamf` declara supports_ddm.
    assert ADAPTER_REGISTRY["jamf"].supports_ddm is True

    dev_single = _apple_ddm_device("dev-x")
    dev_multi = _apple_ddm_device("dev-x", refs={"jamf": "jamf-123"})
    r_single = single.run_command(dev_single, "lock", DDM_PARAMS)
    r_multi = multi.run_command(dev_multi, "lock", DDM_PARAMS)

    assert r_single["enforcement"] == r_multi["enforcement"] == "declarative", \
        (r_single, r_multi)
    assert [a for a, _d in rec_single.calls] == [a for a, _d in rec_multi.calls] \
        == ["apply_ddm"], (rec_single.calls, rec_multi.calls)
    print("  PASS las dos rutas dan el mismo veredicto de vía")


def test_both_paths_agree_when_imperative():
    """Y también coinciden cuando toca imperativo (regresión del hoy)."""
    enf = {"mode": "enforce", "live_actions": ["lock"]}
    rec_single = _RecordingAdapter(supports_ddm=True)
    rec_multi = _RecordingAdapter(supports_ddm=True)
    single = _engine(rec_single, enf)
    multi = _engine_multiuem(rec_multi, enf)
    r_single = single.run_command(_legacy_device("dev-y"), "lock", DDM_PARAMS)
    r_multi = multi.run_command(
        DeviceState(device_id="dev-y", name="iPhone viejo", platform="ios",
                    os_version="12.4", provider_refs={"jamf": "jamf-y"}),
        "lock", DDM_PARAMS)
    assert r_single["enforcement"] == r_multi["enforcement"] == "imperative", \
        (r_single, r_multi)
    assert [a for a, _d in rec_single.calls] == [a for a, _d in rec_multi.calls] \
        == ["lock"], (rec_single.calls, rec_multi.calls)
    print("  PASS las dos rutas coinciden también en imperativo")


def test_non_ddm_adapter_keeps_imperative_path():
    """Regresión: un UEM sin DDM sigue exactamente como hoy."""
    rec = _RecordingAdapter(supports_ddm=False)
    eng = _engine(rec, {"mode": "enforce", "live_actions": ["lock"]})
    res = eng.run_command(_apple_ddm_device(), "lock", DDM_PARAMS)
    assert res["enforcement"] == "imperative", res
    assert "requested_action" not in res, res
    assert rec.calls == [("lock", False)], rec.calls
    print("  PASS adapter sin DDM => camino imperativo intacto")


# ---- (c) el gating NO cambia con la vía -----------------------------------

def test_declarative_wipe_still_needs_the_double_key():
    """Un wipe declarativo exige doble llave igual que el imperativo.

    Se fuerza la equivalencia declarativa de `wipe` (Apple no la publica, así
    que no está en el mapa) para probar el INVARIANTE de orden: el guardarraíl
    se evalúa ANTES de elegir vía, no la vía antes del guardarraíl.
    """
    original = ddm.DECLARATIVE_EQUIVALENTS
    ddm.DECLARATIVE_EQUIVALENTS = dict(original, wipe="apply_ddm")
    try:
        rec = _RecordingAdapter(supports_ddm=True)
        eng = _engine(rec, {"mode": "enforce", "live_actions": ["wipe"]})
        blocked = eng.run_command(_apple_ddm_device(), "wipe", DDM_PARAMS)
        assert blocked["ok"] is False and blocked["blocked"] is True, blocked
        assert blocked["error_type"] == "wipe_not_allowed", blocked
        assert rec.calls == [], rec.calls  # el adapter jamás ve el wipe bloqueado

        # Con la doble llave (allow_wipe + allowlist) sí sale, y por la vía
        # declarativa: el enrutado cambia el transporte, no el permiso.
        rec2 = _RecordingAdapter(supports_ddm=True)
        eng2 = _engine(rec2, {"mode": "enforce", "live_actions": ["wipe"],
                              "allow_wipe": True, "wipe_allowlist": ["dev-mac"]})
        other = eng2.run_command(_apple_ddm_device("dev-otro"), "wipe", DDM_PARAMS)
        assert other["ok"] is False and other["error_type"] == "wipe_not_allowed", other
        allowed = eng2.run_command(_apple_ddm_device("dev-mac"), "wipe", DDM_PARAMS)
        assert allowed["ok"] is True and allowed["enforcement"] == "declarative", allowed
        assert rec2.calls == [("apply_ddm", False)], rec2.calls
    finally:
        ddm.DECLARATIVE_EQUIVALENTS = original
    print("  PASS wipe declarativo sigue exigiendo doble llave")


def test_observe_sends_nothing_live_by_either_path():
    """En observe/dry_run nada sale al UEM por ninguna de las dos vías."""
    rec_single = _RecordingAdapter(supports_ddm=True)
    rec_multi = _RecordingAdapter(supports_ddm=True)
    single = _engine(rec_single, {"mode": "observe"})
    multi = _engine_multiuem(rec_multi, {"mode": "observe"})
    r_single = single.run_command(_apple_ddm_device("dev-z"), "lock", DDM_PARAMS)
    r_multi = multi.run_command(
        _apple_ddm_device("dev-z", refs={"jamf": "jamf-z"}), "lock", DDM_PARAMS)
    for res in (r_single, r_multi):
        assert res["enforcement"] == "declarative", res
        assert res["dry_run"] is True, res
    assert rec_single.calls == [("apply_ddm", True)], rec_single.calls
    assert rec_multi.calls == [("apply_ddm", True)], rec_multi.calls
    print("  PASS observe: dry-run por las dos vías, cero envíos en vivo")


def test_live_actions_allowlist_survives_the_routing():
    """Una acción fuera de `live_actions` sale dry-run, también en declarativo."""
    rec = _RecordingAdapter(supports_ddm=True)
    eng = _engine(rec, {"mode": "enforce", "live_actions": ["message"]})
    res = eng.run_command(_apple_ddm_device(), "lock", DDM_PARAMS)
    assert res["enforcement"] == "declarative" and res["dry_run"] is True, res
    assert rec.calls == [("apply_ddm", True)], rec.calls
    print("  PASS allow-list de acciones se aplica antes de elegir vía")


def test_cooldown_uses_the_requested_action():
    """El cooldown destructivo cuenta el `lock` pedido, no el `apply_ddm` del cable."""
    rec = _RecordingAdapter(supports_ddm=True)
    eng = make_temp_engine(cooldown_seconds=3600, extra_config={
        "enforcement": {"mode": "enforce", "live_actions": ["lock"]}})
    eng.adapter = rec
    eng.orchestrator = None
    dev = _apple_ddm_device()
    first = eng.run_command(dev, "lock", DDM_PARAMS)
    second = eng.run_command(dev, "lock", DDM_PARAMS)
    assert first["enforcement"] == "declarative", first
    assert second.get("cooldown") is True, second
    assert rec.calls == [("apply_ddm", False)], rec.calls
    print("  PASS cooldown intacto tras el enrutado")


def test_action_log_records_the_route():
    """La vía queda auditada en el action log del tenant."""
    rec = _RecordingAdapter(supports_ddm=True)
    eng = _engine(rec, {"mode": "enforce", "live_actions": ["lock"]})
    eng.run_command(_apple_ddm_device(), "lock", DDM_PARAMS)
    logged = eng.store.recent_actions(5) if hasattr(eng.store, "recent_actions") else []
    assert logged, "el action log debe registrar el comando"
    assert logged[-1]["enforcement"] == "declarative", logged[-1]
    print("  PASS la vía elegida queda en el action log")


# ---- (d) el catálogo deriva la capacidad del adapter ----------------------

def test_catalog_derives_declarative_capability_from_adapters():
    entries = {e["name"]: e for e in catalog()}
    assert entries["jamf"]["declarative"] == {"supported": True, "ddm": True, "dsc": False}, \
        entries["jamf"]["declarative"]
    assert entries["windows_conformidad"]["declarative"] == \
        {"supported": True, "ddm": False, "dsc": True}, \
        entries["windows_conformidad"]["declarative"]
    assert entries["fleet"]["declarative"]["supported"] is False, entries["fleet"]
    print(f"  PASS catálogo con capacidad declarativa derivada ({len(entries)} UEMs)")


def test_catalog_follows_the_adapter_flag():
    """Si el adapter cambia de flag, el catálogo cambia: no hay lista paralela."""
    class _FakeJamf:
        name = "jamf"
        supports_ddm = False

    original = ADAPTER_REGISTRY["jamf"]
    ADAPTER_REGISTRY["jamf"] = _FakeJamf
    try:
        assert declarative_support("jamf") == {"supported": False, "ddm": False, "dsc": False}
        entries = {e["name"]: e for e in catalog()}
        assert entries["jamf"]["declarative"]["ddm"] is False, entries["jamf"]
    finally:
        ADAPTER_REGISTRY["jamf"] = original
    assert declarative_support("jamf")["ddm"] is True
    # UEM sin adapter registrado: no se promete capacidad de nadie.
    assert declarative_support("no-existe") == {"supported": False, "ddm": False, "dsc": False}
    print("  PASS el catálogo sigue la flag real del adapter")


if __name__ == "__main__":
    failed = 0
    tests = [fn for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {fn.__name__}: {exc}")
    print(f"\n=== declarative-routing: {len(tests) - failed} passed, {failed} failed ===")
    sys.exit(1 if failed else 0)
