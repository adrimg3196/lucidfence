from __future__ import annotations

import hashlib
import subprocess
import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]


class _CanonicalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "link" and values.get("rel") == "canonical":
            self.href = values.get("href")


def test_web_bundle_is_self_contained_and_owner_neutral():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "dist"
        result = subprocess.run(
            ["python3", "scripts/build_web_bundle.py", "--output", str(out)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
        bundle = out / "lucidfence-web"
        archive = out / "lucidfence-web.zip"
        assert bundle.is_dir() and archive.is_file()
        expected = {
            "index.html", "web.html", "web-core.js", "web-store.js",
            "web-app.js", "web-worker.js", "sw.js", "manifest.webmanifest",
            "lucidfence-icon.svg", "SHA256SUMS", "SELF_HOST.md",
        }
        assert expected <= {p.name for p in bundle.iterdir()}
        assert not list(bundle.rglob("*.py"))
        assert not list(bundle.rglob("saas_server.py"))
        text = "\n".join(p.read_text(errors="ignore") for p in bundle.rglob("*") if p.is_file())
        assert "adrimg3196" not in text
        assert "lucidfence.com" not in text
        assert "127.0.0.1:8765" not in text
        sums = {}
        for line in (bundle / "SHA256SUMS").read_text().splitlines():
            digest, name = line.split("  ", 1)
            sums[name] = digest
        for name, digest in sums.items():
            assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == digest
        with zipfile.ZipFile(archive) as zf:
            names = set(zf.namelist())
            assert "lucidfence-web/web.html" in names
            assert not any(name.endswith(".py") for name in names)


def test_public_page_canonicals_work_for_self_hosting_and_project_pages():
    for page in ("cloud.html", "dashboard.html"):
        parser = _CanonicalParser()
        parser.feed((ROOT / "static" / page).read_text())
        assert parser.href is not None

        for base in (
            f"https://admin.example/static/{page}",
            f"https://example.github.io/lucidfence/{page}",
        ):
            resolved = urlparse(urljoin(base, parser.href))
            assert resolved.path == urlparse(base).path
