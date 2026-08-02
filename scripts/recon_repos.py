#!/usr/bin/env python3
"""Recon de repos GitHub: competidores UEM/MDM + tools de video.
Devuelve minimo 3 repos diversos como inspiracion para el video de LucidFence.
Usa GitHub API publica (sin auth, rate limit 60/h, suficiente para pocas queries)."""
import json, urllib.request, urllib.parse, sys, os

# reusa la busqueda social de agent-reach (X via twscrape, Reddit via auth)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from recon_web import social_pulse
except Exception:
    social_pulse = None

QUERIES = [
    "UEM MDM mobile device management",
    "geofencing device compliance",
    "video marketing generator react",
    "remotion video template",
    "competitor analysis dashboard saas",
]
# clasifica el angulo de cada repo por keywords (inspirado en LakshmanRekha=geofence, UEM/MDM, video)
ANGLES = {
    "geofence": ["geofenc", "geofence", "perimeter", "boundary", "location"],
    "uem_mdm": ["uem", "mdm", "device management", "mobile device", "endpoint"],
    "video": ["video", "remotion", "short-form", "marketing", "script", "content"],
}

def classify(desc, name):
    text = (desc + " " + name).lower()
    for angle, kws in ANGLES.items():
        if any(k in text for k in kws):
            return angle
    return "other"

seen = set()
repos = []
for q in QUERIES:
    url = "https://api.github.com/search/repositories?q=" + urllib.parse.quote(q) + "&sort=stars&order=desc&per_page=5"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lucidfence-recon"})
        data = json.load(urllib.request.urlopen(req, timeout=15))
    except Exception as e:
        continue
    for r in data.get("items", []):
        full = r["full_name"]
        if full in seen:
            continue
        seen.add(full)
        repos.append((full, r["stargazers_count"], r.get("description") or "", r["html_url"], r.get("language") or "", classify(r.get("description") or "", full)))
    # corta cuando tengamos 3 orgs distintos y al menos 6 candidatos
    if len(repos) >= 6:
        break

print("=== RECON REPOS (GitHub) — inspiracion video LucidFence ===\n")
for i, (name, stars, desc, url, lang, angle) in enumerate(repos[:6], 1):
    print(f"{i}. {name}  ★{stars}  [{lang}] #{angle}")
    print(f"   {desc}")
    print(f"   {url}\n")
print(f"Total referencias traidas: {len(repos)} (minimo 3)")
# pulso social via agent-reach (X/Reddit) con los mismos angulos
if social_pulse:
    print("\n=== PULSO SOCIAL (agent-reach: X + Reddit) ===")
    print(social_pulse(QUERIES[:4]))
