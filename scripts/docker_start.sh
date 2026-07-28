#!/bin/sh
# Arranque unificado LucidFence en la VM de Fly.io:
#  - MoA local (IA) en segundo plano, 127.0.0.1:8085
#  - LucidFence SaaS + engine en primer plano, 127.0.0.1:8765
set -e

cd /app

# 1) Motor de IA (MoA) — 100% local, OpenAI-compatible.
echo "[boot] arrancando MoA en 127.0.0.1:8085"
PYTHONPATH=/app/moa python3 /app/moa/server.py --port 8085 --host 127.0.0.1 &
MOA_PID=$!

# Esperar a que MoA responda (health), con timeout.
for i in $(seq 1 20); do
  if python3 -c "import http.client;c=http.client.HTTPConnection('127.0.0.1',8085,timeout=2);c.request('GET','/');c.getresponse()" 2>/dev/null; then
    echo "[boot] MoA listo"
    break
  fi
  sleep 1
done

# 2) LucidFence SaaS + engine (este proceso mantiene viva la VM).
echo "[boot] arrancando LucidFence SaaS en ${LUCIDFENCE_HOST:-127.0.0.1}:8765"
exec python3 /app/saas_server.py
