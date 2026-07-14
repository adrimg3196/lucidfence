"""Live location source backed by the Applivery UEM (MDM) REST API.

Verified contract (2026-07-09, against api.applivery.io with a real service
account token):

  Base URL : https://api.applivery.io/v1
  Auth     : Authorization: Bearer <APPLIVERY_API_KEY>
             (service-account token; NOT X-Api-Token which is a different API)
  Devices  : GET /v1/organizations/{organizationId}/mdm/devices
             -> 200 { "status": true,
                      "data": { "items": [ <device>, ... ],
                                "nextCursor": "..." | null } }
  Device shape (relevant fields):
    id                    : str
    type                  : "android" | "ios" | "windows" | ...
    state                 : "ACTIVE" | "INACTIVE" | ...
    displayName           : str
    summary.name          : friendly model/name  (e.g. "Motorola moto g04")
    summary.os            : "android" | "ios" | "windows"
    summary.model         : str
    summary.compliance.isCompliance : bool
    lastStatusReportTime  : ISO8601
    sortDate              : ISO8601
    lastLocation.agent.latitude  : float
    lastLocation.agent.longitude : float
    lastLocation.agent.date      : ISO8601
    lastLocation.agent.address    : { address, number, postalCode, city, country }
  Pagination: the response `data.nextCursor` (opaque) OR the `Link: rel="next"`
              header. We follow nextCursor when present, else Link.

The Applivery MCP `applivery_learn` is STALE: it documents `/orgs/{org}/devices`
and `X-Api-Token`, both of which return 404 / "No auth token" against the live
API. The real endpoints use `/organizations/{org}/mdm/devices` + Bearer.

Errors from the upstream API are captured (never raised) so the dashboard can
render a graceful integration_error instead of a 500.
"""

import json
import math
import os
import random
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LocationReport:
    device_id: str
    name: str
    platform: str
    lat: float
    lng: float
    status: str = "unknown"
    compliant: Optional[bool] = None
    accuracy_m: Optional[float] = None
    country: Optional[str] = None
    city: Optional[str] = None
    ip: Optional[str] = None
    last_seen: Optional[str] = None
    location_source: str = "applivery"
    apps: list[dict] = field(default_factory=list)  # installed apps (name, version, ...)
    raw: dict = field(default_factory=dict)
    # --- IT inventory fields (MDM/UEM asset management) ---
    os_version: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    serial_number: Optional[str] = None
    imei: Optional[str] = None
    battery_level: Optional[int] = None
    battery_state: Optional[str] = None
    storage_total_gb: Optional[float] = None
    storage_free_gb: Optional[float] = None
    carrier: Optional[str] = None
    assigned_user: Optional[str] = None
    department: Optional[str] = None
    last_checkin: Optional[str] = None
    enrolled_at: Optional[str] = None
    device_tag: Optional[str] = None
    geofence_compliance: Optional[dict] = None


