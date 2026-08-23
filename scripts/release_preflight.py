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
#     5. missing PYPI_TOKEN (SECRET)     -> pypi_token (soft warn)
#   Kanban t_98e9b754 (RELEASE/DEPLOY hazard) added a 6th hard gate:
#     6. docs/README.md index regression -> docs_readme_index
#        The `marketing-outbox-2026-08-20` branch carries a STALE copy of
#        docs/README.md (missing GETTING_STARTED, demo-walkthrough, apple_ddm,
#        windows_dsc, new-adapter-guide, adapters/FLEET, NETWORK_LOCATION, ...).
#        A 3-way merge onto main currently keeps main's newer index, but if
#        that branch ever re-touches the file the stale copy could win silently.
#        This gate fails the moment any canonical doc is no longer linked.
#   This tool is a regression GATE: it fails (exit 1) if any of
#   1-4 or 6 drift back, and soft-warns on 5. Run it in CI / pre-tag.
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
import subprocess
import sys

DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"


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


# Canonical docs/README.md entries that must ALWAYS be linked on main.
# Sourced from issue #191 (t_90a94690 / t_98e9b754): these are the files whose
# index entries would be silently dropped if the stale marketing-outbox copy of
# docs/README.md ever wins a merge. Each entry is matched as a markdown link
# target ([...](<path>) or a directory token) inside docs/README.md.
DOCS_INDEX_REQUIRED = [
    # path, human label
    ("GETTING_STARTED.md",                 "GETTING_STARTED"),
    ("demo-walkthrough.md",                "demo-walkthrough"),
    ("architecture/AI_AND_MCP.md",         "AI_AND_MCP"),
    ("operations/apple_ddm.md",            "apple_ddm"),
    ("operations/windows_dsc.md",          "windows_dsc"),
    ("contributing/new-adapter-guide.md",  "new-adapter-guide"),
    ("adapters/FLEET.md",                  "adapters/FLEET"),
    ("integrations/NETWORK_LOCATION.md",   "NETWORK_LOCATION"),
]


def check_docs_readme_index(repo):
    """docs/README.md must link every canonical doc from #191.

    Hard gate (t_98e9b754): the `marketing-outbox-2026-08-20` branch carries a
    STALE docs/README.md missing all the entries below. A 3-way merge onto main
    currently keeps main's newer index, but if that branch re-touches the file
    the stale copy could win silently. Fail the moment any required entry is no
    longer linked, so the regression can never merge.
    """
    path = os.path.join(repo, "docs", "README.md")
    txt = _read(path)
    if txt is None:
        return False, {"error": "docs/README.md missing"}
    # Build the set of link targets (the text inside the trailing parentheses
    # of each markdown link) plus any bare directory tokens.
    link_targets = set(re.findall(r"\]\(([^)]+)\)", txt))
    missing = []
    for rel, label in DOCS_INDEX_REQUIRED:
        # Match either a direct link to the file, or a link to its directory
        # (e.g. `adapters/` covers `adapters/FLEET.md`). Strip any anchor.
        base = rel.split("#", 1)[0]
        dir_of = base.rsplit("/", 1)[0] + "/" if "/" in base else None
        hit = any(
            t.split("#", 1)[0].rstrip("/") == base.rstrip("/")
            or (dir_of and t.split("#", 1)[0].rstrip("/") == dir_of.rstrip("/"))
            for t in link_targets
        )
        if not hit:
            missing.append(label)
    ok = len(missing) == 0
    return ok, {"missing": missing, "n_required": len(DOCS_INDEX_REQUIRED)}


def check_pypi_token(repo, strict=False):
    tok = os.environ.get("PYPI_TOKEN") or os.environ.get("TWINE_PASSWORD")
    fly = os.environ.get("FLY_API_TOKEN")
    ok = bool(tok)
    detail = {"PYPI_TOKEN_set": bool(tok), "FLY_API_TOKEN_set": bool(fly)}
    if strict:
        return ok, detail
    # soft: never fails the gate, just warns
    return True, detail


