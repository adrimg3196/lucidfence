#!/usr/bin/env python3
"""Recon de competidores USANDO agent-reach (fuente oficial de busqueda).
Canales: YouTube (yt-dlp), web (Jina), X (twitter-cli+cookies), Reddit
(opencli reddit). X/Reddit requieren session/navegador: se intentan y se
reporta estado. YouTube/web funcionan sin login.

Usado por cron recon-web-agent-reach (9AM). Uso: python3 scripts/recon_web.py"""
import subprocess, os, re

VENV = os.path.expanduser("~/.agent-reach-venv")
PY = os.path.join(VENV, "bin", "python")
LOCAL = os.path.expanduser("~/.local/bin")
JINA = "https://r.jina.ai/"

def yt(q, n=3):
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
    env = dict(os.environ); env["PATH"] = LOCAL + ":" + env["PATH"]
    cfg = os.path.expanduser("~/.agent-reach/config.yaml")
    try:
        txt = open(cfg).read()
        env["TWITTER_AUTH_TOKEN"] = re.search(r"twitter_auth_token:\s*(\S+)", txt).group(1)
        env["TWITTER_CT0"] = re.search(r"twitter_ct0:\s*(\S+)", txt).group(1)
    except Exception:
        return "(no cookies X)"
    try:
        r = subprocess.run(["twitter", "search", q, "--lang", "en"],
                          capture_output=True, text=True, timeout=40, env=env)
        return r.stdout[:400] if r.returncode == 0 and r.stdout.strip() else f"(X: {r.stderr[:120] or 'sin salida'})"
    except subprocess.TimeoutExpired:
        return "(X timeout)"

def reddit_search(q):
    env = dict(os.environ); env["PATH"] = LOCAL + ":" + env["PATH"]
    try:
        r = subprocess.run(["opencli", "reddit", "search", q, "-f", "json"],
                          capture_output=True, text=True, timeout=40, env=env)
        return r.stdout[:400] if r.returncode == 0 and r.stdout.strip() else f"(Reddit requiere Chrome con sesion: {r.stderr[:100] or 'sin salida'})"
    except subprocess.TimeoutExpired:
        return "(Reddit timeout)"

def main():
    print("=== RECON WEB (agent-reach) — competidores LucidFence ===\n")
    for q in ["Applivery UEM MDM", "Jamf Pro overview", "Hexnode UEM", "Kandji MDM", "Microsoft Intune"]:
        print(f">>> YouTube: {q}")
        for r in yt(q, 1):
            print(f"   {r}")
    print("\n>>> Web (Jina):")
    print(web("https://github.com/Panniantong/agent-reach")[:250])
    print("\n>>> X (twitter-cli + cookies):")
    print(x_search("UEM MDM")[:300])
    print("\n>>> Reddit (opencli reddit):")
    print(reddit_search("UEM MDM")[:300])
    print("\nCanales sin login: YouTube, web/Jina, GitHub, RSS, V2EX, B站. X/Reddit: cookies listas.")

if __name__ == "__main__":
    main()
