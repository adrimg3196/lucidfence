#!/usr/bin/env python3
"""Genera el short film LucidFence con FLUX 3 vía gateway Nous (tool-gateway).
Un solo plano secuencia: clip1 text_to_video + clip2/3 video_continuation.
Seeds fijos para reproducibilidad. Sin logos/texto en frames (overlay post).
"""
import json, time, urllib.request, urllib.error, sys, os

BASE = "https://tool-gateway.nousresearch.com/api/bfl"
AUTH = json.load(open(os.path.expanduser("~/.hermes/shared/nous_auth.json")))["access_token"]
OUT = os.path.dirname(os.path.abspath(__file__))

def _req(method, url, body=None, binary=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {AUTH}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read()
    return raw if binary else json.loads(raw)

def submit(mode, prompt, seed, input_video=None):
    body = {"mode": mode, "prompt": prompt, "seed": seed}
    if input_video:
        body["input_video"] = input_video
    return _req("POST", f"{BASE}/generations", body)["id"]

def poll(id_, out_path):
    url = f"{BASE}/generations/{id_}"
    for _ in range(120):  # ~10 min a 5s
        j = _req("GET", url)
        st = j.get("status")
        if st in ("Ready", "ready", "completed"):
            res = j.get("result") or {}
            vid = res.get("sample") or res.get("video_url") or res.get("url")
            if not vid and isinstance(res, dict):
                vid = (res.get("samples") or [None])[0]
            if not vid:
                raise SystemExit(f"sin URL en {id_}: {j}")
            with urllib.request.urlopen(vid, timeout=180) as r, open(out_path, "wb") as f:
                f.write(r.read())
            return out_path
        if st in ("failed", "error", "refused"):
            raise SystemExit(f"JOB FALLÓ: {j}")
        time.sleep(5)
    raise SystemExit(f"TIMEOUT esperando {id_}")

# Prompts (de FLUX3_SHORT_FILM.md)
CLIP1 = ("A continuous one-take cinematic shot for a geofencing security brand. Camera "
 "slowly pushes through a dark modern office at night; on a desk sit a phone, a tablet and "
 "a laptop with faintly glowing screens. Around them, a translucent fence of glowing hex "
 "nodes linked by thin mint lines forms a living perimeter. A soft violet pulse of light "
 "travels along the fence like radar. 35mm anamorphic lens, shallow depth of field, "
 "photorealistic premium SaaS look, no text, no logos, no readable words, cinematic.")
CLIP2 = ("Continue this video from its final frames: same desk, same devices, same fence of "
 "hex nodes, same violet radar pulse. A new device node drifts in from the edge and crosses "
 "outside the perimeter; it glows red and the violet pulse isolates it with a thin expanding "
 "ring of light. Camera tilts up slightly. Same anamorphic lens and lighting, no text, no logos.")
CLIP3 = ("Continue this video from its final frames: the red out-of-compliance node is now "
 "enclosed by a violet quarantine ring; the rest of the perimeter settles to calm mint. Camera "
 "pulls back to reveal the whole fence as a gentle glowing halo around the devices, then fades "
 "to the dark background. Same lens, no text, no logos.")

c1 = submit("text_to_video", CLIP1, 882311)
print("clip1", c1, flush=True)
p1 = poll(c1, f"{OUT}/clip1.mp4")
print("clip1 listo", p1, flush=True)

c2 = submit("video_continuation", CLIP2, 882312, input_video=p1)
print("clip2", c2, flush=True)
p2 = poll(c2, f"{OUT}/clip2.mp4")
print("clip2 listo", p2, flush=True)

c3 = submit("video_continuation", CLIP3, 882313, input_video=p2)
print("clip3", c3, flush=True)
p3 = poll(c3, f"{OUT}/clip3.mp4")
print("clip3 listo", p3, flush=True)
print("DONE")
