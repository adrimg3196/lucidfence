#!/bin/bash
# ============================================================
# Geofence UEM — empaquetado del entregable (100% LOCAL)
# Genera un tarball listo para entregar al cliente.
# Uso:  ./build.sh
# Salida: dist/geofence-uem-<fecha>.tar.gz
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

VERSION=$(date +%Y%m%d)
OUT_DIR="dist"
NAME="geofence-uem-$VERSION"
STAGE="$OUT_DIR/$NAME"

mkdir -p "$STAGE"

# --- copiar código fuente (excluye datos de tenant y caches) ---
rsync -a --exclude='data/tenants' --exclude='__pycache__' --exclude='.pytest_cache' \
      --exclude='*.pyc' --exclude='.env' --exclude='data/*.tmp' \
      ./ "$STAGE/"

# --- requirements + readmes ya presentes en el stage ---

# --- manifest del entregable ---
cat > "$STAGE/MANIFEST.txt" <<EOF
Geofence UEM Command Center — entregable cliente
Generado: $(date)
Modo: 100% local (macOS). Sin exfiltrar datos.
Arranque: ./start_all.sh
Dashboard: http://127.0.0.1:8765
Docs cliente: README_CLIENTE.md
Spec producto: SPEC.md
EOF

# --- tarball ---
tar -czf "$OUT_DIR/$NAME.tar.gz" -C "$OUT_DIR" "$NAME"
rm -rf "$STAGE"

echo "Entregable generado: $OUT_DIR/$NAME.tar.gz"
echo "Tamaño: $(du -h "$OUT_DIR/$NAME.tar.gz" | cut -f1)"
echo "Para entregar al cliente: descomprimir y ejecutar ./start_all.sh"
