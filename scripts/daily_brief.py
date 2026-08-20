#!/usr/bin/env python3
"""Cron diario: genera un brief de video LucidFence usando recon de competidores
y lo guarda en brand/briefs/ con commit. Impacto real en el producto/video:
cada dia hay un brief nuevo listo para renderizar.

Uso: python3 scripts/daily_brief.py"""
import os, subprocess, sys

REPO = "/Users/adri/geofence-uem"
sys.path.insert(0, os.path.join(REPO, "scripts"))
import video_brief  # reusa el generador

def main():
    os.chdir(REPO)
    video_brief.main()  # genera brand/brief_<ts>.json
    # encuentra el brief mas reciente generado por video_brief
    import glob
    briefs = sorted(glob.glob(os.path.join(REPO, "brand", "brief_*.json")))
    if not briefs:
        print("No se genero brief"); return
    src = briefs[-1]
    dst_dir = os.path.join(REPO, "brand", "briefs")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    os.rename(src, dst)
    subprocess.run(["git", "add", dst], check=True)
    subprocess.run(["git", "commit", "-m", f"chore(video): brief diario auto-generado {os.path.basename(dst)}"],
                   env={**os.environ, "GIT_AUTHOR_NAME": "Hermes Agent", "GIT_AUTHOR_EMAIL": "hermes@local",
                        "GIT_COMMITTER_NAME": "Hermes Agent", "GIT_COMMITTER_EMAIL": "hermes@local"})
    subprocess.run(["git", "push", "origin", "HEAD:main"])
    print(f"Brief diario commiteado: {dst}")

if __name__ == "__main__":
    main()