class LiveLocationSource:
    """Fetches device locations from the Applivery UEM API."""

    def __init__(self, org_id: str, endpoint_template: str = None, timeout: int = 30,
                 api_key: str = ""):
        self.org_id = org_id
        self.api_key = api_key or ""
        # Real endpoint: /v1/organizations/{org}/mdm/devices
        self.endpoint_template = endpoint_template or "/organizations/{org_id}/mdm/devices/{device_id}"
        self.timeout = timeout
        self.last_error: Optional[dict] = None
        self._api_base = os.environ.get(
            "APPLIVERY_API_BASE", "https://api.applivery.io/v1"
        ).rstrip("/")

    # ------------------------------------------------------------------ auth
    def _headers(self):
        # Service-account Bearer token (verified live).
        key = self.api_key or os.environ.get("APPLIVERY_API_KEY") or ""
        return {
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        }

    # --------------------------------------------------------------- fetching
    def _paginate(self, path: str):
        """Follow Applivery pagination (data.nextCursor, then Link rel=next)."""
        results = []
        url = f"{self._api_base}{path}"
        seen = 0
        while url:
            req = urllib.request.Request(url, headers=self._headers())
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read().decode("utf-8")
                    link = resp.headers.get("Link")
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:500]
                self.last_error = {
                    "stage": "list_devices",
                    "http_status": e.code,
                    "url": url,
                    "body": detail,
                }
                return results
            except Exception as e:  # network / timeout
                self.last_error = {
                    "stage": "list_devices",
                    "error": f"{type(e).__name__}: {e}",
                    "url": url,
                }
                return results

            try:
                data = json.loads(body)
            except json.JSONDecodeError as e:
                self.last_error = {
                    "stage": "list_devices",
                    "error": f"JSON decode: {e}",
                    "url": url,
                }
                return results

            if not data.get("status", True):
                err = data.get("error", {})
                self.last_error = {
                    "stage": "list_devices",
                    "http_status": err.get("code"),
                    "message": err.get("message"),
                    "url": url,
                }
                return results

            payload = data.get("data", data)
            items = (
                payload.get("items")
                or payload.get("devices")
                or payload.get("results")
                or (data.get("items") if "items" in data else None)
                or []
            )
            if not isinstance(items, list):
                items = []
            results.extend(items)

            # Pagination: data.nextCursor first, then Link header.
            nxt = payload.get("nextCursor")
            if nxt:
                sep = "&" if "?" in url else "?"
                url = f"{self._api_base}{path}{sep}cursor={nxt}"
                seen += 1
                if seen > 100:
                    break
                continue
            url = self._next_from_link(link)
            if not url:
                break
        return results

    @staticmethod
    def _next_from_link(link_header: Optional[str]) -> Optional[str]:
        if not link_header:
            return None
        for part in link_header.split(","):
            seg = part.split(";")
            if len(seg) >= 2 and 'rel="next"' in seg[1]:
                return seg[0].strip().strip("<>")
        return None

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _to_int(v):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    # --------------------------------------------------------------- parsing
    @staticmethod
    def _extract_last_location(dev: dict):
        ll = dev.get("lastLocation") or dev.get("last_location") or {}
        # Real shape: lastLocation.agent.{latitude,longitude,date,address}
        agent = ll.get("agent") or ll.get("location") or {}
        lat = agent.get("latitude") or ll.get("latitude")
        lng = agent.get("longitude") or ll.get("longitude")
        ts = agent.get("date") or ll.get("date") or agent.get("lastReportDate")
        addr = agent.get("address") or ll.get("address")
        if addr and isinstance(addr, dict):
            addr = ", ".join(
                str(addr[k]) for k in ("address", "number", "city", "country") if addr.get(k)
            )
        # Fallback: some MDM payloads send the coordinates directly under
        # lastLocation (no nested `agent` object). Be tolerant so a flat shape
        # still yields a usable position instead of a None (and an "unknown"
        # device that never enters any geofence).
        if lat is None:
            lat = ll.get("latitude") or ll.get("lat")
        if lng is None:
            lng = ll.get("longitude") or ll.get("lng")
        if lat is None or lng is None:
            return None
        return {
            "lat": float(lat),
            "lng": float(lng),
            "ts": ts,
            "address": addr,
        }

    def _to_report(self, dev: dict) -> LocationReport:
        summary = dev.get("summary") or {}
        loc = self._extract_last_location(dev)
        name = (
            dev.get("displayName")
            or summary.get("name")
            or summary.get("model")
            or dev.get("id")
        )
        platform = (dev.get("type") or summary.get("os") or "unknown").lower()
        compliant = None
        comp = summary.get("compliance")
        if isinstance(comp, dict):
            compliant = comp.get("isCompliance")
        last_seen = (
            dev.get("lastStatusReportTime")
            or dev.get("sortDate")
            or (loc or {}).get("ts")
        )
        addr = (loc or {}).get("address") or ""
        country = None
        city = None
        if addr and "," in addr:
            parts = [p.strip() for p in addr.split(",")]
            city = parts[0] if parts else None
            country = parts[-1] if len(parts) > 1 else None
        return LocationReport(
            device_id=dev.get("id") or dev.get("deviceId") or "",
            name=name or "unknown",
            platform=platform,
            lat=(loc or {}).get("lat"),
            lng=(loc or {}).get("lng"),
            status=(dev.get("state") or "unknown").upper(),
            compliant=compliant,
            accuracy_m=(loc or {}).get("accuracy"),
            country=country,
            city=city,
            ip=summary.get("ipAddress"),
            last_seen=last_seen,
            location_source="applivery",
            raw=dev,
            # --- IT inventory fields from Applivery device summary ---
            os_version=summary.get("osVersion") or summary.get("os_version"),
            model=summary.get("model"),
            manufacturer=summary.get("manufacturer"),
            serial_number=summary.get("serialNumber") or summary.get("serial_number"),
            imei=summary.get("imei"),
            battery_level=self._to_int(summary.get("batteryLevel") or summary.get("battery_level")),
            battery_state=summary.get("batteryState") or summary.get("battery_state"),
            storage_total_gb=self._to_float(summary.get("storageTotalGb") or summary.get("storage_total_gb")),
            storage_free_gb=self._to_float(summary.get("storageFreeGb") or summary.get("storage_free_gb")),
            carrier=summary.get("carrier") or summary.get("networkOperator"),
            assigned_user=summary.get("userName") or summary.get("assignedUser"),
            department=summary.get("department"),
            last_checkin=dev.get("sortDate") or last_seen,
            enrolled_at=summary.get("enrolledAt") or dev.get("enrolledAt"),
            device_tag=summary.get("tag") or dev.get("tag"),
        )

    # -------------------------------------------------------------- public API
    def fetch(self) -> list:
        self.last_error = None
        devices = self._paginate(f"/organizations/{self.org_id}/mdm/devices")
        return [self._to_report(d) for d in devices]

    def fetch_one(self, device_id: str) -> Optional[LocationReport]:
        self.last_error = None
        path = self.endpoint_template.format(org_id=self.org_id, device_id=device_id)
        url = f"{self._api_base}{path}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except Exception as e:
            self.last_error = {
                "stage": "fetch_one",
                "error": f"{type(e).__name__}: {e}",
                "url": url,
            }
            return None
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            self.last_error = {"stage": "fetch_one", "error": f"JSON decode: {e}"}
            return None
        payload = data.get("data", data)
        return self._to_report(payload)


