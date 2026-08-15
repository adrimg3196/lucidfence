#!/usr/bin/env python3
"""Cron de recon de competidores USANDO agent-reach (fuente oficial).
Canales: YouTube (yt-dlp), web (Jina), X (twitter-cli+cookies), Reddit
(opencli reddit). X/Reddit requieren navegador/session: se intentan y se
reporta estado. YouTube/web funcionan sin login.

Uso: python3 scripts/recon_social.py"""
import subprocess, os, json

VENV = os.path.expanduser("~/.agent-reach-venv")
PY = os.path.join(VENV, "bin", "python")
LOCAL = os.path.expanduser("~/.local/bin")
JINA = "https://r.jina.ai/"

def yt(q, n=2):
    try:
        out = subprocess.run([PY, "-m", "yt_dlp", "--no-warnings", "--print",
                              "%(id)s | %(title)s | %(view_count)s",
                              f"ytsearch{n}:{q}"], capture_output=True, text=True, timeout=30)
        return [l for l in out.stdout.splitlines() if l.strip()]
    except Exception as e:
        return [f"(yt err: {e})"]

def web(url):
    try:
        out = subprocess.run(["curl", "-s", "--max-time", "15", JINA + url],
                             capture_output=True, text=True, timeout=20)
        return "\n".join(l for l in out.stdout.splitlines() if l.strip())[:300]
    except Exception as e:
        return f"(web err: {e})"

def x_search(q):
    env = dict(os.environ)
    env["TWITTER_AUTH_TOKEN"] = "from_config"
    env["PATH"] = LOCAL + ":" + env["PATH"]
    # twitter-cli lee cookies de config.yaml solo si se setean; las sacamos
    import re
    cfg = os.path.expanduser("~/.agent-reach/config.yaml")
    try:
        txt = open(cfg).read()
        at = re.search(r"twitter_auth_token:\s*(\S+)", txt).group(1)
        ct = re.search(r"twitter_ct0:\s*(\S+)", txt).group(1)
        env["TWITTER_AUTH_TOKEN"] = at
        env["TWITTER_CT0"] = ct
    except Exception:
        return "(no cookies X)"
    try:
        r = subprocess.run(["twitter", "search", q, "--lang", "en"],
                          capture_output=True, text=True, timeout=40, env=env)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout[:400]
        return f"(X no responde: {r.stderr[:120] or 'sin salida'})"
    except subprocess.TimeoutExpired:
        return "(X timeout)"

def reddit_search(q):
    env = dict(os.environ)
    env["PATH"] = LOCAL + ":" + env["PATH"]
    try:
        r = subprocess.run(["opencli", "reddit", "search", q, "-f", "json"],
                          capture_output=True, text=True, timeout=40, env=env)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout[:400]
        return f"(Reddit requiere navegador con sesion: {r.stderr[:100] or 'sin salida'})"
    except subprocess.TimeoutExpired:
        return "(Reddit timeout)"

def main():
    print("=== RECON SOCIAL (agent-reach) — LucidFence vs competidores ===\n")
    comps = ["Applivery UEM", "Jamf Pro", "Hexnode MDM", "Kandji MDM", "Microsoft Intune"]
    for q in comps[:2]:
        print(f">>> YouTube: {q}")
        for r in yt(q, 1):
            print(f"   {r}")
    print("\n>>> Web (Jina): referencia agent-reach")
    print(web("https://github.com/Panniantong/agent-reach")[:250])
    print("\n>>> X (twitter-cli + cookies):")
    print(x_search("UEM MDM")[:300])
    print("\n>>> Reddit (opencli reddit):")
    print(reddit_search("UEM MDM")[:300])
    print("\nCanales activos sin login: YouTube, web/Jina, GitHub, RSS, V2EX, B站.")
    print("X: cookies configuradas; Reddit: cookies guardadas (requiere Chrome con sesion).")

if __name__ == "__main__":
    main()
