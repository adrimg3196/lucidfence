#!/usr/bin/env python3.11
"""
build_comparison_pages.py — Publica docs/comparisons/*.md como HTML rastreable
en el sitio de GitHub Pages (tarea t_4a5d2f29, gap #2 REAL).

El build de Pages (publish-pages.yml) sirve static/ a _site/. Este script
CONVIERTE los .md de comparativas a _site/comparisons/*.html con:
  - <link rel="canonical"> absoluto https://adrimg3196.github.io/lucidfence/comparisons/<slug>.html
  - meta og:title/description/type/url, hreflang
  - tema oscuro coherente con la landing (index.html)
  - tablas renderizadas, links internos reescritos a rutas relativas dentro de Pages
  - SIN claims inventados: el contenido es el .md verbatim de main.

Uso (en publish-pages.yml tras cp -r static _site):
  python3.11 scripts/build_comparison_pages.py --out _site/comparisons

No requiere dependencias externas (markdown se parsea con un mini-renderer).
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
from pathlib import Path

BASE_URL = "https://adrimg3196.github.io/lucidfence"
SITE_TITLE = "LucidFence"
THEME_CSS = """
:root{--bg:#08090a;--bg-2:#0c0d0f;--panel:#111214;--panel-2:#16181b;--border:#26282c;--fg:#f7f8f8;--fg-2:#d4d6d9;--muted:#8a8f98;--accent:#5e6ad5;--accent-h:#7d87e6;--green:#4cc38a;--red:#ff6b6b;--radius:8px;--radius-lg:12px;--font:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--fg);font-family:var(--font);line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:var(--accent-h);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:920px;margin:0 auto;padding:0 24px}
header{position:sticky;top:0;z-index:10;background:rgba(8,9,10,.82);backdrop-filter:blur(10px);border-bottom:1px solid var(--border)}
.nav{display:flex;align-items:center;justify-content:space-between;height:60px}
.logo{font-weight:700;font-size:16px;letter-spacing:-.02em;color:var(--fg)}
.nav a{color:var(--muted);font-size:14px}
main{padding:48px 0 64px}
h1{font-size:clamp(28px,5vw,40px);letter-spacing:-.02em;margin-bottom:8px}
h2{font-size:24px;letter-spacing:-.02em;margin:40px 0 16px}
p{color:var(--fg-2);margin:12px 0}
blockquote{border-left:3px solid var(--accent);background:var(--accent-soft,#1c2033);padding:12px 16px;margin:16px 0;border-radius:0 var(--radius) var(--radius) 0;color:var(--fg-2)}
table{width:100%;border-collapse:collapse;margin:20px 0;font-size:14px}
th,td{border:1px solid var(--border);padding:10px 12px;text-align:left;vertical-align:top}
th{background:var(--panel-2);font-weight:600}
tr:nth-child(even) td{background:var(--panel)}
code{font-family:ui-monospace,Menlo,monospace;font-size:.9em;background:var(--panel-2);padding:2px 5px;border-radius:4px}
footer{border-top:1px solid var(--border);padding:28px 0;color:var(--muted);font-size:13px}
.skip-link{position:absolute;left:-9999px;top:0}
""".replace("--accent-soft,#1c2033", "rgba(94,106,213,.14)")


def slug_from_name(name: str) -> str:
    return re.sub(r"\.md$", "", name)


def rewrite_links(md: str) -> str:
    """Rewrite internal relative .md links to relative page paths within Pages.
    docs/comparisons/*.md link like ../README.md or lucidfence-vs-jamf.md.
    We keep them functional but harmless: comparisons/*.md -> ../<slug>.html
    for sibling comparison; other ../*.md -> repo source on GitHub (absolute)."""
    def repl(m):
        text, url = m.group(1), m.group(2)
        if url.startswith("http"):
            return f"[{text}]({url})"
        if url.endswith(".md"):
            if url.startswith("../"):
                # cross-doc link within comparisons (e.g. lucidfence-vs-jamf.md)
                sib = slug_from_name(url.split("/")[-1])
                return f"[{text}](../{sib}.html)"
            return f"[{text}]({url})"
        return f"[{text}]({url})"
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", repl, md)


def md_to_html(md: str) -> str:
    """Minimal markdown -> HTML: headings, blockquote, tables, paragraphs, code, lists."""
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # fenced code (unlikely in comparisons, but safe)
        if line.strip().startswith("```"):
            out.append("<pre><code>")
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                out.append(html.escape(lines[i]))
                i += 1
            out.append("</code></pre>")
            i += 1
            continue
        # table
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            tbl: list[str] = []
            hdr = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2  # skip header + separator
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                tbl.append(row)
                i += 1
            out.append("<table><thead><tr>")
            for c in hdr:
                out.append(f"<th>{inline(c)}</th>")
            out.append("</tr></thead><tbody>")
            for r in tbl:
                out.append("<tr>")
                for c in r:
                    out.append(f"<td>{inline(c)}</td>")
                out.append("</tr>")
            out.append("</tbody></table>")
            continue
        # blockquote
        if line.lstrip().startswith(">"):
            quote = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                quote.append(lines[i].lstrip()[1:].lstrip())
                i += 1
            out.append(f"<blockquote>{inline(' '.join(quote))}</blockquote>")
            continue
        # headings
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        # lists
        if re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.match(r"^\s*[-*]\s+(.*)$", lines[i]).group(1))
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(it)}</li>" for it in items) + "</ul>")
            continue
        # blank
        if not line.strip():
            i += 1
            continue
        # paragraph (merge consecutive non-special lines)
        para = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].lstrip().startswith((">", "#", "|", "-", "*", "```")):
            para.append(lines[i])
            i += 1
        out.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(out)


def inline(text: str) -> str:
    # escape first
    text = html.escape(text)
    # inline code
    text = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", text)
    # bold
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    # links [text](url) — keep markdown-style already rewritten
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    return text


def build_page(md_path: Path, slug: str) -> str:
    raw = md_path.read_text(encoding="utf-8")
    raw = rewrite_links(raw)
    # title = first H1
    m = re.search(r"^#\s+(.*)$", raw, re.MULTILINE)
    title = m.group(1).strip() if m else slug
    body_html = md_to_html(raw)
    canonical = f"{BASE_URL}/comparisons/{slug}.html"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <link rel="canonical" href="{canonical}" />
  <link rel="alternate" hreflang="x-default" href="{canonical}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="{canonical}" />
  <meta property="og:site_name" content="{SITE_TITLE}" />
  <meta property="og:title" content="{html.escape(title)}" />
  <meta property="og:description" content="Capability-by-capability comparison: what each tool does, with cited sources. Not a 'we're better' page." />
  <meta property="og:image" content="{BASE_URL}/og-image.png" />
  <meta name="twitter:card" content="summary_large_image" />
  <style>{THEME_CSS}</style>
</head>
<body>
  <a href="#main" class="skip-link">Skip to content</a>
  <header><div class="wrap nav"><span class="logo">LucidFence</span><a href="../">← Back to home</a></div></header>
  <main class="wrap" id="main">
{body_html}
  </main>
  <footer><div class="wrap">© 2026 LucidFence · <a href="{BASE_URL}/">Home</a> · <a href="{BASE_URL}/comparisons/lucidfence-vs-intune.html">vs Intune</a> · <a href="{BASE_URL}/comparisons/lucidfence-vs-jamf.html">vs Jamf</a></div></footer>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="docs/comparisons", help="dir with comparison .md")
    ap.add_argument("--out", default="_site/comparisons", help="output dir for .html")
    args = ap.parse_args()
    src = Path(args.src)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    md_files = sorted(src.glob("*.md"))
    if not md_files:
        print(f"[WARN] no .md in {src}", flush=True)
    for md in md_files:
        slug = slug_from_name(md.name)
        html_out = build_page(md, slug)
        (out / f"{slug}.html").write_text(html_out, encoding="utf-8")
        print(f"[OK] {md.name} -> {out}/{slug}.html ({len(html_out)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
