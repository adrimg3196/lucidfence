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
HEALTH_TIMEOUT="${LUCIDFENCE_HEALTH_TIMEOUT:-30}"
VENV_DIR="${LUCIDFENCE_VENV_DIR:-.venv}"
REPO="adrimg3196/lucidfence"
REPO_URL="https://github.com/$REPO.git"
PUBLIC_HOST="${LUCIDFENCE_PUBLIC_HOST:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$HEALTH_TIMEOUT" in
  ''|*[!0-9]*)
    echo "ERROR: LUCIDFENCE_HEALTH_TIMEOUT debe ser un entero positivo." >&2
    exit 2
    ;;
esac
if [ "$HEALTH_TIMEOUT" -lt 1 ]; then
  echo "ERROR: LUCIDFENCE_HEALTH_TIMEOUT debe ser mayor que cero." >&2
  exit 2
fi

service_health_payload() {
  local port="$1"
  local url="http://127.0.0.1:${port}/api/health"

  if command -v curl >/dev/null 2>&1; then
    curl -fsS "$url"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$url" <<'PY'
import sys
import urllib.request

with urllib.request.urlopen(sys.argv[1], timeout=5) as response:
    if response.status != 200:
        raise SystemExit(1)
    print(response.read(4096).decode("utf-8", errors="replace"))
PY
    return
  fi
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    docker compose exec -T lucidfence python3 -c \
      "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=5); print(r.read(4096).decode('utf-8', errors='replace'))"
    return
  fi
  echo "ERROR: no hay cliente HTTP disponible (curl, Python 3 o el contenedor Docker)." >&2
  return 127
}

service_verify_health() {
  local port="$1"
  local timeout="${2:-30}"
  local start payload
  start="$(date +%s)"
  while ! payload="$(service_health_payload "$port" 2>/dev/null)"; do
    sleep 1
    if [ "$(($(date +%s) - start))" -ge "$timeout" ]; then
      return 1
    fi
  done
  printf '%s\n' "$payload"
}

install_verify_health() {
  local mode="$1"
  local payload
  echo "== Esperando health de LucidFence (máximo ${HEALTH_TIMEOUT}s) =="
  if ! payload="$(service_verify_health "$PORT" "$HEALTH_TIMEOUT")"; then
    echo "ERROR: LucidFence no respondió en /api/health tras ${HEALTH_TIMEOUT}s (${mode})." >&2
    return 1
  fi
  echo "== Health confirmado: ${payload} =="
}

service_systemd_install() {
  local unit_dir="/etc/systemd/system"
  local unit_file="${unit_dir}/lucidfence.service"
  local working_dir="${SCRIPT_DIR}"
  if [ ! -f "${SCRIPT_DIR}/saas_server.py" ]; then
    echo "ERROR: script no detecta checkout del repo en ${SCRIPT_DIR}" >&2
    exit 1
  fi
  echo "== Instalando servicio systemd (target: ${unit_file}) =="
  mkdir -p "${unit_dir}"
  cat > "${unit_file}" <<EOF
[Unit]
Description=LucidFence local always-on service (systemd)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${working_dir}
ExecStart=/usr/bin/env python3 saas_server.py
Restart=always
RestartSec=5
Environment=LUCIDFENCE_PORT=${PORT}
Environment=LUCIDFENCE_HOST=127.0.0.1

# Hardening básico
ProtectSystem=full
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload || true
  systemctl enable --now lucidfence.service || true
  echo "== Verificación post-install (systemd) =="
  if systemctl is-active --quiet lucidfence.service; then
    service_verify_health "${PORT}" 30 || true
    echo "== Servicio systemd activo. health:"
    systemctl status --no-pager --full lucidfence.service || true
  else
    echo "WARN: lucidfence.service no quedó activo; revisa logs con:" >&2
    echo "  journalctl -u lucidfence.service -n 200" >&2
  fi
  echo "== Para desinstalar:"
  echo "  systemctl disable --now lucidfence.service && rm -f ${unit_file} && systemctl daemon-reload"
}

service_launchd_install() {
  local agent_dir="${HOME}/Library/LaunchAgents"
  local plist_name="com.adrimg3196.lucidfence"
  local plist_file="${agent_dir}/${plist_name}.plist"
  local working_dir="${SCRIPT_DIR}"
  if [ ! -f "${SCRIPT_DIR}/saas_server.py" ]; then
    echo "ERROR: script no detecta checkout del repo en ${SCRIPT_DIR}" >&2
    exit 1
  fi
  echo "== Instalando agente launchd (target: ${plist_file}) =="
  mkdir -p "${agent_dir}"
  cat > "${plist_file}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${plist_name}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>python3</string>
    <string>saas_server.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${working_dir}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>LUCIDFENCE_PORT</key>
    <string>${PORT}</string>
    <key>LUCIDFENCE_HOST</key>
    <string>127.0.0.1</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>
  <key>StandardOutPath</key>
  <string>/tmp/${plist_name}.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/${plist_name}.err.log</string>
</dict>
</plist>
EOF
  launchctl bootout gui/"$(id -u)"/"${plist_name}" >/dev/null 2>&1 || true
  launchctl bootstrap gui/"$(id -u)" "${plist_file}" || true
  echo "== Verificación post-install (launchd) =="
  if launchctl list | awk '{print $3}' | grep -qx "${plist_name}"; then
    service_verify_health "${PORT}" 30 || true
    echo "== Agente launchd registrado. Logs:"
    echo "  /tmp/${plist_name}.log"
    echo "  /tmp/${plist_name}.err.log"
  else
    echo "WARN: ${plist_name} no aparece registrado en launchctl; revisa:" >&2
    echo "  launchctl list | grep ${plist_name}" >&2
  fi
  echo "== Para desinstalar:"
  echo "  launchctl bootout gui/\$(id -u)/${plist_name} && rm -f ${plist_file}"
}

