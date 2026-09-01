#!/usr/bin/env bash
# Loop verify + skill discovery (Hugo) combinados
# Ejecutado por cron cada hora: verify + hugo skill-discovery + registro

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

# --- Hugo Skill Discovery (GitHub repos + @HermesWatcher) ---
if [ -f "scripts/hugo_skill_discovery.py" ]; then
    echo "[$TIMESTAMP] Ejecutando hugo_skill_discovery.py ..." >> "$LOGFILE"
    HUGO_OUTPUT=$($PY scripts/hugo_skill_discovery.py 2>&1) || true
    
    # Extraer métricas clave del output
    HUGO_POSTS=$(echo "$HUGO_OUTPUT" | grep "Posts encontrados:" | sed 's/.*: //')
    HUGO_SKILLS=$(echo "$HUGO_OUTPUT" | grep "Skills/capacidades detectadas:" | sed 's/.*: //')
    HUGO_RELEVANT=$(echo "$HUGO_OUTPUT" | grep "Skills relevantes:" | sed 's/.*: //')
    HUGO_INSTALLED=$(echo "$HUGO_OUTPUT" | grep "Skills instalados:" | sed 's/.*: //')
    HUGO_REPOS=$(echo "$HUGO_OUTPUT" | grep "Repos de GitHub detectados:" | sed 's/.*: //')
    HUGO_CLONED=$(echo "$HUGO_OUTPUT" | grep "Repos clonados" | sed 's/.*: //')
    HUGO_CAPS=$(echo "$HUGO_OUTPUT" | grep "Nuevas capacidades:" | sed 's/.*: //')
    
    echo "- $TIMESTAMP | L2 | Hugo skill discovery | Posts: $HUGO_POSTS | Skills detectadas: $HUGO_SKILLS | Relevantes: $HUGO_RELEVANT | Instaladas: $HUGO_INSTALLED | Cap.: $HUGO_CAPS | Repos GitHub: $HUGO_REPOS | Clonados: $HUGO_CLONED | Zombie: $ZOMBIE_STATUS" >> "$LOGFILE"
fi

echo "[$TIMESTAMP] Loop completado: verify=$STATUS, hugo-skill-discovery=OK, $ZOMBIE_STATUS"
