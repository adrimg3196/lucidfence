#!/usr/bin/env bash
set -e
cd /Users/adri/lucidfence

# 1. Usar Python 3.11 explícitamente
PY=/opt/homebrew/bin/python3.11
if [ ! -x "$PY" ]; then
  echo "ERROR: $PY no encontrado. Buscando python3.11..."
  PY=$(which python3.11 2>/dev/null || which python3 2>/dev/null || echo "")
  if [ -z "$PY" ]; then
    echo "FATAL: No se encontró Python 3.11"
    exit 1
  fi
fi
echo "Usando Python: $PY ($( $PY --version 2>&1))"

# 2. Limpiar puertos zombie
for port in 8799 8791; do
  pids=$(lsof -ti :$port 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "Muriendo procesos en puerto $port: $pids"
    kill -9 $pids 2>/dev/null || true
    sleep 1
  fi
done
echo "Puertos limpios: $(lsof -i:8799 -i:8791 2>/dev/null | wc -l) procesos"

# 3. Corregir enlaces rotos
# PRODUCTION.md línea 298: DEVELOPMENT.md → ../contributing/DEVELOPMENT.md
grep -q 'contributing/DEVELOPMENT.md](DEVELOPMENT.md)' docs/operations/PRODUCTION.md 2>/dev/null && \
  sed -i '' 's|contributing/DEVELOPMENT.md](DEVELOPMENT.md)|contributing/DEVELOPMENT.md](../contributing/DEVELOPMENT.md)|g' docs/operations/PRODUCTION.md && \
  echo "OK: PRODUCTION.md enlace corregido" || echo "OK: PRODUCTION.md ya correcto"

# MANUAL_DE_USO.md: ./POLICY_DSL.md → ../reference/POLICY_DSL.md
grep -q 'Referencia POLICY DSL](./POLICY_DSL.md)' docs/manual/MANUAL_DE_USO.md 2>/dev/null && \
  sed -i '' 's|Referencia POLICY DSL](./POLICY_DSL.md)|Referencia POLICY DSL](../reference/POLICY_DSL.md)|g' docs/manual/MANUAL_DE_USO.md && \
  echo "OK: MANUAL_DE_USO.md enlace corregido" || echo "OK: MANUAL_DE_USO.md ya correcto"

# 4. Ejecutar verify con Python 3.11
echo ""
echo "=== EJECUTANDO VERIFY CON PYTHON 3.11 ==="
$PY scripts/verify.py
