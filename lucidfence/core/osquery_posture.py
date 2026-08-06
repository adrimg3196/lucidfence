"""Optional osquery posture source for LucidFence.

osquery is deliberately treated as an evidence collector, not as a UEM
adapter.  It observes endpoint state; LucidFence correlates that state with
geofences and decides whether a UEM action is required.

Two local-first modes are supported:

``results_log``
    Read osquery's JSON result log in snapshot format. This is
    suitable for a local daemon or for a log-forwarder that consolidates
    endpoint results onto the LucidFence host.

``local``
    Execute a small, immutable allow-list of read-only queries through
    ``osqueryi``. Arbitrary SQL is never accepted from configuration or API
    input.

The integration is opt-in. Missing binaries, stale logs and malformed rows
degrade to "no posture evidence" and never stop a geofencing cycle.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


QUERY_PREFIX = "lucidfence_"
MAX_LOG_BYTES = 4 * 1024 * 1024
MAX_LOG_LINES = 10_000
MAX_FUTURE_SKEW_SECONDS = 300

# Fixed queries only. Values are source-controlled and cannot be replaced from
# tenant configuration, which prevents this integration becoming a remote SQL
# execution primitive.
COMMON_QUERIES = {
    "lucidfence_system_info": (
        "SELECT hostname, uuid, hardware_vendor, hardware_model, "
        "hardware_serial, computer_name, local_hostname FROM system_info;"
    ),
    "lucidfence_os_version": (
        "SELECT name, version, major, minor, patch, build, platform, arch "
        "FROM os_version;"
    ),
    "lucidfence_osquery_info": (
        "SELECT uuid, instance_id, version, config_hash, config_valid "
        "FROM osquery_info;"
    ),
}
POSIX_QUERIES = {
    "lucidfence_mounts": (
        "SELECT device, path, blocks_size, blocks, blocks_free, "
        "blocks_available FROM mounts WHERE path = '/';"
    ),
    "lucidfence_disk_encryption": (
        "SELECT name, uuid, encrypted, type, encryption_status "
        "FROM disk_encryption;"
    ),
}
WINDOWS_QUERIES = {
    "lucidfence_logical_drives": (
        "SELECT device_id, free_space, size, file_system, boot_partition "
        "FROM logical_drives WHERE boot_partition = 1;"
    ),
    "lucidfence_bitlocker": (
        "SELECT device_id, drive_letter, conversion_status, protection_status, "
        "encryption_method, percentage_encrypted, lock_status FROM bitlocker_info;"
    ),
}
DARWIN_BATTERY_QUERY = {
    "lucidfence_battery": (
        "SELECT state, charging, charged, cycle_count, percent_remaining, "
        "health, condition FROM battery;"
    ),
}
WINDOWS_BATTERY_QUERY = {
    "lucidfence_battery": (
        "SELECT state, charging, charged, cycle_count, percent_remaining "
        "FROM battery;"
    ),
}


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "encrypted", "active"}:
            return True
        if normalized in {"0", "false", "no", "off", "unencrypted", "inactive"}:
            return False
    return None


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    parsed = _as_int(value)
    if parsed is None:
        parsed = default
    return max(minimum, min(parsed, maximum))


def _event_ts(event: dict, fallback: float = 0.0) -> float:
    unix = _as_float(event.get("unixTime"))
    if unix is not None:
        return unix
    calendar = event.get("calendarTime")
    if isinstance(calendar, str):
        for fmt in ("%a %b %d %H:%M:%S %Y %Z", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                return datetime.strptime(calendar, fmt).timestamp()
            except ValueError:
                continue
    return fallback


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _canonical_query(name: str) -> Optional[str]:
    """Map pack query variants onto one normalized evidence table."""
    if not isinstance(name, str) or QUERY_PREFIX not in name:
        return None
    # osquery prefixes external pack query names (for example
    # ``pack_lucidfence_lucidfence_os_version``). Use the final occurrence so
    # both raw scheduled names and pack-qualified names normalize identically.
    name = name[name.rfind(QUERY_PREFIX):]
    for canonical in (
        "system_info",
        "os_version",
        "osquery_info",
        "mounts",
        "disk_encryption",
        "logical_drives",
        "bitlocker",
        "battery",
    ):
        if name == QUERY_PREFIX + canonical or name.startswith(QUERY_PREFIX + canonical + "_"):
            return canonical
    return None


def parse_result_event(event: dict, *, fallback_ts: float = 0.0) -> Optional[dict]:
    """Normalize one official osquery result event.

    Snapshot events (``snapshot: [...]``) are accepted. Differential events are
    ignored because one row is not a complete posture table and treating it as
    one could select the wrong disk or encryption state. Unknown query names are
    ignored so an existing shared osquery results log can be used safely.
    """
    if not isinstance(event, dict):
        return None
    query = _canonical_query(event.get("name"))
    if query is None:
        return None
    host = str(event.get("hostIdentifier") or "").strip()
    if not host:
        return None
    rows: list[dict]
    snapshot = event.get("snapshot")
    if isinstance(snapshot, list):
        rows = [row for row in snapshot if isinstance(row, dict)]
    else:
        return None
    return {
        "host": host,
        "query": query,
        "rows": rows,
        "ts": _event_ts(event, fallback=fallback_ts),
    }


def read_result_log(path: Path, *, max_bytes: int = MAX_LOG_BYTES,
                    max_lines: int = MAX_LOG_LINES) -> list[dict]:
    """Read a bounded tail of an osquery JSONL result log."""
    path = Path(path)
    if not path.is_file():
        return []
    size = path.stat().st_size
    start = max(size - max(1, int(max_bytes)), 0)
    with path.open("rb") as fh:
        fh.seek(start)
        if start:
            fh.readline()  # discard a partial JSON line
        raw_lines = fh.readlines()
    fallback_ts = path.stat().st_mtime
    events: list[dict] = []
    for raw in raw_lines[-max(1, int(max_lines)):]:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        parsed = parse_result_event(payload, fallback_ts=fallback_ts)
        if parsed is not None:
            events.append(parsed)
    return events


def _latest_tables(events: Iterable[dict], *, now: float,
                   max_age_seconds: int) -> dict[str, dict[str, dict]]:
    hosts: dict[str, dict[str, dict]] = {}
    for event in events:
        ts = _as_float(event.get("ts")) or 0.0
        if ts > now + MAX_FUTURE_SKEW_SECONDS:
            continue
        if (now - ts) > max_age_seconds:
            continue
        host = str(event.get("host") or "")
        query = str(event.get("query") or "")
        current = hosts.setdefault(host, {}).get(query)
        if current is None or ts >= float(current.get("ts") or 0):
            hosts[host][query] = {
                "rows": list(event.get("rows") or []),
                "ts": ts,
            }
    return hosts


def _select_root_mount(rows: list[dict]) -> Optional[dict]:
    return next((row for row in rows if row.get("path") == "/"), rows[0] if rows else None)


def _select_boot_drive(rows: list[dict]) -> Optional[dict]:
    return next(
        (row for row in rows if _as_bool(row.get("boot_partition")) is True),
        rows[0] if rows else None,
    )


def normalize_posture(tables: dict[str, dict]) -> dict:
    """Convert latest osquery tables into LucidFence inventory/risk fields."""
    posture: dict[str, Any] = {"posture_source": "osquery"}
    timestamps = [float(v.get("ts") or 0) for v in tables.values() if isinstance(v, dict)]
    if timestamps:
        posture["posture_collected_at"] = _iso(max(timestamps))

    system_rows = (tables.get("system_info") or {}).get("rows") or []
    if system_rows:
        row = system_rows[0]
        posture.update({
            key: value for key, value in {
                "hostname": row.get("hostname") or row.get("computer_name") or row.get("local_hostname"),
                "hardware_uuid": row.get("uuid"),
                "manufacturer": row.get("hardware_vendor"),
                "model": row.get("hardware_model"),
                "serial_number": row.get("hardware_serial"),
            }.items() if value not in (None, "")
        })

    os_rows = (tables.get("os_version") or {}).get("rows") or []
    if os_rows:
        row = os_rows[0]
        name = str(row.get("name") or row.get("platform") or "").strip()
        version = str(row.get("version") or "").strip()
        label = " ".join(part for part in (name, version) if part)
        if label:
            posture["os_version"] = label
        if row.get("platform"):
            posture["osquery_platform"] = row["platform"]

    info_rows = (tables.get("osquery_info") or {}).get("rows") or []
    if info_rows:
        row = info_rows[0]
        if row.get("version"):
            posture["osquery_version"] = row["version"]
        valid = _as_bool(row.get("config_valid"))
        if valid is not None:
            posture["osquery_config_valid"] = valid

    mount_rows = (tables.get("mounts") or {}).get("rows") or []
    mount = _select_root_mount(mount_rows)
    if mount:
        block_size = _as_float(mount.get("blocks_size"))
        blocks = _as_float(mount.get("blocks"))
        available = _as_float(mount.get("blocks_available"))
        if block_size is not None and blocks is not None:
            posture["storage_total_gb"] = round(block_size * blocks / (1024 ** 3), 2)
        if block_size is not None and available is not None:
            posture["storage_free_gb"] = round(block_size * available / (1024 ** 3), 2)

    drive_rows = (tables.get("logical_drives") or {}).get("rows") or []
    drive = _select_boot_drive(drive_rows)
    if drive:
        total = _as_float(drive.get("size"))
        free = _as_float(drive.get("free_space"))
        if total is not None and total >= 0:
            posture["storage_total_gb"] = round(total / (1024 ** 3), 2)
        if free is not None and free >= 0:
            posture["storage_free_gb"] = round(free / (1024 ** 3), 2)

    encryption_rows = (tables.get("disk_encryption") or {}).get("rows") or []
    if encryption_rows:
        root_device = str((mount or {}).get("device") or "")
        encryption = next(
            (row for row in encryption_rows if root_device and row.get("name") == root_device),
            encryption_rows[0],
        )
        encrypted = _as_bool(encryption.get("encrypted"))
        if encrypted is not None:
            posture["encryption_enabled"] = encrypted

    bitlocker_rows = (tables.get("bitlocker") or {}).get("rows") or []
    if bitlocker_rows:
        boot_id = str((drive or {}).get("device_id") or "")
        bitlocker = next(
            (
                row for row in bitlocker_rows
                if boot_id and str(row.get("drive_letter") or row.get("device_id") or "").startswith(boot_id)
            ),
            bitlocker_rows[0],
        )
        protected = _as_int(bitlocker.get("protection_status"))
        percentage = _as_int(bitlocker.get("percentage_encrypted"))
        if protected is not None:
            posture["encryption_enabled"] = protected == 1 and (percentage is None or percentage >= 100)

    battery_rows = (tables.get("battery") or {}).get("rows") or []
    if battery_rows:
        row = battery_rows[0]
        level = _as_int(row.get("percent_remaining"))
        if level is not None:
            posture["battery_level"] = max(0, min(level, 100))
        state = str(row.get("state") or "").lower()
        if _as_bool(row.get("charged")):
            posture["battery_state"] = "full"
        elif _as_bool(row.get("charging")):
            posture["battery_state"] = "charging"
        elif state:
            posture["battery_state"] = "discharging" if "battery" in state else state

    return posture


def _aliases(tables: dict[str, dict], host: str) -> set[str]:
    values = {host}
    rows = (tables.get("system_info") or {}).get("rows") or []
    if rows:
        row = rows[0]
        for key in ("hostname", "uuid", "hardware_serial", "computer_name", "local_hostname"):
            value = str(row.get(key) or "").strip()
            if value:
                values.add(value)
    return values


class OsqueryPostureProvider:
    """Caches osquery evidence once per engine cycle and resolves it by device."""

    def __init__(self, config: Optional[dict] = None):
        config = config if isinstance(config, dict) else {}
        self.enabled = bool(config.get("enabled", False))
        self.mode = str(config.get("mode") or "results_log")
        self.results_path = Path(
            config.get("results_path") or "/var/log/osquery/osqueryd.results.log"
        ).expanduser()
        self.binary = str(config.get("binary") or "osqueryi")
        self.local_device_id = str(config.get("device_id") or "")
        raw_host_map = config.get("host_map")
        if not isinstance(raw_host_map, dict):
            raw_host_map = {}
        self.host_map = {
            str(key): str(value)
            for key, value in raw_host_map.items()
            if str(key) and str(value)
        }
        self.max_age_seconds = _bounded_int(
            config.get("max_age_seconds"), 1800, 60, 86_400
        )
        self.timeout_seconds = _bounded_int(
            config.get("timeout_seconds"), 5, 1, 30
        )
        self.total_timeout_seconds = _bounded_int(
            config.get("total_timeout_seconds"), 15, 1, 60
        )
        self._by_device: dict[str, dict] = {}
        self._status = {
            "enabled": self.enabled,
            "mode": self.mode,
            "hosts": 0,
            "fresh": 0,
            "error": None,
        }

    def refresh(self, *, now: Optional[float] = None) -> None:
        self._by_device = {}
        self._status.update({"hosts": 0, "fresh": 0, "error": None})
        if not self.enabled:
            return

        # Pre-populate known devices with fail-closed / non-compliant state.
        # This ensures that if the osquery source is corrupt, absent, or stale,
        # the devices fail closed rather than failing open.
        for device_id in self.host_map.values():
            if device_id:
                self._by_device[device_id] = {
                    "posture_source": "osquery",
                    "encryption_enabled": False,
                    "osquery_config_valid": False,
                    "storage_free_gb": 0.0,
                    "storage_total_gb": 1.0,
                }
        if self.local_device_id:
            self._by_device[self.local_device_id] = {
                "posture_source": "osquery",
                "encryption_enabled": False,
                "osquery_config_valid": False,
                "storage_free_gb": 0.0,
                "storage_total_gb": 1.0,
            }

        try:
            current = time.time() if now is None else float(now)
            if self.mode == "results_log":
                if not self.results_path.is_file():
                    raise FileNotFoundError(f"Archivo de resultados osquery ausente o ilegible: {self.results_path}")
                events = read_result_log(self.results_path)
                if not events:
                    raise ValueError(f"Archivo de resultados osquery vacío o corrupto: {self.results_path}")
                hosts = _latest_tables(
                    events, now=current, max_age_seconds=self.max_age_seconds
                )
                if not hosts:
                    raise ValueError(f"No se encontraron eventos frescos de osquery (todos superan max_age de {self.max_age_seconds}s o están corruptos)")
                self._index_hosts(hosts)
                self._status["hosts"] = len(hosts)
                self._status["fresh"] = len(hosts)
            elif self.mode == "local":
                if not self.local_device_id:
                    raise ValueError("osquery.device_id es obligatorio en modo local")
                tables = self._run_local_queries(current)
                self._by_device[self.local_device_id] = normalize_posture(tables)
                self._status["hosts"] = 1
                self._status["fresh"] = 1
            else:
                raise ValueError("osquery.mode debe ser results_log o local")
        except Exception as exc:  # fail closed without breaking the engine cycle
            self._status["error"] = f"{type(exc).__name__}: {exc}"

    def _index_hosts(self, hosts: dict[str, dict[str, dict]]) -> None:
        alias_candidates: dict[str, list[tuple[str, dict]]] = {}
        for host, tables in hosts.items():
            posture = normalize_posture(tables)
            target = self.host_map.get(host)
            aliases = _aliases(tables, host)
            if target:
                self._by_device[target] = posture
            for alias in aliases:
                alias_candidates.setdefault(alias, []).append((host, posture))

        # Implicit identity is safe only when the alias resolves to one host.
        # Shared hostnames/serials remain unbound until the operator supplies
        # host_map entries keyed by each unique hostIdentifier.
        for alias, candidates in alias_candidates.items():
            if len(candidates) != 1:
                continue
            host, posture = candidates[0]
            if not self.host_map.get(host):
                self._by_device[alias] = posture
            mapped = self.host_map.get(alias)
            if mapped:
                self._by_device[mapped] = posture

    def _run_local_queries(self, now: float) -> dict[str, dict]:
        executable_name = self.binary.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if executable_name not in {"osqueryi", "osqueryi.exe"}:
            raise ValueError("osquery.binary debe apuntar a osqueryi")
        queries = dict(COMMON_QUERIES)
        if sys.platform == "win32":
            queries.update(WINDOWS_QUERIES)
            queries.update(WINDOWS_BATTERY_QUERY)
        elif sys.platform == "darwin":
            queries.update(POSIX_QUERIES)
            queries.update(DARWIN_BATTERY_QUERY)
        elif os.name == "posix":
            queries.update(POSIX_QUERIES)

        tables: dict[str, dict] = {}
        deadline = time.monotonic() + self.total_timeout_seconds
        for name, sql in queries.items():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                result = subprocess.run(
                    [self.binary, "--json", sql],
                    capture_output=True,
                    text=True,
                    timeout=min(float(self.timeout_seconds), remaining),
                    check=False,
                    shell=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if result.returncode != 0:
                continue
            try:
                rows = json.loads(result.stdout or "[]")
            except json.JSONDecodeError:
                continue
            if isinstance(rows, list):
                canonical = _canonical_query(name)
                if canonical:
                    tables[canonical] = {
                        "rows": [row for row in rows if isinstance(row, dict)],
                        "ts": now,
                    }
        if not tables:
            raise RuntimeError("osqueryi no devolvió evidencia válida")
        return tables

    def posture_for(self, device_id: str, *, aliases: Iterable[str] = ()) -> dict:
        for candidate in (str(device_id), *(str(alias) for alias in aliases if alias)):
            posture = self._by_device.get(candidate)
            if posture is not None:
                return dict(posture)
        return {}

    def status(self) -> dict:
        return dict(self._status)
