"""Adapter de vitrina para cumplimiento de geocercas en flotas iOS.

No contacta ningún MDM real. Convierte el estado calculado por el engine
(`fence_state`) en campos explícitos que la vitrina cloud puede mostrar para
dispositivos iOS/iPadOS simulados.

Además exporta la **config de despliegue** que un admin empuja a la app iOS
gestionada vía su propio MDM (Intune / Jamf / Applivery). La evaluación de la
geocerca ocurre **en el dispositivo** (CoreLocation): la config solo lleva la
definición de las geocercas de política (centros/radios de la organización, no
posiciones de dispositivos) y le dice a la app que reporte **solo cumplimiento**,
nunca coordenadas crudas. Ver `docs/integrations/IOS_ONDEVICE.md`.
"""
from __future__ import annotations

import plistlib
import uuid
from typing import Any, Optional


IOS_PLATFORMS = {"ios", "ipados"}

#: Versión del esquema de la managed app configuration que consume la app iOS.
GEOFENCE_APPCONFIG_SCHEMA = "lucidfence.ios_geofence/1"

#: Clave de UserDefaults donde iOS deja la Managed App Configuration para la app.
MANAGED_APP_CONFIG_KEY = "com.apple.configuration.managed"

#: Bundle id por defecto de la app gestionada; el admin lo ajusta al real.
DEFAULT_BUNDLE_ID = "com.lucidfence.geofence"

#: Namespace estable para derivar UUIDs deterministas del perfil (payload estable).
_PROFILE_NS = uuid.UUID("6c1d f3a2-0000-5f00-9c00-6c756369640d".replace(" ", ""))

#: Solo estos campos de una geocerca de política salen en la config. Whitelist
#: explícita: nada de device_id, coordenadas de dispositivo, credenciales, etc.
_FENCE_POLICY_KEYS = ("id", "name", "type", "center", "radius_m", "coordinates")


def _get(device: Any, key: str, default=None):
    if isinstance(device, dict):
        return device.get(key, default)
    return getattr(device, key, default)


def is_ios_device(device: Any) -> bool:
    """True si el dispositivo pertenece a una flota Apple iOS/iPadOS."""
    platform = str(_get(device, "platform", "") or "").strip().lower()
    return platform in IOS_PLATFORMS


def ios_geofence_compliance(device: Any) -> dict:
    """Devuelve campos normalizados de cumplimiento geofence para la vitrina.

    Semántica simulada:
    - iOS/iPadOS dentro de geocerca => geofence_compliant=True.
    - iOS/iPadOS fuera de geocerca => geofence_compliant=False.
    - iOS/iPadOS sin señal/estado unknown => geofence_compliant=None.
    - No iOS/iPadOS => no aplicable; no altera su compliance MDM.
    """
    if not is_ios_device(device):
        return {
            "geofence_compliance_applicable": False,
            "geofence_compliant": None,
            "geofence_compliance_label": "no aplica",
        }

    state = str(_get(device, "fence_state", "unknown") or "unknown").lower()
    if state == "inside":
        compliant: Optional[bool] = True
        label = "dentro de geocerca"
    elif state == "outside":
        compliant = False
        label = "fuera de geocerca"
    else:
        compliant = None
        label = "sin señal de geocerca"

    return {
        "geofence_compliance_applicable": True,
        "geofence_compliant": compliant,
        "geofence_compliance_label": label,
    }


def _as_fence_list(fences: Any) -> list:
    """Acepta la forma de `fences.json` (`{"fences": [...]}`) o una lista pelada."""
    if isinstance(fences, dict):
        return list(fences.get("fences") or [])
    return list(fences or [])


def _notify_on(fence: Any) -> list:
    """Transiciones que la app re-evalúa on-device, derivadas de las acciones.

    `on_enter`/`on_exit` de la política del tenant → `enter`/`exit`. Eventos
    server-side (`on_violation`) no aplican a la app: el dispositivo solo conoce
    dentro/fuera. Sin acciones declaradas, ambas (una geocerca necesita las dos
    para decidir cumplimiento).
    """
    actions = _get(fence, "actions", None) or []
    events: set[str] = set()
    for action in actions:
        when = str(_get(action, "when", "") or "").strip().lower()
        if when == "on_enter":
            events.add("enter")
        elif when == "on_exit":
            events.add("exit")
    return sorted(events) if events else ["enter", "exit"]


