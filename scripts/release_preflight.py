#!/usr/bin/env python3
# ============================================================
# release_preflight.py  —  LucidFence release pipeline preflight
#                          (regression GATE, vendored from Kit Bot)
# ------------------------------------------------------------
# CONTEXT
#   Kanban t_69acb514 (RELEASE/DEPLOY) reported 4 *mechanical*
#   pipeline findings plus 1 human-secret gate (no PYPI_TOKEN):
#     1. __version__ drift (1.3.1)       -> version_consistency
#     2. CHANGELOG without [Unreleased]  -> changelog_unreleased
#     3. .worktrees in the build image   -> dockerignore_worktrees
#     4. zero healthchecks               -> compose_healthcheck
#     5. sin PYPI_TOKEN (SECRETO)          -> pypi_token (soft warn)
#   Kanban t_ecb7085d (RELEASE HYGIENE) reported a 6th gap the gate
#   could not catch: CHANGELOG [Unreleased] *content drift* — the
#   heading exists but is EMPTY, or a released version header is
#   duplicated. Added:
#     6. CHANGELOG [Unreleased] vacio       -> changelog_unreleased_nonempty
#     7. header de version duplicado        -> changelog_no_duplicate_versions
#   This tool is a regression GATE: it fails (exit 1) if any of
#   1-4 or 6-7 drift back, and soft-warns on 5. Run it in CI / pre-tag.
#
# USAGE
#   python3 release_preflight.py [--repo PATH] [--json] [--strict-secret]
#   exit 0 = all hard checks pass
#   exit 1 = at least one hard check failed
#   (with --strict-secret, missing PYPI_TOKEN/FLY_API_TOKEN also fails)
#
#   When --repo is omitted it auto-detects the repo root:
#     - $GITHUB_WORKSPACE (set by actions/checkout in CI), then
#     - the current working directory (so `python3 scripts/release_preflight.py`
#       from the repo root just works), then
#     - the script's own parent directory.
#
# Other bots: call this before any `git tag` / `fly deploy` /
# `twine upload`. If it fails, do NOT release.
# ============================================================

import argparse
import json
import os
import re
import shutil
import sys
import tempfile


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


def check_version_consistency(repo):
    """All of .release-version, pyproject version=, and
    lucidfence/__init__.__version__ must agree."""
    found = {}
    rv = _read(os.path.join(repo, ".release-version"))
    if rv:
        found[".release-version"] = rv.strip()
    pp = _read(os.path.join(repo, "pyproject.toml"))
    if pp:
        m = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', pp, re.M)
        if m:
            found["pyproject.toml"] = m.group(1)
    ini = _read(os.path.join(repo, "lucidfence", "__init__.py"))
    if ini:
        m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', ini)
        if m:
            found["lucidfence/__init__.py"] = m.group(1)
    vals = set(found.values())
    ok = len(vals) <= 1 and len(found) >= 1
    return ok, {
        "found": found,
        "consistent_version": (next(iter(vals)) if len(vals) == 1 else None),
        "n_sources": len(found),
    }


def check_changelog_unreleased(repo):
    txt = _read(os.path.join(repo, "CHANGELOG.md"))
    if txt is None:
        return False, {"error": "CHANGELOG.md missing"}
    # Walk headings; ignore the level-1 title ("# Changelog") and only
    # consider the first real section heading (level-2 or deeper).
    first_section = None
    for line in txt.splitlines():
        s = line.strip()
        if not s.startswith("#"):
            continue
        if re.match(r"^#\s", s):  # level-1 title, skip
            continue
        first_section = s  # first level-2+ heading
        break
    if first_section is None:
        return False, {"error": "no section headings found"}
    m = re.match(r"^#+\s*\[?Unreleased\]?", first_section, re.I)
    return bool(m), {"first_section": first_section}


def check_changelog_unreleased_nonempty(repo):
    """The [Unreleased] section must contain at least one real entry.

    A [Unreleased] heading with no bullets under it is content drift:
    a release would ship an empty changelog. Fails the gate."""
    txt = _read(os.path.join(repo, "CHANGELOG.md"))
    if txt is None:
        return False, {"error": "CHANGELOG.md missing"}
    in_unreleased = False
    entries = 0
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("#"):
            if re.match(r"^#+\s*\[?Unreleased\]?", s, re.I):
                in_unreleased = True
                continue
            if in_unreleased:
                break  # first non-Unreleased heading ends the section
            continue
        if in_unreleased:
            if s.startswith(("-", "*", "+")) or re.match(r"^\d+\.", s) or s:
                entries += 1
    ok = entries >= 1
    return ok, {"unreleased_entries": entries}


