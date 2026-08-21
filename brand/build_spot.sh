#!/usr/bin/env bash
# Monta el spot LucidFence a partir de 3 clips FLUX 3 + overlay del logo oficial.
# Uso: bash brand/build_spot.sh clip1.mp4 clip2.mp4 clip3.mp4
# Requiere ffmpeg y el logo PNG en brand/logo_overlay.png (generado por make_assets_brandkit.py).
set -euo pipefail
[ $# -lt 3 ] && { echo "Uso: $0 clip1 clip2 clip3"; exit 1; }
OUT="lucidfence_spot.mp4"
LOGO="brand/logo_overlay.png"
if [ -f "$LOGO" ]; then
  ffmpeg -y -i "$1" -i "$2" -i "$3" -i "$LOGO" \
    -filter_complex "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]; \
      [v][3]overlay=W-w-40:H-h-40:enable='gte(t,12)':alpha=0.9[out]" \
    -map "[out]" -c:v libx264 -pix_fmt yuv420p -r 24 "$OUT"
else
  ffmpeg -y -i "$1" -i "$2" -i "$3" \
    -filter_complex "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]" \
    -map "[v]" -c:v libx264 -pix_fmt yuv420p -r 24 "$OUT"
fi
# QA técnica fail-closed
ffmpeg -v error -i "$OUT" -f null - && echo "QA decode OK -> $OUT" || { echo "QA FAIL"; exit 1; }
