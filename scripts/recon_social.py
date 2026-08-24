#!/usr/bin/env python3
"""Cron de recon de competidores usando agent-reach cuando está disponible.
Canales: YouTube (yt-dlp), web (Jina), X (twitter-cli+cookies), Reddit
(opencli reddit). Cada canal informa ``available`` o ``unavailable`` sin
convertir dependencias ausentes en un traceback ni en una señal positiva.

Uso: python3 scripts/recon_social.py"""
import os
import re
import shutil
import subprocess

VENV = os.path.expanduser("~/.agent-reach-venv")
PY = os.path.join(VENV, "bin", "python")
LOCAL = os.path.expanduser("~/.local/bin")
JINA = "https://r.jina.ai/"


def unavailable(reason):
    return f"(unavailable: {reason})"


def is_unavailable(value):
    return isinstance(value, str) and value.startswith("(unavailable:")

def yt(q, n=2):
    if not os.path.isfile(PY) or not os.access(PY, os.X_OK):
        return [unavailable("agent-reach python no instalado")]
    try:
        out = subprocess.run([PY, "-m", "yt_dlp", "--no-warnings", "--print",
                              "%(id)s | %(title)s | %(view_count)s",
                              f"ytsearch{n}:{q}"], capture_output=True, text=True, timeout=30)
        rows = [line for line in out.stdout.splitlines() if line.strip()]
        if out.returncode == 0 and rows:
            return rows
        return [unavailable(f"yt-dlp sin datos (exit {out.returncode})")]
    except FileNotFoundError:
        return [unavailable("agent-reach python no instalado")]
    except subprocess.TimeoutExpired:
        return [unavailable("YouTube timeout")]

def web(url):
    if shutil.which("curl") is None:
        return unavailable("curl no instalado")
    try:
        out = subprocess.run(["curl", "-s", "--max-time", "15", JINA + url],
                             capture_output=True, text=True, timeout=20)
        value = "\n".join(line for line in out.stdout.splitlines() if line.strip())[:300]
        if out.returncode == 0 and value:
            return value
        return unavailable(f"Jina sin datos (exit {out.returncode})")
    except FileNotFoundError:
        return unavailable("curl no instalado")
    except subprocess.TimeoutExpired:
        return unavailable("Jina timeout")

def x_search(q):
    env = dict(os.environ)
    env["TWITTER_AUTH_TOKEN"] = "from_config"
    env["PATH"] = LOCAL + ":" + env["PATH"]
    # twitter-cli lee cookies de config.yaml solo si se setean; las sacamos
    cfg = os.path.expanduser("~/.agent-reach/config.yaml")
    try:
        with open(cfg, encoding="utf-8") as config_file:
            txt = config_file.read()
        at = re.search(r"twitter_auth_token:\s*(\S+)", txt).group(1)
        ct = re.search(r"twitter_ct0:\s*(\S+)", txt).group(1)
        env["TWITTER_AUTH_TOKEN"] = at
        env["TWITTER_CT0"] = ct
    except Exception:
        return unavailable("cookies X no configuradas")
    if shutil.which("twitter", path=env["PATH"]) is None:
        return unavailable("twitter-cli no instalado")
    try:
        r = subprocess.run(["twitter", "search", q, "--lang", "en"],
                          capture_output=True, text=True, timeout=40, env=env)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout[:400]
        return unavailable(f"X sin datos (exit {r.returncode})")
    except FileNotFoundError:
        return unavailable("twitter-cli no instalado")
    except subprocess.TimeoutExpired:
        return unavailable("X timeout")

def reddit_search(q):
    env = dict(os.environ)
    env["PATH"] = LOCAL + ":" + env["PATH"]
    if shutil.which("opencli", path=env["PATH"]) is None:
        return unavailable("opencli no instalado")
    try:
        r = subprocess.run(["opencli", "reddit", "search", q, "-f", "json"],
                          capture_output=True, text=True, timeout=40, env=env)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout[:400]
        return unavailable(f"Reddit sin datos (exit {r.returncode})")
    except FileNotFoundError:
        return unavailable("opencli no instalado")
    except subprocess.TimeoutExpired:
        return unavailable("Reddit timeout")

def main():
    print("=== RECON SOCIAL (agent-reach) — LucidFence vs competidores ===\n")
    comps = ["Applivery UEM", "Jamf Pro", "Hexnode MDM", "Kandji MDM", "Microsoft Intune"]
    youtube_results = []
    for q in comps[:2]:
        print(f">>> YouTube: {q}")
        results = yt(q, 1)
        youtube_results.extend(results)
        for result in results:
            print(f"   {result}")
    print("\n>>> Web (Jina): referencia agent-reach")
    web_result = web("https://github.com/Panniantong/agent-reach")
    print(web_result[:250])
    print("\n>>> X (twitter-cli + cookies):")
    x_result = x_search("UEM MDM")
    print(x_result[:300])
    print("\n>>> Reddit (opencli reddit):")
    reddit_result = reddit_search("UEM MDM")
    print(reddit_result[:300])
    statuses = {
        "YouTube": "unavailable" if all(is_unavailable(row) for row in youtube_results) else "available",
        "web/Jina": "unavailable" if is_unavailable(web_result) else "available",
        "X": "unavailable" if is_unavailable(x_result) else "available",
        "Reddit": "unavailable" if is_unavailable(reddit_result) else "available",
    }
    print("\n=== ESTADO DE CANALES ===")
    for channel, status in statuses.items():
        print(f"{channel}: {status}")

if __name__ == "__main__":
    main()
