#!/bin/bash
# quality_gate.sh — gate de calidad en tiempo de escritura para la flota.
# Adaptado de alexfazio/plankton (multi_linter.sh, MIT) al tamaño de este
# repo: solo Python, solo señal real (sintaxis + ruff F/E9 con .ruff.toml),
# stdlib para parsear el JSON del hook (sin jaq), fail-open si falta ruff.
#
# PostToolUse (Edit|Write): exit 2 devuelve los hallazgos al agente para que
# los arregle antes de seguir; exit 0 = limpio o no aplica.
set -uo pipefail

payload=$(cat)
file=$(printf '%s' "$payload" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    pass
" 2>/dev/null)

case "$file" in
  *.py) [[ -f "$file" ]] || exit 0 ;;
  *) exit 0 ;;
esac

# 1) Sintaxis: un fichero que no compila nunca debe quedarse escrito en silencio.
if ! err=$(python3 -m py_compile "$file" 2>&1); then
  echo "quality_gate: $file no compila:" >&2
  echo "$err" >&2
  exit 2
fi

# 2) ruff (config del repo: solo F/E9, estilo de la casa exento). Fail-open.
if command -v ruff >/dev/null 2>&1; then
  if ! out=$(ruff check "$file" 2>&1); then
    echo "quality_gate (ruff F/E9): arregla esto antes de seguir:" >&2
    echo "$out" >&2
    exit 2
  fi
fi
exit 0
