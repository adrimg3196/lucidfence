"""Capability matrix declarativa por UEM.

Fuente de verdad para la UX y el enrutado multi-UEM: el producto NUNCA
ofrece una acción que el UEM no soporte (diseño §3.1 / REQ v1 matriz §3).

Regla de producto (decisiones de Product §10.2 / diseño §3.1):
  * Una acción en ``actions`` se ejecuta de verdad contra el UEM.
  * Una acción en ``dry_run_actions`` se construye y se registra como handoff
    (dry-run) pero NO muta el dispositivo hasta que su endpoint quede validado.
    Esto es exactamente el caso de Applivery: inventario + ubicación live,
    acción nativa pendiente de validar -> dry-run, nunca ejecución ciega.
  * Lo que no esté en ninguno de los dos -> ``unsupported_action`` estructurado.

El registro es aditivo: un adapter de la comunidad que no aparezca aquí conserva
el comportamiento legacy (todas las VALID_ACTIONS), de modo que no rompemos el
contrato congelado de MDMAdapter.
"""
from __future__ import annotations

from lucidfence.core.multiuem import ProviderCapabilities

# Acciones destructivas siempre human-gated en SOAR; aquí solo declaramos lo que
# el UEM expone. El gate humano lo impone el engine, no este mapa.
_APPLIVERY_DRY_RUN = frozenset({
    "lock", "wipe", "reboot", "clear_passcode", "locate", "message",
})

PROVIDER_CAPABILITIES: dict[str, ProviderCapabilities] = {
    # Android/kiosk/field. Inventario + ubicación live tras hardening (2026-07).
    # Acción nativa: endpoint undocumented no validado -> dry-run hasta validar.
    "applivery": ProviderCapabilities(
        inventory=True,
        location=True,
        native_geofences=False,
        actions=frozenset(),
        dry_run_actions=_APPLIVERY_DRY_RUN,
    ),
    # Windows/corporativo vía Microsoft Graph. Sin ubicación. Acciones Graph.
    "intune": ProviderCapabilities(
        inventory=True,
        location=False,
        native_geofences=False,
        actions=frozenset({
            "lock", "wipe", "reboot", "clear_passcode", "locate", "message",
            "set_compliance",
        }),
    ),
    # Mac. Live tras validación de host; aquí acciones declaradas (incl. DDM).
    "jamf": ProviderCapabilities(
        inventory=True,
        location=False,
        native_geofences=False,
        actions=frozenset({
            "lock", "wipe", "reboot", "clear_passcode", "locate", "message",
            "apply_ddm", "ddm_status", "ddm_sync",
        }),
    ),
    # Solicitado por el mercado; live tras validación de host.
    "workspace_one": ProviderCapabilities(
        inventory=True,
        location=False,
        native_geofences=False,
        actions=frozenset({
            "lock", "wipe", "reboot", "clear_passcode", "locate", "message",
        }),
    ),
    # Report/inventory only.
    "chromeos": ProviderCapabilities(
        inventory=True,
        location=False,
        native_geofences=False,
        actions=frozenset(),
    ),
    # Report-only; se desactiva si Intune ya aporta el mismo inventario Windows.
    "windows_conformidad": ProviderCapabilities(
        inventory=True,
        location=False,
        native_geofences=False,
        actions=frozenset(),
    ),
    # Demo 100% local, sin red. Conduce ubicación, no dispositivos reales.
    "simulation": ProviderCapabilities(
        inventory=False,
        location=True,
        native_geofences=True,
        actions=frozenset(),
    ),
}


def capability_for(name: str) -> ProviderCapabilities | None:
    """Devuelve la matriz declarada para ``name`` o ``None`` (usar fallback legacy)."""
    return PROVIDER_CAPABILITIES.get(name)


def actions_for(name: str) -> frozenset[str]:
    """Acciones reales que el UEM expone (ejecución live). Vacío si no declarado."""
    cap = PROVIDER_CAPABILITIES.get(name)
    return frozenset(cap.actions) if cap is not None else frozenset()


def dry_run_actions_for(name: str) -> frozenset[str]:
    """Acciones que el UEM solo acepta como handoff dry-run (endpoint no validado)."""
    cap = PROVIDER_CAPABILITIES.get(name)
    return frozenset(cap.dry_run_actions) if cap is not None else frozenset()
