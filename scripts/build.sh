#!/bin/bash
# ============================================================
# LucidFence — empaquetado del entregable (100% LOCAL)
# Genera un tarball listo para entregar al cliente.
# Uso:  ./scripts/build.sh
# Salida: dist/lucidfence-<fecha>.tar.gz
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."

# Para releases versionadas (workflow release.yml): LUCIDFENCE_BUILD_VERSION=1.5.0
VERSION=${LUCIDFENCE_BUILD_VERSION:-$(date +%Y%m%d)}
OUT_DIR="dist"
NAME="lucidfence-$VERSION"
STAGE="$OUT_DIR/$NAME"

mkdir -p "$STAGE"

# --- copiar código fuente (excluye datos de tenant y caches) ---
# `.git` iba dentro del tarball del cliente: historia completa, ramas y todo lo
# que alguna vez se commiteó. `dist` se copiaba a sí mismo en cada build.
# El entregable es el producto, no el repo: fuera assets de marketing (brand/
# llegó a meter 81MB en el tarball), config interna de agentes/CI y datos
# operativos del pipeline de la vitrina.
rsync -a --exclude='data/tenants' --exclude='__pycache__' --exclude='.pytest_cache' \
      --exclude='*.pyc' --exclude='.env' --exclude='data/*.tmp' \
      --exclude='.git' --exclude='.worktrees' --exclude='dist' --exclude='graphify-out' \
      --exclude='brand' --exclude='.agents' --exclude='.claude' \
      --exclude='.claude-plugin' --exclude='.gemini' --exclude='.superpowers' \
      --exclude='.github' --exclude='data/reports' --exclude='data/cloud_tenants' \
      --exclude='loop_improve.py' --exclude='ZERO-BACKLOG.md' \
      ./ "$STAGE/"

# --- SBOM del entregable ---
# Se genera aquí porque ya no se versiona (issue #74): rsync copiaría la copia
# rancia que el desarrollador tenga en su disco, y un manifest-sha256 que no
# cuadra con los .py entregados es peor señal que no entregar SBOM.
rm -f "$STAGE/sbom.cdx.json"
python3 scripts/generate_sbom.py --root "$STAGE" --out sbom.cdx.json  # --out es relativo a --root

# --- requirements + readmes ya presentes en el stage ---

# --- manifest del entregable ---
cat > "$STAGE/MANIFEST.txt" <<EOF
LucidFence Command Center — entregable cliente
Generado: $(date)
Modo: 100% local (macOS). Sin exfiltrar datos.
Arranque: ./scripts/start_all.sh
Dashboard: http://127.0.0.1:8765
Docs cliente: docs/product/README_CLIENTE.md
Spec producto: docs/architecture/SPEC.md
EOF

# --- tarball ---
tar -czf "$OUT_DIR/$NAME.tar.gz" -C "$OUT_DIR" "$NAME"
rm -rf "$STAGE"

echo "Entregable generado: $OUT_DIR/$NAME.tar.gz"
echo "Tamaño: $(du -h "$OUT_DIR/$NAME.tar.gz" | cut -f1)"
echo "Para entregar al cliente: descomprimir y ejecutar ./scripts/start_all.sh"
