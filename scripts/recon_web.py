#!/usr/bin/env python3
"""Recon de competidores USANDO agent-reach (fuente oficial de busqueda).
Canales: YouTube (yt-dlp), web (Jina), X (Jina Reader de x.com/search, evita
el bug de twitter-cli), Reddit (curl autenticado con cookies guardadas).
Todos funcionan en headless/produccion sin navegador.

Usado por cron recon-web-agent-reach (9AM). Uso: python3 scripts/recon_web.py"""
import subprocess, os, re

VENV = os.path.expanduser("~/.agent-reach-venv")
PY = os.path.join(VENV, "bin", "python")
JINA = "https://r.jina.ai/"

def yt(q, n=3):
    try:
        out = subprocess.run([PY, "-m", "yt_dlp", "--no-warnings", "--print",
                              "%(id)s | %(title)s | %(view_count)s",
                              f"ytsearch{n}:{q}"], capture_output=True, text=True, timeout=30)
        return [l for l in out.stdout.splitlines() if l.strip()]
    except Exception as e:
        return [f"(yt err: {e})"]

def jina(url, head=300):
    try:
        out = subprocess.run(["curl", "-s", "--max-time", "20", JINA + url],
                             capture_output=True, text=True, timeout=25)
        return "\n".join(l for l in out.stdout.splitlines() if l.strip())[:head]
    except Exception as e:
        return f"(err: {e})"

def x_search(q):
    # Jina Reader de x.com/search: evita el bug de twitter-cli (ClientTransaction)
    u = f"https://x.com/search?q={requests_quote(q)}&f=live"
    txt = jina(u, 600)
    return txt if txt and "Blocked" not in txt and "Forbidden" not in txt else f"(X via Jina sin resultados: {txt[:120]})"

def reddit_search(q):
    # curl autenticado con reddit_session guardada: evita opencli (requiere navegador)
    cookie = reddit_cookie()
    if not cookie:
        return "(no cookie Reddit)"
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "20",
             "-H", f"Cookie: {cookie}",
             "-H", "User-Agent: Mozilla/5.0",
             f"https://www.reddit.com/search.json?q={requests_quote(q)}&limit=5"],
            capture_output=True, text=True, timeout=25)
        import json as J
        data = J.loads(out.stdout)
        posts = data.get("data", {}).get("children", [])
        if not posts:
            return "(Reddit sin posts)"
        return "\n".join(f"  - {p['data']['title']} (r/{p['data']['subreddit']})"
                         for p in posts[:5])
    except Exception as e:
        return f"(Reddit err: {e})"

def requests_quote(s):
    return __import__("urllib.parse").quote(s)

def reddit_cookie():
    p = os.path.expanduser("~/.agent-reach/reddit_cookies.txt")
    try:
        for line in open(p):
            if "reddit_session" in line:
                parts = line.split("\t")
                return f"{parts[-2]}={parts[-1].strip()}"
    except Exception:
        return None
    return None

def main():
    print("=== RECON WEB (agent-reach) — competidores LucidFence ===\n")
    for q in ["Applivery UEM MDM", "Jamf Pro overview", "Hexnode UEM", "Kandji MDM", "Microsoft Intune"]:
        print(f">>> YouTube: {q}")
        for r in yt(q, 1):
            print(f"   {r}")
    print("\n>>> Web (Jina):")
    print(jina("https://github.com/Panniantong/agent-reach")[:250])
    print("\n>>> X (Jina Reader x.com/search):")
    print(x_search("UEM MDM")[:400])
    print("\n>>> Reddit (curl autenticado):")
    print(reddit_search("UEM MDM")[:400])
    print("\nCanales en produccion: YouTube, web/Jina, X (Jina), Reddit (auth cookie).")

if __name__ == "__main__":
    main()
