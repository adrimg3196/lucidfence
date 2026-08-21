"""Tests del exportador de config de despliegue del agente iOS on-device.

El exportador produce la Managed App Configuration (y el perfil .mobileconfig)
que un admin empuja a la app iOS gestionada vía su MDM. Invariante estrella del
producto: la geocerca se evalúa EN el dispositivo; la config solo lleva la
definición de las geocercas de política (dato de la organización), nunca
ubicación de dispositivos ni secretos. Sin credenciales reales, sin red.
"""
from __future__ import annotations

import json
import plistlib
import sys

sys.path.insert(0, ".")

from lucidfence.core.adapters import (
    build_geofence_appconfig,
    to_appconfig_plist,
    build_geofence_mobileconfig,
)
from lucidfence.core.adapters.ios_geofence import (
    GEOFENCE_APPCONFIG_SCHEMA,
    MANAGED_APP_CONFIG_KEY,
)


# Set de geocercas de política de ejemplo (forma de fences.json). Los centros
# son ubicaciones de la ORGANIZACIÓN (oficina), no de ningún dispositivo.
SAMPLE = {
    "fences": [
        {
            "id": "office-hq",
            "name": "Oficina HQ",
            "type": "circle",
            "center": {"lat": 40.42, "lng": -3.71},
            "radius_m": 350,
            "actions": [
                {"action": "message", "when": "on_enter"},
                {"action": "message", "when": "on_exit"},
            ],
        },
        {
            "id": "warehouse",
            "name": "Almacen",
            "type": "polygon",
            "coordinates": [
                {"lat": 40.435, "lng": -3.70},
                {"lat": 40.435, "lng": -3.68},
                {"lat": 40.425, "lng": -3.68},
            ],
            "actions": [{"action": "locate", "when": "on_enter"}],
        },
    ]
}


def test_appconfig_has_ondevice_shape():
    cfg = build_geofence_appconfig(SAMPLE)
    assert cfg["schema"] == GEOFENCE_APPCONFIG_SCHEMA
    assert cfg["evaluation"] == "on_device"
    # El reporte es solo cumplimiento: NUNCA coordenadas crudas.
    assert cfg["reporting"] == {"mode": "compliance_only", "include_coordinates": False}
    assert len(cfg["fences"]) == 2
    assert MANAGED_APP_CONFIG_KEY == "com.apple.configuration.managed"


def test_appconfig_keeps_only_policy_fields():
    cfg = build_geofence_appconfig(SAMPLE)
    hq = next(f for f in cfg["fences"] if f["id"] == "office-hq")
    assert hq["type"] == "circle"
    assert hq["center"] == {"lat": 40.42, "lng": -3.71}
    assert hq["radius_m"] == 350
    # Las acciones on_enter/on_exit se destilan a las transiciones que re-evalúa.
    assert hq["notify_on"] == ["enter", "exit"]
    # No se filtran las acciones crudas (concepto server-side).
    assert "actions" not in hq
    poly = next(f for f in cfg["fences"] if f["id"] == "warehouse")
    assert poly["type"] == "polygon"
    assert len(poly["coordinates"]) == 3
    assert poly["notify_on"] == ["enter"]


def test_appconfig_never_leaks_devices_or_secrets():
    # Una geocerca "envenenada" con datos que NO deben salir del dispositivo/servidor.
    poisoned = {
        "fences": [
            {
                "id": "hq",
                "name": "HQ",
                "type": "circle",
                "center": {"lat": 1.0, "lng": 2.0},
                "radius_m": 100,
                # Ruido que un exportador ingenuo copiaría entero:
                "device_id": "iphone-de-ana-123",
                "last_lat": 41.9,
                "last_lng": -3.5,
                "api_key": "SECRET-TOKEN-should-not-travel",
                "apps": [{"bundle": "com.evil"}],
            }
        ]
    }
    cfg = build_geofence_appconfig(poisoned, tenant_id="acme")
    blob = json.dumps(cfg)
    for forbidden in ("device_id", "iphone-de-ana", "last_lat", "last_lng",
                      "api_key", "SECRET-TOKEN", "apps", "com.evil"):
        assert forbidden not in blob, f"fuga de {forbidden!r} en la config"
    # El tenant_id (no secreto) sí puede viajar como etiqueta.
    assert cfg["tenant_id"] == "acme"


def test_appconfig_zero_fences_edge_case():
    for empty in ({"fences": []}, [], None):
        cfg = build_geofence_appconfig(empty)
        assert cfg["fences"] == []
        assert cfg["evaluation"] == "on_device"
        assert cfg["reporting"]["include_coordinates"] is False


def test_appconfig_is_stable_across_calls():
    a = build_geofence_appconfig(SAMPLE, tenant_id="acme")
    b = build_geofence_appconfig(SAMPLE, tenant_id="acme")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_appconfig_plist_roundtrips_and_is_stable():
    cfg = build_geofence_appconfig(SAMPLE, tenant_id="acme")
    xml = to_appconfig_plist(cfg)
    assert to_appconfig_plist(cfg) == xml  # estable (claves ordenadas)
    parsed = plistlib.loads(xml.encode("utf-8"))
    assert parsed == cfg


def test_mobileconfig_wraps_managed_app_config():
    xml = build_geofence_mobileconfig(SAMPLE, organization="Acme", tenant_id="acme")
    profile = plistlib.loads(xml.encode("utf-8"))
    assert profile["PayloadType"] == "Configuration"
    payload = profile["PayloadContent"][0]
    # Payload de Managed App Configuration (entrega config, no captura nada).
    assert payload["PayloadType"] == "com.apple.app.managed"
    assert payload["AppIdentifier"] == "com.lucidfence.geofence"
    inner = payload["Configuration"]
    assert inner["evaluation"] == "on_device"
    assert inner["reporting"]["include_coordinates"] is False


def test_mobileconfig_is_deterministic_per_tenant():
    # Mismo tenant => mismo perfil (incluidos los UUID): diffs limpios en git.
    one = build_geofence_mobileconfig(SAMPLE, organization="Acme", tenant_id="acme")
    two = build_geofence_mobileconfig(SAMPLE, organization="Acme", tenant_id="acme")
    assert one == two
    # Distinto tenant => distinto UUID de payload.
    other = build_geofence_mobileconfig(SAMPLE, organization="Acme", tenant_id="beta")
    assert other != one


def test_mobileconfig_never_leaks_devices():
    poisoned = {
        "fences": [{
            "id": "hq", "name": "HQ", "type": "circle",
            "center": {"lat": 1.0, "lng": 2.0}, "radius_m": 100,
            "device_id": "iphone-de-ana", "api_key": "SECRET",
        }]
    }
    xml = build_geofence_mobileconfig(poisoned, organization="Acme")
    for forbidden in ("device_id", "iphone-de-ana", "api_key", "SECRET"):
        assert forbidden not in xml
