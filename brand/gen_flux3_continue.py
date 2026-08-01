#!/usr/bin/env python3
"""Genera el short film LucidFence con FLUX 3 vía gateway Nous (tool-gateway).
clip1 ya enviado (text_to_video). Descarga y encadena clip2/3 (video_continuation)
usando la URL del clip anterior como input_video. Seeds fijos.
"""
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
    for _ in range(120):
        j = _req("GET", f"{BASE}/generations/{id_}")
        st = j.get("status")
        if st in ("Ready", "ready", "completed"):
            res = j.get("result") or {}
            vid = res.get("sample") or res.get("video_url") or res.get("url")
            if not vid:
                vid = (res.get("samples") or [None])[0]
            return vid, j
        if st in ("failed", "error", "refused"):
            raise SystemExit(f"FALLO {id_}: {j}")
        time.sleep(5)
    raise SystemExit(f"TIMEOUT {id_}")

def download(vid_url, path):
    with urllib.request.urlopen(vid_url, timeout=180) as r, open(path, "wb") as f:
        f.write(r.read())

def submit_cont(mode, prompt, seed, input_video):
    body = {"mode": mode, "prompt": prompt, "seed": seed, "input_video": input_video}
    return _req("POST", f"{BASE}/generations", body)["id"]

CLIP2 = ("Continue this video from its final frames: same desk, same devices, same fence of "
 "hex nodes, same violet radar pulse. A new device node drifts in from the edge and crosses "
 "outside the perimeter; it glows red and the violet pulse isolates it with a thin expanding "
 "ring of light. Camera tilts up slightly. Same anamorphic lens and lighting, no text, no logos.")
CLIP3 = ("Continue this video from its final frames: the red out-of-compliance node is now "
 "enclosed by a violet quarantine ring; the rest of the perimeter settles to calm mint. Camera "
 "pulls back to reveal the whole fence as a gentle glowing halo around the devices, then fades "
 "to the dark background. Same lens, no text, no logos.")

# clip1 ya Ready
c1_id = "bfl_job_e0cae604c17dc98f74c5af32dd9a97ac"
print("clip1 downloading...", flush=True)
url1, _ = get_url(c1_id)
download(url1, f"{OUT}/clip1.mp4")
print("clip1.mp4 listo", flush=True)

c2 = submit_cont("video_continuation", CLIP2, 882312, url1)
print("clip2", c2, flush=True)
url2, _ = get_url(c2)
download(url2, f"{OUT}/clip2.mp4")
print("clip2.mp4 listo", flush=True)

c3 = submit_cont("video_continuation", CLIP3, 882313, url2)
print("clip3", c3, flush=True)
url3, _ = get_url(c3)
download(url3, f"{OUT}/clip3.mp4")
print("clip3.mp4 listo", flush=True)
print("DONE")
