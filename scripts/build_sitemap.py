#!/usr/bin/env python3.11
"""
build_sitemap.py — Genera _site/sitemap.xml para GitHub Pages (tarea t_4a5d2f29, gap #D).

Incluye TODAS las URLs rastreables del sitio de Pages con URLs absolutas:
  - Las páginas HTML servidas desde static/ (index, cloud, dashboard, manual, web, whitelabel)
  - Las comparativas generadas en _site/comparisons/*.html (build_comparison_pages.py)

Uso (en publish-pages.yml, tras copiar static/ a _site y generar comparisons):
  python3.11 scripts/build_sitemap.py --site _site
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

BASE_URL = "https://adrimg3196.github.io/lucidfence"

# Páginas estáticas conocidas servidas desde static/ (en la raíz del site).
# Se expresan como RUTAS de Pages (no nombres de fichero) para coincidir con
# PUBLIC_ROUTES de scripts/pages_seo_check.py (la home es "/" no "/index.html").
STATIC_ROUTES = [
    "/",
    "/cloud.html",
    "/dashboard.html",
    "/manual.html",
    "/web.html",
    "/whitelabel.html",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="_site", help="directorio _site generado")
    ap.add_argument("--base", default=BASE_URL)
    args = ap.parse_args()
    site = Path(args.site)
    if not site.exists():
        print(f"[WARN] {site} no existe; ejecuta tras el cp -r static _site", flush=True)
    urls: list[str] = []
    lastmod = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    # páginas estáticas (rutas de Pages)
    for route in STATIC_ROUTES:
        urls.append(f"{args.base}{route}")
    # comparativas generadas
    comp_dir = site / "comparisons"
    if comp_dir.exists():
        for html in sorted(comp_dir.glob("*.html")):
            urls.append(f"{args.base}/comparisons/{html.name}")
    if not urls:
        print("[WARN] sitemap vacío: sin páginas detectadas", flush=True)
    body = "\n".join(
        f"  <url><loc>{u}</loc><lastmod>{lastmod}</lastmod></url>" for u in urls
    )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )
    out = site / "sitemap.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(sitemap, encoding="utf-8")
    print(f"[OK] sitemap -> {out} ({len(urls)} urls)")
    for u in urls:
        print(f"  - {u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
