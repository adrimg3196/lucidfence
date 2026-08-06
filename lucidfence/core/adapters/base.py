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

    #: Capacidad aditiva: el MDM expone Apple Declarative Device Management.
    #: False por defecto — el camino imperativo actual sigue siendo el fallback.
    supports_ddm: bool = False

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

    def fetch_devices(self) -> list:
        """Optional inventory pull for multi-UEM providers.

        Returns a list of ``NormalizedDevice``-like dicts (or the dataclass
        itself) so the ``MultiUEMOrchestrator`` can list each provider's fleet.
        Default ``[]`` keeps single-adapter subclasses compatible without
        forcing them to implement inventory they don't expose.
        """
        return []

    def test_connection(self) -> dict:
        """Best-effort connectivity check used by the wizard's "Probar" button.

        Adapters that expose a real API define ``_api_base`` and ``_test_path``
        (and any ``_headers``/``_auth_headers`` they already use for ``execute``);
        this default issues one GET and maps the HTTP status to ok/error. When no
        live endpoint is declared, it only validates the credential format so the
        wizard still gives the admin immediate feedback without a false "OK".
        """
        import requests  # stdlib-first would be urllib, but adapters already use requests

        base = getattr(self, "_api_base", "")
        path = getattr(self, "_test_path", "")
        auth = getattr(self, "_headers", None) or getattr(self, "_auth_headers", None)
        headers: dict = {}
        if callable(auth):
            try:
                _h = auth()
                headers = _h if isinstance(_h, dict) else {}
            except Exception as exc:
                return {"ok": False, "error_type": "auth", "error": f"no se pudo autenticar: {exc}"}
        if not base or not path:
            key = (getattr(self, "api_key", "") or "").strip()
            if not key or len(key) < 8:
                return {"ok": False, "error_type": "format", "error": "credencial vacía o demasiado corta"}
            return {"ok": True, "verified": "format_only",
                    "note": "sin endpoint de test declarado; formato de credencial válido"}
        url = (base.rstrip("/") + "/" + path.lstrip("/"))
        try:
            r = requests.get(url, headers=headers, timeout=getattr(self, "timeout", 30))
        except requests.exceptions.RequestException as exc:
            return {"ok": False, "error_type": "unreachable", "error": f"no se pudo conectar: {type(exc).__name__}: {exc}"}
        if 200 <= r.status_code < 300:
            return {"ok": True, "verified": "live", "http_status": r.status_code}
        if r.status_code in (401, 403):
            return {"ok": False, "error_type": "auth", "error": f"credenciales rechazadas (HTTP {r.status_code})"}
        try:
            body = r.text[:200]
        except Exception:
            body = ""
        return {"ok": False, "error_type": "http", "error": f"HTTP {r.status_code}: {body}"}

    # --- helpers compartidos (no parte del contrato estricto) ---

    @staticmethod
    def _dev_id(device: Any) -> Optional[str]:
        return getattr(device, "device_id", None) if not isinstance(device, dict) \
            else device.get("device_id")

    @staticmethod
    def _dev_name(device: Any) -> Optional[str]:
        return getattr(device, "name", None) if not isinstance(device, dict) \
            else device.get("name")