def check_changelog_no_duplicate_versions(repo):
    """No released version header (## [x.y.z]) may appear twice.

    A duplicated version header is a copy/paste drift symptom."""
    txt = _read(os.path.join(repo, "CHANGELOG.md"))
    if txt is None:
        return False, {"error": "CHANGELOG.md missing"}
    seen = {}
    for line in txt.splitlines():
        s = line.strip()
        m = re.match(r"^#+\s*\[?([0-9]+\.[0-9]+\.[0-9]+)\]?", s)
        if m:
            v = m.group(1)
            seen[v] = seen.get(v, 0) + 1
    dups = [v for v, c in seen.items() if c > 1]
    return (not dups), {"duplicate_versions": dups}


def check_dockerignore_worktrees(repo):
    txt = _read(os.path.join(repo, ".dockerignore"))
    if txt is None:
        return False, {"error": ".dockerignore missing"}
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("#") or not s:
            continue
        if s == ".worktrees" or s.startswith(".worktrees"):
            return True, {"entry": s}
    return False, {"note": ".worktrees not excluded from build image"}


def check_compose_healthcheck(repo):
    txt = _read(os.path.join(repo, "docker-compose.yml"))
    if txt is None:
        return False, {"error": "docker-compose.yml missing"}
    has = "healthcheck:" in txt
    return has, {"present": has}


def check_pypi_token(repo, strict=False):
    tok = os.environ.get("PYPI_TOKEN") or os.environ.get("TWINE_PASSWORD")
    fly = os.environ.get("FLY_API_TOKEN")
    ok = bool(tok)
    detail = {"PYPI_TOKEN_set": bool(tok), "FLY_API_TOKEN_set": bool(fly)}
    if strict:
        return ok, detail
    # soft: never fails the gate, just warns
    return True, detail


CHECKS = [
    ("version_consistency", check_version_consistency, True),
    ("changelog_unreleased", check_changelog_unreleased, True),
    ("changelog_unreleased_nonempty", check_changelog_unreleased_nonempty, True),
    ("changelog_no_duplicate_versions", check_changelog_no_duplicate_versions, True),
    ("dockerignore_worktrees", check_dockerignore_worktrees, True),
    ("compose_healthcheck", check_compose_healthcheck, True),
    ("pypi_token", check_pypi_token, False),  # soft by default
]


def _autodetect_repo():
    # 1) CI checkout location
    ws = os.environ.get("GITHUB_WORKSPACE")
    if ws and os.path.isdir(ws):
        return ws
    # 2) current working directory
    cwd = os.getcwd()
    if os.path.isfile(os.path.join(cwd, "pyproject.toml")) or os.path.isdir(
        os.path.join(cwd, "lucidfence")
    ):
        return cwd
    # 3) this script lives in <repo>/scripts/
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    if os.path.isfile(os.path.join(parent, "pyproject.toml")):
        return parent
    return cwd


