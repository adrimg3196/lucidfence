#!/usr/bin/env bash
# lint_workflows.sh — EL linter de los workflows. El mismo en local y en CI.
#
# Por qué existe: el gate de actionlint se introdujo validándolo en un
# contenedor SIN shellcheck. actionlint solo invoca shellcheck si lo encuentra
# en el PATH, así que se saltó en silencio los checks de shell y dio un "0
# hallazgos" falso — el gate estrenó rojo en CI con 9 hallazgos reales
# (2026-08-21, run 32455895540). La lección no es "acuérdate de instalar
# shellcheck": es que un verificador NUNCA debe poder decir verde porque le
# falte una herramienta.
#
# Este script fija ambas versiones, las instala si faltan, y ABORTA si no puede
# tenerlas. Nunca produce un verde silencioso.
#
# Uso:
#   bash scripts/lint_workflows.sh          # lint de .github/workflows
#   ACTIONLINT_CACHE=/ruta bash scripts/... # dónde cachear los binarios
set -euo pipefail

ACTIONLINT_VERSION="1.7.7"
SHELLCHECK_VERSION="0.10.0"
CACHE="${ACTIONLINT_CACHE:-${RUNNER_TEMP:-/tmp}/lucidfence-workflow-lint}"
mkdir -p "$CACHE"

need() { command -v "$1" >/dev/null 2>&1; }

if ! need actionlint; then
  if [ ! -x "$CACHE/actionlint" ]; then
    echo "· descargando actionlint v${ACTIONLINT_VERSION}"
    curl -fsSL -o "$CACHE/al.tar.gz" \
      "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_amd64.tar.gz"
    tar -C "$CACHE" -xzf "$CACHE/al.tar.gz" actionlint
  fi
  PATH="$CACHE:$PATH"
fi

if ! need shellcheck; then
  if [ ! -x "$CACHE/shellcheck" ]; then
    echo "· descargando shellcheck v${SHELLCHECK_VERSION}"
    curl -fsSL -o "$CACHE/sc.tar.xz" \
      "https://github.com/koalaman/shellcheck/releases/download/v${SHELLCHECK_VERSION}/shellcheck-v${SHELLCHECK_VERSION}.linux.x86_64.tar.xz"
    tar -C "$CACHE" -xJf "$CACHE/sc.tar.xz" --strip-components=1 \
      "shellcheck-v${SHELLCHECK_VERSION}/shellcheck"
  fi
  PATH="$CACHE:$PATH"
fi
export PATH

# El guardarraíl que faltaba: sin las DOS herramientas no se lintea, se aborta.
# Un lint incompleto que dice "0 hallazgos" es peor que no linter.
for tool in actionlint shellcheck; do
  if ! need "$tool"; then
    echo "::error::$tool no disponible y no se pudo instalar — lint ABORTADO." >&2
    echo "Sin $tool el resultado seria un falso verde. Instalalo y reintenta." >&2
    exit 2
  fi
done

echo "· actionlint $(actionlint --version | head -1) + shellcheck $(shellcheck --version | awk '/^version:/{print $2}')"
actionlint -color
echo "OK: workflows limpios (YAML, expresiones y shell)."
