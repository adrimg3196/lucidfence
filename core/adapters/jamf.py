"""Jamf Pro (MDM) adapter — LIVE mode (Jamf Pro API).

This is the live counterpart of the existing JamfAdapter stub. The
contract on core.adapters.base is unchanged; the ``live`` flag toggles
between mock (existing behaviour) and real Jamf Pro API calls.

Live endpoints (Jamf Pro API v1/v2):
  Auth   : POST {base_url}/api/v1/auth/token  (Basic client_id:client_secret)
  List   : GET  /api/v1/mobile-devices
                ?page-size=200&section=GENERAL
  Action : POST /api/v1/mobile-devices/{id}/commands
                body: {"commandData": {"commandType": "LOCK_DEVICE" | ...}}
  Verbs  : LOCK_DEVICE | ERASE_DEVICE | RESTART_DEVICE | CLEAR_PASSCODE |
           LOCATE_DEVICE | SEND_MESSAGE

Errors are mapped to AuthError / TransportError so the dashboard never
500s (per the contract on MDMAdapter.execute).
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional

import requests

from core.adapters.base import MDMAdapter


# Acción UEM -> comando Jamf (verb del endpoint de commands).
JAMF_VERB = {
    "lock": "LOCK_DEVICE",
    "wipe": "ERASE_DEVICE",
    "reboot": "RESTART_DEVICE",
    "clear_passcode": "CLEAR_PASSCODE",
    "locate": "LOCATE_DEVICE",
    "message": "SEND_MESSAGE",
}

# Jamf Pro API paths; base_url is substituted at request time.
JAMF_TOKEN_PATH = "/api/v1/auth/token"
JAMF_DEVICES_PATH = "/api/v1/mobile-devices"
JAMF_COMMANDS_PATH = "/api/v1/mobile-devices/{id}/commands"

REQUEST_TIMEOUT_SECS = 30


class AuthError(Exception):
    """Raised on 401/403 from the Jamf Pro API."""


class TransportError(Exception):
    """Raised on 5xx, network failures, or malformed responses."""


class JamfAdapter(MDMAdapter):
    """Live Jamf Pro adapter.

    Construct with ``live=True`` to enable real Jamf Pro API calls. Otherwise
    falls back to the existing mock behaviour (SimulationAdapter-style).

    Required config (when live=True):
      base_url    - Jamf Pro tenant URL (e.g. https://acme.jamfcloud.com)
      client_id    - API role client_id (Basic auth)
      client_secret - API role client_secret (rotate via env)
    """

    name = "jamf"

    def __init__(
        self,
        org_id: str = "",
        endpoint_template: str = "",
        timeout: int = REQUEST_TIMEOUT_SECS,
        webhook_url: str = "",
        api_key: str = "",
        live: bool = False,
        base_url: str = "",
        client_id: str = "",
        client_secret: str = "",
        token_cache_seconds: int = 3000,
    ):
        self.org_id = org_id
        self.api_key = api_key or ""
        self.timeout = timeout
        self.webhook_url = webhook_url or os.environ.get("REMEDIATION_WEBHOOK_URL", "")
        self.live = live
        self.base_url = (base_url or endpoint_template or os.environ.get("JAMF_BASE_URL", "")).rstrip("/")
        self.client_id = client_id or os.environ.get("JAMF_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("JAMF_CLIENT_SECRET", "")
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._token_cache_seconds = token_cache_seconds

    # --- token cache (Basic auth -> bearer) ---

    def _is_token_valid(self) -> bool:
        return bool(self._token) and time.time() < self._token_expires_at - 30

    def _fetch_token(self) -> str:
        """Jamf Pro API token grant (Basic auth)."""
        if not (self.base_url and self.client_id and self.client_secret):
            raise AuthError(
                "JamfAdapter live mode requires base_url, client_id, client_secret "
                "(or JAMF_BASE_URL / JAMF_CLIENT_ID / JAMF_CLIENT_SECRET env vars)"
            )
        url = f"{self.base_url}{JAMF_TOKEN_PATH}"
        try:
            resp = requests.post(
                url,
                auth=(self.client_id, self.client_secret),
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise TransportError(f"Jamf token endpoint unreachable: {exc!r}") from exc

        if resp.status_code in (401, 403):
            raise AuthError(
                f"Jamf token request rejected ({resp.status_code}): "
                f"{resp.text[:200] if resp.text else '<empty body>'}"
            )
        if resp.status_code >= 500:
            raise TransportError(
                f"Jamf token endpoint {resp.status_code}: "
                f"{resp.text[:200] if resp.text else '<empty body>'}"
            )
        try:
            payload = resp.json()
        except ValueError as exc:
            raise TransportError(f"Jamf token response not JSON: {resp.text[:200]!r}") from exc

        token = payload.get("token")
        expires_in = int(payload.get("expires_in", 3600))
        if not token:
            raise AuthError(
                f"Jamf token response missing token: {resp.text[:200]!r}"
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

    # --- helpers ---

    @staticmethod
    def _dev_id_str(device: Any) -> str:
        if isinstance(device, dict):
            return str(device.get("device_id") or device.get("id") or device.get("managementId") or "")
        return str(getattr(device, "device_id", "") or getattr(device, "id", "") or getattr(device, "managementId", ""))

    def _normalize_list_item(self, raw: dict) -> dict:
        return {
            "device_id": raw.get("id"),
            "name": (raw.get("general") or {}).get("name") or raw.get("name"),
            "platform": ((raw.get("general") or {}).get("platform") or "").lower(),
            "compliant": None,  # Jamf mobile-devices doesn't expose compliance directly
            "encrypted": None,
            "os_version": (raw.get("general") or {}).get("osVersion"),
            "battery_level": None,
            "storage_free_gb": None,
        }

    # --- public API per MDMAdapter ---

    def execute(self, device: Any, action: str, params: dict, dry_run: bool = False) -> dict:
        if not self.live:
            return self._execute_mock(device, action, params, dry_run)
        try:
            return self._execute_live(device, action, params, dry_run)
        except AuthError as exc:
            return self._err("jamf", device, action, "auth_error", str(exc))
        except TransportError as exc:
            return self._err("jamf", device, action, "transport_error", str(exc))
        except Exception as exc:  # noqa: BLE001 — contract: never raise
            return self._err("jamf", device, action, "unknown_error", repr(exc))

    # --- live mode ---

    def _execute_live(self, device: Any, action: str, params: dict, dry_run: bool) -> dict:
        if action == "list":
            return self._list_devices_live()
        device_id = self._dev_id_str(device)
        if not device_id:
            return self._err("jamf", device, action, "missing_device_id", "device_id is required")

        if action not in JAMF_VERB:
            return self._err(
                "jamf", device, action, "unsupported_action",
                f"action {action!r} not in {list(JAMF_VERB)}",
            )
        verb = JAMF_VERB[action]
        url = f"{self.base_url}{JAMF_COMMANDS_PATH.format(id=device_id)}"
        body: dict = {"commandData": {"commandType": verb}}
        if action == "message":
            body["clientData"] = []
            body["commandData"]["pushNotification"] = {
                "message": str(params.get("text", "")),
                "subject": str(params.get("title", "From MDM")),
            }

        if dry_run:
            return {
                "adapter": "jamf",
                "ok": True,
                "device_id": device_id,
                "action": action,
                "mode": "dry_run",
                "would_send": {"method": "POST", "url": url, "json": body},
            }

        resp = requests.post(url, headers=self._auth_headers(), json=body, timeout=self.timeout)

        if resp.status_code in (401, 403):
            self._token = None  # force refresh on next call
            raise AuthError(f"Jamf API rejected the command call ({resp.status_code}): {resp.text[:200]}")
        if resp.status_code == 404:
            return self._err("jamf", device, action, "device_not_found",
                             f"mobile device {device_id} not found in {self.base_url}")
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransportError(f"Jamf API {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            return self._err("jamf", device, action, "jamf_rejected",
                             f"Jamf {resp.status_code}: {resp.text[:200]}")
        try:
            data = resp.json()
        except ValueError:
            data = {}
        return {
            "adapter": "jamf",
            "ok": True,
            "device_id": device_id,
            "action": action,
            "mode": "live",
            "jamf_status": resp.status_code,
            "jamf_response_keys": list(data.keys())[:8],
        }

    def _list_devices_live(self) -> dict:
        url = f"{self.base_url}{JAMF_DEVICES_PATH}"
        resp = requests.get(
            url,
            headers=self._auth_headers(),
            params={"page-size": 200, "section": "GENERAL"},
            timeout=self.timeout,
        )
        if resp.status_code in (401, 403):
            self._token = None
            raise AuthError(f"Jamf list rejected ({resp.status_code}): {resp.text[:200]}")
        if resp.status_code >= 500:
            raise TransportError(f"Jamf list {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            return self._err("jamf", {"device_id": "", "name": ""}, "list",
                             "jamf_rejected", f"Jamf {resp.status_code}: {resp.text[:200]}")
        results = (resp.json() or {}).get("results", [])
        items = [self._normalize_list_item(x) for x in results]
        return {
            "adapter": "jamf",
            "ok": True,
            "action": "list",
            "mode": "live",
            "devices": items,
            "count": len(items),
        }

    # --- mock fallback (unchanged contract behaviour) ---

    def _execute_mock(self, device: Any, action: str, params: dict, dry_run: bool) -> dict:
        # Mock-mode path matches the legacy JamfAdapter shape so existing
        # test_adapters_contrib assertions (mock=True, jamf_verb=...) stay green.
        import uuid as _uuid
        device_id = self._dev_id_str(device)
        cmd_id = f"jamf-mock-{_uuid.uuid4().hex[:12]}"
        return {
            "adapter": self.name,
            "ok": True,
            "mock": True,
            "command_id": cmd_id,
            "device_id": device_id,
            "device_name": self._dev_name(device),
            "action": action,
            "jamf_verb": JAMF_VERB.get(action),
            "params": params,
            "dry_run": dry_run,
            "note": "JamfAdapter in mock mode (no live credentials). Resolves #2.",
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
            device_id = str(device.get("device_id") or device.get("id") or "")
        else:
            device_id = str(getattr(device, "device_id", "") or getattr(device, "id", "") or "")
        return {
            "adapter": adapter,
            "ok": False,
            "device_id": device_id,
            "action": action,
            "error": message,
            "error_type": kind,
        }


def build_jamf_adapter_from_config(cfg: dict) -> JamfAdapter:
    """Construct a JamfAdapter from a config dict.

    Recognises:
        live: bool
        base_url: str
        client_id: str
        client_secret: str
    """
    jamf_cfg = (cfg.get("mdm") or {}).get("jamf") or {}
    return JamfAdapter(
        live=jamf_cfg.get("live", False),
        base_url=jamf_cfg.get("base_url", ""),
        client_id=jamf_cfg.get("client_id", ""),
        client_secret=jamf_cfg.get("client_secret", ""),
    )
