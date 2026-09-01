#!/usr/bin/env bash
# Loop verify + skill discovery combinados
# Ejecutado por cron cada hora: verify + skill discovery + registro

set -e
cd /Users/adri/lucidfence

LOGFILE="docs/internal/loop-run-log.md"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
PY=/Users/adri/lucidfence/.venv/bin/python
PUERTO_TEST=8799

# --- Health-check zombie ---
ZOMBIE_PIDS=$(lsof -t -i :$PUERTO_TEST 2>/dev/null | tr '\n' ' ' || true)
if [ -n "$ZOMBIE_PIDS" ]; then
    for pid in $ZOMBIE_PIDS; do
        kill -9 "$pid" 2>/dev/null || true
    done
    sleep 1
    ZOMBIE_STATUS="LIMPIADO: $ZOMBIE_PIDS"
else
    ZOMBIE_STATUS="OK: puerto libre"
fi

# --- Verify ---
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

# --- Skill discovery ---
if [ -f "scripts/agent_skill_discovery.py" ]; then
    SKILL_OUTPUT=$($PY scripts/agent_skill_discovery.py 2>&1) || true
    SKILL_LINE=$(echo "$SKILL_OUTPUT" | grep "AGENTE AUTOMEJORA EJECUTADO" | head -1 | sed 's/.*\(capacidades\|skills\).*/\1/')
    if [ -n "$SKILL_LINE" ]; then
        echo "- $TIMESTAMP | L2 | Skill discovery (automejora) | Feed @HermesWatcher consultado + skills detectados | $SKILL_LINE" >> "$LOGFILE"
    fi
fi

echo "[$TIMESTAMP] Loop completado: verify=$STATUS, skill-discovery=OK, $ZOMBIE_STATUS"
