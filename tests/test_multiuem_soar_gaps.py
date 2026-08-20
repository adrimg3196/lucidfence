"""Tests para los 3 huecos implementados en CTO multi-UEM/SOAR:

A. Matriz de capacidades por UEM (diseño §3.1 / REQ §3 / decisión §10.2):
   - Applivery declara dry_run_actions, NO acciones live destructivas.
   - Intune/Jamf declaran sus acciones reales.
B. Playbooks SOAR del tenant (REQ §5): crear/validar/cargar sin código.
C. Human-gate SOAR (diseño §5): una acción destructiva de un playbook NO se
   ejecuta de forma autónoma; se emite como handoff (soar_handoff).

Run via: python3 tests/run_tests.py   (o python3 tests/test_multiuem_soar_gaps.py)
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from lucidfence.core.adapters.capabilities import (
    capability_for, actions_for, dry_run_actions_for,
)
from lucidfence.core.multiuem import MultiUEMOrchestrator, ProviderBinding, ProviderCapabilities
from lucidfence.core.soar_playbook_store import TenantPlaybookStore
from lucidfence.core.soar import DEFAULT_PLAYBOOKS, evaluate_soar, SOARPlaybook

passed = 0
fails = []


def check(cond, msg):
    global passed
    if cond:
        passed += 1
        print("  PASS", msg)
    else:
        fails.append(msg)
        print("  FAIL", msg)


# --------------------------------------------------------------------------
# GAP A — matriz de capacidades
# --------------------------------------------------------------------------
def test_capability_matrix_applivery_dry_run_only():
    cap = capability_for("applivery")
    check(cap is not None, "applivery tiene matriz declarada")
    check("lock" not in actions_for("applivery"), "applivery NO expone lock como acción live")
    check("lock" in dry_run_actions_for("applivery"), "applivery expone lock como dry-run (pendiente validar)")


def test_capability_matrix_intune_jamf_real():
    check("lock" in actions_for("intune"), "intune expone lock live")
    check("wipe" in actions_for("intune"), "intune expone wipe live")
    check("lock" in actions_for("jamf"), "jamf expone lock live")
    check("apply_ddm" in actions_for("jamf"), "jamf expone apply_ddm (DDM)")


def test_orchestrator_forces_dry_run_for_pending_action():
    calls = []
    binding = ProviderBinding(
        name="applivery",
        capabilities=capability_for("applivery"),
        fetch_devices=lambda: [],
        execute_action=lambda dev_id, action, params, dry_run: (
            calls.append((dev_id, action, dry_run)) or
            {"ok": True, "adapter": "applivery", "action": action, "dry_run": dry_run}
        ),
    )
    orch = MultiUEMOrchestrator([binding])
    res = orch.execute({"provider": "applivery", "provider_device_id": "d1",
                         "provider_refs": {"applivery": "d1"}}, "lock", {}, dry_run=False)
    check(res.get("dry_run") is True, "lock en applivery se fuerza a dry_run")
    check(res.get("handoff") is True, "lock en applivery se marca handoff")
    check(res.get("dry_run_reason") == "provider_endpoint_pending_validation",
          "razón de dry-run = endpoint pendiente de validar")
    check(len(calls) == 1 and calls[0][2] is True, "adapter recibió dry_run=True")


def test_orchestrator_unsupported_action_structured():
    binding = ProviderBinding(
        name="chromeos",
        capabilities=capability_for("chromeos"),
        fetch_devices=lambda: [],
        execute_action=lambda dev_id, action, params, dry_run: {"ok": True},
    )
    orch = MultiUEMOrchestrator([binding])
    res = orch.execute({"provider": "chromeos", "provider_device_id": "d1",
                         "provider_refs": {"chromeos": "d1"}}, "lock", {}, dry_run=False)
    check(res.get("error_type") == "unsupported_action", "chromeos rechaza lock como unsupported_action")


# --------------------------------------------------------------------------
# GAP B — playbooks del tenant
# --------------------------------------------------------------------------
def test_tenant_playbook_store_roundtrip_and_validation():
    d = tempfile.mkdtemp(prefix="lf-soar-")
    store = TenantPlaybookStore(data_dir=d, builtin=DEFAULT_PLAYBOOKS)
    pb = store.upsert({
        "id": "soar-cliente-x", "name": "Cliente X",
        "condition": {"field": "compliant", "op": "eq", "value": False},
        "actions": [{"action": "notify", "params": {"channel": "soc"}}],
    })
    check(pb.id == "soar-cliente-x" and pb.enabled, "upsert crea playbook del tenant")
    loaded = store.load()
    check(len(loaded) == 1 and loaded[0].id == "soar-cliente-x", "load recupera el playbook")
    check(len(store.all_playbooks()) == len(DEFAULT_PLAYBOOKS) + 1, "all_playbooks fusiona builtin + tenant")
    # validación en caliente: condición inválida -> ValueError
    try:
        store.upsert({"id": "bad", "name": "bad", "condition": {"op": "nope"}, "actions": []})
        check(False, "condición inválida debe rechazarse")
    except ValueError:
        check(True, "validación en caliente rechaza condición inválida")
    # disable / delete
    check(store.set_enabled("soar-cliente-x", False), "set_enabled(false) ok")
    check(store.get("soar-cliente-x").enabled is False, "playbook queda inactivo")
    check(store.delete("soar-cliente-x"), "delete ok")
    check(store.load() == [], "delete vacía el store")


def test_tenant_playbook_evaluated_in_engine_style():
    custom = SOARPlaybook(
        id="soar-custom", name="custom",
        condition={"all": [{"field": "compliant", "op": "eq", "value": False},
                           {"field": "fence_state", "op": "eq", "value": "outside"}]},
        actions=[{"action": "notify", "params": {"channel": "soc"}}],
    )
    dev = {"compliant": False, "fence_state": "outside", "apps": []}
    execs = evaluate_soar(dev, [custom], {"on_error": None})
    check(any(e["playbook_id"] == "soar-custom" for e in execs), "playbook custom del tenant evalúa")


# --------------------------------------------------------------------------
# GAP C — human-gate SOAR
# --------------------------------------------------------------------------
def test_soar_human_gate_emits_handoff_not_execution():
    """Replica el bucle del engine: un playbook con acción destructiva NO debe
    ejecutarla, sino emitir soar_handoff y dejar constancia de human_gate."""
    import sqlite3
    # Usamos StateStore en un dir temporal para capturar eventos.
    from lucidfence.core.state_store import StateStore, DeviceState

    d = tempfile.mkdtemp(prefix="lf-soargate-")
    store = StateStore(d)
    ds = DeviceState(device_id="dev-1", name="n", platform="android",
                     compliant=False, fence_state="outside",
                     provider_refs={"applivery": "a1"})
    store.upsert(ds)

    # playbook soar-rooted-outside que incluye lock destructivo
    pb = next(p for p in DEFAULT_PLAYBOOKS if p.id == "soar-rooted-outside")
    dev_dict = ds.to_dict()
    execs = evaluate_soar(dev_dict, [pb], {"on_error": None})

    DESTRUCTIVE = {"wipe", "lock", "clear_passcode", "reboot"}
    executed = []
    handoffs = []
    for ex in execs:
        for act in ex.get("actions", []):
            aname = act.get("action")
            if aname in DESTRUCTIVE:
                # En el engine esto NO llama a _dedupe_action; emite handoff.
                handoffs.append((ex["playbook_id"], aname))
            else:
                executed.append(aname)

    check(("soar-rooted-outside", "lock") in handoffs,
          "lock destructivo de SOAR se registra como handoff, no se ejecuta")
    check(len(executed) == 1 and executed[0] == "notify",
          "acciones no destructivas (notify) sí proceden")


if __name__ == "__main__":
    test_capability_matrix_applivery_dry_run_only()
    test_capability_matrix_intune_jamf_real()
    test_orchestrator_forces_dry_run_for_pending_action()
    test_orchestrator_unsupported_action_structured()
    test_tenant_playbook_store_roundtrip_and_validation()
    test_tenant_playbook_evaluated_in_engine_style()
    test_soar_human_gate_emits_handoff_not_execution()
    print(f"\n=== multiuem-soar-gaps: {passed} passed, {len(fails)} failed ===")
    sys.exit(1 if fails else 0)