# ---------------------------------------------------------------------------
# Provenance / SBOM release checks (t_f455bc58 / #233)
# HARD checks, but only engage when the operator passes the release artifact
# + sbom + dsse envelope (see --artifact/--sbom/--dsse). Daily preflight is
# unaffected when these are omitted.
# ---------------------------------------------------------------------------
def _read_project_version(repo):
    pp = _read(os.path.join(repo, "pyproject.toml"))
    if pp:
        m = re.search(r'^version\s*=\s*[\"\']([^\"\']+)[\"\']', pp, re.M)
        if m:
            return m.group(1)
    return None


def check_sbom_present(repo, artifact=None, sbom=None, dsse=None):
    path = sbom or os.path.join(repo, "sbom.cdx.json")
    if not os.path.isfile(path):
        return False, {"error": f"sbom missing: {path}"}
    try:
        import json as _json
        data = _json.loads(_read(path))
    except Exception as exc:  # noqa: BLE001
        return False, {"error": f"sbom not parseable: {exc}"}
    ok = data.get("bomFormat") == "CycloneDX" and data.get("specVersion") == "1.5"
    return ok, {"path": path, "bomFormat": data.get("bomFormat"),
                "specVersion": data.get("specVersion")}


def check_provenance_present(repo, artifact=None, sbom=None, dsse=None):
    path = dsse or os.path.join(repo, "provenance.dsse.json")
    if not os.path.isfile(path):
        return False, {"error": f"provenance envelope missing: {path}"}
    try:
        import base64
        import json as _json
        env = _json.loads(_read(path))
        if env.get("payloadType") != DSSE_PAYLOAD_TYPE:
            return False, {"error": f"unexpected payloadType: {env.get('payloadType')}"}
        statement = _json.loads(base64.b64decode(env["payload"]))
        return True, {"path": path,
                      "predicateType": statement.get("predicateType"),
                      "subject": statement.get("subject", [{}])[0].get("name")}
    except Exception as exc:  # noqa: BLE001
        return False, {"error": f"provenance not parseable: {exc}"}


def check_prov_artifact_match(repo, artifact=None, sbom=None, dsse=None):
    dsse_path = dsse or os.path.join(repo, "provenance.dsse.json")
    art_path = artifact
    if not art_path or not os.path.isfile(dsse_path):
        return False, {"error": "need --artifact and --dsse to compare"}
    import base64
    import hashlib
    import json as _json
    env = _json.loads(_read(dsse_path))
    statement = _json.loads(base64.b64decode(env["payload"]))
    expected = statement["subject"][0]["digest"].get("sha256")
    actual = hashlib.sha256(open(art_path, "rb").read()).hexdigest()
    ok = expected == actual
    return ok, {"expected": expected, "actual": actual}


def check_prov_commit_ancestor(repo, artifact=None, sbom=None, dsse=None):
    dsse_path = dsse or os.path.join(repo, "provenance.dsse.json")
    if not os.path.isfile(dsse_path):
        return False, {"error": "provenance envelope missing (need --dsse)"}
    import base64
    import json as _json
    env = _json.loads(_read(dsse_path))
    statement = _json.loads(base64.b64decode(env["payload"]))
    commit = statement["predicate"]["invocation"]["configSource"]["commit"]
    res = subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor",
                          commit, "HEAD"], capture_output=True)
    ok = res.returncode == 0
    return ok, {"commit": commit, "is_ancestor_of_head": ok}


def check_prov_version_match(repo, artifact=None, sbom=None, dsse=None):
    dsse_path = dsse or os.path.join(repo, "provenance.dsse.json")
    if not os.path.isfile(dsse_path):
        return False, {"error": "provenance envelope missing (need --dsse)"}
    import base64
    import json as _json
    env = _json.loads(_read(dsse_path))
    statement = _json.loads(base64.b64decode(env["payload"]))
    pred_version = statement["predicate"]["version"]
    pp_version = _read_project_version(repo)
    rv = _read(os.path.join(repo, ".release-version"))
    rv_version = rv.strip() if rv else None
    versions = {"predicate": pred_version, "pyproject": pp_version}
    if rv_version:
        versions[".release-version"] = rv_version
    ok = len(set(v for v in versions.values() if v)) <= 1
    return ok, {"versions": versions}


