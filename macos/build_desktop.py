#!/usr/bin/env python3
"""Build a self-contained LucidFence.app and drag-to-Applications DMG on macOS."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MACOS = ROOT / "macos"
BUILD = ROOT / "build" / "macos-desktop"
DIST = ROOT / "dist"
DEFAULT_VERSION = "1.2.0"
PYINSTALLER_VERSION = "6.16.0"
MINIMUM_MACOS = "14.0"
SAFE_SEEDS = ("fleet_seed.json", "fences.json", "routes.json", "policies.json")
ATOMICMAIL_MODULES = (
    "core.atomicmail.auth_http", "core.atomicmail.config", "core.atomicmail.constants",
    "core.atomicmail.credentials", "core.atomicmail.help", "core.atomicmail.jmap_request",
    "core.atomicmail.jwt_utils", "core.atomicmail.pow", "core.atomicmail.session",
    "core.atomicmail.shared_assets",
)


def run(command: list[str], *, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, env=env, check=check, text=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_builder_python(skip_dependencies: bool) -> Path:
    venv_dir = BUILD / "builder-venv"
    python = venv_dir / "bin" / "python3"
    if skip_dependencies:
        if not python.exists():
            raise RuntimeError("--skip-dependencies requires an existing locked builder venv")
        return python
    shutil.rmtree(venv_dir, ignore_errors=True)
    base = Path("/usr/bin/python3")
    print(f"Creating clean isolated builder with {base}")
    subprocess.run([str(base), "-m", "venv", str(venv_dir)], check=True)
    run([
        str(python), "-m", "pip", "install", "--disable-pip-version-check",
        "--require-hashes", "-r", str(MACOS / "requirements-build.lock"),
        "-r", str(ROOT / "requirements.lock"),
    ])
    return python


def build_backend(python: Path) -> Path:
    backend_dist = BUILD / "backend-dist"
    work = BUILD / "pyinstaller-work"
    spec = BUILD / "pyinstaller-spec"
    for path in (backend_dist, work, spec):
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)

    command = [
        str(python), "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
        "--name", "LucidFenceBackend", "--distpath", str(backend_dist),
        "--workpath", str(work), "--specpath", str(spec), "--paths", str(ROOT),
        "--collect-submodules", "core", "--collect-submodules", "saas",
        "--add-data", f"{ROOT / 'static'}:static",
        "--add-data", f"{MACOS / 'config.desktop.json'}:.",
        "--add-data", f"{ROOT / 'core' / 'atomicmail' / 'vendor_shared'}:core/atomicmail/vendor_shared",
    ]
    for module in ATOMICMAIL_MODULES:
        command += ["--hidden-import", module]
    for name in SAFE_SEEDS:
        seed = ROOT / "data" / name
        if not seed.is_file():
            raise FileNotFoundError(f"Required safe seed missing: {seed}")
        command += ["--add-data", f"{seed}:data"]
    command.append(str(ROOT / "saas_server.py"))
    analysis_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
        "HOME": str(Path.home()),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "ATOMIC_MAIL_SHARED_DIR": str(ROOT / "core" / "atomicmail" / "vendor_shared"),
    }
    for key in ("LANG", "LC_ALL"):
        if key in os.environ:
            analysis_env[key] = os.environ[key]
    run(command, env=analysis_env)

    bundled = backend_dist / "LucidFenceBackend"
    executable = bundled / "LucidFenceBackend"
    if not executable.is_file():
        raise RuntimeError(f"PyInstaller backend missing: {executable}")
    return bundled


def build_app(version: str, backend: Path, identity: str) -> Path:
    app = DIST / "LucidFence.app"
    shutil.rmtree(app, ignore_errors=True)
    macos_dir = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    macos_dir.mkdir(parents=True)
    resources.mkdir(parents=True)

    swift_env = dict(os.environ)
    swift_env["MACOSX_DEPLOYMENT_TARGET"] = MINIMUM_MACOS
    swift_target = f"{platform.machine().lower()}-apple-macosx{MINIMUM_MACOS}"
    run([
        "/usr/bin/swiftc", "-O", "-target", swift_target,
        "-framework", "AppKit", "-framework", "WebKit",
        "-o", str(macos_dir / "LucidFence"), str(MACOS / "LucidFenceApp.swift"),
    ], env=swift_env)

    template = (MACOS / "Info.plist").read_text(encoding="utf-8")
    (app / "Contents" / "Info.plist").write_text(
        template.replace("__VERSION__", version), encoding="utf-8"
    )
    shutil.copy2(MACOS / "Resources" / "lucidfence.icns", resources / "lucidfence.icns")
    shutil.copytree(backend, resources / "backend")

    run(["/usr/bin/plutil", "-lint", str(app / "Contents" / "Info.plist")])
    run(["/usr/bin/xattr", "-cr", str(app)])
    sign_args = ["/usr/bin/codesign", "--force", "--deep", "--sign", identity]
    if identity != "-":
        sign_args += ["--options", "runtime", "--timestamp"]
    sign_args.append(str(app))
    run(sign_args)
    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)])
    return app


def build_dmg(app: Path, version: str, arch: str) -> Path:
    stage = BUILD / "dmg-stage"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    shutil.copytree(app, stage / "LucidFence.app", symlinks=True)
    os.symlink("/Applications", stage / "Applications")

    dmg = DIST / f"LucidFence-{version}-{arch}.dmg"
    dmg.unlink(missing_ok=True)
    run([
        "/usr/bin/hdiutil", "create", "-volname", "LucidFence",
        "-srcfolder", str(stage), "-ov", "-format", "UDZO", str(dmg),
    ])
    run(["/usr/bin/hdiutil", "verify", str(dmg)])
    return dmg


def notarize_if_configured(dmg: Path) -> bool:
    profile = os.environ.get("LUCIDFENCE_NOTARY_PROFILE", "").strip()
    if not profile:
        return False
    run(["/usr/bin/xcrun", "notarytool", "submit", str(dmg), "--keychain-profile", profile, "--wait"])
    run(["/usr/bin/xcrun", "stapler", "staple", str(dmg)])
    run(["/usr/bin/xcrun", "stapler", "validate", str(dmg)])
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--skip-dependencies", action="store_true")
    parser.add_argument("--no-dmg", action="store_true")
    parser.add_argument("--allow-adhoc", action="store_true",
                        help="Allow a QA-only ad-hoc build that Gatekeeper will reject")
    args = parser.parse_args()
    if sys.platform != "darwin":
        raise SystemExit("This builder must run on macOS")
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        raise SystemExit("Version must use semantic X.Y.Z format")
    identity = os.environ.get("LUCIDFENCE_CODESIGN_IDENTITY", "-").strip() or "-"
    if identity == "-" and not args.allow_adhoc:
        raise SystemExit("Release build requires LUCIDFENCE_CODESIGN_IDENTITY; use --allow-adhoc only for local QA")

    DIST.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    python = prepare_builder_python(args.skip_dependencies)
    backend = build_backend(python)
    app = build_app(args.version, backend, identity)
    arch = platform.machine().lower()
    dmg = None if args.no_dmg else build_dmg(app, args.version, arch)
    notarized = bool(dmg and notarize_if_configured(dmg))

    # spctl rejects ad-hoc signatures by design. Record the assessment honestly;
    # a Developer ID + notarization profile turns this into a distributable PASS.
    assessment = run(["/usr/sbin/spctl", "--assess", "--type", "execute", "--verbose=2", str(app)], check=False)
    release_ready = identity != "-" and notarized and assessment.returncode == 0
    manifest = {
        "product": "LucidFence Desktop",
        "version": args.version,
        "architecture": arch,
        "minimum_macos": MINIMUM_MACOS,
        "app": app.name,
        "dmg": dmg.name if dmg else None,
        "dmg_sha256": sha256(dmg) if dmg else None,
        "codesign_identity": identity,
        "notarized": notarized,
        "spctl_exit_code": assessment.returncode,
        "release_ready": release_ready,
        "safe_seeds": list(SAFE_SEEDS),
    }
    manifest_path = DIST / f"LucidFence-{args.version}-{arch}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
