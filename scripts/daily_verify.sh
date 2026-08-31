#!/usr/bin/env bash
cd /Users/adri/lucidfence

# 1. Forzar Python 3.11 y limpiar puertos zombie
export PATH="/opt/homebrew/bin:$PATH"
PY=$(which python3.11)
echo "Python: $($PY --version 2>&1)"
for port in 8799 8791; do
  lsof -ti :$port 2>/dev/null | xargs -r kill -9 2>/dev/null || true
done
sleep 1
echo "Puertos 8799/8791 libres: $(lsof -i:8799 -i:8791 2>/dev/null | wc -l) procesos"

# 2. Corregir último enlace roto: PRODUCTION.md línea 298
sed -i '' 's|\[`contributing/DEVELOPMENT.md`](DEVELOPMENT.md)|[`contributing/DEVELOPMENT.md`](../contributing/DEVELOPMENT.md)|g' docs/operations/PRODUCTION.md
echo "Enlace PRODUCTION.md → ../contributing/DEVELOPMENT.md corregido"

# 3. Ejecutar verify con Python 3.11
echo ""
echo "=== VERIFY CON PYTHON 3.11 ==="
$PY scripts/verify.py

echo ""
echo "=== TEST ADAPTER CLOUD ==="
$PY -m pytest tests/test_adapter_scaffold.py::test_cli_wires_adapter_new_command -v --tb=long 2>&1 | tail -50