CHECKS = [
    ("version_consistency", check_version_consistency, True),
    ("changelog_unreleased", check_changelog_unreleased, True),
    ("dockerignore_worktrees", check_dockerignore_worktrees, True),
    ("compose_healthcheck", check_compose_healthcheck, True),
    ("docs_readme_index", check_docs_readme_index, True),  # t_98e9b754 guard
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


def main():
    ap = argparse.ArgumentParser(description="LucidFence release preflight gate")
    ap.add_argument("--repo", default=None,
                    help="path to lucidfence repo (default: auto-detect — "
                         "$GITHUB_WORKSPACE, then cwd, then <script>/..)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict-secret", action="store_true",
                    help="treat missing PYPI_TOKEN as a hard failure")
    # Provenance / SBOM release checks (t_f455bc58 / #233). Only engage when
    # the operator is actually releasing an artifact.
    ap.add_argument("--artifact", default=None,
                    help="release artifact (e.g. dist/lucidfence-1.6.0.tar.gz) "
                         "— enables the provenance/SBOM hard checks")
    ap.add_argument("--sbom", default=None,
                    help="CycloneDX SBOM path (default: <repo>/sbom.cdx.json)")
    ap.add_argument("--dsse", default=None,
                    help="DSSE provenance envelope (default: "
                         "<repo>/provenance.dsse.json)")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo) if args.repo else _autodetect_repo()
    if not os.path.isdir(repo):
        print(f"ERROR: repo path not found: {repo}", file=sys.stderr)
        return 2

    # Base checklist (always runs).
    checks = list(CHECKS)

    # Provenance / SBOM checks only run when releasing an artifact.
    release_mode = bool(args.artifact)
    if release_mode:
        checks += [
            ("sbom_present", check_sbom_present, True),
            ("provenance_present", check_provenance_present, True),
            ("prov_artifact_match", check_prov_artifact_match, True),
            ("prov_commit_ancestor", check_prov_commit_ancestor, True),
            ("prov_version_match", check_prov_version_match, True),
        ]
    else:
        # Avoid a misleading "PASS" on provenance checks that have no input.
        checks = [c for c in checks if c[0] not in (
            "sbom_present", "provenance_present", "prov_artifact_match",
            "prov_commit_ancestor", "prov_version_match")]

    results = []
    hard_failed = 0
    for name, fn, hard in checks:
        try:
            if name == "pypi_token":
                ok, detail = fn(repo, strict=args.strict_secret)
                is_hard = args.strict_secret
            elif release_mode and name in (
                "sbom_present", "provenance_present", "prov_artifact_match",
                "prov_commit_ancestor", "prov_version_match",
            ):
                ok, detail = fn(repo, artifact=args.artifact,
                                sbom=args.sbom, dsse=args.dsse)
                is_hard = hard
            else:
                ok, detail = fn(repo)
                is_hard = hard
        except Exception as exc:  # noqa: BLE001
            ok, detail, is_hard = False, {"error": f"{type(exc).__name__}: {exc}"}, hard
        status = "PASS" if ok else ("WARN" if not is_hard else "FAIL")
        # Soft-secret special case: present-but-unset => WARN (never hard-fail)
        if name == "pypi_token" and not detail.get("PYPI_TOKEN_set"):
            status = "WARN"
        if not ok and is_hard:
            hard_failed += 1
        results.append({"check": name, "status": status,
                        "hard": is_hard, "detail": detail})

    if args.json:
        print(json.dumps({"repo": repo, "release_mode": release_mode,
                          "hard_failed": hard_failed,
                          "checks": results}, indent=2, ensure_ascii=False))
    else:
        print(f"=== release_preflight  ({repo}) ==="
              + ("  [RELEASE MODE]" if release_mode else ""))
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
