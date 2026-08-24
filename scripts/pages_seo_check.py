#!/usr/bin/env python3
"""Validate the intentionally public GitHub Pages discovery surface.

The gate checks the sitemap and any URL metadata that already exists.  It
deliberately does not require or validate ``robots.txt``: a project Pages site
at ``/<repository>/`` cannot publish the origin-level ``/robots.txt`` file.
"""
from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET


DEFAULT_SITE_ROOT = "https://adrimg3196.github.io/lucidfence"
PUBLIC_ROUTES = {
    "/": "index.html",
    "/cloud.html": "cloud.html",
    "/manual.html": "manual.html",
    "/web.html": "web.html",
    "/whitelabel.html": "whitelabel.html",
}


class _UrlMetadataParser(HTMLParser):
    """Collect existing canonical and Open Graph URL values."""

    def __init__(self) -> None:
        super().__init__()
        self.values: list[tuple[str, str]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = {key.lower(): value for key, value in attrs}
        if tag.lower() == "link":
            rel = (attributes.get("rel") or "").lower().split()
            href = attributes.get("href")
            if "canonical" in rel and href:
                self.values.append(("canonical", href))
        elif tag.lower() == "meta":
            property_name = (
                attributes.get("property") or attributes.get("name") or ""
            ).lower()
            content = attributes.get("content")
            if property_name == "og:url" and content:
                self.values.append(("og:url", content))


def _normalise_site_root(raw_site_root: str) -> tuple[str, str, str]:
    site_root = raw_site_root.rstrip("/")
    parsed = urlsplit(site_root)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("site-root debe ser una URL HTTPS sin query ni fragmento")
    root_path = parsed.path.rstrip("/")
    return site_root, parsed.netloc, root_path


def _read_sitemap(static_dir: Path, errors: list[str]) -> list[str]:
    sitemap_path = static_dir / "sitemap.xml"
    if not sitemap_path.is_file():
        errors.append("falta sitemap.xml")
        return []
    try:
        root = ET.parse(sitemap_path).getroot()
    except (ET.ParseError, OSError) as exc:
        errors.append(f"sitemap.xml no es válido: {exc}")
        return []
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    return [
        element.text.strip()
        for element in root.findall(f"{namespace}url/{namespace}loc")
        if element.text and element.text.strip()
    ]


def _route_within_project(path: str, root_path: str) -> str | None:
    boundary = f"{root_path}/" if root_path else "/"
    if not path.startswith(boundary):
        return None
    relative = path[len(root_path) :] if root_path else path
    return relative or "/"


def validate(static_dir: Path, raw_site_root: str) -> list[str]:
    """Return all sitemap and existing URL metadata contract violations."""
    errors: list[str] = []
    try:
        site_root, expected_host, root_path = _normalise_site_root(raw_site_root)
    except ValueError as exc:
        return [str(exc)]

    locations = _read_sitemap(static_dir, errors)
    duplicates = sorted(url for url, count in Counter(locations).items() if count > 1)
    for duplicate in duplicates:
        errors.append(f"URL duplicada en sitemap: {duplicate}")

    seen_routes: set[str] = set()
    for location in locations:
        parsed = urlsplit(location)
        if parsed.scheme != "https" or parsed.netloc != expected_host:
            errors.append(f"URL fuera de site-root: {location}")
            continue
        route = _route_within_project(parsed.path, root_path)
        if route is None:
            errors.append(f"URL fuera de site-root: {location}")
            continue
        if parsed.query or parsed.fragment:
            errors.append(f"URL con query o fragmento en sitemap: {location}")
            continue
        if route not in PUBLIC_ROUTES:
            errors.append(f"ruta no pública en sitemap: {route}")
            continue
        seen_routes.add(route)
        public_file = static_dir / PUBLIC_ROUTES[route]
        if not public_file.is_file():
            errors.append(f"falta la página pública {PUBLIC_ROUTES[route]}")

    for missing_route in sorted(set(PUBLIC_ROUTES) - seen_routes):
        errors.append(f"falta URL pública en sitemap: {site_root}{missing_route}")

    for html_path in sorted(static_dir.glob("*.html")):
        parser = _UrlMetadataParser()
        try:
            parser.feed(html_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            errors.append(f"no se pudo leer {html_path.name}: {exc}")
            continue
        for kind, value in parser.values:
            if "/static/" in value:
                errors.append(
                    f"{html_path.name}: {kind} contiene /static/ y no es portable"
                )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-dir", type=Path, default=Path("static"))
    parser.add_argument("--site-root", default=DEFAULT_SITE_ROOT)
    args = parser.parse_args(argv)

    errors = validate(args.static_dir, args.site_root)
    if errors:
        print("NO APTO: contrato SEO de GitHub Pages incumplido")
        for error in errors:
            print(f"- {error}")
        return 1
    print("APTO: sitemap público y metadatos URL portables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
