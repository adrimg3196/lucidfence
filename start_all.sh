#!/bin/bash
# ============================================================
# LucidFence — arranque completo (100% LOCAL)
# Levanta:  MoA (127.0.0.1:8085)  +  LucidFence (127.0.0.1:8765)
# Verifica salud y reporta estado de claves de IA.
# Uso:  ./start_all.sh          (arranca y deja en background)
#       ./start_all.sh stop     (para ambos)
#       ./start_all.sh status   (estado)
# ============================================================
set -u

MOA_DIR="$(cd "$(dirname "$0")/../moa" 2>/dev/null && pwd || echo "/Users/adri/moa")"
GEO_DIR="$(cd "$(dirname "$0")" && pwd)"
MOA_PORT=8085
GEO_PORT=8765
LOG_MOA="${GEO_DIR}/logs/moa.log"
LOG_GEO="${GEO_DIR}/logs/geofence.log"

c_grn='\033[0;32m'; c_red='\033[0;31m'; c_yel='\033[0;33m'; c_cyn='\033[0;36m'; c_off='\033[0m'

mkdir -p "$GEO_DIR/logs"

is_up(){ curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$1/" 2>/dev/null; }
health_ok(){ curl -s "http://127.0.0.1:$1/api/health" 2>/dev/null | grep -q '"status": "ok"'; }

stop_all(){
  echo "Parando servidores..."
  pkill -f "moa/server.py" 2>/dev/null
  pkill -f "$MOA_DIR/server.py" 2>/dev/null
  pkill -f "saas_server.py" 2>/dev/null
  sleep 1
  echo "Parados."
}

status_all(){
  local m g
  m=$(is_up $MOA_PORT); g=$(is_up $GEO_PORT)
  echo -e "MoA        (:$MOA_PORT)  -> HTTP $m"
  echo -e "Geofence   (:$GEO_PORT)  -> HTTP $g"
}

case "${1:-start}" in
  stop)   stop_all; exit 0 ;;
  status) status_all; exit 0 ;;
esac

echo -e "${c_cyn}== LucidFence · arranque completo ==${c_off}"

# 1) dependencia mínima
python3 -c "import requests" 2>/dev/null || { echo "Instalando 'requests'..."; pip3 install --quiet requests; }

# 2) MoA
if [ "$(is_up $MOA_PORT)" = "000" ]; then
  echo "Arrancando MoA..."
  ( cd "$MOA_DIR" && nohup python3 server.py >"$LOG_MOA" 2>&1 </dev/null & )
  for i in $(seq 1 20); do
    sleep 1
    health_ok $MOA_PORT && break
  done
  health_ok $MOA_PORT && echo -e "  ${c_grn}✓ MoA arriba${c_off} (:$MOA_PORT)" || echo -e "  ${c_red}✗ MoA no arrancó${c_off} — ver $LOG_MOA"
else
  echo "MoA ya estaba corriendo."
fi

# 3) Geofence
if [ "$(is_up $GEO_PORT)" = "000" ]; then
  echo "Arrancando LucidFence..."
  ( cd "$GEO_DIR" && nohup python3 saas_server.py >"$LOG_GEO" 2>&1 </dev/null & )
  for i in $(seq 1 20); do
    sleep 1
    health_ok $GEO_PORT && break
  done
  health_ok $GEO_PORT && echo -e "  ${c_grn}✓ Geofence arriba${c_off} (:$GEO_PORT)" || echo -e "  ${c_red}✗ Geofence no arrancó${c_off} — ver $LOG_GEO"
else
  echo "Geofence ya estaba corriendo."
fi

echo
status_all
echo

# 4) estado de claves de IA (solo presencia, nunca el valor)
echo -e "${c_cyn}== Claves de IA (MoA) ==${c_off}"
ENV_FILE="$MOA_DIR/.env"
found=0
for k in GROQ_API_KEY OPENROUTER_API_KEY NVIDIA_API_KEY DEEPSEEK_API_KEY CEREBRAS_API_KEY MISTRAL_API_KEY GITHUB_TOKEN HF_TOKEN GEMINI_API_KEY; do
  val=$(grep -E "^$k=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"' ')
  if [ -n "$val" ]; then echo -e "  ${c_grn}✓${c_off} $k"; found=$((found+1)); else echo -e "  ${c_yel}·${c_off} $k (vacía)"; fi
done
echo
if [ "$found" -eq 0 ]; then
  echo -e "${c_yel}IA en modo DEMO (mock):${c_off} no hay claves. Añade al menos una en:"
  echo "  $ENV_FILE"
  echo "  (Groq recomendado: https://console.groq.com/keys) y reinicia: ./start_all.sh stop && ./start_all.sh"
else
  echo -e "${c_grn}IA REAL activa${c_off} con $found proveedor(es). La mezcla MoA usará los disponibles."
fi
echo
echo -e "${c_grn}Dashboard:${c_off} http://127.0.0.1:$GEO_PORT/"
echo "Logs: $LOG_GEO  |  $LOG_MOA"
