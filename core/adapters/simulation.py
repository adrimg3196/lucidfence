"""Simulation adapter — registra la acción localmente, sin contactar un dispositivo real.

Perfecto para una demo 100% local y funcional. Implementa MDMAdapter.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from core.adapters.base import MDMAdapter


class SimulationAdapter(MDMAdapter):
    name = "simulation"

    def execute(self, device: Any, action: str, params: dict, dry_run: bool = False) -> dict:
        cmd_id = f"sim-{uuid.uuid4().hex[:12]}"
        return {
            "adapter": self.name,
            "ok": True,
            "command_id": cmd_id,
            "device_id": self._dev_id(device),
            "device_name": self._dev_name(device),
            "action": action,
            "params": params,
            "dry_run": dry_run,
            "note": "Simulated action (no real device contacted).",
        }

    def geofence_compliance_snapshot(
        self,
        device: Any,
        fence_state: str = "unknown",
        fence_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Return a simulated iOS geofence-compliance posture.

        This helper is deliberately outside the strict MDMAdapter contract so a
        local demo can show Apple/iOS geofence compliance without contacting any
        real MDM tenant or forcing community adapters to implement new methods.
        """
        from core.adapters.ios_geofence import is_ios_device

        if not is_ios_device(device):
            return None

        raw = device if isinstance(device, dict) else getattr(device, "raw", {}) or {}
        seed = raw.get("geofence_compliance") if isinstance(raw, dict) else None
        seed = seed if isinstance(seed, dict) else {}
        compliant = seed.get("compliant")
        if compliant is None:
            dev_compliant = getattr(device, "compliant", None) if not isinstance(device, dict) else device.get("compliant")
            compliant = dev_compliant is not False and fence_state != "outside"

        return {
            "platform": "ios",
            "mode": "simulated",
            "policy_id": seed.get("policy_id") or "ios-geofence-sales-v1",
            "policy_name": seed.get("policy_name") or "iOS Sales / Showroom geofence",
            "required": bool(seed.get("required", True)),
            "compliant": bool(compliant),
            "state": seed.get("state") or ("inside_required_zone" if fence_state == "inside" else fence_state),
            "fence_id": fence_id or seed.get("fence_id"),
            "supervised": bool(seed.get("supervised", True)),
            "ade_enrolled": bool(seed.get("ade_enrolled", True)),
            "ddm_status": seed.get("ddm_status") or "simulated",
            "last_checkin": seed.get("last_checkin") or raw.get("last_checkin") or raw.get("last_seen"),
            "evidence": seed.get("evidence") or "Simulated from local iOS fleet seed + engine fence_state.",
        }
