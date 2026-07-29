"""Android Management API (AMAPI) policy generation module.

AMAPI is declarative by design. The server publishes a desired-state policy
JSON document, and the device converges autonomously.

This module builds an AMAPI policy patch from a LucidFence fence policy,
supporting restrictions per fence state and policyEnforcementRules for
graduated enforcement.
"""
from __future__ import annotations

from typing import Any, Optional


def generate_amapi_policy_patch(fence_state: str, fence: Any) -> dict[str, Any]:
    """Genera un parche de política AMAPI a partir de una geocerca y su estado.

    Args:
        fence_state: El estado de la geocerca para el dispositivo ("inside" | "outside" | "unknown").
        fence: El objeto geocerca (Fence o un diccionario con su configuración).

    Returns:
        Un diccionario que representa el parche de política AMAPI deseado.
    """
    # Extraer reglas de la geocerca
    rules = getattr(fence, "rules", {}) if not isinstance(fence, dict) else fence.get("rules", {})
    if not isinstance(rules, dict):
        rules = {}

    # Soporte para reglas específicas por estado o general amapi_rules
    amapi_rules = {}
    if f"amapi_rules_{fence_state}" in rules:
        amapi_rules = rules[f"amapi_rules_{fence_state}"]
    elif "amapi" in rules:
        amapi_rules = rules["amapi"]
    else:
        # Fallback: usar reglas directamente si contienen claves AMAPI válidas
        amapi_rules = rules

    if not isinstance(amapi_rules, dict):
        amapi_rules = {}

    patch: dict[str, Any] = {}

    # 1. cameraDisabled
    if "cameraDisabled" in amapi_rules:
        patch["cameraDisabled"] = bool(amapi_rules["cameraDisabled"])
    elif "camera_disabled" in amapi_rules:
        patch["cameraDisabled"] = bool(amapi_rules["camera_disabled"])

    # 2. applications
    apps = amapi_rules.get("applications") or amapi_rules.get("apps")
    if apps and isinstance(apps, list):
        patch["applications"] = []
        for app in apps:
            if isinstance(app, dict) and "packageName" in app:
                app_entry = {
                    "packageName": app["packageName"],
                    "installType": app.get("installType", "FORCE_INSTALLED"),
                }
                # Propagar otros campos válidos de aplicación de AMAPI
                for k, v in app.items():
                    if k not in ("packageName", "installType"):
                        app_entry[k] = v
                patch["applications"].append(app_entry)
            elif isinstance(app, str):
                patch["applications"].append({
                    "packageName": app,
                    "installType": "FORCE_INSTALLED"
                })

    # 3. kioskCustomLauncherEnabled
    if "kioskCustomLauncherEnabled" in amapi_rules:
        patch["kioskCustomLauncherEnabled"] = bool(amapi_rules["kioskCustomLauncherEnabled"])
    elif "kiosk_custom_launcher_enabled" in amapi_rules:
        patch["kioskCustomLauncherEnabled"] = bool(amapi_rules["kiosk_custom_launcher_enabled"])

    # 4. locationMode
    if "locationMode" in amapi_rules:
        patch["locationMode"] = str(amapi_rules["locationMode"])
    elif "location_mode" in amapi_rules:
        patch["locationMode"] = str(amapi_rules["location_mode"])

    # 5. wifiConfigsLockdownEnabled
    if "wifiConfigsLockdownEnabled" in amapi_rules:
        patch["wifiConfigsLockdownEnabled"] = bool(amapi_rules["wifiConfigsLockdownEnabled"])
    elif "wifi_configs_lockdown_enabled" in amapi_rules:
        patch["wifiConfigsLockdownEnabled"] = bool(amapi_rules["wifi_configs_lockdown_enabled"])

    # 6. policyEnforcementRules (graduated enforcement: warn -> block -> wipe-scoped)
    enforcement_rules = amapi_rules.get("policyEnforcementRules") or amapi_rules.get("policy_enforcement_rules")
    if enforcement_rules and isinstance(enforcement_rules, list):
        patch["policyEnforcementRules"] = enforcement_rules
    else:
        # Generar automáticamente a partir del campo graduated_enforcement o graduatedEnforcement
        grad = amapi_rules.get("graduatedEnforcement") or amapi_rules.get("graduated_enforcement")
        if grad and isinstance(grad, dict):
            setting = grad.get("settingName") or grad.get("setting_name") or "cameraDisabled"
            rule_entry: dict[str, Any] = {"settingName": setting}

            block_days = grad.get("blockAfterDays") or grad.get("block_days")
            if block_days is not None:
                rule_entry["blockAction"] = {"blockAfterDays": int(block_days)}

            wipe_days = grad.get("wipeAfterDays") or grad.get("wipe_days")
            if wipe_days is not None:
                rule_entry["wipeAction"] = {"wipeAfterDays": int(wipe_days)}

            patch["policyEnforcementRules"] = [rule_entry]

    return patch
