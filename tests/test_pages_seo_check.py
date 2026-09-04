"""Behavioral tests for the GitHub Pages SEO deployment gate."""
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "pages_seo_check.py"
SITE_ROOT = "https://example.github.io/lucidfence"
PUBLIC_FILES = (
    "index.html",
    "cloud.html",
    "dashboard.html",
    "manual.html",
    "web.html",
    "whitelabel.html",
)
COMPARISON_FILES = (
    "comparisons/lucidfence-vs-intune.html",
    "comparisons/lucidfence-vs-jamf.html",
    "comparisons/lucidfence-vs-kandji.html",
)


def _html(name: str) -> str:
    canonical = (
        f'<link rel="canonical" href="{name}">' if name == "cloud.html" else ""
    )
    return (
        f'<!doctype html><html lang="es"><head><title>{name}</title>'
        f"{canonical}</head></html>"
    )


def _sitemap(paths: list[str]) -> str:
    rows = "\n".join(f"  <url><loc>{SITE_ROOT}{path}</loc></url>" for path in paths)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{rows}\n"
        "</urlset>\n"
    )


def _fixture(root: Path, paths: list[str] | None = None) -> Path:
    static_dir = root / "static"
    static_dir.mkdir()
    for name in PUBLIC_FILES + COMPARISON_FILES:
        target = static_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_html(name), encoding="utf-8")
    sitemap_paths = paths or [
        "/",
        "/cloud.html",
        "/dashboard.html",
        "/manual.html",
        "/web.html",
        "/whitelabel.html",
        "/comparisons/lucidfence-vs-intune.html",
        "/comparisons/lucidfence-vs-jamf.html",
        "/comparisons/lucidfence-vs-kandji.html",
    ]
    (static_dir / "sitemap.xml").write_text(_sitemap(sitemap_paths), encoding="utf-8")
    return static_dir


def _check(
    static_dir: Path, site_root: str | None = SITE_ROOT
) -> subprocess.CompletedProcess[str]:
    command = ["python3", str(CHECK), "--static-dir", str(static_dir)]
    if site_root is not None:
        command.extend(["--site-root", site_root])
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_pages_seo_check_accepts_public_sitemap_without_origin_root_robots():
    """Project Pages can publish a sitemap without pretending to own /robots.txt."""
    with tempfile.TemporaryDirectory(prefix="pages-seo-ok-") as tmp:
        result = _check(_fixture(Path(tmp)))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "APTO" in result.stdout


