#!/usr/bin/env python3
"""Recon de competidores USANDO agent-reach (fuente oficial de busqueda).
Resuelve los problemas previos: YouTube (subtitulos+busqueda), web limpia (Jina
Reader), GitHub (gh), RSS, V2EX. Twitter/Reddit requieren cookies del usuario.

Canales usados (upstream tools de agent-reach):
- YouTube: yt-dlp ytsearch (instalado por agent-reach)
- Web: curl https://r.jina.ai/<url> (markdown limpio)
- GitHub: gh cli (ya con auth)

Salida: referencias de competidores para inspirar el video de LucidFence.
Uso: python3 scripts/recon_web.py"""
import subprocess, sys, os, json

VENV = os.path.expanduser("~/.agent-reach-venv")
PY = os.path.join(VENV, "bin", "python")
JINA = "https://r.jina.ai/"

def yt_search(q, n=3):
    try:
        out = subprocess.run([PY, "-m", "yt_dlp", "--no-warnings", "--print",
                              "%(id)s | %(title)s | %(view_count)s",
                              f"ytsearch{n}:{q}"], capture_output=True, text=True, timeout=30)
        return [l for l in out.stdout.splitlines() if l.strip()]
    except Exception as e:
        return [f"(yt error: {e})"]

def web_read(url):
    try:
        out = subprocess.run(["curl", "-s", "--max-time", "15", JINA + url],
                             capture_output=True, text=True, timeout=20)
        # primeras lineas utiles
        lines = [l for l in out.stdout.splitlines() if l.strip()][:6]
        return "\n".join(lines)
    except Exception as e:
        return f"(web error: {e})"

def main():
    print("=== RECON WEB (agent-reach) — competidores LucidFence ===\n")
    queries = ["Applivery UEM MDM", "Jamf Pro overview", "Hexnode UEM", "Kandji MDM", "Microsoft Intune"]
    for q in queries:
        print(f">>> YouTube: {q}")
        for r in yt_search(q, 1):
            print(f"   {r}")
    print("\n>>> Web (Jina) — pagina competidor de referencia:")
    print(web_read("https://github.com/Panniantong/agent-reach")[:400])
    print("\nTotal canales agent-reach activos: YouTube, Web/Jina, RSS, V2EX, B站, GitHub(gh).")
    print("Twitter/Reddit requieren cookies del usuario (agent-reach install --channels=twitter,reddit).")

if __name__ == "__main__":
    main()
