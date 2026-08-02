#!/usr/bin/env python3
"""Recon de competidores USANDO agent-reach (fuente oficial de busqueda).
Canales: YouTube (yt-dlp), web (Jina), X (Jina Reader de x.com/search, evita
el bug de twitter-cli), Reddit (curl autenticado con cookies guardadas).
Todos funcionan en headless/produccion sin navegador.

Usado por cron recon-web-agent-reach (9AM). Uso: python3 scripts/recon_web.py"""
import subprocess, os, re, json

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
    # twscrape (en el venv de agent-reach) genera ClientTransaction y usa
    # auth_token+ct0: funciona en headless. Se ejecuta en subprocess con el venv
    # para no requerir twscrape en el python del sistema.
    at, ct = x_cookies()
    if not at:
        return "(no cookies X)"
    code = (
        "import asyncio,json,sys\n"
        "from twscrape import API\n"
        "c=json.load(open('/tmp/x_cookies.json')); d={x['name']:x['value'] for x in c}\n"
        "twid=d.get('twid','')\n"
        f"ck='auth_token={at}; ct0={ct}'" + ("+'; twid='+twid if twid else ''") + "\n"
        "async def run():\n"
        "  api=API(); await api.pool.add_account_cookies('xuser',ck)\n"
        "  out=[]\n"
        "  async for t in api.search(" + repr(q) + ", limit=5):\n"
        "    c=getattr(t,'rawContent',None) or getattr(t,'content',None) or ''\n"
        "    out.append(str(c)[:90])\n"
        "  return out\n"
        "r=asyncio.run(run())\n"
        "print('\\n'.join('  - '+x for x in r[:5]) if r else '(X sin tweets)')\n"
    )
    try:
        out = subprocess.run([PY, "-c", code], capture_output=True, text=True, timeout=60)
        return out.stdout.strip() or f"(X err: {out.stderr[:120]})"
    except subprocess.TimeoutExpired:
        return "(X timeout)"
    except Exception as e:
        return f"(X err: {e})"

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
    print("\n>>> X (twscrape + cookies, ClientTransaction):")
    print(x_search("UEM MDM")[:400])
    print("\n>>> Reddit (curl autenticado):")
    print(reddit_search("UEM MDM")[:400])
    print("\nCanales en produccion: YouTube, web/Jina, X (API+twid), Reddit (auth cookie).")

if __name__ == "__main__":
    main()
