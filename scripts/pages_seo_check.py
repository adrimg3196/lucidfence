#!/usr/bin/env python3
"""
pages_seo_check.py — Linter de SEO para la superficie estática pública de
LucidFence servida en GitHub Pages.

Este script es la fuente de verdad del guardarraíl de SEO de Pages. Valida:

  1. SEO esencial por página: <title>, meta description, <link canonical>,
     og:title, og:url y twitter:card presentes en cada static/*.html.
  2. GUARDRAIL P0 (#110 / PR #223): canonical y og:url NO deben contener el
     segmento '/static/'. En un project page (adrimg3196.github.io/lucidfence)
     las rutas /static/X.html dan 404 — deben ser rutas de raíz del sitio
     (/X.html). Cualquier '/static/' BLOCKEA.
  3. Descubrimiento: static/robots.txt y static/sitemap.xml deben existir.
  4. Cada <loc> del sitemap debe apuntar a un fichero estático real en static/.

Uso:
  python3 scripts/pages_seo_check.py
  python3 scripts/pages_seo_check.py --static-dir static \\
      --site-root https://adrimg3196.github.io/lucidfence

Sale con código 1 si hay violaciones (formato adecuado para un gate de CI).
Solo usa la stdlib de Python 3.
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REQUIRED_META = [
    ("title", re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)),
    ("meta description", re.compile(r'<meta\s+name=["\']description["\'][^>]*>', re.IGNORECASE)),
    ("canonical", re.compile(r'<link\s+rel=["\']canonical["\'][^>]*>', re.IGNORECASE)),
    ("og:title", re.compile(r'<meta\s+property=["\']og:title["\'][^>]*>', re.IGNORECASE)),
    ("og:url", re.compile(r'<meta\s+property=["\']og:url["\'][^>]*>', re.IGNORECASE)),
    ("twitter:card", re.compile(r'<meta\s+name=["\']twitter:card["\'][^>]*>', re.IGNORECASE)),
]

# Extrae el valor de href/src/content de una etiqueta ya localizada.
ATTR_RE = re.compile(r'(?:href|content)\s*=\s*["\']([^"\']*)["\']', re.IGNORECASE)
# Rutas que contienen el segmento prohibido /static/ (causa 404 en project page).
STATIC_SEGMENT_RE = re.compile(r"/static/", re.IGNORECASE)


def check_page(path: Path, problems: list[str]) -> None:
    html = path.read_text(encoding="utf-8", errors="replace")
    name = path.name
    for label, rx in REQUIRED_META:
        if not rx.search(html):
            problems.append(f"  [SEO] {name}: falta {label}")

    # Guardrail P0: canonical / og:url no deben llevar /static/.
    for label, rx in (("canonical", REQUIRED_META[2][1]), ("og:url", REQUIRED_META[4][1])):
        m = rx.search(html)
        if not m:
            continue
        tag = m.group(0)
        av = ATTR_RE.search(tag)
        if not av:
            continue
        val = av.group(1)
        if STATIC_SEGMENT_RE.search(val):
            problems.append(
                f"  [BLOCK] {name}: {label} apunta a ruta /static/ ('{val}') "
                f"-> 404 en project page; usar ruta de raíz (/X.html)"
            )


def check_seo_files(static_dir: Path, problems: list[str]) -> None:
    html_files = sorted(static_dir.glob("*.html"))
    if not html_files:
        problems.append("  [SEO] no se encontró ningún static/*.html")
        return
    for f in html_files:
        check_page(f, problems)


def check_discovery(static_dir: Path, site_root: str, problems: list[str]) -> None:
    robots = static_dir / "robots.txt"
    sitemap = static_dir / "sitemap.xml"
    if not robots.is_file():
        problems.append("  [DISCOVERY] falta static/robots.txt")
    if not sitemap.is_file():
        problems.append("  [DISCOVERY] falta static/sitemap.xml")
        return

    # El sitemap debe listar la URL del propio sitemap en robots.txt.
    robots_txt = robots.read_text(encoding="utf-8", errors="replace")
    if "sitemap" not in robots_txt.lower():
        problems.append("  [DISCOVERY] robots.txt no declara Sitemap:")

    # Cada <loc> debe resolverse a un fichero real en static/.
    try:
        tree = ET.parse(sitemap)
    except ET.ParseError as e:
        problems.append(f"  [DISCOVERY] sitemap.xml no es XML válido: {e}")
        return
    root = tree.getroot()
    locs = [loc.text for loc in root.iter() if loc.tag.endswith("loc") and loc.text]
    if not locs:
        problems.append("  [DISCOVERY] sitemap.xml no contiene ningún <loc>")
    for loc in locs:
        if not loc.startswith(site_root):
            problems.append(f"  [DISCOVERY] <loc> fuera de site-root: {loc}")
            continue
        rel = loc[len(site_root):].lstrip("/")
        if not rel:
            rel = "index.html"
        if not (static_dir / rel).is_file():
            problems.append(f"  [DISCOVERY] <loc> {loc} -> static/{rel} no existe")


def main() -> int:
    ap = argparse.ArgumentParser(description="Linter SEO de Pages para LucidFence")
    ap.add_argument("--static-dir", default="static")
    ap.add_argument(
        "--site-root",
        default="https://adrimg3196.github.io/lucidfence",
        help="Raíz del project page (sin barra final).",
    )
    args = ap.parse_args()

    # Permitir ejecutar desde la raíz del repo o desde scripts/.
    candidates = [Path(args.static_dir), Path("..") / args.static_dir]
    static_dir = next((c for c in candidates if c.is_dir()), Path(args.static_dir))

    problems: list[str] = []
    print("== pages_seo_check.py ==")
    print(f"static-dir: {static_dir.resolve()}")
    print(f"site-root : {args.site_root}")
    print()

    check_seo_files(static_dir, problems)
    check_discovery(static_dir, args.site_root.rstrip("/"), problems)

    if problems:
        print("VIOLACIONES ENCONTRADAS:")
        for p in problems:
            print(p)
        print(f"\nTotal: {len(problems)} problema(s).")
        return 1

    print("OK: sin violaciones de SEO de Pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
