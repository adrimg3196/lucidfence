"""Persistent state store: device states, transitions, actions log.

All state lives under the `data/` directory so the product is fully local and
survives restarts. No external database required.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class DeviceState:
    device_id: str
    name: str
    platform: str
    status: Optional[str] = None
    compliant: Optional[bool] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    accuracy_m: Optional[float] = None
    country: Optional[str] = None
    city: Optional[str] = None
    ip: Optional[str] = None
    last_seen: Optional[str] = None
    fence_id: Optional[str] = None
    inside_fence: Optional[str] = None  # fence id the device is currently inside
    fence_state: str = "unknown"  # inside | outside | unknown
    location_source: str = "unknown"  # gps | coarse_ip | simulated
    risk_score: Optional[float] = None  # MOAT: geospatial risk 0-100
    risk_severity: Optional[str] = None  # low|medium|high|critical
    route_id: Optional[str] = None  # assigned route (if any)
    route_state: Optional[str] = None  # on_route|off_route|unassigned
    route_deviation_m: Optional[float] = None  # meters from route polyline
    last_report_ts: Optional[str] = None
    apps: list[dict] = field(default_factory=list)  # installed apps enriched with CVEs
    # --- IT inventory fields (MDM/UEM asset management) ---
    os_version: Optional[str] = None          # e.g. "Android 14", "iOS 17.4", "Windows 11 23H2"
    model: Optional[str] = None               # e.g. "Samsung Galaxy S23", "iPhone 14"
    manufacturer: Optional[str] = None        # e.g. "Samsung", "Apple", "Dell"
    serial_number: Optional[str] = None       # hardware serial / asset tag
    imei: Optional[str] = None                # mobile device IMEI (android/ios)
    battery_level: Optional[int] = None       # 0-100 %
    battery_state: Optional[str] = None       # charging|discharging|full|unknown
    storage_total_gb: Optional[float] = None  # total capacity
    storage_free_gb: Optional[float] = None   # free space
    carrier: Optional[str] = None             # cellular carrier / network
    assigned_user: Optional[str] = None       # user / owner of the device
    department: Optional[str] = None          # business unit
    last_checkin: Optional[str] = None        # last successful MDM check-in (ISO)
    enrolled_at: Optional[str] = None         # enrollment date (ISO)
    device_tag: Optional[str] = None          # free-text asset tag / label
    geofence_compliance: Optional[dict] = None  # simulated/live iOS geofence posture

    def to_dict(self) -> dict:
        return asdict(self)


class StateStore:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.states_path = self.data_dir / "device_states.json"
        self.events_path = self.data_dir / "events.jsonl"
        self.actions_path = self.data_dir / "actions_log.jsonl"
        self.trails_path = self.data_dir / "trails.jsonl"
        self.stats_path = self.data_dir / "stats_history.jsonl"
        self.dwell_path = self.data_dir / "dwell.json"
        self.cooldown_path = self.data_dir / "action_cooldowns.json"
        self.lock = threading.Lock()
        self._states: dict[str, DeviceState] = {}
        self._dwell: dict[str, dict] = {}
        self._load()
        self._load_dwell()

    def _load(self):
        if self.states_path.exists():
            try:
                raw = json.loads(self.states_path.read_text(encoding="utf-8"))
                for d in raw:
                    self._states[d["device_id"]] = DeviceState(**d)
            except Exception:
                self._states = {}

    def snapshot(self) -> dict[str, DeviceState]:
        with self.lock:
            return dict(self._states)

    def get(self, device_id: str) -> Optional[DeviceState]:
        with self.lock:
            return self._states.get(device_id)

    def upsert(self, state: DeviceState):
        with self.lock:
            self._states[state.device_id] = state
            self._persist_states()

    def _persist_states(self):
        tmp = self.states_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([s.to_dict() for s in self._states.values()], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.states_path)

    def log_event(self, event: dict):
        with self.lock:
            with self.events_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    def log_action(self, action: dict):
        with self.lock:
            with self.actions_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(action, ensure_ascii=False) + "\n")

    def recent_events(self, limit: int = 200) -> list[dict]:
        if not self.events_path.exists():
            return []
        lines = self.events_path.read_text(encoding="utf-8").splitlines()
        out = []
        for ln in lines[-limit:]:
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
        return out

    def recent_actions(self, limit: int = 200) -> list[dict]:
        if not self.actions_path.exists():
            return []
        lines = self.actions_path.read_text(encoding="utf-8").splitlines()
        out = []
        for ln in lines[-limit:]:
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
        return out

    def _load_dwell(self):
        if self.dwell_path.exists():
            try:
                self._dwell = json.loads(self.dwell_path.read_text(encoding="utf-8"))
            except Exception:
                self._dwell = {}

    def _persist_dwell(self):
        tmp = self.dwell_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._dwell, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.dwell_path)

    def bump_dwell(self, device_id: str, interval_seconds: int):
        """Accumulate dwell time (seconds) for the device's current state."""
        with self.lock:
            rec = self._dwell.get(device_id, {"seconds": 0, "cycles": 0})
            rec["seconds"] = rec.get("seconds", 0) + int(interval_seconds)
            rec["cycles"] = rec.get("cycles", 0) + 1
            self._dwell[device_id] = rec
            self._persist_dwell()

    def reset_dwell(self, device_id: str):
        with self.lock:
            if device_id in self._dwell:
                self._dwell[device_id] = {"seconds": 0, "cycles": 0}
                self._persist_dwell()

    def dwell_seconds(self, device_id: str) -> int:
        return int(self._dwell.get(device_id, {}).get("seconds", 0))

    def dwell_cycles(self, device_id: str) -> int:
        return int(self._dwell.get(device_id, {}).get("cycles", 0))

    def log_trail(self, device_id: str, lat: float | None, lng: float | None,
                  fence_state: str, ts: str, max_points: int = 200):
        if lat is None or lng is None:
            return
        with self.lock:
            with self.trails_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"device_id": device_id, "lat": lat, "lng": lng,
                                     "fence_state": fence_state, "ts": ts}, ensure_ascii=False) + "\n")

    def trail(self, device_id: str, limit: int = 200) -> list[dict]:
        if not self.trails_path.exists():
            return []
        out = []
        for ln in self.trails_path.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if d.get("device_id") == device_id:
                out.append(d)
        return out[-limit:]

    def last_action_at(self, device_id: str, action: str) -> float:
        """Unix epoch (s) of the last execution of (device, action), or 0.0."""
        rec = self._cooldowns().get(f"{device_id}|{action}")
        return float(rec or 0.0)

    def record_action_at(self, device_id: str, action: str, ts: float):
        with self.lock:
            data = self._cooldowns()
            data[f"{device_id}|{action}"] = ts
            self._persist_cooldowns(data)

    def _cooldowns(self) -> dict:
        if not self.cooldown_path.exists():
            return {}
        try:
            return json.loads(self.cooldown_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _persist_cooldowns(self, data: dict):
        tmp = self.cooldown_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.cooldown_path)

    def log_stats(self, stats: dict):
        with self.lock:
            with self.stats_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(stats, ensure_ascii=False) + "\n")

    def stats_history(self, limit: int = 120) -> list[dict]:
        if not self.stats_path.exists():
            return []
        out = []
        for ln in self.stats_path.read_text(encoding="utf-8").splitlines()[-limit:]:
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
        return out


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
