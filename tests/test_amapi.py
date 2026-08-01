from __future__ import annotations

from typing import Any

from lucidfence.core.amapi import generate_amapi_policy_patch
from lucidfence.core.adapters.applivery import AppliveryAdapter
from lucidfence.core.adapters.intune import IntuneAdapter
from lucidfence.core.adapters.workspace_one import WorkspaceONEAdapter
from lucidfence.core.location_source import LocationReport
from lucidfence.core.state_store import DeviceState, StateStore
from lucidfence.core.engine import Engine


# --- Robust AMAPI Schema Validator for Unit Tests ---
def validate_against_amapi_schema(patch: dict[str, Any]) -> None:
    """Verifica que el diccionario cumpla estrictamente con la especificación de Google AMAPI."""
    valid_keys = {
        "cameraDisabled",
        "applications",
        "kioskCustomLauncherEnabled",
        "locationMode",
        "wifiConfigsLockdownEnabled",
        "policyEnforcementRules",
    }

    # 1. Comprobar claves desconocidas
    for k in patch.keys():
        assert k in valid_keys, f"Clave no estándar encontrada en el parche AMAPI: {k}"

    # 2. Validar cameraDisabled
    if "cameraDisabled" in patch:
        assert isinstance(patch["cameraDisabled"], bool), "cameraDisabled debe ser booleano"

    # 3. Validar applications
    if "applications" in patch:
        assert isinstance(patch["applications"], list), "applications debe ser una lista"
        valid_install_types = {
            "INSTALL_TYPE_UNSPECIFIED",
            "FORCE_INSTALLED",
            "BLOCKED",
            "AVAILABLE",
            "REQUIRED_FOR_SETUP",
            "KVP",
        }
        for app in patch["applications"]:
            assert isinstance(app, dict), "Cada elemento de applications debe ser un objeto"
            assert "packageName" in app, "Cada elemento de applications debe contener packageName"
            assert isinstance(app["packageName"], str) and app["packageName"], "packageName debe ser un string válido"
            if "installType" in app:
                assert app["installType"] in valid_install_types, f"installType inválido: {app['installType']}"

    # 4. Validar kioskCustomLauncherEnabled
    if "kioskCustomLauncherEnabled" in patch:
        assert isinstance(patch["kioskCustomLauncherEnabled"], bool), "kioskCustomLauncherEnabled debe ser booleano"

    # 5. Validar locationMode
    if "locationMode" in patch:
        valid_location_modes = {
            "LOCATION_MODE_UNSPECIFIED",
            "HIGH_ACCURACY",
            "BATTERY_SAVING",
            "SENSORS_ONLY",
            "OFF",
        }
        assert patch["locationMode"] in valid_location_modes, f"locationMode inválido: {patch['locationMode']}"

    # 6. Validar wifiConfigsLockdownEnabled
    if "wifiConfigsLockdownEnabled" in patch:
        assert isinstance(patch["wifiConfigsLockdownEnabled"], bool), "wifiConfigsLockdownEnabled debe ser booleano"

    # 7. Validar policyEnforcementRules (graduated enforcement)
    if "policyEnforcementRules" in patch:
        assert isinstance(patch["policyEnforcementRules"], list), "policyEnforcementRules debe ser una lista"
        for rule in patch["policyEnforcementRules"]:
            assert isinstance(rule, dict), "Cada elemento de policyEnforcementRules debe ser un objeto"
            assert "settingName" in rule, "Cada elemento de policyEnforcementRules debe contener settingName"
            assert isinstance(rule["settingName"], str) and rule["settingName"], "settingName debe ser un string válido"

            if "blockAction" in rule:
                assert isinstance(rule["blockAction"], dict), "blockAction debe ser un objeto"
                assert "blockAfterDays" in rule["blockAction"], "blockAction debe contener blockAfterDays"
                assert isinstance(rule["blockAction"]["blockAfterDays"], int), "blockAfterDays debe ser entero"

            if "wipeAction" in rule:
                assert isinstance(rule["wipeAction"], dict), "wipeAction debe ser un objeto"
                assert "wipeAfterDays" in rule["wipeAction"], "wipeAction debe contener wipeAfterDays"
                assert isinstance(rule["wipeAction"]["wipeAfterDays"], int), "wipeAfterDays debe ser entero"


