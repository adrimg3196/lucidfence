"""Persistent state store: device states, transitions, actions log.

All state lives under the `data/` directory so the product is fully local and
survives restarts. No external database required.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field, fields, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


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
    # Última cerca conocida mientras el dispositivo está "unknown" (sin señal):
    # si reaparece fuera, esa es la cerca que abandonó y cuyo on_exit toca.
    last_inside_fence: Optional[str] = None
    location_source: str = "unknown"  # gps | coarse_ip | simulated
    risk_score: Optional[float] = None  # MOAT: geospatial risk 0-100
    risk_severity: Optional[str] = None  # low|medium|high|critical
    # --- Defect 2 (issue #302): persisted EXPLAIN of the verdict. ---
    # Written by Engine.run_once alongside risk_score/risk_severity so the GET
    # path can PROJECT the exact verdict (WHY) that fired actions — instead of
    # recomputing with a fresh context after a shift change / config edit and
    # silently disagreeing with itself. All Optional => old JSON loads clean.
    risk_reasons: Optional[list] = None  # reasons[] from RiskEngine.evaluate
    risk_matched_policies: Optional[list] = None  # policy ids from match_policies
    risk_evaluated_at: Optional[str] = None  # ISO timestamp of the cycle verdict
    risk_provenance: Optional[str] = None  # "tool"|"context"|"none"
    risk_verified: Optional[bool] = None  # provenance gate (evidence-backed?)
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
    encryption_enabled: Optional[bool] = None # FileVault/LUKS/BitLocker posture
    # Lo que el UEM AFIRMÓ sobre el cifrado, preservado tal cual. La postura
    # observada (osquery) gana en `encryption_enabled` — y así debe ser, es la
    # evidencia directa —, pero antes eso BORRABA la afirmación del UEM y con
    # ella la discrepancia. Guardar las dos caras es lo que hace posible la
    # segunda opinión (core/second_opinion.py). None = el UEM no lo reportó.
    uem_claimed_encryption: Optional[bool] = None
    carrier: Optional[str] = None             # cellular carrier / network
    assigned_user: Optional[str] = None       # user / owner of the device
    department: Optional[str] = None          # business unit
    last_checkin: Optional[str] = None        # last successful MDM check-in (ISO)
    enrolled_at: Optional[str] = None         # enrollment date (ISO)
    device_tag: Optional[str] = None          # free-text asset tag / label
    geofence_compliance: Optional[dict] = None    # simulated/live iOS geofence posture
    # --- declarative-eligibility signals (Issue #88) ---
    # Populated by the adapter from the real UEM/EMM response and carried
    # through NormalizedDevice -> LocationReport -> DeviceState. None = the
    # adapter did not report it (never inferred). Feed the declarative gate
    # (core.declarative) so it no longer falls through to imperative for
    # every device in production.
    management_mode: Optional[str] = None        # e.g. device_owner|profile_owner|fully_managed|mdm|configurator
    ownership: Optional[str] = None              # company|employee_owned|unknown
    # --- multi-UEM: which UEM provider(s) own this device, for action routing ---
    provider_refs: dict = field(default_factory=dict)  # {"applivery": "dev123", ...}
    # --- declarative readback (DDM status report / DSC compliance) ---
    passcode_compliant: Optional[bool] = None  # passcode.is-compliant
    filevault_enabled: Optional[bool] = None   # diskmanagement.filevault.enabled
    lockdown_mode: Optional[bool] = None       # security.lockdown-mode.enabled (Apple OS 27); None=unknown
    supervised: Optional[bool] = None          # enrollment supervision (Apple OS 27); None=unknown
    hardware_health: Optional[dict] = None     # hardware-health status items (Apple OS 27); None=unknown
    # --- integridad de ubicación (anti-spoofing, ver location_integrity.py) ---
    location_integrity: Optional[dict] = None  # {"suspicious", "checks", "speed_kmh", ...}
    # --- endpoint posture evidence (osquery) ---
    posture_source: Optional[str] = None       # e.g. osquery
    posture_collected_at: Optional[str] = None # evidence timestamp (ISO)
    osquery_version: Optional[str] = None
    osquery_config_valid: Optional[bool] = None

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
            except Exception:
                return
            # Isolate per-record failures: a single corrupt or
            # schema-drifted row must be skipped, never wipe the whole fleet's
            # persisted state. (ponytail: no logging infra here; skip silently
            # but keep every good record — add logging if forensics matter.)
            # Una clave que este build no conoce (fila escrita por un build más
            # nuevo, luego rollback) se ignora: descartar la fila entera dejaba
            # al dispositivo como "recién visto" y re-disparaba on_enter en masa.
            known = {f.name for f in fields(DeviceState)}
            for d in raw:
                try:
                    self._states[d["device_id"]] = DeviceState(
                        **{k: v for k, v in d.items() if k in known})
                except Exception:
                    continue

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
