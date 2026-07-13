"""MDMAdapter — interfaz congelada para conectores de Mobile Device Management.

Esta es la superficie de contribución del proyecto open-source. Cualquier MDM
(Applivery, Intune, Jamf, Fleet, Workspace ONE...) se integra implementando
esta interfaz. El core del producto (Risk Engine, geofencing, dashboard) es
agnóstico al MDM: un adapter es solo fuente de ubicación + destino de acciones.

CONTRATO (no lo cambies sin bump de versión mayor — rompe adapters de la comunidad):

    class MDMAdapter:
        name: str                      # identificador estable, p.ej. "applivery"
        def execute(self, device, action: str, params: dict, dry_run: bool = False) -> dict:
            # Ejecuta una acción UEM remota (lock/wipe/locate/message/reboot/
            # clear_passcode). Retorna un dict normalizado (ver SimulationAdapter).
            # NUNCA debe hacer raise: el dashboard no debe 500ear. Devolver
            # {"ok": False, "error": ...} en lugar de excepción.

Ver `ADAPTER.md` para la guía de contribución y el Adapter Bounty Sprint.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class MDMAdapter(ABC):
    """Interfaz base de un conector MDM.

    Implementa `execute` y expón `name`. El resto del producto solo depende
    de estos dos miembros.
    """

    #: Identificador estable del MDM (p.ej. "applivery", "intune", "jamf").
    name: str = "base"

    @abstractmethod
    def execute(self, device: Any, action: str, params: dict, dry_run: bool = False) -> dict:
        """Ejecuta una acción UEM remota y devuelve un dict normalizado.

        Args:
            device: objeto con al menos ``device_id`` y ``name`` (o un dict).
            action: uno de VALID_ACTIONS (lock/wipe/message/locate/reboot/
                clear_passcode/custom).
            params: argumentos de la acción (p.ej. texto del mensaje).
            dry_run: si True, construye la petición pero no la envía.

        Returns:
            dict con claves: adapter, ok (bool), device_id, action, y detalles.
            En fallo: {"ok": False, "error": "..."} — NUNCA lance excepción.
        """
        raise NotImplementedError

    # --- helpers compartidos (no parte del contrato estricto) ---

    @staticmethod
    def _dev_id(device: Any) -> Optional[str]:
        return getattr(device, "device_id", None) if not isinstance(device, dict) \
            else device.get("device_id")

    @staticmethod
    def _dev_name(device: Any) -> Optional[str]:
        return getattr(device, "name", None) if not isinstance(device, dict) \
            else device.get("name")
