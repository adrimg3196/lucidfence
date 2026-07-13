#!/bin/bash
# LucidFence — DEPLOY a Fly.io (free tier, always-on).
#
# PRE-REQUISITO (tu cuenta, fuera de sesión del agente):
#   flyctl auth login          # abre navegador, autentícate
#   flyctl auth whoami       # confirma
#
# Luego el agente (o tú) ejecuta este script:
#   ./deploy_fly.sh
#
# Qué hace:
#   1) flyctl launch --no-deploy   (crea la app, no despliega)
#   2) flyctl deploy                  (sube la imagen Docker con MoA + SaaS + SQLite)
#   3) flyctl status                  (confirma que corre 24/7)
#
# El free tier de Fly.io cubre 1 VM shared-cpu SIEMPRE ON (auto_stop=off).
# Variables de entorno y secretos (API keys de MoA) se montan aparte:
#   flyctl secrets set MOA_OPENROUTER_KEY=xxx   # opcional, para IA real
set -e

cd "$(dirname "$0")"

echo "[deploy] verificando flyctl..."
command -v flyctl >/dev/null 2>&1 || { echo "[deploy] ERROR: instala flyctl (https://fly.io/install.sh) y haz 'flyctl auth login'"; exit 1; }
flyctl auth whoami >/dev/null 2>&1 || { echo "[deploy] ERROR: haz 'flyctl auth login' primero"; exit 1; }

APP="${FLY_APP:-lucidfence}"

echo "[deploy] launch (no deploy) -> $APP"
flyctl launch --no-deploy --name "$APP" --region "${FLY_REGION:-mad}" --vm-size shared-cpu-1x --memory 256 || \
  echo "[deploy] (app ya existe, continuo)"

echo "[deploy] deploy de la imagen (MoA + SaaS + SQLite)..."
flyctl deploy

echo "[deploy] estado:"
flyctl status

echo ""
echo "[deploy] LISTO. Tu LucidFence corre 24/7 en free tier."
echo "  landing:   https://$APP.fly.dev/"
echo "  dashboard: https://$APP.fly.dev/app"
echo "  (el dominio FreeDomain se apunta a Cloudflare y redirige a esta VM)"
