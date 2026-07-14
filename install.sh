#!/usr/bin/env bash
# LucidFence — installer para clientes (100% local, soberano, $0)
#
# Deja LucidFence corriendo en la máquina del cliente con un solo comando.
# No requiere credenciales del proveedor ni envía datos a terceros.
#
# Modo de uso:
#   curl -fsSL https://raw.githubusercontent.com/adrimg3196/lucidfence/main/install.sh | bash
#   — o bien, dentro del repo clonado:  ./install.sh
#
# El script detecta Docker y, si está presente, levanta el stack completo
# (LucidFence SaaS + engine + IA local) en un contenedor always-on. Si no
# hay Docker, deja el stack corriendo en segundo plano con Python directo.
set -euo pipefail

PORT="${LUCIDFENCE_PORT:-8765}"
REPO="adrimg3196/lucidfence"

echo "== LucidFence installer =="
echo "   Puerto: $PORT"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "== Docker detectado: levantando stack con docker compose =="
  if [ ! -f docker-compose.yml ]; then
    echo "   Descargando docker-compose.yml del repo…"
    curl -fsSL "https://raw.githubusercontent.com/$REPO/main/docker-compose.yml" -o docker-compose.yml
  fi
  mkdir -p data
  docker compose up -d --build
  echo "== LucidFence arrancado en http://localhost:$PORT =="
  echo "   (corre 24/7; para pararlo: docker compose down)"
  exit 0
fi

echo "== Docker no encontrado: arranque con Python directo =="
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: se necesita python3. Instalalo e intenta de nuevo." >&2
  exit 1
fi

# Clonar si no estamos ya dentro del repo.
if [ ! -f saas_server.py ]; then
  echo "   Clonando repo $REPO…"
  git clone --depth=1 "https://github.com/$REPO.git" lucidfence-tmp
  cd lucidfence-tmp
fi

echo "   Instalando dependencias (requirements.txt)…"
python3 -m pip install -q -r requirements.txt || {
  echo "   (pip no disponible o falló; si ya tienes las deps, continúa)"
}

mkdir -p data
echo "== Arrancando LucidFence en segundo plano (puerto $PORT) =="
nohup python3 saas_server.py > lucidfence.log 2>&1 &
echo $! > lucidfence.pid
echo "== LucidFence arrancado en http://localhost:$PORT =="
echo "   PID: $(cat lucidfence.pid)  ·  log: lucidfence.log"
echo "   Para pararlo: kill \$(cat lucidfence.pid)"