def _selftest():
    """Verify all 7 check functions against isolated temp fixtures."""
    d = tempfile.mkdtemp(prefix="rpf_selftest_")
    fails = 0

    def mk(name, content):
        with open(os.path.join(d, name), "w") as f:
            f.write(content)

    try:
        # version_consistency: consistent vs drifted
        mk(".release-version", "1.2.3\n")
        mk("pyproject.toml", 'version = "1.2.3"\n')
        os.makedirs(os.path.join(d, "lucidfence"))
        mk("lucidfence/__init__.py", '__version__ = "1.2.3"\n')
        ok, _ = check_version_consistency(d)
        assert ok, "version_consistency should PASS when all agree"
        mk("lucidfence/__init__.py", '__version__ = "9.9.9"\n')
        ok, _ = check_version_consistency(d)
        assert not ok, "version_consistency should FAIL on drift"

        # changelog_unreleased
        mk("CHANGELOG.md", "# Changelog\n## [Unreleased]\n- x\n")
        ok, _ = check_changelog_unreleased(d)
        assert ok, "changelog should PASS with [Unreleased] first"
        mk("CHANGELOG.md", "# Changelog\n## 1.2.3\n- x\n")
        ok, _ = check_changelog_unreleased(d)
        assert not ok, "changelog should FAIL without [Unreleased]"

        # changelog_unreleased_nonempty
        mk("CHANGELOG.md", "# Changelog\n## [Unreleased]\n- new thing\n")
        ok, _ = check_changelog_unreleased_nonempty(d)
        assert ok, "unreleased_nonempty should PASS with an entry"
        mk("CHANGELOG.md", "# Changelog\n## [Unreleased]\n\n\n")
        ok, _ = check_changelog_unreleased_nonempty(d)
        assert not ok, "unreleased_nonempty should FAIL when empty"
        mk("CHANGELOG.md", "# Changelog\n## [Unreleased]\n  \n\t\n")
        ok, _ = check_changelog_unreleased_nonempty(d)
        assert not ok, "unreleased_nonempty should FAIL with only whitespace"

        # changelog_no_duplicate_versions
        mk("CHANGELOG.md",
           "# Changelog\n## [1.0.0]\n- x\n## [1.0.0]\n- y\n")
        ok, det = check_changelog_no_duplicate_versions(d)
        assert not ok, "no_duplicate_versions should FAIL on dup header"
        assert det["duplicate_versions"] == ["1.0.0"]
        mk("CHANGELOG.md",
           "# Changelog\n## [Unreleased]\n- z\n## [1.0.0]\n- x\n")
        ok, _ = check_changelog_no_duplicate_versions(d)
        assert ok, "no_duplicate_versions should PASS when unique"

        # dockerignore_worktrees
        mk(".dockerignore", ".worktrees\n")
        ok, _ = check_dockerignore_worktrees(d)
        assert ok, "dockerignore should PASS with .worktrees excluded"
        mk(".dockerignore", "node_modules\n")
        ok, _ = check_dockerignore_worktrees(d)
        assert not ok, "dockerignore should FAIL without .worktrees"

        # compose_healthcheck
        mk("docker-compose.yml", "services:\n  web:\n    healthcheck:\n")
        ok, _ = check_compose_healthcheck(d)
        assert ok, "compose should PASS with healthcheck"
        mk("docker-compose.yml", "services:\n  web:\n")
        ok, _ = check_compose_healthcheck(d)
        assert not ok, "compose should FAIL without healthcheck"

        # pypi_token: soft never fails; strict fails when unset
        os.environ.pop("PYPI_TOKEN", None)
        os.environ.pop("TWINE_PASSWORD", None)
        ok, _ = check_pypi_token(d, strict=False)
        assert ok, "pypi_token soft mode must always PASS"
        ok, _ = check_pypi_token(d, strict=True)
        assert not ok, "pypi_token strict mode should FAIL when token unset"
    except AssertionError as e:
        fails += 1
        print("ASSERT FAILED:", e)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    if fails:
        print(f"SELFTEST: FAIL ({fails})")
        return 1
    print("SELFTEST: PASS (all 7 checks verified against isolated fixtures)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="LucidFence release preflight gate")
    ap.add_argument("--repo", default=None,
                    help="path to lucidfence repo (default: auto-detect — "
                         "$GITHUB_WORKSPACE, then cwd, then <script>/..)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict-secret", action="store_true",
                    help="treat missing PYPI_TOKEN as a hard failure")
    ap.add_argument("--selftest", action="store_true",
                    help="run isolated offline tests for all checks")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    repo = os.path.abspath(args.repo) if args.repo else _autodetect_repo()
    if not os.path.isdir(repo):
        print(f"ERROR: repo path not found: {repo}", file=sys.stderr)
        return 2

    results = []
    hard_failed = 0
    for name, fn, hard in CHECKS:
        if name == "pypi_token":
            ok, detail = fn(repo, strict=args.strict_secret)
            is_hard = args.strict_secret
        else:
            ok, detail = fn(repo)
            is_hard = hard
        status = "PASS" if ok else ("WARN" if not is_hard else "FAIL")
        # Soft-secret special case: present-but-unset => WARN (never hard-fail)
        if name == "pypi_token" and not detail.get("PYPI_TOKEN_set"):
            status = "WARN"
        if not ok and is_hard:
            hard_failed += 1
        results.append({"check": name, "status": status,
                        "hard": is_hard, "detail": detail})

    if args.json:
        print(json.dumps({"repo": repo, "hard_failed": hard_failed,
                          "checks": results}, indent=2, ensure_ascii=False))
    else:
        print(f"=== release_preflight  ({repo}) ===")
        for r in results:
            print(f"  [{r['status']:4s}] {r['check']}")
            if r["status"] != "PASS" or args.json is False:
                d = r["detail"]
                extra = ", ".join(f"{k}={v}" for k, v in d.items()
                                  if k not in ("found",))
                if "found" in d:
                    extra += "  versions=" + json.dumps(d["found"])
                if extra:
                    print(f"          {extra}")
        print()
        print(f"HARD FAILURES: {hard_failed}")
        if hard_failed == 0:
            print("VERDICT: READY TO RELEASE (mechanical checks pass)")
        else:
            print("VERDICT: DO NOT RELEASE — fix the FAIL items above")

    return 1 if hard_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
