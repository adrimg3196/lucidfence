#!/usr/bin/env python3
"""Regenera los 3 clips FLUX 3 con prompts de ALTA CALIDAD (formula FLUX:
subject+action+style+context+lighting+technical, hex colors, lighting especifico,
sin negativos) siguiendo la habilidad flux-best-practices de OpenMontage."""
import json, time, urllib.request, os

BASE = "https://tool-gateway.nousresearch.com/api/bfl"
AUTH = json.load(open(os.path.expanduser("~/.hermes/shared/nous_auth.json")))["access_token"]
OUT = os.path.dirname(os.path.abspath(__file__))

def _req(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {AUTH}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())

def get_url(id_):
    for _ in range(150):
        j = _req("GET", f"{BASE}/generations/{id_}")
        st = j.get("status")
        if st in ("Ready", "ready", "completed"):
            res = j.get("result") or {}
            vid = res.get("sample") or res.get("video_url") or res.get("url") or (res.get("samples") or [None])[0]
            if not vid: raise SystemExit(f"sin URL {id_}: {j}")
            return vid
        if st in ("failed", "error", "refused"):
            raise SystemExit(f"FALLO {id_}: {j}")
        time.sleep(5)
    raise SystemExit(f"TIMEOUT {id_}")

def download(vid, path):
    with urllib.request.urlopen(vid, timeout=180) as r, open(path, "wb") as f:
        f.write(r.read())

def submit(mode, prompt, seed, input_video=None):
    body = {"mode": mode, "prompt": prompt, "seed": seed}
    if input_video: body["input_video"] = input_video
    return _req("POST", f"{BASE}/generations", body)["id"]

CLIP1 = ("A cinematic product film coming to life: a sleek matte-black smartphone, a thin "
 "tablet and a closed laptop resting on a minimalist desk of brushed dark metal, inside a dim "
 "executive office at night. Around the devices, a translucent perimeter of glowing hexagonal "
 "nodes linked by hair-thin mint #49d59c lines forms a living fence that slowly rotates. A soft "
 "violet #7c82ff pulse of light travels clockwise along the fence like a radar sweep. Dramatic "
 "single-source rim light from a hidden violet LED strip on the left, deep shadows, shallow "
 "depth of field, 35mm anamorphic lens, cinematic bloom, photorealistic, hyper-detailed, "
 "Kodak Vision3 500T color science.")
CLIP2 = ("Continuing from the final frame: same dim executive office, same desk with the "
 "smartphone tablet and laptop inside the mint #49d59c hexagonal fence, same violet #7c82ff radar "
 "pulse. A small additional device node drifts in from the right edge of frame and crosses outside "
 "the perimeter; it ignites in warning red #ff737e and the violet pulse isolates it with an "
 "expanding thin ring of light. Camera slowly tilts upward, 35mm anamorphic, shallow depth of "
 "field, dramatic rim light, cinematic bloom, photorealistic, Kodak Vision3 500T.")
CLIP3 = ("Continuing from the final frame: the red #ff737e out-of-compliance node is now enclosed "
 "by a calm violet #7c82ff quarantine ring; the rest of the hexagonal perimeter settles to "
 "tranquil mint #49d59c. Camera pulls back revealing the whole fence as a gentle glowing halo "
 "around the devices, then dissolves into the near-black background #090b0f. 35mm anamorphic, "
 "shallow depth of field, cinematic bloom, photorealistic, Kodak Vision3 500T.")

c1 = submit("text_to_video", CLIP1, 882311)
print("clip1", c1, flush=True)
u1 = get_url(c1); download(u1, f"{OUT}/clip1.mp4"); print("clip1.mp4 listo", flush=True)

c2 = submit("video_continuation", CLIP2, 882312, u1)
print("clip2", c2, flush=True)
u2 = get_url(c2); download(u2, f"{OUT}/clip2.mp4"); print("clip2.mp4 listo", flush=True)

c3 = submit("video_continuation", CLIP3, 882313, u2)
print("clip3", c3, flush=True)
u3 = get_url(c3); download(u3, f"{OUT}/clip3.mp4"); print("clip3.mp4 listo", flush=True)
print("DONE")
