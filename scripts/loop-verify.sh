#!/usr/bin/env bash
# Loop de verificación automática para LucidFence
# Ejecuta verify.py, registra el resultado en loop-run-log.md
# Uso: ./scripts/loop-verify.sh [opcional: --commit]

set -e
cd /Users/adri/lucidfence

LOGFILE="docs/internal/loop-run-log.md"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
PY=/Users/adri/lucidfence/.venv/bin/python

echo "[$TIMESTAMP] Ejecutando loop-verify..."

# Ejecutar verify
OUTPUT=$($PY scripts/verify.py 2>&1) || true
echo "$OUTPUT"

# Extraer resumen
if echo "$OUTPUT" | grep -q "APTO (4/4 checks)"; then
    STATUS="APTO"
    CHECKS="4/4 checks"
elif echo "$OUTPUT" | grep -q "FALLO"; then
    STATUS="FALLO"
    FAILS=$(echo "$OUTPUT" | grep "FALLO" | wc -l)
    CHECKS="$FAILS checks en fallo"
else
    STATUS="UNKNOWN"
    CHECKS="desconocido"
fi

# Detectar fallos específicos
DOCS_FAIL=$(echo "$OUTPUT" | grep -c "Enlaces de docs:.*rotos" || true)
RUNTIME_FAIL=$(echo "$OUTPUT" | grep -c "Batería runtime" | grep -c "FALLO" || true)
SUITE_FAIL=$(echo "$OUTPUT" | grep -c "Suite honesta.*FALLO" || true)
HONEST_TALLY=$(echo "$OUTPUT" | grep "Suite honesta:.*passed.*failed" || echo "")

# Buscar evidencia adicional del output
if echo "$OUTPUT" | grep -q "582 passed, 0 failed"; then
    HONEST="582 passed, 0 failed"
elif echo "$OUTPUT" | grep -q "555 passed, 0 failed"; then
    HONEST="555 passed, 0 failed"
elif echo "$OUTPUT" | grep -q "551 passed, 0 failed"; then
    HONEST="551 passed, 0 failed"
else
    HONEST="ver vía output completo"
fi

# Formatear la entrada del log
ENTRY="- $TIMESTAMP | L2 | Loop verify automático | verify.py: $STATUS ($CHECKS) | "
if [ "$STATUS" = "APTO" ]; then
    ENTRY+="todos los checks paso. "
else
    ENTRY+="algunos checks fallaron. "
fi
ENTRY+="Batería runtime: $(echo "$OUTPUT" | grep "Batería runtime" | head -1). "
ENTRY+="Suite honesta: $HONEST. "
ENTRY+="Enlaces docs: $(echo "$OUTPUT" | grep "Enlaces de docs" | head -1). "
ENTRY+="Loop verify ejecutado automáticamente."

# Añadir al log (append)
echo "$ENTRY" >> "$LOGFILE"

echo "[$TIMESTAMP] Loop verify completado. Entrada añadida a $LOGFILE"
echo "Status: $STATUS"

# Si se pasó --commit, hacer commit
if [ "$1" = "--commit" ]; then
    echo "Haciendo commit..."
    git add docs/internal/loop-run-log.md
    git commit -m "Loop verify automático: $STATUS ($HONEST, $(date -u +'%Y-%m-%d'))" || echo "Commit skip"
fi
