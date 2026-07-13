#!/bin/bash
# LucidFence — arranque LOCAL (macOS / Linux) sin Docker.
# Corre MoA (IA) + LucidFence SaaS (engine + dashboard) en tu máquina.
#
# Uso:
#   ./start_local.sh            # MoA (:8085) + SaaS (:8765)
#   MOA_DRY=false ./start_local.sh   # fuerza IA real (necesita claves en moa/.env)
#
# Requiere: python3.11 en el venv .venv (creado con: python3.11 -m venv .venv && .venv/bin/pip install requests pytest)
set -e

cd "$(dirname "$0")"

# MoA vive fuera del repo de LucidFence (en /Users/adri/moa por defecto).
# Sobrescribe con MOA_DIR si tu ruta es distinta.
MOA_DIR="${MOA_DIR:-/Users/adri/moa}"
[ -d "$MOA_DIR" ] || MOA_DIR="../moa"
[ -d "$MOA_DIR" ] || { echo "[start] ERROR: no encontre moa en $MOA_DIR"; exit 1; }

PY="${VENV_PYTHON:-.venv/bin/python}"
MOA_PORT="${MOA_PORT:-8085}"
SAAS_PORT="${LUCIDFENCE_PORT:-8765}"

if [ ! -x "$PY" ] && [ ! -f "$PY" ]; then
  echo "[start] no encontre el venv en .venv/bin/python; usa python3 del sistema"
  PY="$(command -v python3.11 || command -v python3)"
fi

echo "[start] arrancando MoA (IA) en :$MOA_PORT"
PYTHONPATH="$MOA_DIR" "$PY" "$MOA_DIR/server.py" --port "$MOA_PORT" --host 127.0.0.1 &
MOA_PID=$!

# Esperar a que MoA responda (health), con timeout.
for i in $(seq 1 20); do
  if "$PY" -c "import http.client;c=http.client.HTTPConnection('127.0.0.1',$MOA_PORT,timeout=2);c.request('GET','/');c.getresponse()" 2>/dev/null; then
    echo "[start] MoA listo"
    break
  fi
  sleep 1
done

echo "[start] arrancando LucidFence SaaS en :$SAAS_PORT"
echo "[start]   landing:  http://127.0.0.1:$SAAS_PORT/"
echo "[start]   dashboard: http://127.0.0.1:$SAAS_PORT/app"
echo "[start] Ctrl+C para detener."
exec "$PY" saas_server.py
