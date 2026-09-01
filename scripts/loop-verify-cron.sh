#!/usr/bin/env bash
# Loop verify automático para LucidFence
# Ejecutado por cron cada hora. Detecta zombies, ejecuta verify, registra en loop-log.

set -e
cd /Users/adri/lucidfence

LOGFILE="docs/internal/loop-run-log.md"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
PY=/Users/adri/lucidfence/.venv/bin/python
PUERTO_TEST=8799

# --- Health-check: detectar y limpiar zombies en puerto de tests ---
ZOMBIE_PIDS=$(lsof -t -i :$PUERTO_TEST 2>/dev/null | tr '\n' ' ' || true)
if [ -n "$ZOMBIE_PIDS" ]; then
    for pid in $ZOMBIE_PIDS; do
        kill -9 "$pid" 2>/dev/null || true
    done
    sleep 1
    ZOMBIE_PIDS_AFTER=$(lsof -t -i :$PUERTO_TEST 2>/dev/null | tr '\n' ' ' || true)
    if [ -n "$ZOMBIE_PIDS_AFTER" ]; then
        ZOMBIE_STATUS="FALLIDO: puerto sigue ocupado"
    else
        ZOMBIE_STATUS="LIMPIADO: $ZOMBIE_PIDS matados"
    fi
    echo "- $TIMESTAMP | L2 | Health-check zombie | Puerto $PUERTO_TEST: $ZOMBIE_PIDS detectados → kill -9. Resultado: $ZOMBIE_STATUS" >> "$LOGFILE"
else
    ZOMBIE_STATUS="OK: puerto libre"
fi

# --- Ejecutar verify ---
OUTPUT=$($PY scripts/verify.py 2>&1) || true

if echo "$OUTPUT" | grep -q "APTO (4/4 checks)"; then
    STATUS="APTO"
elif echo "$OUTPUT" | grep -q "FALLO"; then
    STATUS="FALLO"
else
    STATUS="UNKNOWN"
fi

RUNTIME_LINE=$(echo "$OUTPUT" | grep "Batería runtime" | head -1 | sed 's/^[[:space:]]*//' || echo "sin datos")
SUITE_LINE=$(echo "$OUTPUT" | grep "Suite honesta:" | head -1 | sed 's/^[[:space:]]*//' || echo "sin datos")
DOCS_LINE=$(echo "$OUTPUT" | grep "Enlaces de docs" | head -1 | sed 's/^[[:space:]]*//' || echo "sin datos")

echo "- $TIMESTAMP | L2 | Loop verify (cron) | verify.py: $STATUS | Runtime: $RUNTIME_LINE. Suite honesta: $SUITE_LINE. Docs: $DOCS_LINE. $ZOMBIE_STATUS" >> "$LOGFILE"

echo "[$TIMESTAMP] Loop verify: $STATUS ($ZOMBIE_STATUS)"
