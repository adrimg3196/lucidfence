#!/usr/bin/env bash
# Monta el short film LucidFence estilo OpenMontage (narrativa + branding):
# title(2s) xfade clip1 xfade clip2 xfade clip3 xfade endcard(2s), 24fps.
set -euo pipefail
cd "$(dirname "$0")"
FPS=24
# imagenes a video 2s
ffmpeg -y -loop 1 -i title.png -t 2 -r $FPS -c:v libx264 -pix_fmt yuv420p -vf "scale=1280:704" title_v.mp4
ffmpeg -y -loop 1 -i endcard.png -t 2 -r $FPS -c:v libx264 -pix_fmt yuv420p -vf "scale=1280:704" endcard_v.mp4
# normaliza audio de clips (silencio si no hay)
for c in clip1 clip2 clip3; do
  ffmpeg -y -i $c.mp4 -an -c:v copy ${c}_v.mp4
done
# xfade en cadena (0.5s crossfade)
ffmpeg -y -i title_v.mp4 -i clip1_v.mp4 -filter_complex "[0][1]xfade=transition=fade:duration=0.5:offset=1.5[v]" x01.mp4
ffmpeg -y -i x01.mp4 -i clip2_v.mp4 -filter_complex "[0][1]xfade=transition=fade:duration=0.5:offset=11[v]" x02.mp4
ffmpeg -y -i x02.mp4 -i clip3_v.mp4 -filter_complex "[0][1]xfade=transition=fade:duration=0.5:offset=21[v]" x03.mp4
ffmpeg -y -i x03.mp4 -i endcard_v.mp4 -filter_complex "[0][1]xfade=transition=fade:duration=0.5:offset=30.5[v]" lucidfence_spot.mp4
# QA
ffmpeg -v error -i lucidfence_spot.mp4 -f null - && echo "QA OK -> lucidfence_spot.mp4" || { echo "QA FAIL"; exit 1; }
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 lucidfence_spot.mp4
