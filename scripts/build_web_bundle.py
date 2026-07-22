#!/usr/bin/env python3
"""Build a deterministic, owner-neutral LucidFence Web self-host bundle."""
from __future__ import annotations

import argparse
import hashlib
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
DEPLOY = ROOT / "deploy" / "web"
ASSETS = (
    "web.html",
    "web-core.js",
    "web-store.js",
    "web-app.js",
    "web-worker.js",
    "sw.js",
    "manifest.webmanifest",
    "lucidfence-icon.svg",
)
DEPLOY_FILES = ("Dockerfile", "nginx.conf", "Caddyfile", "github-pages.yml")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output: Path) -> tuple[Path, Path]:
    bundle = output / "lucidfence-web"
    archive = output / "lucidfence-web.zip"
    if bundle.exists():
        shutil.rmtree(bundle)
    output.mkdir(parents=True, exist_ok=True)
    bundle.mkdir()
    for name in ASSETS:
        shutil.copy2(STATIC / name, bundle / name)
    # A self-hosted customer's root opens the app, not a vendor-owned landing page.
    shutil.copy2(STATIC / "web.html", bundle / "index.html")
    shutil.copy2(DEPLOY / "SELF_HOST.md", bundle / "SELF_HOST.md")
    deploy_out = bundle / "deploy"
    deploy_out.mkdir()
    for name in DEPLOY_FILES:
        shutil.copy2(DEPLOY / name, deploy_out / name)

    files = sorted(path for path in bundle.rglob("*") if path.is_file())
    lines = [f"{sha256(path)}  {path.relative_to(bundle).as_posix()}" for path in files]
    (bundle / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(p for p in bundle.rglob("*") if p.is_file()):
            relative = Path("lucidfence-web") / path.relative_to(bundle)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return bundle, archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    bundle, archive = build(args.output.resolve())
    print(bundle)
    print(archive)
    print(sha256(archive))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
