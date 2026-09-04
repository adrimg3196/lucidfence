"""Persistent incident lifecycle for the local UEM command center.

Derived incidents describe what is currently wrong. This store adds the human
operations layer (acknowledge, assign, resolve, reopen, notes) without changing
the risk engine. State is isolated inside each tenant data directory.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

VALID_STATUSES = {"open", "acknowledged", "resolved"}


class IncidentStore:
    def __init__(self, data_dir: Path | str):
        self.path = Path(data_dir) / "incidents.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._items: dict[str, dict] = {}
        self.notifier: Optional[Any] = None  # IncidentNotifier-like; wired by the Engine
        self._load()

    def _load(self) -> None:
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
            self._items = {str(row["id"]): row for row in rows if row.get("id")}
        except Exception:
            self._items = {}

    def _persist(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(list(self._items.values()), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def merge(self, derived: list[dict]) -> list[dict]:
        """Merge current derived incidents with persistent operator state.

        A resolved incident stays resolved when the same deterministic incident
        ID is derived again. An operator must explicitly reopen it, avoiding an
        endless open/resolve loop on a standing device condition.
        """
        with self.lock:
            changed = False
            for raw in derived:
                incident_id = str(raw.get("id") or "")
                if not incident_id:
                    continue
                existing = self._items.get(incident_id)
                if existing is None:
                    row = dict(raw)
                    row.setdefault("status", "open")
                    row.setdefault("assignee", None)
                    row.setdefault("acknowledged_at", None)
                    row.setdefault("resolved_at", None)
                    row.setdefault("timeline", [])
                    self._items[incident_id] = row
                    changed = True
                    if self.notifier:
                        self.notifier.notify("open", row)
                else:
                    # Refresh sensor-derived facts while preserving workflow state.
                    preserved = {
                        key: existing.get(key)
                        for key in ("status", "assignee", "acknowledged_at", "resolved_at", "timeline")
                    }
                    existing.update(raw)
                    existing.update(preserved)
                    changed = True
            if changed:
                self._persist()
            current_ids = {str(d.get("id")) for d in derived}
            return self.list(current_ids=current_ids)

    def list(self, status: Optional[str] = None, current_ids: Optional[set[str]] = None) -> list[dict]:
        with self.lock:
            rows = [dict(v) for v in self._items.values()]
        if current_ids is not None:
            # Keep resolved historical incidents visible; hide stale open incidents
            # whose underlying condition disappeared.
            rows = [r for r in rows if r.get("id") in current_ids or r.get("status") == "resolved"]
        if status:
            rows = [r for r in rows if r.get("status") == status]
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        status_order = {"open": 0, "acknowledged": 1, "resolved": 2}
        return sorted(rows, key=lambda r: (
            status_order.get(r.get("status"), 9),
            severity_order.get(r.get("severity"), 9),
            str(r.get("title") or ""),
        ))

    def get(self, incident_id: str) -> Optional[dict]:
        with self.lock:
            row = self._items.get(incident_id)
            return dict(row) if row else None

    def transition(self, incident_id: str, status: str, actor: str,
                   assignee: Optional[str] = None, note: str = "") -> dict:
        if status not in VALID_STATUSES:
            raise ValueError("estado de incidente inválido")
        with self.lock:
            row = self._items.get(incident_id)
            if row is None:
                raise KeyError(incident_id)
            previous = row.get("status", "open")
            now = _now()
            if assignee is not None:
                row["assignee"] = assignee.strip() or None
            row["status"] = status
            if status == "acknowledged":
                row["acknowledged_at"] = now
                row["resolved_at"] = None
            elif status == "resolved":
                row["resolved_at"] = now
            elif status == "open":
                row["resolved_at"] = None
                row["acknowledged_at"] = None
            row.setdefault("timeline", []).append({
                "ts": now,
                "from": previous,
                "to": status,
                "actor": actor,
                "assignee": row.get("assignee"),
                "note": (note or "").strip(),
            })
            self._persist()
            if self.notifier:
                self.notifier.notify(status, row)
            return dict(row)


    def analytics(self, now: Callable[[], float] = time.time) -> dict:
        """MTTR and operational counts for the SOC panel.

        MTTR is computed only over resolved incidents as the elapsed time
        between the first 'open' timeline entry and the 'resolved' entry.
        Returns mean + median (seconds), open/resolved counts, per-severity
        breakdown, and the age (s) of the oldest still-open incident.
        """
        with self.lock:
            rows = list(self._items.values())
        open_rows = [r for r in rows if r.get("status") != "resolved"]
        resolved_rows = [r for r in rows if r.get("status") == "resolved"]
        by_sev: dict[str, int] = {}
        for r in rows:
            sev = (r.get("severity") or "info").lower()
            by_sev[sev] = by_sev.get(sev, 0) + 1
        durations = []
        for r in resolved_rows:
            opened = _opened_ts(r)
            resolved_ts = None
            for ev in r.get("timeline") or []:
                if ev.get("to") == "resolved":
                    resolved_ts = _parse_ts(ev.get("ts"))
            if opened is not None and resolved_ts is not None:
                durations.append(max(0.0, resolved_ts - opened))
        # Sin datos -> None, nunca 0: un "MTTR 0s" en el panel es un falso
        # verde (parece resolución instantánea cuando no hay nada que medir).
        mttr = int(sum(durations) / len(durations)) if durations else None
        median = int(sorted(durations)[len(durations) // 2]) if durations else None
        oldest = None
        tnow = now()
        for r in open_rows:
            opened = _opened_ts(r)
            if opened is not None:
                age = tnow - opened
                oldest = age if oldest is None else max(oldest, age)
        return {
            "open": len(open_rows),
            "resolved": len(resolved_rows),
            "total": len(rows),
            "by_severity": by_sev,
            "mttr_seconds": mttr,
            "mttr_median_seconds": median,
            "oldest_open_seconds": int(oldest) if oldest is not None else None,
        }


def _opened_ts(row: dict) -> Optional[float]:
    """Instante de apertura de un incidente.

    Los incidentes derivados nacen en ``merge()`` con timeline vacío (solo las
    transiciones del operador añaden entradas), así que la primera entrada
    ``to == "open"`` solo existe tras una reapertura. Sin ella, la apertura es
    ``first_seen`` del sensor; si tampoco existe, no se sabe (None).
    """
    for ev in row.get("timeline") or []:
        if ev.get("to") == "open":
            return _parse_ts(ev.get("ts"))
    return _parse_ts(row.get("first_seen"))


def _parse_ts(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        from datetime import datetime, timezone
        s = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_csv(rows: list[dict]) -> str:
    """Render incidents as CSV for compliance/ops export (Excel-friendly).

    Flattens the most useful operator + sensor columns. Quotes/escapes per RFC
    4180. The `timeline` audit trail is summarised as a count + last note.
    """
    cols = [
        ("id", "id"),
        ("title", "title"),
        ("severity", "severity"),
        ("status", "status"),
        ("device_id", "device_id"),
        ("device_name", "device_name"),
        ("fence_id", "fence_id"),
        ("route_state", "route_state"),
        ("risk_score", "risk_score"),
        ("assignee", "assignee"),
        ("acknowledged_at", "acknowledged_at"),
        ("resolved_at", "resolved_at"),
        ("created_at", "created_at"),
        ("updated_at", "updated_at"),
        ("notes", "notes"),
        ("events", "events"),
    ]

    def esc(v: object) -> str:
        s = "" if v is None else str(v)
        if any(ch in s for ch in (",", '"', "\n", "\r")):
            return '"' + s.replace('"', '""') + '"'
        return s

    out = [",".join(c[0] for c in cols)]
    for r in rows:
        tl = r.get("timeline") or []
        last_note = ""
        if tl:
            for ev in reversed(tl):
                if ev.get("note"):
                    last_note = f"{ev.get('actor','?')}: {ev['note']}"
                    break
        row = dict(r)
        row["notes"] = last_note
        row["events"] = len(tl)
        out.append(",".join(esc(row.get(c[1])) for c in cols))
    return "\n".join(out) + "\n"