def _sanitize_fence(fence: Any) -> dict:
    """Proyecta una geocerca a solo sus campos de política (whitelist).

    Nunca copia `device_id`, `apps`, `last_seen`, ni nada fuera de la whitelist:
    la config lleva la definición de la geocerca (dato de la organización), no la
    ubicación de ningún dispositivo.
    """
    out: dict = {}
    for key in _FENCE_POLICY_KEYS:
        value = _get(fence, key, None)
        if value is None:
            continue
        if key == "center" and isinstance(value, dict):
            out["center"] = {
                "lat": value.get("lat"),
                "lng": value.get("lng"),
            }
        elif key == "coordinates" and isinstance(value, (list, tuple)):
            out["coordinates"] = [
                {"lat": _get(p, "lat", None), "lng": _get(p, "lng", None)}
                for p in value
            ]
        else:
            out[key] = value
    out["notify_on"] = _notify_on(fence)
    return out


def build_geofence_appconfig(fences: Any, *, tenant_id: Optional[str] = None) -> dict:
    """Construye la Managed App Configuration que el MDM empuja a la app iOS.

    Es el diccionario clave-valor que iOS deja en `UserDefaults` bajo
    ``com.apple.configuration.managed`` y que la app lee para saber qué geocercas
    evaluar **on-device**. Contiene SOLO la definición de las geocercas de
    política (no coordenadas de dispositivos, no secretos) y fija el modo de
    reporte a solo-cumplimiento.

    Args:
        fences: la forma de `fences.json` (`{"fences": [...]}`) o una lista.
        tenant_id: identificador de tenant, opcional (no es un secreto).

    Returns:
        dict estable y serializable (JSON/plist) sin ubicación de dispositivos.
    """
    payload: dict = {
        "schema": GEOFENCE_APPCONFIG_SCHEMA,
        "evaluation": "on_device",
        "reporting": {
            "mode": "compliance_only",
            "include_coordinates": False,
        },
        "fences": [_sanitize_fence(f) for f in _as_fence_list(fences)],
    }
    if tenant_id:
        payload["tenant_id"] = str(tenant_id)
    return payload


def to_appconfig_plist(appconfig: dict) -> str:
    """Serializa la managed app config a XML plist (lo que ingiere Jamf/Intune-XML).

    Salida estable (`plistlib` ordena claves) para poder versionarla/diffearla.
    """
    return plistlib.dumps(appconfig, sort_keys=True).decode("utf-8")


def build_geofence_mobileconfig(
    fences: Any,
    *,
    organization: str,
    bundle_id: str = DEFAULT_BUNDLE_ID,
    tenant_id: Optional[str] = None,
) -> str:
    """Envuelve la app config en un perfil de configuración `.mobileconfig`.

    Para MDMs que ingieren un perfil subido en vez de clave-valor. Los UUID son
    deterministas (uuid5 sobre organización+tenant+bundle) para que el mismo
    tenant produzca siempre el mismo perfil (diffs limpios, sin ruido).

    El payload es de tipo ``com.apple.app.managed`` (Managed App Configuration):
    entrega config a una app gestionada, no captura nada del dispositivo.
    """
    appconfig = build_geofence_appconfig(fences, tenant_id=tenant_id)
    seed = f"{organization}:{tenant_id or ''}:{bundle_id}"
    profile_uuid = str(uuid.uuid5(_PROFILE_NS, seed)).upper()
    payload_uuid = str(uuid.uuid5(_PROFILE_NS, seed + ":appconfig")).upper()
    profile = {
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": f"com.lucidfence.geofence.{bundle_id}",
        "PayloadUUID": profile_uuid,
        "PayloadDisplayName": "LucidFence iOS Geofence (on-device)",
        "PayloadDescription": (
            "Configura las geocercas que la app LucidFence evalúa en el "
            "dispositivo. No recoge ubicación: el dispositivo solo reporta "
            "cumplimiento."
        ),
        "PayloadOrganization": organization,
        "PayloadContent": [
            {
                "PayloadType": "com.apple.app.managed",
                "PayloadVersion": 1,
                "PayloadIdentifier": f"com.lucidfence.geofence.{bundle_id}.appconfig",
                "PayloadUUID": payload_uuid,
                "PayloadDisplayName": "LucidFence Geofence App Configuration",
                "AppIdentifier": bundle_id,
                "Configuration": appconfig,
            }
        ],
    }
    return plistlib.dumps(profile, sort_keys=True).decode("utf-8")


__all__ = [
    "IOS_PLATFORMS",
    "GEOFENCE_APPCONFIG_SCHEMA",
    "MANAGED_APP_CONFIG_KEY",
    "DEFAULT_BUNDLE_ID",
    "is_ios_device",
    "ios_geofence_compliance",
    "build_geofence_appconfig",
    "to_appconfig_plist",
    "build_geofence_mobileconfig",
]
