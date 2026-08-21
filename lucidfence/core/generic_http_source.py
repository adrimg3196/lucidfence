"""Generic HTTP location source — bring your own UEM/MDM API.

One configurable connector for ANY vendor. You declare the endpoint, auth and
field mapping in config.json; no per-vendor code. LucidFence turns the JSON
response into LocationReport objects the engine already understands.

Config shape (under `location_source` in config.json):

    "location_source": {
      "url": "https://mdm.tu-vendor.com/api/devices",
      "method": "GET",                       # optional, default GET
      "headers": {"Authorization": "Bearer ${MY_TOKEN}"},
      "items_path": "data.items",            # optional; "."=root, ""=root
      "fields": {
        "device_id": "id",
        "name": "displayName",
        "platform": "os",
        "lat": "location.lat",
        "lng": "location.lng",
        "compliant": "compliance.ok",
        "status": "state"
      }
    }

Header values support ${ENV_VAR} substitution so secrets never live in the
repo. Missing fields map to None (engine treats them as unknown, not crash).
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any, Optional

from lucidfence.core.location_source import LocationReport


def _resolve_env(value: str) -> str:
    """Expand ${VAR} from env in a header value."""
    if not isinstance(value, str):
        return value
    out = value
    for token in set(__import__("re").findall(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", out)):
        env_val = os.environ.get(token[2:-1], "")
        out = out.replace(token, env_val)
    return out


def _dig(obj: Any, path: str) -> Any:
    """Return obj dotted-path value, or None. Empty/'.' path = obj itself."""
    if not path or path == ".":
        return obj
    cur: Any = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


class GenericHTTPLocationSource:
    """Polls any JSON device API and maps it to LocationReport."""

    name = "generic"

    def __init__(self, cfg: dict):
        self.cfg = cfg or {}
        self.url = self.cfg.get("url", "")
        self.method = self.cfg.get("method", "GET").upper()
        self.headers = {k: _resolve_env(v) for k, v in self.cfg.get("headers", {}).items()}
        self.items_path = self.cfg.get("items_path", "")
        self.fields = self.cfg.get("fields", {})
        self.timeout = int(self.cfg.get("timeout", 30))
        self.last_error: Optional[dict] = None

    def _parse_items(self, body: bytes) -> list:
        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as e:
            self.last_error = {"stage": "decode", "error": f"JSON decode: {e}"}
            return []
        items = _dig(data, self.items_path)
        if items is None:
            # Be tolerant: many APIs return a bare list or a dict of devices.
            items = data if isinstance(data, list) else list(data.values())
        return items if isinstance(items, list) else [items]

    def _to_report(self, dev: dict) -> Optional[LocationReport]:
        f = self.fields
        dev_id = _dig(dev, f.get("device_id", "id") or "id")
        if not dev_id:
            return None
        lat = _dig(dev, f.get("lat", "lat") or "lat")
        lng = _dig(dev, f.get("lng", "lng") or "lng")
        if lat is None or lng is None:
            return None
        platform = str(_dig(dev, f.get("platform", "platform") or "platform") or "unknown").lower()
        return LocationReport(
            device_id=str(dev_id),
            name=str(_dig(dev, f.get("name", "name") or "name") or dev_id),
            platform=platform,
            lat=float(lat),
            lng=float(lng),
            status=str(_dig(dev, f.get("status", "status") or "status") or "unknown").upper(),
            compliant=_dig(dev, f.get("compliant", "compliant") or "compliant"),
            location_source="generic",
            raw=dev,
        )

    def fetch(self) -> list:
        self.last_error = None
        if not self.url:
            self.last_error = {"stage": "config", "error": "location_source.url is empty"}
            return []
        req = urllib.request.Request(self.url, headers=self.headers, method=self.method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
        except urllib.error.HTTPError as e:
            self.last_error = {"stage": "http", "http_status": e.code, "url": self.url,
                               "body": e.read().decode("utf-8", "replace")[:500]}
            return []
        except Exception as e:  # noqa: BLE001 — never crash the cycle
            self.last_error = {"stage": "http", "error": f"{type(e).__name__}: {e}", "url": self.url}
            return []
        out = []
        for dev in self._parse_items(body):
            if isinstance(dev, dict):
                rep = self._to_report(dev)
                if rep is not None:
                    out.append(rep)
        return out

    def fetch_one(self, device_id: str):
        for r in self.fetch():
            if r.device_id == device_id:
                return r
        return None
