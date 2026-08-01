#!/usr/bin/env bash
# LucidFence pre-commit: frena regresiones tontas antes de commitear.
# Native git hook, sin dependencias. Ponytail: lo mínimo que falla si el
# dashboard o el backend se rompen localmente.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
fail=0

# 1) Sintaxis JS: si app.js/i18n.js cambian, deben parsear.
for f in static/app.js static/i18n.js; do
  if git diff --cached --name-only | grep -qx "$f" && command -v node >/dev/null 2>&1; then
    if ! node --check "$ROOT/$f"; then
      echo "ABORT: $f tiene error de sintaxis (node --check falló)" >&2
      fail=1
    fi
  fi
done

# 2) SBOM: sin comprobación. Es un artefacto de build que genera CI
# (dependency-audit → upload-artifact); no vive en git (issue #74).

# 3) Secret scan local (best-effort, no bloquea si gitleaks no está).
if command -v gitleaks >/dev/null 2>&1; then
  if ! gitleaks git --staged --redact --no-banner --exit-code 1 . >/dev/null 2>&1; then
    echo "ABORT: gitleaks detectó un secreto en los archivos staged" >&2
    fail=1
  fi
fi

if [ "$fail" -ne 0 ]; then
  echo "pre-commit bloqueó el commit. Corrige y reintenta." >&2
  exit 1
fi
exit 0
