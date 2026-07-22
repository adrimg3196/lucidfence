#!/usr/bin/env bash
# Arranque local reproducible de LucidFence. No instala dependencias fuera de su venv.
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
VENV_DIR="${LUCIDFENCE_VENV:-$ROOT/.venv}"
VENV_PYTHON="$VENV_DIR/bin/python"

python_supported() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1
}

if [[ -x "$VENV_PYTHON" ]]; then
  if ! python_supported "$VENV_PYTHON"; then
    echo "ERROR: el venv existente requiere Python 3.11 o superior: $VENV_DIR" >&2
    echo "Elimínalo o define LUCIDFENCE_VENV con una ruta nueva." >&2
    exit 1
  fi
else
  BASE_PYTHON=""
  if [[ -n "${PYTHON:-}" ]]; then
    if python_supported "$PYTHON"; then
      BASE_PYTHON="$PYTHON"
    else
      echo "ERROR: PYTHON debe apuntar a Python 3.11 o superior." >&2
      exit 1
    fi
  else
    for candidate in python3.13 python3.12 python3.11 python3; do
      if command -v "$candidate" >/dev/null 2>&1 && python_supported "$candidate"; then
        BASE_PYTHON="$(command -v "$candidate")"
        break
      fi
    done
  fi
  if [[ -z "$BASE_PYTHON" ]]; then
    echo "ERROR: LucidFence requiere Python 3.11 o superior." >&2
    exit 1
  fi
  "$BASE_PYTHON" -m venv "$VENV_DIR"
fi

LOCK_HASH="$($VENV_PYTHON -c 'import hashlib, pathlib; print(hashlib.sha256(pathlib.Path("requirements.lock").read_bytes()).hexdigest())')"
LOCK_MARKER="$VENV_DIR/.lucidfence-requirements.sha256"
INSTALLED_HASH="$(cat "$LOCK_MARKER" 2>/dev/null || true)"
if [[ "$INSTALLED_HASH" != "$LOCK_HASH" ]]; then
  "$VENV_PYTHON" -m pip install \
    --disable-pip-version-check \
    --require-hashes \
    -r requirements.lock
  printf '%s\n' "$LOCK_HASH" > "$LOCK_MARKER.tmp"
  mv "$LOCK_MARKER.tmp" "$LOCK_MARKER"
fi
"$VENV_PYTHON" -m pip check >/dev/null

echo "Iniciando LucidFence local en http://127.0.0.1:8765 ..."
echo "Dashboard: http://127.0.0.1:8765"
exec "$VENV_PYTHON" saas_server.py
