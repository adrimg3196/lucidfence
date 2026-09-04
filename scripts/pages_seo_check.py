#!/usr/bin/env python3
"""Validate the repository's GitHub Pages discovery surface.

The sitemap is exclusively a deployment artifact for this GitHub Project Pages
site; it is not an SEO contract for self-hosted installations.  The gate also
checks any canonical and ``og:url`` metadata that already exists against each
page's Pages URL.  It deliberately does not require or validate ``robots.txt``:
a project Pages site at ``/<repository>/`` cannot publish the origin-level
``/robots.txt`` file.
"""
from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import urljoin, urlsplit, urlunsplit
import xml.etree.ElementTree as ET


DEFAULT_SITE_ROOT = "https://adrimg3196.github.io/lucidfence"
PUBLIC_ROUTES = {
    "/": "index.html",
    "/cloud.html": "cloud.html",
    "/dashboard.html": "dashboard.html",
    "/manual.html": "manual.html",
    "/web.html": "web.html",
    "/whitelabel.html": "whitelabel.html",
    "/comparisons/lucidfence-vs-intune.html": "comparisons/lucidfence-vs-intune.html",
    "/comparisons/lucidfence-vs-jamf.html": "comparisons/lucidfence-vs-jamf.html",
    "/comparisons/lucidfence-vs-kandji.html": "comparisons/lucidfence-vs-kandji.html",
}

# Comparison pages are generated from docs/comparisons/*.md into
# _site/comparisons/*.html. The static allowlist above is the contract for the
# known/co-signed pages; every OTHER comparisons/*.html that exists on disk is
# also a public route (the sitemap generator discovers them dynamically). This
# keeps the gate in sync when a new comparison page lands, instead of silently
# breaking the Pages deploy because PUBLIC_ROUTES was not hand-edited.
def _comparison_routes_from_dir(static_dir: Path) -> dict[str, str]:
    routes: dict[str, str] = {}
    comp_dir = static_dir / "comparisons"
    if comp_dir.is_dir():
        for html in sorted(comp_dir.glob("*.html")):
            if html.name in ("index.html",):
                continue
            rel = f"comparisons/{html.name}"
            routes[f"/{rel}"] = rel
    return routes


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
            if "canonical" in rel and href is not None:
                self.values.append(("canonical", href))
        elif tag.lower() == "meta":
            property_name = (
                attributes.get("property") or attributes.get("name") or ""
            ).lower()
            content = attributes.get("content")
            if property_name == "og:url" and content is not None:
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


def _expected_page_path(rel_html: str, root_path: str) -> str:
    """Resolve the published route for a page file.

    ``rel_html`` is the path relative to static_dir (e.g.
    "index.html" or "comparisons/lucidfence-vs-intune.html"). Nested
    comparison pages are keyed by their full relative path in PUBLIC_ROUTES.
    """
    route_by_file = {
        filename: route for route, filename in PUBLIC_ROUTES.items()
    }
    route = route_by_file.get(rel_html)
    if route is None:
        # Root-level pages are keyed only by filename.
        route = route_by_file.get(Path(rel_html).name, f"/{Path(rel_html).name}")
    if route == "/":
        return f"{root_path}/" if root_path else "/"
    return f"{root_path}{route}"


def _validate_page_url(
    *,
    rel_html: str,
    kind: str,
    value: str,
    expected_host: str,
    root_path: str,
) -> list[str]:
    """Validate one canonical/og:url against the page that declares it."""
    expected_path = _expected_page_path(rel_html, root_path)
    document_url = urlunsplit(("https", expected_host, expected_path, "", ""))
    raw_value = value.strip()
    parsed_value = urlsplit(raw_value)
    prefix = f"{rel_html}: {kind} {value!r}"

    if not raw_value:
        return [f"{prefix} está vacío"]
    if parsed_value.scheme and parsed_value.scheme != "https":
        return [f"{prefix} usa un esquema no permitido"]
    if parsed_value.netloc and parsed_value.netloc != expected_host:
        return [f"{prefix} usa un host externo"]

    resolved = urlsplit(urljoin(document_url, raw_value))
    if resolved.scheme != "https" or resolved.netloc != expected_host:
        return [f"{prefix} usa un host externo"]
    if _route_within_project(resolved.path, root_path) is None:
        return [f"{prefix} queda fuera de site-root"]
    if resolved.query or resolved.fragment:
        return [f"{prefix} contiene query o fragmento"]
    if resolved.path != expected_path:
        return [
            f"{prefix} no apunta a su propia ruta {expected_path}"
        ]
    return []


def validate(static_dir: Path, raw_site_root: str) -> list[str]:
    """Return all sitemap and existing URL metadata contract violations."""
    errors: list[str] = []
    try:
        site_root, expected_host, root_path = _normalise_site_root(raw_site_root)
    except ValueError as exc:
        return [str(exc)]

    # Public contract = the curated allowlist PLUS any comparison page that was
    # actually generated into comparisons/. This prevents the gate from rejecting
    # legitimate pages the sitemap generator already discovered (e.g. Kandji).
    public_routes = dict(PUBLIC_ROUTES)
    public_routes.update(_comparison_routes_from_dir(static_dir))

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
        if route not in public_routes:
            errors.append(f"ruta no pública en sitemap: {route}")
            continue
        seen_routes.add(route)
        public_file = static_dir / public_routes[route]
        if not public_file.is_file():
            errors.append(f"falta la página pública {public_routes[route]}")

    for missing_route in sorted(set(public_routes) - seen_routes):
        errors.append(f"falta URL pública en sitemap: {site_root}{missing_route}")

    # Validate URL metadata on EVERY published page, including nested
    # comparison pages under comparisons/ (P2 Codex review thread, #324).
    # PUBLIC_ROUTES is keyed by route; reverse it to map a file path to the
    # route it is published at so metadata is checked against the right URL.
    route_by_file = {
        filename: route for route, filename in public_routes.items()
    }
    for html_path in sorted(static_dir.rglob("*.html")):
        rel_html = str(html_path.relative_to(static_dir))
        # Metadata only matters for intentionally public routes; skip anything
        # not in the public contract (e.g. stray or dev-only pages).
        route = route_by_file.get(rel_html)
        if route is None:
            continue
        parser = _UrlMetadataParser()
        try:
            parser.feed(html_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            errors.append(f"no se pudo leer {rel_html}: {exc}")
            continue
        for kind, value in parser.values:
            errors.extend(
                _validate_page_url(
                    rel_html=rel_html,
                    kind=kind,
                    value=value,
                    expected_host=expected_host,
                    root_path=root_path,
                )
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
    print("APTO: sitemap de GitHub Pages y metadatos URL coherentes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
