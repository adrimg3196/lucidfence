"""UEM action executors — façade sobre core.adapters.

El código de los adapters vive en core/adapters/ (SimulationAdapter, AppliveryAdapter,
IntuneAdapter, JamfAdapter) detrás de la interfaz MDMAdapter (core/adapters/base.py).
Este módulo reexporta los símbolos para mantener compatibilidad con el engine y
los tests existentes. Nuevos MDMs: añadir un adapter en core/adapters/ y
registrarlo en ADAPTER_REGISTRY (ver ADAPTER.md).

Verified contract (2026-07-09, live contra api.applivery.io con token real):
  Auth : Authorization: Bearer <APPLIVERY_API_KEY>   (NO X-Api-Token)
  Base : https://api.applivery.io/v1
  Command endpoint: POST /v1/organizations/{org}/mdm/devices/{deviceId}/commands
    NOTA: el comando remoto no está en la referencia pública; el AppliveryAdapter
    delega vía webhook de remediación si el endpoint 404ea. NUNCA hace raise.
"""
from __future__ import annotations

from core.adapters import (  # noqa: F401
    MDMAdapter,
    SimulationAdapter,
    AppliveryAdapter,
    IntuneAdapter,
    JamfAdapter,
    VALID_ACTIONS,
    ADAPTER_REGISTRY,
    build_adapter,
)

# Alias para no romper referencias históricas (LiveAdapter === AppliveryAdapter).
LiveAdapter = AppliveryAdapter

__all__ = [
    "MDMAdapter",
    "SimulationAdapter",
    "AppliveryAdapter",
    "LiveAdapter",
    "IntuneAdapter",
    "JamfAdapter",
    "VALID_ACTIONS",
    "ADAPTER_REGISTRY",
    "build_adapter",
]
