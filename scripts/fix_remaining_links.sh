#!/bin/bash
set -e
cd /Users/adri/lucidfence

# 1. Limpiar puertos zombie
for port in 8799 8791; do
  pids=$(lsof -ti :$port 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "Muriendo procesos en puerto $port: $pids"
    kill -9 $pids 2>/dev/null || true
    sleep 1
  fi
done
echo "Puertos 8799/8791 limpios: $(lsof -i:8799 -i:8791 2>/dev/null | wc -l) procesos"

# 2. Corregir los 2 enlaces rotos restantes
# docs/operations/PRODUCTION.md:298 → DEVELOPMENT.md (debe ser ../contributing/DEVELOPMENT.md)
if grep -q '\[`contributing/DEVELOPMENT.md`\](DEVELOPMENT.md)' docs/operations/PRODUCTION.md 2>/dev/null; then
  sed -i '' 's|\[`contributing/DEVELOPMENT.md`\](DEVELOPMENT.md)|[`contributing/DEVELOPMENT.md`](../contributing/DEVELOPMENT.md)|g' docs/operations/PRODUCTION.md
  echo "Corregido: PRODUCTION.md → ../contributing/DEVELOPMENT.md"
fi

# docs/manual/MANUAL_DE_USO.md:204 → ./POLICY_DSL.md (debe ser ../reference/POLICY_DSL.md)
if grep -q '\[Referencia POLICY DSL\](./POLICY_DSL.md)' docs/manual/MANUAL_DE_USO.md 2>/dev/null; then
  sed -i '' 's|\[Referencia POLICY DSL\](./POLICY_DSL.md)|[Referencia POLICY DSL](../reference/POLICY_DSL.md)|g' docs/manual/MANUAL_DE_USO.md
  echo "Corregido: MANUAL_DE_USO.md → ../reference/POLICY_DSL.md"
fi

echo "Enlaces corregidos. Ejecutando verify..."
