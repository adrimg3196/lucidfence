#!/usr/bin/env bash
# Compila (si hace falta) y ejecuta la batería runtime contra el binario real.
set -euo pipefail
cd "$(dirname "$0")/.."
bin="${1:-bin/lucidfence}"
[ -x "$bin" ] || CGO_ENABLED=0 go build -trimpath -o "$bin" ./cmd/lucidfence
go run ./cmd/battery -bin "$bin"
