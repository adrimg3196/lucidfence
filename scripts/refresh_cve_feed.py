#!/usr/bin/env python3
"""Refresca el feed CVE desde NVD (red) y lo deja listo para el engine.

Diseno (respeta "100% local" en runtime):
  - El dashboard NO depende de red en caliente; el feed se precarga en
    data/cve_feed_nvd.json y se renueva por este script en un cron local.
  - Si la red falla, NO se machaca el feed previo (deja el ultimo bueno).
  - No imprime nada salvo errores (pensado para cron silencioso).

Uso en cron:
  17 3 * * *  /usr/bin/python3 /Users/adri/geofence-uem/scripts/refresh_cve_feed.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.cve_feed_nvd import sync_nvd_feed, load_nvd_feed_into_cve

if __name__ == "__main__":
    try:
        n = sync_nvd_feed()
        load_nvd_feed_into_cve()
        if n:
            print(f"OK CVE feed refreshed: {n} entries")
        else:
            print("WARN: CVE feed sync returned 0 (network down? keeping previous feed)")
    except Exception as e:
        # Silencioso en cron: el feed anterior sigue vigente.
        print(f"ERROR refreshing CVE feed: {type(e).__name__}: {e}")
        sys.exit(0)
