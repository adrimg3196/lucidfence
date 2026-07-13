"""Bulk export / audit module for the local UEM command center.

Generates:
  - CSV exports (real RFC-4180) for inventory, actions log, and compliance.
  - A print-ready HTML report (the browser's "Print -> Save as PDF" produces a
    real PDF with zero external dependencies).

Everything is local; no network, no third-party libraries.
"""
from __future__ import annotations

import csv
import io
import time
from typing import Any


def _csv_escape(value: Any) -> str:
    if value is None:
        return ""
    s = str(value)
    if any(ch in s for ch in (",", '"', "\n", "\r")):
        return '"' + s.replace('"', '""') + '"'
    return s


def to_csv(headers: list[str], rows: list[list[Any]]) -> str:
    out = io.StringIO()
    out.write(",".join(_csv_escape(h) for h in headers) + "\n")
    for r in rows:
        out.write(",".join(_csv_escape(c) for c in r) + "\n")
    return out.getvalue()


# ----------------------------------------------------------------- inventory
INVENTORY_HEADERS = [
    "device_id", "name", "platform", "model", "manufacturer", "os_version",
    "serial_number", "imei", "assigned_user", "department", "device_tag",
    "status", "compliant", "fence_state", "inside_fence", "battery_level",
    "battery_state", "storage_total_gb", "storage_free_gb", "carrier",
    "city", "country", "last_checkin", "enrolled_at", "risk_score",
    "risk_severity", "lat", "lng",
]


def export_inventory_csv(devices: list[dict]) -> str:
    rows = []
    for d in devices:
        rows.append([
            d.get("device_id"), d.get("name"), d.get("platform"), d.get("model"),
            d.get("manufacturer"), d.get("os_version"), d.get("serial_number"),
            d.get("imei"), d.get("assigned_user"), d.get("department"),
            d.get("device_tag"), d.get("status"), d.get("compliant"),
            d.get("fence_state"), d.get("inside_fence"), d.get("battery_level"),
            d.get("battery_state"), d.get("storage_total_gb"),
            d.get("storage_free_gb"), d.get("carrier"), d.get("city"),
            d.get("country"), d.get("last_checkin"), d.get("enrolled_at"),
            d.get("risk_score"), d.get("risk_severity"), d.get("lat"), d.get("lng"),
        ])
    return to_csv(INVENTORY_HEADERS, rows)


# -------------------------------------------------------------------- actions
def export_actions_csv(actions: list[dict]) -> str:
    headers = ["ts", "device_id", "device_name", "action", "ok", "adapter",
               "trigger", "policy_name", "operator", "dry_run", "manual",
               "fence_id", "error", "delegated"]
    rows = []
    for a in actions:
        rows.append([
            a.get("ts"), a.get("device_id"), a.get("device_name"),
            a.get("action"), a.get("ok"), a.get("adapter"), a.get("trigger"),
            a.get("policy_name"), a.get("operator"), a.get("dry_run"),
            a.get("manual"), a.get("fence_id"), a.get("error"), a.get("delegated"),
        ])
    return to_csv(headers, rows)


# ----------------------------------------------------------------- compliance
def export_compliance_csv(devices: list[dict]) -> str:
    headers = ["device_id", "name", "platform", "compliant", "fence_state",
               "inside_fence", "risk_score", "risk_severity", "os_version",
               "last_checkin"]
    rows = []
    for d in devices:
        rows.append([
            d.get("device_id"), d.get("name"), d.get("platform"),
            d.get("compliant"), d.get("fence_state"), d.get("inside_fence"),
            d.get("risk_score"), d.get("risk_severity"), d.get("os_version"),
            d.get("last_checkin"),
        ])
    return to_csv(headers, rows)


# --------------------------------------------------------- print-ready HTML
def export_inventory_html(devices: list[dict], org_name: str = "",
                          summary: dict | None = None) -> str:
    now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    rows = []
    for d in devices:
        comp = "SI" if d.get("compliant") is True else ("NO" if d.get("compliant") is False else "?")
        rows.append(
            "<tr>"
            f"<td>{_h(d.get('name'))}</td>"
            f"<td>{_h(d.get('device_id'))}</td>"
            f"<td>{_h(d.get('platform'))}</td>"
            f"<td>{_h(d.get('model'))}</td>"
            f"<td>{_h(d.get('os_version'))}</td>"
            f"<td>{_h(d.get('serial_number'))}</td>"
            f"<td>{_h(d.get('assigned_user'))}</td>"
            f"<td>{_h(d.get('department'))}</td>"
            f"<td>{_h(d.get('fence_state'))}</td>"
            f"<td>{comp}</td>"
            f"<td>{_h(d.get('battery_level'))}%</td>"
            f"<td>{_h(d.get('risk_score'))}</td>"
            "</tr>"
        )
    s = summary or {}
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Inventario UEM — {_h(org_name)}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; color:#1a1a1a; padding:24px; }}
  h1 {{ font-size:20px; }} .meta {{ color:#666; font-size:12px; margin-bottom:16px; }}
  table {{ border-collapse:collapse; width:100%; font-size:11px; }}
  th,td {{ border:1px solid #ddd; padding:5px 7px; text-align:left; }}
  th {{ background:#f3f4f6; text-transform:uppercase; font-size:10px; }}
  tr:nth-child(even) {{ background:#fafafa; }}
  .sum {{ display:flex; gap:18px; margin:12px 0; font-size:13px; }}
  .sum b {{ font-size:18px; display:block; }}
  @media print {{ body {{ padding:0; }} .noprint {{ display:none; }} }}
</style></head>
<body>
  <h1>Inventario de Flota — LucidFence</h1>
  <div class="meta">Organización: {_h(org_name)} · Generado: {now} · {len(devices)} dispositivos</div>
  <div class="sum">
    <div>Total<b>{s.get('total', len(devices))}</b></div>
    <div>Conformes<b>{s.get('compliant', '—')}</b></div>
    <div>Incumplen<b>{s.get('noncompliant', '—')}</b></div>
    <div>Fuera de perímetro<b>{s.get('outside', '—')}</b></div>
    <div>Riesgo alto<b>{s.get('high_risk', '—')}</b></div>
  </div>
  <table>
    <thead><tr>
      <th>Dispositivo</th><th>ID</th><th>SO</th><th>Modelo</th><th>OS ver</th>
      <th>Serial</th><th>Usuario</th><th>Depto</th><th>Geovalla</th>
      <th>Cumple</th><th>Batería</th><th>Riesgo</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <p class="meta noprint">Imprime (⌘P / Ctrl+P) y elige "Guardar como PDF" para archivar este reporte.</p>
</body></html>"""


def _h(v) -> str:
    if v is None:
        return ""
    s = str(v)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