# ------------------------------------------------------------------- simulation


class SimulationLocationSource:
    """Local, fully-functional fleet simulator (no network, no real devices)."""

    def __init__(self, sim_seed_path: str = "data/fleet_seed.json", org_id: str = ""):
        self.sim_seed_path = sim_seed_path
        self.org_id = org_id
        self.last_error = None
        self._ticks = 0  # advances on every fetch() so simulated devices move
                         # across route corridors between engine cycles.

    def _load_seed(self) -> list:
        try:
            with open(self.sim_seed_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("devices", [])
        except FileNotFoundError:
            return []

    def _moving_point(self, waypoints: list, tick: int) -> tuple:
        if not waypoints:
            return 40.4168, -3.7038  # Madrid fallback
        n = len(waypoints)
        # Advance a segment every 3 ticks so a 45-cycle engine loop clearly
        # moves the device on/off the route corridor.
        seg = (tick // 3) % n
        a = waypoints[seg]
        b = waypoints[(seg + 1) % n]
        frac = (tick % 3) / 3.0
        lat = a["lat"] + (b["lat"] - a["lat"]) * frac
        lng = a["lng"] + (b["lng"] - a["lng"]) * frac
        return lat, lng

    def fetch(self) -> list:
        self.last_error = None
        tick = self._ticks
        self._ticks += 1
        out = []
        for dev in self._load_seed():
            wps = dev.get("waypoints", [])
            lat, lng = self._moving_point(wps, tick)
            plat = (dev.get("platform") or "android").lower()
            # Inventory defaults so the MDM/UEM asset view is always populated,
            # even when a (legacy) seed omits the new fields.
            os_default = {"android": "Android 13", "ios": "iOS 17.4",
                           "windows": "Windows 11 23H2", "macos": "macOS 14",
                           "chromeos": "ChromeOS 126"}.get(plat, "Desconocido")
            model_default = {"android": "Dispositivo Android", "ios": "iPhone",
                              "windows": "PC Windows", "macos": "Mac",
                              "chromeos": "Chromebook Enterprise"}.get(plat, "Dispositivo")
            out.append(LocationReport(
                device_id=dev.get("id", ""),
                name=dev.get("name", "unknown"),
                platform=plat,
                lat=lat,
                lng=lng,
                status=(dev.get("status") or "active").upper(),
                compliant=dev.get("compliant"),
                accuracy_m=12.0,
                country=dev.get("country"),
                city=dev.get("city"),
                ip=dev.get("ip"),
                last_seen=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                location_source="simulation",
                apps=[dict(a) for a in dev.get("apps", [])],
                raw=dev,
                # --- IT inventory fields from the seed (with platform defaults) ---
                os_version=dev.get("os_version") or os_default,
                model=dev.get("model") or model_default,
                manufacturer=dev.get("manufacturer") or (model_default if plat in ("android","ios") else "OEM"),
                serial_number=dev.get("serial_number") or f"SN-{dev.get('id','')}",
                imei=dev.get("imei") or (f"IMEI-{dev.get('id','')}" if plat in ("android","ios") else None),
                battery_level=dev.get("battery_level") if dev.get("battery_level") is not None else 100,
                battery_state=dev.get("battery_state") or "full",
                storage_total_gb=dev.get("storage_total_gb") or 128.0,
                storage_free_gb=dev.get("storage_free_gb") if dev.get("storage_free_gb") is not None else 64.0,
                carrier=dev.get("carrier") or "Movistar",
                assigned_user=dev.get("assigned_user") or dev.get("name"),
                department=dev.get("department") or "Operaciones",
                last_checkin=dev.get("last_checkin"),
                enrolled_at=dev.get("enrolled_at") or "2026-01-01T00:00:00Z",
                device_tag=dev.get("device_tag") or dev.get("id"),
                geofence_compliance=dev.get("geofence_compliance") if plat in ("ios", "ipados") else None,
            ))
        return out

    def fetch_one(self, device_id: str):
        for r in self.fetch():
            if r.device_id == device_id:
                return r
        return None


# ----------------------------------------------------------------------- factory
def build_location_source(mode: str, org_id: str, sim_seed_path: str = "data/fleet_seed.json",
                          api_key: str = ""):
    """Return a location source for the given mode.

    mode == "live"       -> LiveLocationSource(org_id)  (reads APPLIVERY_API_KEY)
    mode == "simulation" -> SimulationLocationSource(sim_seed_path)
    """
    if mode == "live":
        return LiveLocationSource(org_id=org_id, api_key=api_key)
    return SimulationLocationSource(sim_seed_path=sim_seed_path, org_id=org_id)

