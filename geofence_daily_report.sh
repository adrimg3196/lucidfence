#!/usr/bin/env bash
# geofence_daily_report.sh — Reporte diario de compliance de geofencing (100% local)
#
# Genera el reporte de compliance leyendo SOLO el estado local (data/) y la
# configuracion de cercas (fences.json). Escribe reportes md/csv/json en --out
# y compone un resumen de una línea. Sin red, sin credenciales, sin contacto
# con dispositivos.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

OUT_DIR="${1:-reports}"

# Genera el reporte completo a partir de data/ + fences.json (modo offline).
RESULT="$(python3 reports.py --out "$OUT_DIR")"

# Extrae los totales y compone el resumen en una sola línea.
python3 - "$RESULT" <<'PY'
import json, sys
res = json.loads(sys.argv[1])
t = res["totals"]
print("Reporte diario geofencing OK | "
      f"dispositivos={t['devices']} dentro={t['inside']} "
      f"no-compliant={t['non_compliant']} violaciones={t['violations']} "
      f"compliance={t['compliance_rate_pct']}%")
PY