# --- Tests ---

def test_amapi_policy_patch_generation_outside():
    """Prueba la generación de parches AMAPI para dispositivos fuera de la geocerca."""
    fence_mock = {
        "id": "hq_restricted",
        "name": "HQ Restricted Zone",
        "rules": {
            "amapi_rules_outside": {
                "cameraDisabled": True,
                "locationMode": "HIGH_ACCURACY",
                "wifiConfigsLockdownEnabled": True,
                "apps": ["com.android.chrome", "com.google.android.youtube"],
                "graduatedEnforcement": {
                    "settingName": "cameraDisabled",
                    "blockAfterDays": 1,
                    "wipeAfterDays": 5,
                }
            }
        }
    }

    patch = generate_amapi_policy_patch("outside", fence_mock)

    # Validar contra el esquema oficial AMAPI
    validate_against_amapi_schema(patch)

    # Comprobar valores
    assert patch["cameraDisabled"] is True
    assert patch["locationMode"] == "HIGH_ACCURACY"
    assert patch["wifiConfigsLockdownEnabled"] is True
    assert len(patch["applications"]) == 2
    assert patch["applications"][0]["packageName"] == "com.android.chrome"
    assert patch["applications"][0]["installType"] == "FORCE_INSTALLED"

    # Comprobar graduated enforcement rules
    assert len(patch["policyEnforcementRules"]) == 1
    rule = patch["policyEnforcementRules"][0]
    assert rule["settingName"] == "cameraDisabled"
    assert rule["blockAction"]["blockAfterDays"] == 1
    assert rule["wipeAction"]["wipeAfterDays"] == 5


def test_amapi_policy_patch_generation_inside():
    """Prueba la generación de parches AMAPI para dispositivos dentro de la geocerca."""
    fence_mock = {
        "id": "hq_restricted",
        "name": "HQ Restricted Zone",
        "rules": {
            "amapi_rules_inside": {
                "cameraDisabled": False,
                "kioskCustomLauncherEnabled": False,
                "apps": [
                    {"packageName": "com.lucidfence.agent", "installType": "FORCE_INSTALLED"},
                    {"packageName": "com.games.blocked", "installType": "BLOCKED"}
                ]
            }
        }
    }

    patch = generate_amapi_policy_patch("inside", fence_mock)

    validate_against_amapi_schema(patch)
    assert patch["cameraDisabled"] is False
    assert patch["kioskCustomLauncherEnabled"] is False
    assert len(patch["applications"]) == 2
    assert patch["applications"][1]["packageName"] == "com.games.blocked"
    assert patch["applications"][1]["installType"] == "BLOCKED"


def test_adapters_supports_amapi_policy_flag():
    """Prueba que los adapters que gestionan Android exponen el flag de capacidad correcto."""
    assert getattr(AppliveryAdapter, "supports_amapi_policy", False) is True
    assert getattr(IntuneAdapter, "supports_amapi_policy", False) is True
    assert getattr(WorkspaceONEAdapter, "supports_amapi_policy", False) is True


