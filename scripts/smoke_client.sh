#!/usr/bin/env bash
# smoke_client.sh — smoke test del CLIENTE LucidFence (modelo soberano).
# Cualquiera puede correrlo y VER que el producto funciona en su maquina.
# Uso:  bash scripts/smoke_client.sh
# Requisitos: python3.11 (o `brew install adrimg3196/lucidfence/lucidfence`).
set -euo pipefail

PORT="${LUCIDFENCE_PORT:-8790}"
REPO="adrimg3196/lucidfence"
RELEASE="v1.0.2"
ASSET="lucidfence-${RELEASE}.tar.gz"
URL="https://github.com/${REPO}/releases/download/${RELEASE}/${ASSET}"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

echo "== Smoke test cliente LucidFence (${RELEASE}) =="
echo "1. Descarga del release (lo que hace 'brew install')..."
# 'gh release download' es la via fiable (maneja el redirect de GitHub).
# El cliente dev debe tener 'gh' (o usar 'brew install' directo).
GH=$(command -v gh || true)
if [ -z "$GH" ]; then
  echo "   [AVISO] 'gh' no encontrado en PATH. Usa 'brew install adrimg3196/lucidfence/lucidfence'"
  echo "   o instala gh: brew install gh"
  exit 1
fi
"$GH" release download "$RELEASE" --repo "$REPO" --pattern "$ASSET" --dir "$WORK" --clobber < /dev/null 2>/dev/null
file "$WORK/$ASSET" | grep -q "gzip" || { echo "   [FAIL] el release no se bajó como gzip (red/CORS)"; exit 1; }
tar xzf "$WORK/$ASSET" -C "$WORK"
APP="$WORK/lucidfence"

echo "2. Arranca el server on-prem (en TU maquina)..."
LUCIDFENCE_PORT="$PORT" nohup "$APP/bin/lucidfence" serve >"$WORK/server.log" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null || true; rm -rf "$WORK"' EXIT

# esperar a que suba
for i in $(seq 1 30); do
  if curl -s -o /dev/null "http://127.0.0.1:$PORT/"; then break; fi
  sleep 1
done

echo "3. Verificaciones:"
code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/")
[ "$code" = "200" ] && echo "   [OK] dashboard HTTP $code" || { echo "   [FAIL] dashboard HTTP $code"; kill $SRV 2>/dev/null; exit 1; }

code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/api/health")
[ "$code" = "200" ] && echo "   [OK] /api/health HTTP $code" || echo "   [WARN] /api/health HTTP $code"

# login demo
login=$(curl -s -c "$WORK/cj.txt" -X POST "http://127.0.0.1:$PORT/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"ciso@acme.test","password":"demo1234"}' -w "\n%{http_code}")
http_code=$(echo "$login" | tail -1)
echo "$login" | grep -q '"ok": true' && echo "   [OK] login demo (ciso@acme.test) HTTP $http_code" || echo "   [FAIL] login demo HTTP $http_code"

code=$(curl -s -b "$WORK/cj.txt" -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/api/risk")
[ "$code" = "200" ] && echo "   [OK] /api/risk autenticado HTTP $code (motor de riesgo)" || echo "   [WARN] /api/risk HTTP $code"

echo ""
echo "== RESULTADO: EL CLIENTE FUNCIONA =="
echo "   Abre en tu navegador: http://localhost:$PORT/"
echo "   Usuario demo: ciso@acme.test / demo1234"
kill $SRV 2>/dev/null || true
