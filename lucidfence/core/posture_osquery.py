"""Postura local vía osquery — señales reales del endpoint para el Risk Engine.

osquery (github.com/osquery/osquery, Apache-2.0/GPL-2.0) expone el estado del
dispositivo como tablas SQL. LucidFence NO vendoriza osquery: lee su salida.
Dos vías, ambas opcionales y sin dependencias nuevas:

1. Results log del osqueryd (filesystem logger, JSON-lines). Cero acoplamiento:
   el demonio ya corre en la flota (p. ej. desplegado con Fleet) y LucidFence
   solo parsea ``osqueryd.results.log``. Pack de queries en
   ``deploy/osquery/lucidfence.conf``.
2. ``osqueryi --json`` ad-hoc si el binario está instalado (subprocess con
   timeout). Pensado para el modo local/desktop de una sola máquina.

La salida es posture por host con EXACTAMENTE los campos que ya consumen
``sig_device_posture`` / ``sig_device_health`` en policies.py:
``os_version``, ``encryption_enabled``, ``storage_free_gb``,
``storage_total_gb``, ``battery_level`` (+ ``posture_source``, ``posture_ts``).

Evidence gate: una señal más vieja que ``max_age_min`` se descarta. Mejor sin
señal que con señal caducada presentada como fresca.

Regla dura heredada de los adapters: este módulo NUNCA hace raise hacia el
engine. Log corrupto, binario ausente o JSON roto → posture vacía.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

# Queries del pack que entendemos. El nombre puede venir pelado ("lf_os_version")
# o con prefijo de pack ("pack/lucidfence/lf_os_version"): se matchea el último
# segmento.
KNOWN_QUERIES = {
    "lf_os_version",
    "lf_disk_encryption",
    "lf_storage",
    "lf_battery",
    "lf_agent_health",
}

# SQL para el modo osqueryi (una máquina, sin demonio). Tablas estables de
# osquery; battery solo existe en macOS/Windows y devolver 0 filas es normal.
OSQUERYI_SQL = {
    "lf_os_version": "SELECT name, version, platform FROM os_version;",
    "lf_disk_encryption": "SELECT name, encrypted, type FROM disk_encryption;",
    "lf_storage": (
        "SELECT path, blocks, blocks_available, blocks_size FROM mounts "
        "WHERE path = '/';"
    ),
    "lf_battery": "SELECT percent_remaining FROM battery;",
    "lf_agent_health": "SELECT version, uuid FROM osquery_info;",
}

DEFAULT_MAX_AGE_MIN = 30
_MAX_LOG_BYTES = 8 * 1024 * 1024  # leemos como mucho la cola de 8 MB del log


def _base_name(query_name: str) -> str:
    return (query_name or "").rsplit("/", 1)[-1]


def _rows_from_entry(entry: dict) -> list[dict]:
    """Normaliza los tres formatos del results log a una lista de filas."""
    if isinstance(entry.get("snapshot"), list):
        return [r for r in entry["snapshot"] if isinstance(r, dict)]
    if isinstance(entry.get("columns"), dict):
        if entry.get("action") == "removed":
            return []
        return [entry["columns"]]
    diff = entry.get("diffResults")
    if isinstance(diff, dict) and isinstance(diff.get("added"), list):
        return [r for r in diff["added"] if isinstance(r, dict)]
    return []


def _to_float(val: Any) -> Optional[float]:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _fields_from_rows(query: str, rows: list[dict]) -> dict:
    """Mapea filas de una query conocida a campos de posture del device dict."""
    out: dict[str, Any] = {}
    if not rows:
        return out
    if query == "lf_os_version":
        r = rows[0]
        name, version = (r.get("name") or "").strip(), (r.get("version") or "").strip()
        if name or version:
            out["os_version"] = (name + " " + version).strip()
    elif query == "lf_disk_encryption":
        # Heurística documentada: cifrado si ALGÚN volumen reporta encrypted=1
        # (FileVault/BitLocker/LUKS del disco de sistema aparece aquí).
        vals = [str(r.get("encrypted", "")).strip() for r in rows]
        if any(v in ("1", "1.0", "true", "True") for v in vals):
            out["encryption_enabled"] = True
        elif vals:
            out["encryption_enabled"] = False
    elif query == "lf_storage":
        root = next((r for r in rows if r.get("path") == "/"), rows[0])
        bsize = _to_float(root.get("blocks_size"))
        blocks = _to_float(root.get("blocks"))
        avail = _to_float(root.get("blocks_available"))
        if bsize and blocks:
            out["storage_total_gb"] = round(blocks * bsize / 1024**3, 1)
        if bsize and avail is not None:
            out["storage_free_gb"] = round(avail * bsize / 1024**3, 1)
    elif query == "lf_battery":
        pct = _to_float(rows[0].get("percent_remaining"))
        if pct is not None:
            out["battery_level"] = pct
    elif query == "lf_agent_health":
        ver = (rows[0].get("version") or "").strip()
        if ver:
            out["osquery_version"] = ver
    return out


def parse_results_log(
    path: str | Path,
    max_age_min: int = DEFAULT_MAX_AGE_MIN,
    now: Optional[float] = None,
) -> dict[str, dict]:
    """Parsea un osqueryd.results.log → {host_identifier: posture_fields}.

    Se queda con la entrada MÁS RECIENTE por (host, query) y descarta las que
    superen ``max_age_min``. Líneas corruptas se ignoran en silencio.
    """
    now = time.time() if now is None else now
    try:
        p = Path(path)
        size = p.stat().st_size
        with p.open("rb") as fh:
            if size > _MAX_LOG_BYTES:
                fh.seek(size - _MAX_LOG_BYTES)
                fh.readline()  # descarta la línea partida
            raw_lines = fh.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return {}

    # newest[(host, query)] = (unix_time, rows)
    newest: dict[tuple[str, str], tuple[float, list[dict]]] = {}
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        query = _base_name(str(entry.get("name", "")))
        host = str(entry.get("hostIdentifier", "")).strip()
        if query not in KNOWN_QUERIES or not host:
            continue
        ts = _to_float(entry.get("unixTime")) or 0.0
        if ts and (now - ts) > max_age_min * 60:
            continue
        key = (host, query)
        if key not in newest or ts >= newest[key][0]:
            newest[key] = (ts, _rows_from_entry(entry))

    posture: dict[str, dict] = {}
    for (host, query), (ts, rows) in newest.items():
        fields = _fields_from_rows(query, rows)
        if not fields:
            continue
        entry_p = posture.setdefault(host, {"posture_source": "osquery"})
        entry_p.update(fields)
        entry_p["posture_ts"] = max(entry_p.get("posture_ts", 0.0), ts)
    return posture


def query_local(osqueryi: str = "osqueryi", timeout: int = 10) -> dict:
    """Postura de ESTA máquina vía ``osqueryi --json``. {} si no hay binario."""
    fields: dict[str, Any] = {}
    for query, sql in OSQUERYI_SQL.items():
        try:
            out = subprocess.run(
                [osqueryi, "--json", sql],
                capture_output=True, text=True, timeout=timeout,
            )
            rows = json.loads(out.stdout) if out.returncode == 0 else []
        except (OSError, ValueError, subprocess.SubprocessError):
            return {}
        if isinstance(rows, list):
            fields.update(_fields_from_rows(query, [r for r in rows if isinstance(r, dict)]))
    if fields:
        fields["posture_source"] = "osquery"
        fields["posture_ts"] = time.time()
    return fields


class OsqueryPosture:
    """Fuente de posture para el engine. Construir con ``from_config``.

    Config (``config.json``)::

        "posture": {
          "source": "osquery",
          "results_log": "/var/log/osquery/osqueryd.results.log",
          "max_age_min": 30,
          "local_device_id": "mi-mac"   // opcional: modo osqueryi una máquina
        }
    """

    def __init__(self, results_log: Optional[str], max_age_min: int,
                 local_device_id: Optional[str] = None, osqueryi_bin: str = "osqueryi"):
        self.results_log = results_log
        self.max_age_min = max_age_min
        self.local_device_id = local_device_id
        self.osqueryi_bin = osqueryi_bin
        self._cache: dict[str, dict] = {}
        self._cache_ts = 0.0

    @classmethod
    def from_config(cls, config: dict) -> Optional["OsqueryPosture"]:
        pc = config.get("posture") or {}
        if pc.get("source") != "osquery":
            return None
        return cls(
            results_log=pc.get("results_log"),
            max_age_min=int(pc.get("max_age_min", DEFAULT_MAX_AGE_MIN)),
            local_device_id=pc.get("local_device_id"),
            osqueryi_bin=pc.get("osqueryi_bin", "osqueryi"),
        )

    def refresh(self) -> None:
        """Relee las fuentes (cache 60 s para no re-parsear el log por device)."""
        if time.time() - self._cache_ts < 60:
            return
        cache: dict[str, dict] = {}
        if self.results_log:
            cache.update(parse_results_log(self.results_log, self.max_age_min))
        if self.local_device_id:
            local = query_local(self.osqueryi_bin)
            if local:
                cache[self.local_device_id] = local
        self._cache = cache
        self._cache_ts = time.time()

    def enrich(self, device: dict) -> dict:
        """Devuelve el device dict con la posture osquery del host aplicada.

        Matchea hostIdentifier contra device_id, name o serial (case-insensitive).
        osquery es verdad del endpoint: sus campos PISAN los del adapter, pero
        solo si la señal está fresca (el gate ya filtró en parse).
        """
        try:
            self.refresh()
            if not self._cache:
                return device
            keys = {str(device.get(k, "")).strip().lower()
                    for k in ("device_id", "name", "serial") if device.get(k)}
            for host, fields in self._cache.items():
                if host.strip().lower() in keys:
                    merged = dict(device)
                    merged.update(fields)
                    return merged
        except Exception:  # noqa: BLE001 — nunca romper el ciclo del engine
            pass
        return device
