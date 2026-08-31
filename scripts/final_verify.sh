#!/usr/bin/env bash
set -e
cd /Users/adri/lucidfence

PY=/opt/homebrew/bin/python3.11
echo "Python: $($PY --version 2>&1)"

# Limpiar puertos
for port in 8799 8791; do
  pids=$(lsof -ti :$port 2>/dev/null || true)
  [ -n "$pids" ] && kill -9 $pids 2>/dev/null && sleep 1
done
echo "Puertos: $(lsof -i:8799 -i:8791 2>/dev/null | wc -l) procesos"

# Corregir último enlace roto: PRODUCTION.md línea 298
TARGET='- [`contributing/DEVELOPMENT.md`](DEVELOPMENT.md) — Development setup'
REPLACEMENT='- [`contributing/DEVELOPMENT.md`](../contributing/DEVELOPMENT.md) — Development setup'
if grep -qF "$TARGET" docs/operations/PRODUCTION.md; then
  sed -i '' "s|$(echo "$TARGET" | sed 's/[&/\]/\\&/g')|$(echo "$REPLACEMENT" | sed 's/[&/\]/\\&/g')|g" docs/operations/PRODUCTION.md
  echo "OK: enlace PRODUCTION.md corregido"
fi

# Ejecutar verify con 3.11
echo ""
echo "=== VERIFY ==="
$PY scripts/verify.py

echo ""
echo "=== ADAPTER TEST ==="
$PY -m pytest tests/test_adapter_scaffold.py::test_cli_wires_adapter_new_command -v --tb=long 2>&1 | tail -40
