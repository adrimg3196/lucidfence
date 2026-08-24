#!/usr/bin/env python3
"""Generate and verify LucidFence's pinned Agency Agents catalog.

Only Markdown profiles and the license are read from the external checkout. No
external script, workflow, executable, or automation is copied or executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


REPOSITORY = "msitarzewski/agency-agents"
COMMIT = "ebe9c99acb5c96f9468de368d8bead775387d1a7"
LICENSE = "MIT"
LICENSE_SHA256 = "9a45258434d5cedf0af73c9ad4771373701225038d246c49219026c33677f66f"
LOCK_SCHEMA = "lucidfence-agency-agents-lock/v1"
CATALOG_SCHEMA = "lucidfence-agency-catalog/v1"
DIVISIONS = (
    "academic",
    "design",
    "engineering",
    "finance",
    "game-development",
    "gis",
    "healthcare",
    "marketing",
    "paid-media",
    "product",
    "project-management",
    "sales",
    "security",
    "spatial-computing",
    "specialized",
    "support",
    "testing",
)
PROFILE_COUNT = 270
INVENTORY_SHA256 = "068aa4b13c1292b27c451955d194fa8ecd027bb6243bef5d813207f90395adda"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_document(value: object) -> bytes:
    return canonical_bytes(value) + b"\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git_head(source: Path) -> str:
    process = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise ValueError("source is not a readable git checkout")
    return process.stdout.strip()


def _require_clean_checkout(source: Path) -> None:
    process = subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise ValueError("source checkout cleanliness could not be verified")
    if process.stdout:
        raise ValueError("source checkout must be clean at the pinned commit")


def build_documents(source: Path) -> tuple[dict, dict]:
    source = source.resolve()
    if _git_head(source) != COMMIT:
        raise ValueError(f"source commit must be exactly {COMMIT}")
    _require_clean_checkout(source)
    license_bytes = (source / "LICENSE").read_bytes()
    if sha256_bytes(license_bytes) != LICENSE_SHA256:
        raise ValueError("source MIT license digest changed")
    if not license_bytes.startswith(b"MIT License\n"):
        raise ValueError("source license is not MIT")

    profiles: list[dict[str, object]] = []
    for division in DIVISIONS:
        directory = source / division
        if not directory.is_dir():
            raise ValueError(f"missing division: {division}")
        for path in sorted(directory.rglob("*.md"), key=lambda item: item.as_posix()):
            relative = path.relative_to(source).as_posix()
            raw = path.read_bytes()
            profiles.append(
                {
                    "bytes": len(raw),
                    "division": division,
                    "path": relative,
                    "sha256": sha256_bytes(raw),
                }
            )

    if len(profiles) != PROFILE_COUNT:
        raise ValueError(f"expected {PROFILE_COUNT} profiles, found {len(profiles)}")

    inventory_sha256 = sha256_bytes(canonical_bytes(profiles))
    if inventory_sha256 != INVENTORY_SHA256:
        raise ValueError("source profile paths or SHA-256 values differ from the fixed inventory")
    lock = {
        "catalog_schema": CATALOG_SCHEMA,
        "division_count": len(DIVISIONS),
        "divisions": list(DIVISIONS),
        "inventory_sha256": inventory_sha256,
        "profile_count": PROFILE_COUNT,
        "profiles": profiles,
        "schema": LOCK_SCHEMA,
        "source": {
            "commit": COMMIT,
            "license": LICENSE,
            "license_sha256": LICENSE_SHA256,
            "repository": REPOSITORY,
        },
    }
    catalog = {
        "lock": lock,
        "profiles": profiles,
        "schema": CATALOG_SCHEMA,
    }
    return lock, catalog


def _read_json(path: Path, errors: list[str]) -> object | None:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        errors.append(f"missing {path.name}: {exc}")
        return None
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid {path.name}: {exc}")
        return None
    if raw != canonical_document(value):
        errors.append(f"{path.name} is not canonical deterministic JSON")
    return value


def verify_repository(root: str | os.PathLike[str]) -> list[str]:
    root_path = Path(root)
    errors: list[str] = []
    lock = _read_json(root_path / "config" / "agency-agents.lock.json", errors)
    catalog = _read_json(root_path / "data" / "agency_catalog.json", errors)
    if not isinstance(lock, dict) or not isinstance(catalog, dict):
        return errors

    source = lock.get("source")
    if source != {
        "commit": COMMIT,
        "license": LICENSE,
        "license_sha256": LICENSE_SHA256,
        "repository": REPOSITORY,
    }:
        errors.append("source pin or MIT license does not match the fixed trust root")
    if lock.get("schema") != LOCK_SCHEMA:
        errors.append("lock schema mismatch")
    if lock.get("catalog_schema") != CATALOG_SCHEMA:
        errors.append("catalog schema binding mismatch")
    if catalog.get("schema") != CATALOG_SCHEMA:
        errors.append("catalog schema mismatch")
    if catalog.get("lock") != lock:
        errors.append("catalog embedded lock differs from repository lock")
    if lock.get("divisions") != list(DIVISIONS):
        errors.append("division paths or ordering changed")
    if lock.get("division_count") != len(DIVISIONS):
        errors.append("division count must be 17")

    profiles = lock.get("profiles")
    if not isinstance(profiles, list):
        errors.append("lock profiles must be a list")
        return errors
    if lock.get("profile_count") != PROFILE_COUNT or len(profiles) != PROFILE_COUNT:
        errors.append("profile count must be exactly 270")
    if catalog.get("profiles") != profiles:
        errors.append("catalog profile inventory differs from lock")
    if lock.get("inventory_sha256") != sha256_bytes(canonical_bytes(profiles)):
        errors.append("profile inventory digest mismatch")
    if lock.get("inventory_sha256") != INVENTORY_SHA256:
        errors.append("profile paths or SHA-256 values differ from the fixed inventory")

    paths: list[str] = []
    for index, profile in enumerate(profiles):
        if not isinstance(profile, dict):
            errors.append(f"profile {index} is not an object")
            continue
        path = profile.get("path")
        division = profile.get("division")
        digest = profile.get("sha256")
        size = profile.get("bytes")
        if not isinstance(path, str) or not path.endswith(".md"):
            errors.append(f"profile {index} has invalid path")
            continue
        paths.append(path)
        if division not in DIVISIONS or not path.startswith(f"{division}/"):
            errors.append(f"profile path is outside canonical division: {path}")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            errors.append(f"profile has invalid SHA-256: {path}")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            errors.append(f"profile has invalid byte length: {path}")
    if paths != sorted(paths):
        errors.append("profile paths are not deterministically sorted")
    if len(set(paths)) != len(paths):
        errors.append("profile paths contain duplicates")
    return errors


def write_documents(root: Path, lock: dict, catalog: dict) -> None:
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "config" / "agency-agents.lock.json").write_bytes(canonical_document(lock))
    (root / "data" / "agency_catalog.json").write_bytes(canonical_document(catalog))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--verify-source", action="store_true")
    args = parser.parse_args(argv)

    if args.write:
        if args.source is None:
            parser.error("--write requires --source")
        lock, catalog = build_documents(args.source)
        write_documents(args.root, lock, catalog)
    elif args.verify_source:
        if args.source is None:
            parser.error("--verify-source requires --source")
        expected_lock, expected_catalog = build_documents(args.source)
        actual_lock = json.loads((args.root / "config" / "agency-agents.lock.json").read_bytes())
        actual_catalog = json.loads((args.root / "data" / "agency_catalog.json").read_bytes())
        if actual_lock != expected_lock or actual_catalog != expected_catalog:
            print("Agency Agents source does not reproduce committed lock/catalog", file=sys.stderr)
            return 1

    errors = verify_repository(args.root)
    for error in errors:
        print(f"FALLO: {error}", file=sys.stderr)
    if errors:
        return 1
    print("AGENCY CATALOG: APTO (270 profiles, 17 divisions, pinned MIT source)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
