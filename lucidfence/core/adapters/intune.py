"""Microsoft Intune (MDM) adapter — LIVE mode (Microsoft Graph).

This is the live counterpart of the existing IntuneAdapter stub. The
contract on core.adapters.base is unchanged; the `_live` flag toggles
between mock (existing behaviour) and real Microsoft Graph calls.

Live endpoints (Microsoft Graph v1.0):
  Auth   : POST {tenant}/oauth2/v2.0/token  (client_credentials)
  List   : GET  /deviceManagement/managedDevices
  Action : POST /deviceManagement/managedDevices/{id}/remoteLock
                 /resetPasscode | /wipe | /rebootNow | /locateDevice
                 /sendCustomNotification (Custom Body)

Errors are mapped to AuthError / TransportError so the dashboard never
500s (per the contract on MDMAdapter.execute).
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import requests

from lucidfence.core.adapters.base import MDMAdapter
from lucidfence.core.adapters.replay import retry_after_seconds


# Mapeo acción UEM -> operación Graph + endpoint pattern.
# Para live se requiere token con scope DeviceManagementConfiguration.ReadWrite.All.
GRAPH_ACTION = {
    "lock":            ("remoteLock",         None),
    "wipe":            ("wipe",               None),
    "clear_passcode":  ("resetPasscode",      None),
    "reboot":          ("rebootNow",          None),
    "locate":          ("locateDevice",       None),
    "message":         ("sendCustomNotification", {"notificationBody": None, "notificationTitle": None}),
}

# Standard Graph paths; tenant_id is substituted at request time.
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

# Default scope for DeviceManagementManagedDevices read/write.
GRAPH_DEFAULT_SCOPE = "https://graph.microsoft.com/.default"

REQUEST_TIMEOUT_SECS = 30


class AuthError(Exception):
    """Raised on 401/403 from Microsoft Graph."""


class TransportError(Exception):
    """Raised on 5xx, network failures, or malformed responses."""


class IntuneAdapter(MDMAdapter):
    """Live Intune adapter (Microsoft Graph).

    Construct with ``live=True`` to enable real Graph calls. Otherwise
    falls back to the existing mock behaviour (SimulationAdapter-style).

    Required config (when live=True):
      tenant_id       - Azure AD tenant GUID
      client_id       - App registration client_id
      client_secret   - App registration client_secret (rotate via env)
      endpoint_template - URL template containing "{tenant_id}" placeholder
    """

    name = "intune"

    def __init__(
        self,
        org_id: str = "",
        endpoint_template: str = "https://graph.microsoft.com/v1.0",
        timeout: int = REQUEST_TIMEOUT_SECS,
        webhook_url: str = "",
        api_key: str = "",
        live: bool = False,
        tenant_id: str = "",
        client_id: str = "",
        client_secret: str = "",
        token_cache_seconds: int = 3000,
    ):
        self.org_id = org_id
        self.api_key = api_key or ""
        self.timeout = timeout
        self.webhook_url = webhook_url or os.environ.get("REMEDIATION_WEBHOOK_URL", "")
        self.live = live
        self.tenant_id = tenant_id or os.environ.get("INTUNE_TENANT_ID", "")
        self.client_id = client_id or os.environ.get("INTUNE_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("INTUNE_CLIENT_SECRET", "")
        self.endpoint_template = endpoint_template or GRAPH_BASE
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._token_cache_seconds = token_cache_seconds
        self.requests = requests
        self.replay_clock = None

    # --- token cache ---

    def _is_token_valid(self) -> bool:
        return bool(self._token) and time.time() < self._token_expires_at - 30

    def _fetch_token(self) -> str:
        """OAuth client_credentials grant against Azure AD."""
        if not (self.tenant_id and self.client_id and self.client_secret):
            raise AuthError(
                "IntuneAdapter live mode requires tenant_id, client_id, client_secret "
                "(or INTUNE_TENANT_ID / INTUNE_CLIENT_ID / INTUNE_CLIENT_SECRET env vars)"
            )
        url = GRAPH_TOKEN_URL.format(tenant_id=self.tenant_id)
        try:
            resp = self.requests.post(
                url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": GRAPH_DEFAULT_SCOPE,
                    "grant_type": "client_credentials",
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise TransportError(f"Graph token endpoint unreachable: {exc!r}") from exc

        if resp.status_code in (401, 403):
            raise AuthError(
                f"Graph token request rejected ({resp.status_code}): "
                f"{resp.text[:200] if resp.text else '<empty body>'}"
            )
        if resp.status_code >= 500:
            raise TransportError(
                f"Graph token endpoint {resp.status_code}: "
                f"{resp.text[:200] if resp.text else '<empty body>'}"
            )
        try:
            payload = resp.json()
        except ValueError as exc:
            raise TransportError(f"Graph token response not JSON: {resp.text[:200]!r}") from exc

        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        if not token:
            raise AuthError(
                f"Graph token response missing access_token: {resp.text[:200]!r}"
            )
        self._token = token
        self._token_expires_at = time.time() + min(expires_in, self._token_cache_seconds)
        return token

    def _auth_headers(self) -> dict:
        if not self._is_token_valid():
            self._fetch_token()
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, url: str, **kwargs):
        """Issue one HTTP request, honoring one 429 Retry-After via injected clock.

        Tests inject ``self.requests`` and ``self.replay_clock`` so API failures
        are replayable offline without real sleeps or secrets.
        """
        transport = self.requests
        call = {
            "GET": transport.get,
            "POST": transport.post,
            "PATCH": transport.patch,
        }[method]
        response = call(url, headers=self._auth_headers(), timeout=self.timeout, **kwargs)
        if response.status_code == 429:
            delay = retry_after_seconds(response)
            clock = self.replay_clock or getattr(transport, "clock", None) or getattr(getattr(transport, "transport", None), "clock", None)
            if delay is not None and clock is not None and hasattr(clock, "sleep"):
                clock.sleep(delay)
            response = call(url, headers=self._auth_headers(), timeout=self.timeout, **kwargs)
            setattr(response, "_lucidfence_rate_limited", 1)
        return response

    # --- helpers ---

    @staticmethod
    def _dev_id_str(device: Any) -> str:
        if isinstance(device, dict):
            return str(device.get("device_id") or device.get("id") or "")
        return str(getattr(device, "device_id", "") or getattr(device, "id", ""))

    def _normalize_list_item(self, raw: dict) -> dict:
        return {
            "device_id":   raw.get("id"),
            "name":        raw.get("deviceName"),
            "platform":    (raw.get("operatingSystem") or "").lower(),
            "compliant":   raw.get("complianceState") == "compliant",
            "encrypted":   bool(raw.get("isEncrypted")),
            "os_version":  raw.get("osVersion"),
            "battery_level": raw.get("batteryLevelPercentage"),
            "storage_free_gb": None,  # not exposed by managedDevices directly
        }

    # --- public API per MDMAdapter ---

    def test_connection(self) -> dict:
        # The OAuth client_credentials grant against Azure AD validates the
        # tenant_id / client_id / client_secret directly — a successful token
        # fetch IS a live connection check.
        try:
            self._fetch_token()
        except AuthError as exc:
            return {"ok": False, "error_type": "auth", "error": f"credenciales rechazadas: {exc}"}
        except TransportError as exc:
            return {"ok": False, "error_type": "unreachable", "error": f"no se pudo conectar: {exc}"}
        return {"ok": True, "verified": "live", "note": "token OAuth obtenido"}

    def execute(self, device: Any, action: str, params: dict, dry_run: bool = False) -> dict:
        if not self.live:
            return self._execute_mock(device, action, params, dry_run)
        try:
            return self._execute_live(device, action, params, dry_run)
        except AuthError as exc:
            return self._err("intune", device, action, "auth_error", str(exc))
        except TransportError as exc:
            return self._err("intune", device, action, "transport_error", str(exc))
        except Exception as exc:  # noqa: BLE001 — contract: never raise
            return self._err("intune", device, action, "unknown_error", repr(exc))

    # --- live mode ---

    def _execute_live(self, device: Any, action: str, params: dict, dry_run: bool) -> dict:
        if action == "list":
            return self._list_devices_live()
        device_id = self._dev_id_str(device)
        if not device_id:
            return self._err("intune", device, action, "missing_device_id", "device_id is required")

        if action == "set_compliance":
            return self._set_compliance_live(device, device_id, params, dry_run)

        if action not in GRAPH_ACTION:
            return self._err(
                "intune", device, action, "unsupported_action",
                f"action {action!r} not in {list(GRAPH_ACTION)}",
            )
        verb, body = GRAPH_ACTION[action]
        url = (
            f"{self.endpoint_template}/deviceManagement/managedDevices/"
            f"{device_id}/{verb}"
        )
        if action == "message":
            body = {
                "notificationBody":  str(params.get("text", "")),
                "notificationTitle": str(params.get("title", "From MDM")),
            }

        if dry_run:
            return {
                "adapter":  "intune",
                "ok":       True,
                "device_id": device_id,
                "action":    action,
                "mode":      "dry_run",
                "would_send": {"method": "POST", "url": url, "json": body},
            }

        resp = self._request("POST", url, json=body)

        if resp.status_code in (401, 403):
            self._token = None  # force refresh on next call
            raise AuthError(f"Graph API rejected the action call ({resp.status_code}): {resp.text[:200]}")
        if resp.status_code == 404:
            return self._err("intune", device, action, "device_not_found",
                             f"managed device {device_id} not found in tenant {self.tenant_id}")
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransportError(f"Graph API {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            return self._err("intune", device, action, "graph_rejected",
                             f"Graph {resp.status_code}: {resp.text[:200]}")
        try:
            data = resp.json()
        except ValueError:
            data = {}
        return {
            "adapter":   "intune",
            "ok":        True,
            "device_id": device_id,
            "action":    action,
            "mode":      "live",
            "graph_status": resp.status_code,
            "graph_response_keys": list(data.keys())[:8],
        }

    def _set_compliance_live(self, device: Any, device_id: str, params: dict, dry_run: bool) -> dict:
        """Marca el dispositivo (no) conforme en Entra vía Graph.

        Camino: managedDevice -> azureADDeviceId -> objeto /devices ->
        PATCH isCompliant. Requiere Device.ReadWrite.All ADEMÁS del scope
        de Intune, y Microsoft solo lo acepta desde apps MDM aprobadas /
        integraciones de compliance partner (en Windows de forma general;
        en Apple puede rechazarlo). Por eso el error de Graph se devuelve
        VERBATIM: el admin tiene que ver el motivo real, no un genérico.
        """
        compliant = bool((params or {}).get("compliant", False))

        r1 = self._request(
            "GET",
            f"{self.endpoint_template}/deviceManagement/managedDevices/{device_id}"
            "?$select=id,azureADDeviceId",
        )
        if r1.status_code in (401, 403):
            self._token = None
            raise AuthError(f"Graph rejected managedDevice lookup ({r1.status_code}): {r1.text[:200]}")
        if r1.status_code == 404:
            return self._err("intune", device, "set_compliance", "device_not_found",
                             f"managed device {device_id} not found in tenant {self.tenant_id}")
        if r1.status_code >= 400:
            raise TransportError(f"Graph API {r1.status_code}: {r1.text[:200]}")
        aad_id = (r1.json() or {}).get("azureADDeviceId") or ""
        if not aad_id or aad_id == "00000000-0000-0000-0000-000000000000":
            return self._err("intune", device, "set_compliance", "no_azuread_device",
                             "managed device has no Entra (Azure AD) device object; "
                             "compliance/Conditional Access does not apply to it")

        r2 = self._request(
            "GET",
            f"{self.endpoint_template}/devices?$filter=deviceId eq '{aad_id}'&$select=id",
        )
        if r2.status_code in (401, 403):
            self._token = None
            raise AuthError(
                f"Graph rejected /devices lookup ({r2.status_code}): {r2.text[:200]} "
                "(hint: la app registration necesita Device.ReadWrite.All)")
        if r2.status_code >= 400:
            raise TransportError(f"Graph API {r2.status_code}: {r2.text[:200]}")
        values = (r2.json() or {}).get("value") or []
        if not values:
            return self._err("intune", device, "set_compliance", "no_azuread_device",
                             f"no /devices object found for deviceId {aad_id}")
        object_id = values[0].get("id")

        url = f"{self.endpoint_template}/devices/{object_id}"
        body = {"isCompliant": compliant}
        if dry_run:
            return {
                "adapter": "intune", "ok": True, "device_id": device_id,
                "action": "set_compliance", "mode": "dry_run", "compliant": compliant,
                "would_send": {"method": "PATCH", "url": url, "json": body},
            }
        r3 = self._request("PATCH", url, json=body)
        if r3.status_code in (401, 403):
            self._token = None
            raise AuthError(
                f"Graph rejected isCompliant PATCH ({r3.status_code}): {r3.text[:200]} "
                "(hint: solo apps MDM aprobadas / compliance partners pueden "
                "escribir isCompliant; requiere Device.ReadWrite.All)")
        if r3.status_code >= 400:
            return self._err("intune", device, "set_compliance", "graph_rejected",
                             f"Graph {r3.status_code}: {r3.text[:200]}")
        return {
            "adapter": "intune", "ok": True, "device_id": device_id,
            "action": "set_compliance", "mode": "live", "compliant": compliant,
            "azuread_object_id": object_id, "graph_status": r3.status_code,
        }

    def _list_devices_live(self) -> dict:
        url = f"{self.endpoint_template}/deviceManagement/managedDevices"
        params = {"$top": 200, "$select": "id,deviceName,operatingSystem,complianceState,isEncrypted,osVersion,batteryLevelPercentage"}
        items: list[dict] = []
        seen_urls = set()
        rate_limited = 0
        while True:
            if url in seen_urls:
                return {
                    "adapter": "intune",
                    "ok": False,
                    "action": "list",
                    "mode": "live",
                    "error_type": "duplicate_cursor",
                    "error": f"Graph pagination repeated cursor {url!r}",
                    "replay": {"partial_count": len(items), "rate_limited": rate_limited},
                }
            seen_urls.add(url)
            resp = self._request("GET", url, params=params)
            rate_limited += int(getattr(resp, "_lucidfence_rate_limited", 0) or 0)
            if resp.status_code in (401, 403):
                self._token = None
                raise AuthError(f"Graph list rejected ({resp.status_code}): {resp.text[:200]}")
            if resp.status_code >= 500:
                raise TransportError(f"Graph list {resp.status_code}: {resp.text[:200]}")
            if resp.status_code >= 400:
                return self._err("intune", {"device_id": "", "name": ""}, "list",
                                 "graph_rejected", f"Graph {resp.status_code}: {resp.text[:200]}")
            try:
                payload = resp.json() or {}
            except ValueError:
                return self._err("intune", {"device_id": "", "name": ""}, "list",
                                 "invalid_payload", "Graph list response was not JSON")
            items.extend(payload.get("value", []) or [])
            next_url = payload.get("@odata.nextLink")
            if not next_url:
                break
            url = str(next_url)
            params = None
        normalized = [self._normalize_list_item(x) for x in items]
        return {
            "adapter":   "intune",
            "ok":        True,
            "action":    "list",
            "mode":      "live",
            "devices":   normalized,
            "count":     len(normalized),
            "replay":    {"pages": len(seen_urls), "rate_limited": rate_limited},
        }

    # --- mock fallback (unchanged contract behaviour) ---

    def _execute_mock(self, device: Any, action: str, params: dict, dry_run: bool) -> dict:
        # Mock-mode path matches the legacy IntuneAdapter shape so existing
        # test_adapters_contrib assertions (``mock=True``, ``graph_action``, …)
        # stay green. Identical surface to the pre-live adapter.
        import uuid as _uuid
        device_id = self._dev_id_str(device)
        cmd_id = f"intune-mock-{_uuid.uuid4().hex[:12]}"
        return {
            "adapter":      self.name,
            "ok":           True,
            "mock":         True,
            "command_id":   cmd_id,
            "device_id":    device_id,
            "device_name":  self._dev_name(device),
            "action":       action,
            "graph_action": GRAPH_ACTION.get(action, ("", None))[0],
            "params":       params,
            "dry_run":      dry_run,
            "note":         "IntuneAdapter in mock mode (no live credentials). Resolves #1.",
        }

    @staticmethod
    def _dev_name(device: Any) -> Optional[str]:
        if isinstance(device, dict):
            return device.get("name")
        return getattr(device, "name", None)

    # --- error helpers ---

    @staticmethod
    def _err(adapter: str, device: Any, action: str, kind: str, message: str) -> dict:
        device_id = ""
        if isinstance(device, dict):
            device_id = str(device.get("device_id") or "")
        else:
            device_id = str(getattr(device, "device_id", "") or "")
        return {
            "adapter":   adapter,
            "ok":        False,
            "device_id": device_id,
            "action":    action,
            "error":     message,
            "error_type": kind,
        }


def build_intune_adapter_from_config(cfg: dict) -> IntuneAdapter:
    """Construct an IntuneAdapter from a config dict.

    Recognises:
        live: bool
        tenant_id: str
        client_id: str
        client_secret: str
        endpoint_template: str
    """
    intune_cfg = (cfg.get("mdm") or {}).get("intune") or {}
    return IntuneAdapter(
        live=intune_cfg.get("live", False),
        tenant_id=intune_cfg.get("tenant_id", ""),
        client_id=intune_cfg.get("client_id", ""),
        client_secret=intune_cfg.get("client_secret", ""),
        endpoint_template=intune_cfg.get("endpoint_template", GRAPH_BASE),
    )
