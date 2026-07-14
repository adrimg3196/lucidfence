"""Adapter de vitrina para cumplimiento de geocercas en flotas iOS.

No contacta ningún MDM real. Convierte el estado calculado por el engine
(`fence_state`) en campos explícitos que la vitrina cloud puede mostrar para
dispositivos iOS/iPadOS simulados.
"""
from __future__ import annotations

from typing import Any, Optional


IOS_PLATFORMS = {"ios", "ipados"}


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


__all__ = ["IOS_PLATFORMS", "is_ios_device", "ios_geofence_compliance"]
