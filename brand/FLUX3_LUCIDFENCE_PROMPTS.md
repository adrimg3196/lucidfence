# LucidFence · Brand pack para FLUX 3 (OpenMontage / fal.ai)

Paleta oficial (de `static/web.html`):
- violet `#7c82ff` / violet profundo `#5c62e8`
- mint `#49d59c` (compliance/salud)
- amber `#f0bc5e` · red `#ff737e` (riesgo/fuera)
- blue `#65b5ff`
- fondo `#090b0f` · panel `#12161d` · tinta `#f5f7fa`
- Tipografía: Inter. Sin texto legible ni logos dentro de los frames (FLUX los deforma).

Regla de marca: el logo LucidFence (escudo con check) NUNCA se genera dentro de FLUX.
Va como overlay post en ffmpeg, nunca en los frames.

====================================================================
# 1) IMAGEN DE MARCA (poster / key visual)
====================================================================

Prompt FLUX 3 (text-to-image, 16:9, estilo "Apple moderno + seguridad"):

A cinematic product brand visual for "LucidFence", a geofencing + UEM security
platform. Dark studio background #090b0f with a soft volumetric violet glow
#7c82ff at the edges. Center: an abstract translucent fence of glowing hex
nodes connected by thin mint #49d59c lines forming a perimeter around a cluster
of device silhouettes (phone, tablet, laptop) that are calm and inside the
perimeter. One node outside the fence glows red #ff737e with a subtle pulse,
signaling a device out of compliance. A faint violet pulse of light travels
along the fence like a living radar. Shallow depth of field, 35mm anamorphic
lens, photorealistic, high contrast, premium SaaS aesthetic, no text, no logos,
no readable words, bokeh, cinematic lighting, 8k detail.

Negativo / notas: no UI screenshots, no fake logos, no text, no watermark.

Variaciones (cambiar solo el foco):
- VARIACIÓN A (trust): misma escena pero la luz mint domina, todos los nodos
  dentro del perímetro, tono "compliance total".
- VARIACIÓN B (threat): un nodo red fuera, un rayo violeta lo aísla, tono
  "respuesta automática".

====================================================================
# 2) VIDEO SPOT (one-take, FLUX 3 text-to-video + continuation)
====================================================================

Técnica (OpenMontage / skill): un solo plano secuencia, cámara con movimiento,
"pulso violeta" como puente de continuidad entre clips. 720p/24fps, audio off,
seed fijo por clip.

CLIP 1 (text_to_video) — seed 882311:
A continuous one-take cinematic shot for LucidFence geofencing security SaaS.
Camera slowly pushes in through a dark modern office at night; on a desk sit a
phone, a tablet and a laptop, their screens faintly glowing. Around them, a
translucent fence of glowing hex nodes linked by thin mint #49d59c lines forms
a living perimeter. A soft violet #7c82ff pulse of light travels along the
fence like radar. 35mm anamorphic lens, shallow depth of field, photorealistic
premium SaaS look, no text, no logos, no readable words, cinematic.

CLIP 2 (video_continuation) — seed 882312:
Continue this video from its final frames: same desk, same devices, same
fence of hex nodes, same violet radar pulse. A new device node appears at the
edge and drifts outside the perimeter; it glows red #ff737e and the violet
pulse isolates it with a thin ring of light. The camera tilts up slightly.
Keep the same anamorphic lens and lighting, no text, no logos.

CLIP 3 (video_continuation) — seed 882313:
Continue this video from its final frames: the red out-of-compliance node is
now enclosed by a violet quarantine ring; the rest of the perimeter settles to
calm mint #49d59c. Camera pulls back to reveal the whole fence as a gentle
glowing halo around the devices, then fades to the dark background #090b0f.
Same lens, no text, no logos.

====================================================================
# 3) POST / MONTAXE (ffmpeg, estilo OpenMontage)
====================================================================

Concat de los 3 clips + overlay del logo oficial (lucidfence-icon.svg exportado
a PNG con aire, wordmark horizontal) con fade-in al final + score continuo.

  ffmpeg -i clip1.mp4 -i clip2.mp4 -i clip3.mp4 \
    -filter_complex "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]; \
      [v]overlay=W-w-40:H-h-40:enable='gte(t,12)':alpha=0.9[out]" \
    -map "[out]" -c:v libx264 -pix_fmt yuv420p -r 24 lucidfence_spot.mp4

Logo: SVG oficial en /Users/adri/geofence-uem/static/lucidfence-icon.svg
(usar make_assets_brandkit.py del skill para PNG con assert de geometría).

====================================================================
# 4) CÓMO EJECUTARLO (lo que falta en este entorno)
====================================================================

El toolset `bfl` (bfl_flux3_*) NO está cargado aquí: falta la API key.
Para activarlo: pon en /Users/adri/.hermes/.env  FAL_KEY=<tu_key_de_fal.ai>
o conecta el MCP de Black Forest Labs, reinicia Hermes, y las tools
bfl_flux3_text_to_image / bfl_flux3_text_to_video / bfl_flux3_video_continuation
aparecerán. Entonces se ejecuta este pack directamente.
