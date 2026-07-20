"""ChromeOS device adapter for LucidFence.

Reports on-device compliance posture for ChromeOS endpoints managed via
Google Admin SDK / Directory API (cross-platform parity with #13 Intune
and #21 Windows). Read-only contract — same pattern as
WindowsConformidadAdapter.

Implementa MDMAdapter (read-only contract: action='report').
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Optional

from core.adapters.base import MDMAdapter


class ChromeOSAdapter(MDMAdapter):
    """Read-only ChromeOS device posture reporter.

    In live mode, requires Google Workspace creds (GOOGLE_ADMIN_REFRESH_TOKEN
    / GOOGLE_ADMIN_CLIENT_ID / GOOGLE_ADMIN_CLIENT_SECRET) and queries
    `https://admin.googleapis.com/admin/directory/v1/customer/{id}/devices/chromeos`.

    In mock mode (default, no creds), returns a stable synthetic report
    so the dashboard pipeline is exercisable end-to-end without a
    Google Workspace tenant.
    """

    name = "chromeos"

    SUPPORTED_ACTIONS = {"report"}

    def __init__(
        self,
        org_id: str = "",
        endpoint_template: str = "https://admin.googleapis.com/admin/directory/v1",
        timeout: int = 30,
        webhook_url: str = "",
        api_key: str = "",
        live: bool = False,
        refresh_token: str = "",
        client_id: str = "",
        client_secret: str = "",
        customer_id: str = "",
    ):
        self.org_id = org_id
        self.endpoint_template = endpoint_template
        self.timeout = timeout
        self.webhook_url = webhook_url or os.environ.get("REMEDIATION_WEBHOOK_URL", "")
        self.api_key = api_key or ""
        self.live = live
        self.refresh_token = refresh_token or os.environ.get("GOOGLE_ADMIN_REFRESH_TOKEN", "")
        self.client_id = client_id or os.environ.get("GOOGLE_ADMIN_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("GOOGLE_ADMIN_CLIENT_SECRET", "")
        self.customer_id = customer_id or os.environ.get("GOOGLE_ADMIN_CUSTOMER_ID", "my_customer")
        self._access_token: Optional[str] = None
        self._access_token_expires_at: float = 0.0

    # --- helpers ---

    @staticmethod
    def _dev_id_str(device: Any) -> str:
        if isinstance(device, dict):
            return str(device.get("device_id") or device.get("id") or "")
        return str(getattr(device, "device_id", "") or getattr(device, "id", ""))

    def _is_token_valid(self) -> bool:
        return bool(self._access_token) and time.time() < self._access_token_expires_at - 30

    def _fetch_access_token(self) -> str:
        """OAuth refresh_token grant against Google's token endpoint."""
        import requests as _req
        if not (self.refresh_token and self.client_id and self.client_secret):
            raise RuntimeError(
                "ChromeOSAdapter live mode requires refresh_token / client_id / client_secret "
                "(or GOOGLE_ADMIN_REFRESH_TOKEN / CLIENT_ID / CLIENT_SECRET env vars)"
            )
        resp = _req.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Google OAuth refresh HTTP {resp.status_code}: {resp.text[:200]}"
            )
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Google OAuth response missing access_token")
        self._access_token = token
        self._access_token_expires_at = time.time() + int(data.get("expires_in", 3600))
        return token

    def _auth_headers(self) -> dict:
        if not self._is_token_valid():
            self._fetch_access_token()
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

    # --- public API ---

    def execute(self, device: Any, action: str, params: dict, dry_run: bool = False) -> dict:
        device_id = self._dev_id_str(device)
        if action not in self.SUPPORTED_ACTIONS:
            return self._err(action, "unsupported_action",
                             f"action {action!r} not supported (only 'report')")
        if self.live:
            return self._report_live(device_id, params, dry_run)
        return self._report_mock(device_id, params, dry_run)

    # --- live path (Google Admin SDK / Directory API) ---

    def _report_live(self, device_id: str, params: dict, dry_run: bool) -> dict:
        import requests as _req
        if not (self.refresh_token and self.client_id and self.client_secret):
            return self._err("report", "auth_error",
                             "ChromeOS live mode requires "
                             "GOOGLE_ADMIN_REFRESH_TOKEN / CLIENT_ID / CLIENT_SECRET")
        url = (
            f"{self.endpoint_template}/customer/{self.customer_id}/devices/chromeos"
            "?projection=FULL&maxResults=200"
        )
        if dry_run:
            return {
                "adapter": self.name,
                "ok": True,
                "mode": "dry_run",
                "would_send": {"method": "GET", "url": url,
                                "headers": {"Authorization": "Bearer <stub>"}},
            }
        try:
            resp = _req.get(url, headers=self._auth_headers(), timeout=self.timeout)
        except _req.RequestException as exc:
            return self._err("report", "transport_error", repr(exc))
        if resp.status_code in (401, 403):
            return self._err("report", "auth_error",
                             f"Google Admin rejected {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 500:
            return self._err("report", "transport_error",
                             f"Google Admin {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            return self._err("report", "google_rejected",
                             f"Google Admin {resp.status_code}: {resp.text[:200]}")
        items = resp.json().get("chromeosdevices", [])
        devices = [self._normalize(item) for item in items]
        return {
            "adapter": self.name,
            "ok": True,
            "mode": "live",
            "action": "report",
            "count": len(devices),
            "devices": devices,
            "queried_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    @staticmethod
    def _normalize(item: dict) -> dict:
        # Map Google Admin SDK's chromeosdevices shape into a small normalised dict.
        status = item.get("status", "")
        compliant = status in ("ACTIVE", "Provisioned")
        boot_mode = item.get("bootMode", "Unknown")
        return {
            "device_id": item.get("deviceId"),
            "name": item.get("machineName") or item.get("annotatedAsset") or item.get("deviceId"),
            "os": "ChromeOS",
            "os_version": item.get("osVersion", ""),
            "compliant": compliant,
            "encrypted": boot_mode in ("Verified", "DevMode"),  # verified boot ≈ device-encrypted storage
            "device_type": item.get("model", "chromebook"),
            "last_sync": item.get("lastSync"),
            "org_unit": item.get("orgUnitPath"),
        }

    # --- mock fallback (stable synthetic report) ---

    def _report_mock(self, device_id: str, params: dict, dry_run: bool) -> dict:
        seed = abs(hash(device_id or "unknown")) if device_id else 0
        compliant = bool(seed % 2 == 0)
        verified_boot = bool(seed % 3 != 0)
        if dry_run:
            return {
                "adapter": self.name,
                "ok": True,
                "mode": "dry_run",
                "would_send": {"method": "GET", "url": "<google-admin>"},
            }
        device_obj = {
            "device_id": device_id or f"croso-mock-{uuid.uuid4().hex[:8]}",
            "name": f"Chromebook {device_id or 'unknown'}",
            "os": "ChromeOS",
            "os_version": "130.0.6723.116",
            "compliant": compliant,
            "encrypted": verified_boot,
            "device_type": "chromebook",
            "last_sync": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "org_unit": "/",
        }
        report: dict = {
            "adapter": self.name,
            "ok": True,
            "mode": "mock",
            "action": "report",
            "queried_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "devices": [device_obj],
            "summary": {
                "compliant": compliant,
                "verified_boot": verified_boot,
                "policy_id": params.get("policy_id", "default"),
            },
            "note": "ChromeOSAdapter mock mode (no Google Workspace creds).",
        }
        report["count"] = len(report["devices"])
        return report

    # --- error helpers ---

    def _err(self, action: str, error_type: str, message: str) -> dict:
        return {
            "adapter": self.name,
            "ok": False,
            "device_id": "",
            "action": action,
            "error": message,
            "error_type": error_type,
        }


def build_chromeos_adapter_from_config(cfg: dict) -> ChromeOSAdapter:
    """Construct from a config dict (mirrors Intune/Windows helper shape)."""
    ccfg = (cfg.get("mdm") or {}).get("chromeos") or {}
    return ChromeOSAdapter(
        live=ccfg.get("live", False),
        refresh_token=ccfg.get("refresh_token", ""),
        client_id=ccfg.get("client_id", ""),
        client_secret=ccfg.get("client_secret", ""),
        customer_id=ccfg.get("customer_id", "my_customer"),
        endpoint_template=ccfg.get(
            "endpoint_template",
            "https://admin.googleapis.com/admin/directory/v1",
        ),
    )