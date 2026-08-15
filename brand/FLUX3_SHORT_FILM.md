# LucidFence · Short Film para concurso FLUX 3 (NousResearch × BFL)
Taggear: @NousResearch @bfl_ai  ·  deadline 7PM PT Aug 1

Concepto (15-20s, one-take): "El perímetro que piensa".
Una oficina de noche, dispositivos en calma dentro de una cerca viva de luz,
y un intruso que cruza la línea y es aislado en cuestión de segundos.
Sin texto, sin logos en los frames (overlay post con el escudo LucidFence).

Paleta: violeta #7c82ff / #5c62e8, mint #49d59c (calma), red #ff737e (alarma).
Fondo #090b0f. Lente 35mm anamórfico, DOF, look Apple moderno + seguridad.

CLIP 1 (bfl_flux3_text_to_video, seed 882311, 720p/24fps, audio off):
A continuous one-take cinematic shot for a geofencing security brand. Camera
slowly pushes through a dark modern office at night; on a desk sit a phone, a
tablet and a laptop with faintly glowing screens. Around them, a translucent
fence of glowing hex nodes linked by thin mint #49d59c lines forms a living
perimeter. A soft violet #7c82ff pulse of light travels along the fence like
radar. 35mm anamorphic lens, shallow depth of field, photorealistic premium
SaaS look, no text, no logos, no readable words, cinematic, 8k detail.

CLIP 2 (bfl_flux3_video_continuation, seed 882312):
Continue this video from its final frames: same desk, same devices, same fence
of hex nodes, same violet radar pulse. A new device node drifts in from the
edge and crosses outside the perimeter; it glows red #ff737e and the violet
pulse isolates it with a thin expanding ring of light. Camera tilts up
slightly. Same anamorphic lens and lighting, no text, no logos.

CLIP 3 (bfl_flux3_video_continuation, seed 882313):
Continue this video from its final frames: the red out-of-compliance node is
now enclosed by a violet quarantine ring; the rest of the perimeter settles to
calm mint #49d59c. Camera pulls back to reveal the whole fence as a gentle
glowing halo around the devices, then fades to the dark background #090b0f.
Same lens, no text, no logos.

POST (ffmpeg, build_spot.sh): concat 3 clips + overlay escudo LucidFence PNG
con fade-in final + score continuo. Logo NUNCA dentro de los frames.

Caption sugerido para X:
"LucidFence — the perimeter that thinks. Geofencing + UEM security, autonomous
and local-first. Made with FLUX 3 🎬 @NousResearch @bfl_ai #FLUX3"