def test_adapters_execute_apply_amapi_policy():
    """Prueba la acción 'apply_amapi_policy' en los adapters."""
    fence_mock = {
        "id": "fence_one",
        "rules": {
            "camera_disabled": True,
            "kiosk_custom_launcher_enabled": True,
            "location_mode": "HIGH_ACCURACY"
        }
    }
    params = {"fence_state": "outside", "fence": fence_mock}

    # 1. Applivery
    adapter_applivery = AppliveryAdapter(org_id="org_test", endpoint_template="")
    res_applivery = adapter_applivery.execute({"device_id": "and-1"}, "apply_amapi_policy", params, dry_run=True)
    assert res_applivery["ok"] is True
    assert res_applivery["action"] == "apply_amapi_policy"
    validate_against_amapi_schema(res_applivery["amapi_patch"])
    assert res_applivery["amapi_patch"]["cameraDisabled"] is True
    assert res_applivery["amapi_patch"]["kioskCustomLauncherEnabled"] is True

    # 2. Intune
    adapter_intune = IntuneAdapter(live=False)
    res_intune = adapter_intune.execute({"device_id": "and-2"}, "apply_amapi_policy", params, dry_run=True)
    assert res_intune["ok"] is True
    assert res_intune["action"] == "apply_amapi_policy"
    validate_against_amapi_schema(res_intune["amapi_patch"])

    # 3. Workspace ONE
    adapter_ws1 = WorkspaceONEAdapter(live=False)
    res_ws1 = adapter_ws1.execute({"device_id": "and-3"}, "apply_amapi_policy", params, dry_run=True)
    assert res_ws1["ok"] is True
    assert res_ws1["action"] == "apply_amapi_policy"
    validate_against_amapi_schema(res_ws1["amapi_patch"])


def test_state_readback_and_propagation():
    """Prueba que los campos AMAPI se mapean en LocationReport, DeviceState y se propagan en el Engine."""
    # 1. LocationReport
    rep = LocationReport(
        device_id="and-100",
        name="Android Device 100",
        platform="android",
        lat=40.0,
        lng=-3.0,
        amapi_policy_compliant=True,
        amapi_non_compliance_details=[]
    )
    assert rep.amapi_policy_compliant is True
    assert rep.amapi_non_compliance_details == []

    # 2. DeviceState
    state = DeviceState(
        device_id="and-100",
        name="Android Device 100",
        platform="android",
        amapi_policy_compliant=False,
        amapi_non_compliance_details=[{"settingName": "cameraDisabled", "nonComplianceReason": "USER_REJECTED"}]
    )
    assert state.amapi_policy_compliant is False
    assert len(state.amapi_non_compliance_details) == 1
    assert state.to_dict()["amapi_policy_compliant"] is False

    # 3. Engine Cycle Integration (Mock/Simulation mode)
    import tempfile
    import json
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_file = Path(tmpdir) / "fleet_seed.json"
        seed_data = {
            "devices": [
                {
                    "id": "and-100",
                    "name": "Android Device 100",
                    "platform": "android",
                    "compliant": True,
                    "amapi_policy_compliant": False,
                    "amapi_non_compliance_details": [
                        {
                            "settingName": "cameraDisabled",
                            "nonComplianceReason": "USER_REJECTED",
                            "packageName": "",
                            "currentValue": "enabled"
                        }
                    ],
                    "waypoints": [{"lat": 40.4, "lng": -3.7}]
                }
            ]
        }
        seed_file.write_text(json.dumps(seed_data), encoding="utf-8")

        fences_file = Path(tmpdir) / "fences.json"
        fences_file.write_text(json.dumps({"fences": []}), encoding="utf-8")

        policies_file = Path(tmpdir) / "policies.json"
        policies_file.write_text(json.dumps([]), encoding="utf-8")

        config = {
            "mode": "simulation",
            "data_dir": str(tmpdir),
            "sim_seed_path": str(seed_file),
            "fences_path": str(fences_file),
            "policies_path": str(policies_file),
            "dry_run": True,
        }

        engine = Engine(config)
        engine.run_once()

        saved_state = engine.store.get("and-100")
        assert saved_state is not None
        assert saved_state.amapi_policy_compliant is False
        assert len(saved_state.amapi_non_compliance_details) == 1
        assert saved_state.amapi_non_compliance_details[0]["settingName"] == "cameraDisabled"
        assert saved_state.amapi_non_compliance_details[0]["nonComplianceReason"] == "USER_REJECTED"
