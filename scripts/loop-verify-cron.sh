#!/usr/bin/env bash
# Loop verify automático para LucidFence
# Este script es ejecutado por el cron cada hora
# Ejecuta verify.py, registra resultado en loop-run-log.md

set -e
cd /Users/adri/lucidfence

LOGFILE="docs/internal/loop-run-log.md"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
PY=/Users/adri/lucidfence/.venv/bin/python

# Ejecutar verify
OUTPUT=$($PY scripts/verify.py 2>&1) || true

# Extraer resultados
if echo "$OUTPUT" | grep -q "APTO (4/4 checks)"; then
    STATUS="APTO"
    CHECKS="4/4 checks 통과"
elif echo "$OUTPUT" | grep -q "FALLO"; then
    FAILS=$(echo "$OUTPUT" | grep "FALLO" | wc -l)
    STATUS="FALLO"
    CHECKS="$FAILS checks en fallo"
else
    STATUS="UNKNOWN"
    CHECKS="desconocido"
fi

# Extraer métricas específicas del output
RUNTIME_LINE=$(echo "$OUTPUT" | grep "Batería runtime" | head -1 || echo "   OK   Batería runtime (en vivo): sin datos")
SUITE_LINE=$(echo "$OUTPUT" | grep "Suite honesta:" | head -1 || echo "   OK   Suite honesta: sin datos")
DOCS_LINE=$(echo "$OUTPUT" | grep "Enlaces de docs" | head -1 || echo "   OK   Enlaces de docs: sin datos")

# Crear entrada del log
ENTRY="- $TIMESTAMP | L2 | Loop verify automático (cron) | verify.py: $STATUS ($CHECKS) | "
ENTRY+="Runtime: $(echo "$RUNTIME_LINE" | sed 's/^[[:space:]]*//'). "
ENTRY+="Suite honesta: $(echo "$SUITE_LINE" | sed 's/^[[:space:]]*//'). "
ENTRY+="Docs: $(echo "$DOCS_LINE" | sed 's/^[[:space:]]*//'). "
ENTRY+="Loop ejecutado automáticamente por cron."

# Append al log
echo "$ENTRY" >> "$LOGFILE"

echo "[$TIMESTAMP] Loop verify completado: $STATUS"
