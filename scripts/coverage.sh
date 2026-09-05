#!/usr/bin/env bash
# Suelos de cobertura por paquete (spec §9.1 paso 4): domain y engine 85 %,
# resto 70 %, cmd/battery exento. Falla si algún paquete queda por debajo o
# no tiene tests.
set -euo pipefail
cd "$(dirname "$0")/.."
go test -race -count=1 -covermode=atomic -coverprofile=coverage.out ./... | tee test.out
status=0
while IFS= read -r line; do
  pkg=$(awk '{print $2}' <<<"$line")
  case "$pkg" in
    */cmd/battery) continue ;;
    */internal/domain/*|*/internal/domain|*/internal/engine|*/internal/engine/*) floor=85 ;;
    *) floor=70 ;;
  esac
  if grep -q '\[no statements\]' <<<"$line"; then continue; fi
  if grep -q '\[no test files\]' <<<"$line"; then
    echo "COVERAGE: $pkg sin tests (mínimo $floor%)"; status=1; continue
  fi
  pct=$(grep -oE 'coverage: [0-9.]+%' <<<"$line" | grep -oE '[0-9.]+' || echo 0)
  if awk -v p="$pct" -v f="$floor" 'BEGIN{exit !(p+0 < f)}'; then
    echo "COVERAGE: $pkg ${pct}% < ${floor}%"; status=1
  fi
done < <(grep -E '^(ok|\?)\s' test.out)
[ "$status" -eq 0 ] && echo "COVERAGE: OK"
exit "$status"