def test_pages_seo_check_accepts_dashboard_and_comparisons_in_public_sitemap():
    """The static vitrina dashboard and comparison pages ARE intentionally public
    (dashboard.html is a serverless vitrina page, comparisons are pre-existing
    honest docs published to Pages). The gate must accept them. See t_4a5d2f29."""
    with tempfile.TemporaryDirectory(prefix="pages-seo-dashboard-ok-") as tmp:
        static_dir = _fixture(
            Path(tmp),
            [
                "/",
                "/cloud.html",
                "/dashboard.html",
                "/manual.html",
                "/web.html",
                "/whitelabel.html",
                "/comparisons/lucidfence-vs-intune.html",
                "/comparisons/lucidfence-vs-jamf.html",
                "/comparisons/lucidfence-vs-kandji.html",
            ],
        )
        result = _check(static_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "APTO" in result.stdout


def test_pages_seo_check_rejects_site_root_prefix_collision():
    """A sibling URL that merely starts with site_root is outside the project."""
    with tempfile.TemporaryDirectory(prefix="pages-seo-boundary-") as tmp:
        static_dir = _fixture(Path(tmp))
        sitemap = static_dir / "sitemap.xml"
        sitemap.write_text(
            sitemap.read_text(encoding="utf-8").replace(
                f"{SITE_ROOT}/cloud.html", f"{SITE_ROOT}cloud.html"
            ),
            encoding="utf-8",
        )
        result = _check(static_dir)

    assert result.returncode == 1
    assert "fuera de site-root" in result.stdout


def test_pages_seo_check_rejects_missing_public_page_url():
    """Every intentionally public page must remain discoverable in the sitemap."""
    with tempfile.TemporaryDirectory(prefix="pages-seo-missing-url-") as tmp:
        result = _check(
            _fixture(Path(tmp), ["/", "/cloud.html", "/web.html", "/whitelabel.html"])
        )

    assert result.returncode == 1
    assert "manual.html" in result.stdout


def test_pages_seo_check_rejects_static_segment_in_existing_canonical():
    """Existing canonicals cannot point at the non-deployed source directory."""
    with tempfile.TemporaryDirectory(prefix="pages-seo-canonical-") as tmp:
        static_dir = _fixture(Path(tmp))
        cloud = static_dir / "cloud.html"
        cloud.write_text(
            cloud.read_text(encoding="utf-8").replace(
                'href="cloud.html"', 'href="/static/cloud.html"'
            ),
            encoding="utf-8",
        )
        result = _check(static_dir)

    assert result.returncode == 1
    assert "/static/" in result.stdout


def test_pages_seo_check_rejects_root_relative_canonical_outside_project():
    """A domain-root URL must not escape the GitHub Project Pages prefix."""
    with tempfile.TemporaryDirectory(prefix="pages-seo-root-relative-") as tmp:
        static_dir = _fixture(Path(tmp))
        cloud = static_dir / "cloud.html"
        cloud.write_text(
            cloud.read_text(encoding="utf-8").replace(
                'href="cloud.html"', 'href="/cloud.html"'
            ),
            encoding="utf-8",
        )
        result = _check(static_dir)

    assert result.returncode == 1
    assert "fuera de site-root" in result.stdout


def test_pages_seo_check_rejects_external_og_url():
    """Existing Open Graph URLs cannot advertise an external host."""
    with tempfile.TemporaryDirectory(prefix="pages-seo-external-og-") as tmp:
        static_dir = _fixture(Path(tmp))
        cloud = static_dir / "cloud.html"
        cloud.write_text(
            cloud.read_text(encoding="utf-8").replace(
                "</head>",
                '<meta property="og:url" '
                'content="https://outside.example/lucidfence/cloud.html">'
                "</head>",
            ),
            encoding="utf-8",
        )
        result = _check(static_dir)

    assert result.returncode == 1
    assert "host externo" in result.stdout


def test_pages_seo_check_rejects_canonical_for_a_different_page():
    """A page cannot canonicalize itself to another page in the project."""
    with tempfile.TemporaryDirectory(prefix="pages-seo-mismatch-") as tmp:
        static_dir = _fixture(Path(tmp))
        cloud = static_dir / "cloud.html"
        cloud.write_text(
            cloud.read_text(encoding="utf-8").replace(
                'href="cloud.html"', 'href="manual.html"'
            ),
            encoding="utf-8",
        )
        result = _check(static_dir)

    assert result.returncode == 1
    assert "no apunta a su propia ruta" in result.stdout


def test_pages_seo_check_accepts_same_page_absolute_and_project_root_urls():
    """Correct absolute and project-root metadata resolve to the declaring page."""
    with tempfile.TemporaryDirectory(prefix="pages-seo-valid-metadata-") as tmp:
        static_dir = _fixture(Path(tmp))
        cloud = static_dir / "cloud.html"
        cloud.write_text(
            cloud.read_text(encoding="utf-8")
            .replace(
                'href="cloud.html"',
                f'href="{SITE_ROOT}/cloud.html"',
            )
            .replace(
                "</head>",
                '<meta property="og:url" content="/lucidfence/cloud.html">'
                "</head>",
            ),
            encoding="utf-8",
        )
        result = _check(static_dir)

    assert result.returncode == 0, result.stdout + result.stderr


def test_pages_seo_check_rejects_duplicate_sitemap_url():
    """Duplicate URLs make the discovery contract ambiguous."""
    with tempfile.TemporaryDirectory(prefix="pages-seo-duplicate-") as tmp:
        result = _check(
            _fixture(
                Path(tmp),
                [
                    "/",
                    "/cloud.html",
                    "/cloud.html",
                    "/manual.html",
                    "/web.html",
                    "/whitelabel.html",
                ],
            )
        )

    assert result.returncode == 1
    assert "duplicada" in result.stdout


def test_pages_seo_check_rejects_external_sitemap_host():
    """Every sitemap URL must use the configured GitHub Pages host."""
    with tempfile.TemporaryDirectory(prefix="pages-seo-host-") as tmp:
        static_dir = _fixture(Path(tmp))
        sitemap = static_dir / "sitemap.xml"
        sitemap.write_text(
            sitemap.read_text(encoding="utf-8").replace(
                f"{SITE_ROOT}/cloud.html",
                "https://outside.example/lucidfence/cloud.html",
            ),
            encoding="utf-8",
        )
        result = _check(static_dir)

    assert result.returncode == 1
    assert "fuera de site-root" in result.stdout


def test_pages_seo_check_rejects_missing_public_file():
    """A listed URL must resolve to a file in the Pages artifact."""
    with tempfile.TemporaryDirectory(prefix="pages-seo-missing-file-") as tmp:
        static_dir = _fixture(Path(tmp))
        (static_dir / "manual.html").unlink()
        result = _check(static_dir)

    assert result.returncode == 1
    assert "falta la página pública manual.html" in result.stdout


def test_repository_sitemap_matches_public_page_contract():
    """The checked-in artifact itself must satisfy the same deploy gate."""
    result = _check(ROOT / "static", site_root=None)

    assert result.returncode == 0, result.stdout + result.stderr


def test_pages_workflow_copies_once_and_runs_a_blocking_gate():
    """The build has one source copy and cannot downgrade the SEO gate."""
    workflow = (ROOT / ".github" / "workflows" / "publish-pages.yml").read_text(
        encoding="utf-8"
    )

    assert workflow.count("cp -rL static/* _site/") == 1
    assert "cp static/sitemap.xml" not in workflow
    assert "cp static/robots.txt" not in workflow
    assert "python3 scripts/pages_seo_check.py --static-dir _site" in workflow
    assert "continue-on-error" not in workflow
    assert "grep_status=$?" in workflow
    assert '[ "$grep_status" -gt 1 ]' in workflow
    assert "project Pages/self-hosting" not in workflow
