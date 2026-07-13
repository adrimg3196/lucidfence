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
