#!/bin/bash
# Arranque rápido del producto LucidFence en local (100% local, sin exfiltrar datos).
set -e
cd "$(dirname "$0")"
python3 -c "import requests" 2>/dev/null || pip install requests >/dev/null
echo "Iniciando LucidFence (SaaS local, multi-tenant) en http://127.0.0.1:8765 ..."
echo "Dashboard: http://127.0.0.1:8765  ·  usuario demo: ciso@acme.test / [REDACTED]"
python3 saas_server.py
