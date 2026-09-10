#!/usr/bin/env bash
# Compila (si hace falta) y ejecuta la batería runtime contra el binario real.
set -euo pipefail
cd "$(dirname "$0")/.."
bin="${1:-bin/lucidfence}"
[ -x "$bin" ] || CGO_ENABLED=0 go build -trimpath -o "$bin" ./cmd/lucidfence
# M2 añade entregas de webhook reales (aunque locales) con hasta 10 s de
# sondeo cada una si algo va mal; se sube el presupuesto total de 3 a 5 min.
go run ./cmd/battery -bin "$bin" -timeout 5m
