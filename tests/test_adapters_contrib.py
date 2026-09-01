"""Tests de los adapters de la comunidad (Intune/Jamf) y del registry.

Valida el contrato MDMAdapter sin tocar la red de ningún MDM real:
- SimulationAdapter / AppliveryAdapter siguen funcionando (regresión).
- IntuneAdapter / JamfAdapter en modo mock devuelven ok:True y respetan el nombre.
- build_adapter selecciona la clase correcta por modo.
- La interfaz no cambia (execute con 4 args, name presente).
"""
from __future__ import annotations

import sys, types
sys.path.insert(0, ".")

from lucidfence.core.adapters import (
    MDMAdapter, SimulationAdapter, AppliveryAdapter, IntuneAdapter,
    JamfAdapter, VALID_ACTIONS, ADAPTER_REGISTRY, build_adapter,
)
from lucidfence.core.ddm import build_mock_status_result, build_mock_sync_result
from lucidfence.core.actions import LiveAdapter  # alias histórico


def check(cond, msg):
    assert cond, f"FAIL: {msg}"


def _fake_device():
    class D:
        device_id = "dev-001"
        name = "Tablet Campo A1"
        platform = "android"
    return D()


def test_interface_contract():
    for cls in (SimulationAdapter, AppliveryAdapter, IntuneAdapter, JamfAdapter):
        check(issubclass(cls, MDMAdapter), f"{cls.__name__} hereda MDMAdapter")
        check(isinstance(cls.name, str) and cls.name, f"{cls.__name__} tiene name")
        inst = cls() if cls is SimulationAdapter else cls(org_id="o", endpoint_template="/x")
        r = inst.execute(_fake_device(), "lock", {})
        check(set(r.keys()) >= {"adapter", "ok", "device_id", "action"}, f"{cls.name} devuelve dict normalizado")
        check(r["adapter"] == cls.name, f"{cls.name} refleja su name en el resultado")


def test_simulation_adapter_ddm_status_mock_dispatch():
    a = SimulationAdapter()
    dev = _fake_device()
    res = a.execute(dev, "ddm_status", {})
    assert res["ok"] is True
    assert res["adapter"] == "simulation"
    assert res["action"] == "ddm_status"
    # Mock dispatch routes to build_mock_status_result shape (issue #71).
    assert res["status_items"] == []
    assert res["device_state"] == {}
    assert res["mode"] == "mock"
    assert "note" in res


def test_simulation_adapter_ddm_sync_mock_dispatch():
    a = SimulationAdapter()
    dev = _fake_device()
    res = a.execute(dev, "ddm_sync", {})
    assert res["ok"] is True
    assert res["adapter"] == "simulation"
    assert res["action"] == "ddm_sync"
    # Mock dispatch routes to build_mock_sync_result shape (issue #71).
    assert res["jamf_status"] == 204
    assert res["synced"] is True
    assert res["mode"] == "mock"
    assert "note" in res


def test_simulation_adapter_ddm_mock_returns_the_same_shape_as_builders():
    a = SimulationAdapter()
    dev = _fake_device()
    status_res = a.execute(dev, "ddm_status", {})
    sync_res = a.execute(dev, "ddm_sync", {})
    assert status_res["status_items"] == build_mock_status_result()["status_items"]
    assert status_res["device_state"] == build_mock_status_result()["device_state"]
    assert sync_res["jamf_status"] == build_mock_sync_result()["jamf_status"]
    assert sync_res["synced"] == build_mock_sync_result()["synced"]


def test_simulation_adapter_nonzero_action_still_returns_base_shape():
    """Regression: an action not in {ddm_status, ddm_sync} still works."""
    a = SimulationAdapter()
    dev = _fake_device()
    res = a.execute(dev, "lock", {})
    assert res["ok"] is True
    assert res["adapter"] == "simulation"
    assert "status_items" not in res
    assert "jamf_status" not in res


def test_intune_mock():
    a = IntuneAdapter()
    r = a.execute(_fake_device(), "lock", {})
    check(r["ok"] is True and r["mock"] is True, "Intune mock ok sin token")
    check(r["graph_action"] == "remoteLock", "Intune mapea lock -> remoteLock")


def test_jamf_mock():
    a = JamfAdapter()
    r = a.execute(_fake_device(), "wipe", {})
    check(r["ok"] is True and r["mock"] is True, "Jamf mock ok sin token")
    check(r["jamf_verb"] == "ERASE_DEVICE", "Jamf mapea wipe -> ERASE_DEVICE")


def test_applivery_no_token_is_safe():
    a = AppliveryAdapter(org_id="o", endpoint_template="/x")
    r = a.execute(_fake_device(), "lock", {})
    check(r["ok"] is False and "error" in r, "Applivery sin token no crashea (ok:False)")


def test_build_adapter_selection():
    check(isinstance(build_adapter("simulation", "o", "/x"), SimulationAdapter), "build sim -> Simulation")
    check(isinstance(build_adapter("intune", "o", "/x"), IntuneAdapter), "build intune -> Intune")
    check(isinstance(build_adapter("jamf", "o", "/x"), JamfAdapter), "build jamf -> Jamf")
    check(isinstance(build_adapter("applivery", "o", "/x"), AppliveryAdapter), "build applivery -> Applivery")
    check(isinstance(build_adapter("live", "o", "/x"), AppliveryAdapter), "build live -> Applivery (default)")


def test_registry_discoverable():
    for n in ("simulation", "applivery", "intune", "jamf"):
        check(n in ADAPTER_REGISTRY, f"{n} registrado")
    # Un adapter de la comunidad puede registrarse así:
    class DummyAdapter(MDMAdapter):
        name = "dummy"
        def __init__(self, *a, **k):
            pass
        def execute(self, device, action, params, dry_run=False):
            return {"adapter": self.name, "ok": True, "device_id": self._dev_id(device), "action": action}
    ADAPTER_REGISTRY["dummy"] = DummyAdapter
    check(isinstance(build_adapter("dummy", "o", "/x"), DummyAdapter), "registry acepta adapter de comunidad")


def test_liveadapter_alias():
    check(LiveAdapter is AppliveryAdapter, "LiveAdapter === AppliveryAdapter (compat)")


if __name__ == "__main__":
    for fn in (v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)):
        fn()
        print(f"PASS {fn.__name__}")
    print("ALL ADAPTER TESTS PASS")
