#!/usr/bin/env python3
"""Genera 4 clips FLUX 3 (enfoque anuncio YC LucidFence) con la habilidad
flux-best-practices: formula subject+action+style+context+lighting+technical,
hex colors, lighting especifico, sin negativos. One-take continuo."""
import json, time, urllib.request, os
BASE = "https://tool-gateway.nousresearch.com/api/bfl"
AUTH = json.load(open(os.path.expanduser("~/.hermes/shared/nous_auth.json")))["access_token"]
OUT = os.path.dirname(os.path.abspath(__file__))

def _req(m, u, b=None):
    d = json.dumps(b).encode() if b is not None else None
    r = urllib.request.Request(u, data=d, method=m)
    r.add_header("Authorization", f"Bearer {AUTH}")
    if d: r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=180) as x: return json.loads(x.read())

def url(id_):
    for _ in range(150):
        j = _req("GET", f"{BASE}/generations/{id_}")
        if j.get("status") in ("Ready","ready","completed"):
            res = j.get("result") or {}
            v = res.get("sample") or res.get("video_url") or res.get("url") or (res.get("samples") or [None])[0]
            if not v: raise SystemExit(f"sin URL {id_}")
            return v
        if j.get("status") in ("failed","error","refused"): raise SystemExit(f"FALLO {id_}: {j}")
        time.sleep(5)
    raise SystemExit(f"TIMEOUT {id_}")

def dl(v, p):
    with urllib.request.urlopen(v, timeout=180) as x, open(p,"wb") as f: f.write(x.read())

def submit(mode, prompt, seed, inp=None):
    b = {"mode": mode, "prompt": prompt, "seed": seed}
    if inp: b["input_video"] = inp
    return _req("POST", f"{BASE}/generations", b)["id"]

C1 = ("A cinematic product film: a sleek matte-black smartphone, a thin tablet and a closed "
 "laptop resting on a minimalist desk of brushed dark metal in a dim executive office at night. "
 "Each device slowly emits a soft calm mint #49d59c halo of light, suggesting protection and "
 "safety. Dramatic single-source rim light from a hidden violet #7c82ff LED strip on the left, "
 "deep shadows, shallow depth of field, 35mm anamorphic lens, cinematic bloom, photorealistic, "
 "hyper-detailed, Kodak Vision3 500T color science.")
C2 = ("Continuing from the final frame: same dim executive office, same desk with the smartphone "
 "tablet and laptop glowing calm mint #49d59c. One small additional device node drifts in from "
 "the right and separates from the group; its halo flickers and turns warning red #ff737e. A thin "
 "violet #7c82ff perimeter line draws itself around the trusted devices, visually separating "
 "safe from untrusted. Camera slowly tilts upward, 35mm anamorphic, shallow depth of field, "
 "cinematic bloom, photorealistic, Kodak Vision3 500T.")
C3 = ("Continuing from the final frame: an abstract console made of light appears in the same dark "
 "space. Five hexagonal nodes glow into existence and connect one by one with a soft violet "
 "#7c82ff chime of light, forming one unified luminous fence that wraps the devices: this is "
 "Applivery, Intune, Jamf, Hexnode and Fleetsmith joined as one perimeter. Gentle push-in, 35mm "
 "anamorphic, cinematic bloom, photorealistic product-graphic hybrid, Kodak Vision3 500T.")
C4 = ("Continuing from the final frame: the unified fence dissolves and particles of violet "
 "#7c82ff and mint #49d59c light converge to form a clean shield emblem on near-black #090b0f "
 "background; the emblem settles with a calm glow. Restrained and triumphant, 35mm anamorphic, "
 "cinematic bloom, photorealistic, Kodak Vision3 500T.")

c1 = submit("text_to_video", C1, 771231); print("clip1", c1, flush=True)
u1 = url(c1); dl(u1, f"{OUT}/v1.mp4"); print("v1.mp4", flush=True)
c2 = submit("video_continuation", C2, 771232, u1); print("clip2", c2, flush=True)
u2 = url(c2); dl(u2, f"{OUT}/v2.mp4"); print("v2.mp4", flush=True)
c3 = submit("video_continuation", C3, 771233, u2); print("clip3", c3, flush=True)
u3 = url(c3); dl(u3, f"{OUT}/v3.mp4"); print("v3.mp4", flush=True)
c4 = submit("video_continuation", C4, 771234, u3); print("clip4", c4, flush=True)
u4 = url(c4); dl(u4, f"{OUT}/v4.mp4"); print("v4.mp4 DONE", flush=True)
