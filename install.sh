#!/usr/bin/env bash
# LucidFence — installer para clientes (100% local, soberano, $0)
#
# Deja LucidFence corriendo en la máquina del cliente con un solo comando.
# No requiere credenciales del proveedor ni envía datos a terceros.
#
# Modo recomendado:
#   git clone https://github.com/adrimg3196/lucidfence.git && cd lucidfence && ./install.sh
# También soporta curl|bash para bootstrap, pero clona el repo completo antes
# de arrancar y usa dependencias pineadas con hash.
#
# El script detecta Docker y, si está presente, levanta el stack completo
# (LucidFence SaaS + engine + IA local) en un contenedor always-on. Si no
# hay Docker, deja el stack corriendo en segundo plano con Python directo.
set -euo pipefail

PORT="${LUCIDFENCE_PORT:-8765}"
REPO="adrimg3196/lucidfence"
REPO_URL="https://github.com/$REPO.git"
PUBLIC_HOST="${LUCIDFENCE_PUBLIC_HOST:-}"

inside_repo() {
  [ -f saas_server.py ] && [ -f requirements.lock ] && [ -f docker-compose.yml ]
}

ensure_repo_checkout() {
  if inside_repo; then
    return 0
  fi
  if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: se necesita git para clonar el repo completo y evitar descargas raw no verificadas." >&2
    exit 1
  fi
  target="lucidfence-tmp"
  echo "   Clonando repo completo $REPO…"
  rm -rf "$target"
  git clone --depth=1 "$REPO_URL" "$target"
  cd "$target"
}

echo "== LucidFence installer =="
echo "   Puerto: $PORT"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "== Docker detectado: levantando stack con docker compose =="
  ensure_repo_checkout
  mkdir -p data
  if [ -n "$PUBLIC_HOST" ]; then
    echo "   Internet-facing: activando reverse proxy TLS para $PUBLIC_HOST"
    LUCIDFENCE_PUBLIC_HOST="$PUBLIC_HOST" docker compose --profile internet-facing up -d --build
    echo "== LucidFence arrancado en https://$PUBLIC_HOST =="
  else
    docker compose up -d --build
    echo "== LucidFence arrancado en http://localhost:$PORT =="
    echo "   Puerto publicado solo en 127.0.0.1. Para internet: LUCIDFENCE_PUBLIC_HOST=tu.dominio ./install.sh"
  fi
  echo "   (corre 24/7; para pararlo: docker compose down)"
  exit 0
fi

echo "== Docker no encontrado: arranque con Python directo =="
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: se necesita python3. Instalalo e intenta de nuevo." >&2
  exit 1
fi

ensure_repo_checkout

echo "   Instalando dependencias (requirements.txt)…"
python3 -m pip install -q --require-hashes -r requirements.lock

mkdir -p data
echo "== Arrancando LucidFence en segundo plano (puerto $PORT) =="
nohup python3 saas_server.py > lucidfence.log 2>&1 &
echo $! > lucidfence.pid
echo "== LucidFence arrancado en http://localhost:$PORT =="
echo "   PID: $(cat lucidfence.pid)  ·  log: lucidfence.log"
echo "   Para pararlo: kill \$(cat lucidfence.pid)"
