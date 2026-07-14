"""Registry de adapters MDM.

Reexporta las clases y helpers para mantener compatibilidad con el resto del
producto (core/actions.py, core/engine.py, tests). Añade un registro de
adapters descubribles para que la comunidad registre los suyos.

Para añadir un adapter nuevo: crea core/adapters/<mimdm>.py con una clase que
herede MDMAdapter y regístrala en ADAPTER_REGISTRY. Ver ADAPTER.md.
"""
from __future__ import annotations

from core.adapters.base import MDMAdapter
from core.adapters.simulation import SimulationAdapter
from core.adapters.applivery import AppliveryAdapter
from core.adapters.intune import IntuneAdapter
from core.adapters.jamf import JamfAdapter
from core.adapters.ios_geofence import is_ios_device, ios_geofence_compliance

# Acciones UEM válidas (compartidas por todos los adapters).
VALID_ACTIONS = {
    "lock",
    "wipe",
    "message",
    "locate",
    "reboot",
    "clear_passcode",
    "custom",
}

# Registro de adapters por nombre. La comunidad puede hacer:
#   from core.adapters import ADAPTER_REGISTRY
#   ADAPTER_REGISTRY["mymdm"] = MyMdmAdapter
ADAPTER_REGISTRY = {
    "simulation": SimulationAdapter,
    "applivery": AppliveryAdapter,
    "intune": IntuneAdapter,
    "jamf": JamfAdapter,
}


def build_adapter(mode: str, org_id: str, endpoint_template: str,
                  webhook_url: str = "", api_key: str = "") -> MDMAdapter:
    """Construye el adapter según el modo. Mantiene la firma de core.actions
    para no romper el engine ni los tests existentes."""
    if mode in ADAPTER_REGISTRY:
        cls = ADAPTER_REGISTRY[mode]
    elif mode == "live":
        cls = AppliveryAdapter  # compat: live por defecto = Applivery
    else:
        cls = SimulationAdapter
    # Los adapters simulados no necesitan credenciales.
    if mode == "simulation" or cls is SimulationAdapter:
        return SimulationAdapter()
    if cls is AppliveryAdapter:
        return AppliveryAdapter(org_id=org_id, endpoint_template=endpoint_template,
                                webhook_url=webhook_url, api_key=api_key)
    # Intune/Jamf: pasan org_id + credenciales por env (mock si no hay token).
    return cls(org_id=org_id, endpoint_template=endpoint_template,
               webhook_url=webhook_url, api_key=api_key)


__all__ = [
    "MDMAdapter",
    "SimulationAdapter",
    "AppliveryAdapter",
    "IntuneAdapter",
    "JamfAdapter",
    "is_ios_device",
    "ios_geofence_compliance",
    "VALID_ACTIONS",
    "ADAPTER_REGISTRY",
    "build_adapter",
]
