#!/usr/bin/env python3
"""Continua generacion YC desde v2 (clip3 y clip4) con prompts SIN marcas
(evita 'Request Moderated' del moderador BFL)."""
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
        if j.get("status") in ("failed","error","refused","Request Moderated"):
            raise SystemExit(f"FALLO {id_}: {j.get('status')}")
        time.sleep(5)
    raise SystemExit(f"TIMEOUT {id_}")

def dl(v, p):
    with urllib.request.urlopen(v, timeout=180) as x, open(p,"wb") as f: f.write(x.read())

def submit(mode, prompt, seed, inp=None):
    b = {"mode": mode, "prompt": prompt, "seed": seed}
    if inp: b["input_video"] = inp
    return _req("POST", f"{BASE}/generations", b)["id"]

C3 = ("Continuing from the final frame: an abstract console made of light appears in the same dark "
 "space. Five hexagonal nodes for different device-management platforms glow into existence and "
 "connect one by one with a soft violet #7c82ff chime of light, forming one unified luminous fence "
 "that wraps the devices. Gentle push-in, 35mm anamorphic, cinematic bloom, photorealistic "
 "product-graphic hybrid, Kodak Vision3 500T.")
C4 = ("Continuing from the final frame: the unified fence dissolves and particles of violet #7c82ff "
 "and mint #49d59c light converge to form a clean shield emblem on near-black #090b0f background; "
 "the emblem settles with a calm glow. Restrained and triumphant, 35mm anamorphic, cinematic bloom, "
 "photorealistic, Kodak Vision3 500T.")

u2 = f"{OUT}/v2.mp4"
c3 = submit("text_to_video", C3, 771233); print("clip3", c3, flush=True)
u3 = url(c3); dl(u3, f"{OUT}/v3.mp4"); print("v3.mp4", flush=True)
c4 = submit("text_to_video", C4, 771234); print("clip4", c4, flush=True)
u4 = url(c4); dl(u4, f"{OUT}/v4.mp4"); print("v4.mp4 DONE", flush=True)
