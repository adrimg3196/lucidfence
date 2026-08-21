"""Registry de adapters MDM.

Reexporta las clases y helpers para mantener compatibilidad con el resto del
producto (core/actions.py, core/engine.py, tests). Añade un registro de
adapters descubribles para que la comunidad registre los suyos.

Para añadir un adapter nuevo: crea core/adapters/<mimdm>.py con una clase que
herede MDMAdapter y regístrala en ADAPTER_REGISTRY. Ver ADAPTER.md.
"""
from __future__ import annotations

from lucidfence.core.adapters.base import MDMAdapter
from lucidfence.core.adapters.simulation import SimulationAdapter
from lucidfence.core.adapters.applivery import AppliveryAdapter
from lucidfence.core.adapters.intune import IntuneAdapter
from lucidfence.core.adapters.jamf import JamfAdapter
from lucidfence.core.adapters.ios_geofence import (
    is_ios_device,
    ios_geofence_compliance,
    build_geofence_appconfig,
    to_appconfig_plist,
    build_geofence_mobileconfig,
)
from lucidfence.core.adapters.windows_conformidad import (
    WindowsConformidadAdapter,
    build_windows_conformidad_adapter_from_config,
)
from lucidfence.core.adapters.chromeos import (
    ChromeOSAdapter,
    build_chromeos_adapter_from_config,
)
from lucidfence.core.adapters.workspace_one import (
    WorkspaceONEAdapter,
    build_workspace_one_adapter_from_config,
)
from lucidfence.core.adapters.fleet import FleetAdapter

# Acciones UEM válidas (compartidas por todos los adapters).
# Los adapters que no soportan una acción devuelven `unsupported_action`; el
# gate de aquí solo decide qué acepta el engine/API, no qué sabe hacer el MDM.
VALID_ACTIONS = {
    "lock",
    "wipe",
    "message",
    "locate",
    "reboot",
    "clear_passcode",
    "custom",
    # Declarativas (Apple DDM). Sin ellas aquí, Engine.run_command y
    # POST /api/devices/{id}/command las rechazaban con "accion no valida":
    # la capa DDM quedaba inalcanzable desde el producto.
    "apply_ddm",
    "ddm_status",
    "ddm_sync",
    # Marca el dispositivo como (no) conforme en el directorio del UEM para
    # que Conditional Access le corte el acceso. Es la remediación de menor
    # riesgo y mayor uso real en flotas Microsoft: no toca el dispositivo,
    # solo su acceso. Intune la implementa vía Graph; el resto degrada con
    # unsupported_action explicando el mecanismo equivalente de su plataforma.
    "set_compliance",
}

# Registro de adapters por nombre. La comunidad puede hacer:
#   from core.adapters import ADAPTER_REGISTRY
#   ADAPTER_REGISTRY["mymdm"] = MyMdmAdapter
ADAPTER_REGISTRY = {
    "simulation": SimulationAdapter,
    "applivery": AppliveryAdapter,
    "intune": IntuneAdapter,
    "jamf": JamfAdapter,
    "windows_conformidad": WindowsConformidadAdapter,
    "chromeos": ChromeOSAdapter,
    "workspace_one": WorkspaceONEAdapter,
    "fleet": FleetAdapter,
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


def build_bindings(providers: list[dict]) -> list:
    """Build MultiUEMOrchestrator bindings from a tenant's provider config.

    Each entry: {"name": str, "org_id"?: str, "endpoint"?: str, "api_key"?: str}.
    Unknown names are skipped. The community MDMAdapter contract is reused:
    capabilities come from ``ProviderCapabilities`` defaults, inventory from
    ``adapter.fetch_devices``, actions from ``adapter.execute``.
    """
    from lucidfence.core.multiuem import ProviderBinding, ProviderCapabilities
    from lucidfence.core.adapters.capabilities import capability_for

    bindings = []
    for p in providers or []:
        name = p.get("name")
        cls = ADAPTER_REGISTRY.get(name)
        if cls is None:
            continue
        adapter = cls(
            org_id=p.get("org_id", ""),
            endpoint_template=p.get("endpoint", ""),
            api_key=p.get("api_key", ""),
        )
        # Matriz declarada por UEM (diseño §3.1 / REQ §3). Un UEM sin matriz
        # explícita conserva el comportamiento legacy (todas las VALID_ACTIONS)
        # para no romper adapters de la comunidad; uno con matriz usa SOLO lo
        # que declara (acciones reales + dry-run), nunca más.
        declared = capability_for(name)
        if declared is not None:
            capabilities = declared
        else:
            capabilities = getattr(adapter, "capabilities", None)
            if not isinstance(capabilities, ProviderCapabilities):
                capabilities = ProviderCapabilities(actions=frozenset(VALID_ACTIONS))
        bindings.append(ProviderBinding(
            name=name,
            capabilities=capabilities,
            fetch_devices=adapter.fetch_devices,
            execute_action=adapter.execute,
        ))
    return bindings


__all__ = [
    "MDMAdapter",
    "SimulationAdapter",
    "AppliveryAdapter",
    "IntuneAdapter",
    "JamfAdapter",
    "WorkspaceONEAdapter",
    "build_workspace_one_adapter_from_config",
    "is_ios_device",
    "ios_geofence_compliance",
    "build_geofence_appconfig",
    "to_appconfig_plist",
    "build_geofence_mobileconfig",
    "VALID_ACTIONS",
    "ADAPTER_REGISTRY",
    "build_adapter",
    "build_bindings",
]
