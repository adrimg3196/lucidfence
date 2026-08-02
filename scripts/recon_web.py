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
    # curl directo a la API de X con cookies (auth_token+ct0+twid+guest token)
    at, ct = x_cookies()
    if not at:
        return "(no cookies X)"
    twid = x_twid()
    bearer = ("AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH2Kr1s8T2rK"
              "O8X2h7jU7MaxZUc0pGMKQ %3D%3D")
    try:
        g = subprocess.run([
            "curl", "-s", "--max-time", "20",
            "-H", f"authorization: Bearer {bearer}",
            "-H", "User-Agent: Mozilla/5.0",
            "https://api.twitter.com/1.1/guest/activate.json"],
            capture_output=True, text=True, timeout=25)
        import json as J
        gt = J.loads(g.stdout).get("guest_token", "")
    except Exception:
        gt = ""
    cookie = f"auth_token={at}; ct0={ct}"
    if twid:
        cookie += f"; twid={twid}"
    if gt:
        cookie += f"; gt={gt}"
    try:
        out = subprocess.run([
            "curl", "-s", "--max-time", "25",
            "-H", f"authorization: Bearer {bearer}",
            "-H", f"x-csrf-token: {ct}",
            "-H", f"x-guest-token: {gt}",
            "-H", "x-twitter-auth-type: OAuth2Session",
            "-H", "x-twitter-active-user: yes",
            "-H", "User-Agent: Mozilla/5.0",
            "--cookie", cookie,
            f"https://twitter.com/i/api/2/search/adaptive.json?q={requests_quote(q)}&count=5&tweet_search_mode=live"],
            capture_output=True, text=True, timeout=30)
        d = J.loads(out.stdout)
        tweets = d.get("globalObjects", {}).get("tweets", {})
        if not tweets:
            return f"(X sin tweets: {out.stdout[:150]})"
        return "\n".join(f"  - {t['full_text'][:90]}" for t in list(tweets.values())[:5])
    except Exception as e:
        return f"(X err: {e})"

def x_twid():
    p = os.path.expanduser("~/.agent-reach/config.yaml")
    try:
        txt = open(p).read()
        m = re.search(r"twitter_twid:\s*(\S+)", txt)
        if m:
            return m.group(1)
        # intenta del json original
        c = json.load(open("/tmp/x_cookies.json"))
        d = {x["name"]: x["value"] for x in c}
        return d.get("twid", "")
    except Exception:
        return ""

def x_cookies():
    cfg = os.path.expanduser("~/.agent-reach/config.yaml")
    try:
        txt = open(cfg).read()
        at = re.search(r"twitter_auth_token:\s*(\S+)", txt).group(1)
        ct = re.search(r"twitter_ct0:\s*(\S+)", txt).group(1)
        return at, ct
    except Exception:
        return None, None

def reddit_search(q):
    # curl autenticado con reddit_session: funciona en headless
    cookie = reddit_cookie()
    if not cookie:
        return "(no cookie Reddit)"
    try:
        out = subprocess.run([
            "curl", "-sL", "--max-time", "25",
            "-H", f"Cookie: {cookie}",
            "-H", "User-Agent: Mozilla/5.0 (compatible; HermesAgent/1.0)",
            "-H", "Accept: application/json",
            f"https://www.reddit.com/search.json?q={requests_quote(q)}&limit=5"],
            capture_output=True, text=True, timeout=30)
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
    from urllib.parse import quote
    return quote(s)

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
    print("\nCanales en produccion: YouTube, web/Jina, X (API+twid), Reddit (auth cookie).")

if __name__ == "__main__":
    main()