service_usage() {
  echo "Uso: $0 service <systemd|launchd>" >&2
  echo "  service systemd   instala unit systemd con arranque automático" >&2
  echo "  service launchd   instala agente launchd para macOS" >&2
  exit 1
}

if [ "${1:-}" = "service" ]; then
  target="${2:-}"
  case "$target" in
    systemd) service_systemd_install ;;
    launchd) service_launchd_install ;;
    *) service_usage ;;
  esac
  exit 0
fi

assert_secure_repo_url() {
  case "$REPO_URL" in
    https://github.com/"$REPO".git) return 0 ;;
  esac
  echo "ERROR: REPO_URL debe usar HTTPS hacia github.com/$REPO.git; no se permiten transportes no verificados." >&2
  exit 1
}

verify_locked_deps() {
  if [ ! -s requirements.lock ] || ! grep -q -- '--hash=sha256:' requirements.lock; then
    echo "ERROR: requirements.lock falta o no contiene hashes sha256; abortando instalación." >&2
    exit 1
  fi
}

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
  assert_secure_repo_url
  git -c http.sslVerify=true -c protocol.file.allow=never -c protocol.ext.allow=never \
    clone --depth=1 --filter=blob:none "$REPO_URL" "$target"
  cd "$target"
}

echo "== LucidFence installer =="
echo "   Puerto: $PORT"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "== Docker detectado: levantando stack con docker compose =="
  ensure_repo_checkout
  verify_locked_deps
  mkdir -p data
  if [ -n "$PUBLIC_HOST" ]; then
    echo "   Internet-facing: activando reverse proxy TLS para $PUBLIC_HOST"
    LUCIDFENCE_PUBLIC_HOST="$PUBLIC_HOST" docker compose --profile internet-facing up -d --build
  else
    docker compose up -d --build
  fi
  install_verify_health "Docker"
  if [ -n "$PUBLIC_HOST" ]; then
    echo "== LucidFence arrancado en https://$PUBLIC_HOST =="
  else
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
verify_locked_deps

PYTHON_RUNTIME="${VENV_DIR}/bin/python"
if [ ! -x "$PYTHON_RUNTIME" ]; then
  echo "== Creando entorno Python aislado en ${VENV_DIR} =="
  if ! python3 -m venv "$VENV_DIR"; then
    echo "ERROR: Python no pudo crear el entorno virtual." >&2
    echo "   En Debian/Ubuntu instala python3-venv; en macOS usa Python de Homebrew o Docker." >&2
    exit 1
  fi
fi
if ! "$PYTHON_RUNTIME" -m pip --version >/dev/null 2>&1; then
  echo "ERROR: el entorno virtual no contiene pip; reinstala Python con venv/ensurepip o usa Docker." >&2
  exit 1
fi

echo "   Instalando dependencias verificadas (requirements.lock) en ${VENV_DIR}…"
"$PYTHON_RUNTIME" -m pip install -q --require-hashes -r requirements.lock
echo "== Dependencias instaladas en ${VENV_DIR} =="

mkdir -p data
# Arma el pre-commit local (scripts/pre-commit.sh) como git hook nativo.
# Best-effort: no falla la instalación si algo se tuerce.
if [ -f "$SCRIPT_DIR/scripts/pre-commit.sh" ]; then
  git config core.hooksPath scripts 2>/dev/null || true
  echo "== Pre-commit hook activado (scripts/pre-commit.sh) =="
fi
echo "== Arrancando LucidFence en segundo plano (puerto $PORT) =="
nohup "$PYTHON_RUNTIME" saas_server.py > lucidfence.log 2>&1 &
server_pid=$!
echo "$server_pid" > lucidfence.pid
if ! install_verify_health "Python"; then
  kill "$server_pid" >/dev/null 2>&1 || true
  wait "$server_pid" >/dev/null 2>&1 || true
  rm -f lucidfence.pid
  echo "   Revisa el log de arranque: lucidfence.log" >&2
  exit 1
fi
if ! kill -0 "$server_pid" >/dev/null 2>&1; then
  wait "$server_pid" >/dev/null 2>&1 || true
  rm -f lucidfence.pid
  echo "ERROR: el proceso Python terminó aunque /api/health respondió; puede existir otro servicio en el puerto ${PORT}." >&2
  echo "   Revisa el log de arranque: lucidfence.log" >&2
  exit 1
fi
echo "== LucidFence arrancado en http://localhost:$PORT =="
echo "   PID: $(cat lucidfence.pid)  ·  log: lucidfence.log"
echo "   Para pararlo: kill \$(cat lucidfence.pid)"
