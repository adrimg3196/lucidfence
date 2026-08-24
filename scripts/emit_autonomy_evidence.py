#!/usr/bin/env python3
"""Run-derived evidence producer for ``autonomy-evidence.yml``.

The CLI accepts artifact *kinds* and paths, never verdicts, hashes, producers,
repository identity, commits, run identity, or evidence text. Those values are
derived from the GitHub event, git bytes, and the pinned catalog.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from email.parser import Parser
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_autonomy_evidence import (
    EVIDENCE_SCHEMA,
    EXPECTED_COMMAND_IDS,
    HIGH_RISK_ARTIFACTS,
    MANIFEST_SCHEMA,
    REQUIRED_ARTIFACTS,
    SENSITIVE_PATTERNS,
    canonical_bytes,
    canonical_document,
    classify_risk,
    seal_manifest,
    sha256_file,
)


EXPECTED_REPOSITORY = "adrimg3196/lucidfence"
PRODUCT = ("product/product-manager.md", "4a3fe4661e72e5173877bcba7c362392181774b20efc27ac1789171e98676c9d")
MAKER = ("engineering/engineering-api-platform-engineer.md", "278798c42d7a7cf4f42d3973795765403105ce60d518d647abfdaa522d862d8e")
FINAL = ("testing/testing-reality-checker.md", "6d32fcdb114233e13902ec6372d50293b120e85d490b5e81d372c29808f988a1")
APPSEC_PRIMARY = ("security/security-appsec-engineer.md", "f3ee22350c9e0e7289d2d4747e7c1a8fe196d70340feec7b176b13bacc3deb77")
APPSEC_SECONDARY = ("security/security-architect.md", "b1a68e9614f7adb43938f5bd9964f6e41250febc9a57f691eefcbab58d5b1df1")
ALL_KINDS = tuple(REQUIRED_ARTIFACTS) + tuple(HIGH_RISK_ARTIFACTS)
COMMAND_IDS = EXPECTED_COMMAND_IDS
LOCK_ENTRY = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)"
    r"(?:\[(?P<extras>[A-Za-z0-9_,.-]+)\])?"
    r"==(?P<version>[A-Za-z0-9][A-Za-z0-9._+-]*)"
    r"(?P<hashes>(?:\s+--hash=sha256:[0-9a-f]{64})+)$"
)
RUNTIME_PACKAGE_ALLOWLIST = frozenset(
    {
        "certifi",
        "cffi",
        "charset-normalizer",
        "cryptography",
        "idna",
        "pycparser",
        "pyjwt",
        "requests",
        "urllib3",
    }
)
CONTROL_PLANE_ASSETS = frozenset(
    {
        ".gitleaks.toml",
        ".github/CODEOWNERS",
        ".github/workflows/autonomy-attest.yml",
        ".github/workflows/autonomy-evidence.yml",
        ".github/workflows/autonomy-guard.yml",
        ".github/workflows/ci.yml",
        ".github/workflows/docker.yml",
        "config/agency-agents.lock.json",
        "config/autonomy-tools.lock",
        "config/night-shift-manifest.schema.json",
        "data/agency_catalog.json",
        "scripts/emit_autonomy_evidence.py",
        "scripts/generate_agency_catalog.py",
        "scripts/runtime_validation.py",
        "scripts/supervise_autonomy_check.py",
        "scripts/verify.py",
        "scripts/verify_autonomy_evidence.py",
        "tests/run_tests.py",
        "tests/test_agency_catalog.py",
        "tests/test_autonomy_evidence.py",
        "tests/test_autonomy_evidence_producer.py",
        "tests/test_night_shift_schema.py",
    }
)
FORBIDDEN_WORKFLOW_PERMISSION = re.compile(
    r"(?ix)(?:[\"']?(?:statuses|checks|id-token|attestations)[\"']?)\s*:"
)
WRITE_ALL_PERMISSION = re.compile(
    r"(?ix)(?:[\"']?permissions[\"']?)\s*:\s*[\"']?write-all[\"']?"
)
SCALAR_WORKFLOW_PERMISSIONS = re.compile(
    r"(?im)^[ \t]*[\"']?permissions[\"']?[ \t]*:[ \t]*"
    r"(?!$|\{\}[ \t]*(?:#.*)?$)\S.*$"
)
YAML_EXPLICIT_MAPPING_KEY = re.compile(
    r"(?m)(?:^[ \t-]*\?[ \t]+|[{,][ \t]*\?[ \t]*)"
)
YAML_ANCHOR_OR_ALIAS = re.compile(
    r"(?<![A-Za-z0-9_-])[&*][A-Za-z0-9_-]+"
)
YAML_MERGE_KEY = re.compile(
    r"(?m)(?:^[ \t-]*|[{,][ \t]*)<<[ \t]*:"
)
YAML_TAG = re.compile(
    r"(?m)(?:^[ \t-]*|[{,:?][ \t]*)!(?:!|<|[A-Za-z]|(?=[ \t]))"
)
YAML_DIRECTIVE = re.compile(r"(?m)^[ \t]*%(?:YAML|TAG)\b")
YAML_FORBIDDEN_CONTROL = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u2028\u2029\ufeff]"
)
MAX_WHEEL_SIZE = 200 * 1024 * 1024
MAX_WHEEL_UNCOMPRESSED = 500 * 1024 * 1024
MAX_SUPERVISED_OUTPUT = 10 * 1024 * 1024
MAX_SECRET_SCAN_FILE = 10 * 1024 * 1024
GUARD_STATUS_MAX_AGE = timedelta(days=5)
GUARD_SCHEMA = "lucidfence-autonomy-guard/v1"
SUPERVISOR_SCHEMA = "lucidfence-trusted-supervisor-receipt/v2"
SUPERVISED_KINDS = frozenset({"runtime", "reality"})
CONVENTIONAL_CI_SNAPSHOT_SCHEMA = "lucidfence-github-ci-snapshot/v1"
CONVENTIONAL_CI_RECEIPT_SCHEMA = "lucidfence-conventional-ci-receipt/v1"
CONVENTIONAL_CI_SOURCE = "github-rest-api/2022-11-28"
MAX_CONVENTIONAL_CI_SNAPSHOT = 2 * 1024 * 1024
CONVENTIONAL_CI_CHECKS = (
    "Dependency audit",
    "Frontend syntax check",
    "Lint (ruff F/E9)",
    "No runtime artifacts in PR",
    "Python tests (3.11) (3.11)",
    "Runtime validation (claims en vivo)",
    "Secret scan (gitleaks)",
    "Verify (versión + enlaces de docs)",
    "Workflows lint (actionlint)",
)
CONVENTIONAL_CI_CONTROL_FILES = (
    ".github/workflows/autonomy-evidence.yml",
    ".github/workflows/ci.yml",
)


def _yaml_line_without_quoted_scalars_or_comment(line: str) -> str:
    """Mask scalars/comments only to locate a block-scalar indicator."""
    masked = list(line)
    index = 0
    quote: str | None = None
    while index < len(line):
        character = line[index]
        if quote is None:
            if character in {"'", '"'}:
                quote = character
                masked[index] = " "
            elif character == "#" and (index == 0 or line[index - 1].isspace()):
                for offset in range(index, len(line)):
                    if masked[offset] not in "\r\n":
                        masked[offset] = " "
                break
        else:
            if character not in "\r\n":
                masked[index] = " "
            if quote == "'" and character == "'":
                if index + 1 < len(line) and line[index + 1] == "'":
                    masked[index + 1] = " "
                    index += 1
                else:
                    quote = None
            elif quote == '"' and character == "\\":
                if index + 1 < len(line):
                    if line[index + 1] not in "\r\n":
                        masked[index + 1] = " "
                    index += 1
            elif quote == '"' and character == '"':
                quote = None
        index += 1
    return "".join(masked)


def _mask_yaml_block_scalar_bodies(text: str) -> str:
    """Remove embedded scripts from the YAML syntax surface.

    Workflow ``run: |`` bodies are arbitrary shell/Python/JSON and must not be
    mistaken for YAML keys. The first content line determines implicit block
    indentation, so an outdented sibling is inspected rather than hidden.
    """
    output: list[str] = []
    parent_indent: int | None = None
    content_indent: int | None = None
    explicit_indent: int | None = None
    header = re.compile(
        r"(?:^|:[ \t]+|-[ \t]+)(?P<indicator>[|>])"
        r"(?P<mods>(?:[1-9][+-]?|[+-][1-9]?|[+-])?)[ \t]*$"
    )
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        newline = line[len(body) :]
        stripped = body.lstrip(" ")
        indent = len(body) - len(stripped)
        if parent_indent is not None:
            if not stripped or stripped.startswith("#"):
                output.append(" " * len(body) + newline)
                continue
            if explicit_indent is not None:
                if indent >= explicit_indent:
                    output.append(" " * len(body) + newline)
                    continue
            else:
                if content_indent is None and indent > parent_indent:
                    content_indent = indent
                if content_indent is not None and indent >= content_indent:
                    output.append(" " * len(body) + newline)
                    continue
            parent_indent = None
            content_indent = None
            explicit_indent = None

        output.append(line)
        code = _yaml_line_without_quoted_scalars_or_comment(body).rstrip()
        match = header.search(code)
        if match:
            parent_indent = indent
            digit = next((item for item in match.group("mods") if item.isdigit()), None)
            prefix = code[: match.start("indicator")].strip()
            compact_mapping_indent = 2 if prefix.startswith("- ") and ":" in prefix[2:] else 0
            explicit_indent = (
                indent + compact_mapping_indent + int(digit)
                if digit is not None
                else None
            )
            content_indent = None
    return "".join(output)


def _workflow_yaml_surfaces(text: str) -> tuple[str, bool]:
    """Return inspectable YAML and flag syntax that can obscure parsed keys.

    Quoted/escaped mapping keys, explicit keys, aliases, anchors, merge keys,
    tags, and directives are unnecessary in LucidFence workflows. Rejecting
    them avoids implementing a second YAML parser inside the trust boundary.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    surface_chars = list(_mask_yaml_block_scalar_bodies(normalized))
    outside_chars = list(surface_chars)
    quoted_mapping_key = False
    index = 0
    while index < len(surface_chars):
        character = surface_chars[index]
        if character == "#" and (index == 0 or surface_chars[index - 1].isspace()):
            while index < len(surface_chars) and surface_chars[index] not in "\r\n":
                surface_chars[index] = " "
                outside_chars[index] = " "
                index += 1
            continue
        if character not in {"'", '"'}:
            index += 1
            continue

        start = index
        previous = start - 1
        while previous >= 0 and surface_chars[previous] in " \t":
            previous -= 1
        begins_node = previous < 0 or surface_chars[previous] in "\r\n:[{,?-"
        quote = character
        outside_chars[index] = " "
        index += 1
        closed = False
        while index < len(surface_chars):
            character = surface_chars[index]
            if character not in "\r\n":
                outside_chars[index] = " "
            if quote == "'" and character == "'":
                if index + 1 < len(surface_chars) and surface_chars[index + 1] == "'":
                    outside_chars[index + 1] = " "
                    index += 2
                    continue
                closed = True
                index += 1
                break
            if quote == '"' and character == "\\":
                if index + 1 < len(surface_chars):
                    if surface_chars[index + 1] not in "\r\n":
                        outside_chars[index + 1] = " "
                    index += 2
                    continue
            elif quote == '"' and character == '"':
                closed = True
                index += 1
                break
            index += 1
        if not closed:
            continue
        following = index
        while following < len(surface_chars) and surface_chars[following] in " \t\r\n":
            following += 1
        if begins_node and following < len(surface_chars) and surface_chars[following] == ":":
            quoted_mapping_key = True

    surface = "".join(surface_chars)
    outside = "".join(outside_chars)
    advanced = (
        YAML_FORBIDDEN_CONTROL.search(surface) is not None
        or quoted_mapping_key
        or any(
            pattern.search(outside)
            for pattern in (
                YAML_EXPLICIT_MAPPING_KEY,
                YAML_ANCHOR_OR_ALIAS,
                YAML_MERGE_KEY,
                YAML_TAG,
                YAML_DIRECTIVE,
            )
        )
    )
    return surface, advanced


def _workflow_has_event(surface: str, event: str) -> bool:
    """Recognize canonical, scalar, and flow-list GitHub event declarations."""
    escaped = re.escape(event)
    return re.search(
        rf"(?m)^(?:[ \t]+{escaped}[ \t]*:|"
        rf"on[ \t]*:[ \t]*(?:{escaped}[ \t]*(?:#.*)?$|"
        rf"\[[^\]\r\n]*\b{escaped}\b[^\]\r\n]*\]))",
        surface,
    ) is not None


def _profile(value: tuple[str, str]) -> dict[str, str]:
    return {"path": value[0], "sha256": value[1]}


def context_from_environment(env: dict[str, str], *, changed_paths: list[str]) -> dict[str, object]:
    event_path = Path(env["GITHUB_EVENT_PATH"])
    event = json.loads(event_path.read_bytes())
    number = event.get("pull_request", {}).get("number")
    if not isinstance(number, int) or number <= 0:
        raise ValueError("autonomy evidence requires a pull_request event number")
    repository = env.get("GITHUB_REPOSITORY")
    if repository != EXPECTED_REPOSITORY:
        raise ValueError(f"repository must be exactly {EXPECTED_REPOSITORY}")
    base_sha, head_sha = env.get("LF_BASE_SHA", ""), env.get("LF_HEAD_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", base_sha) or not re.fullmatch(r"[0-9a-f]{40}", head_sha):
        raise ValueError("GitHub base/head commits must be lowercase 40-hex SHAs")
    workflow = env.get("GITHUB_WORKFLOW")
    if workflow != "autonomy-evidence":
        raise ValueError("workflow identity must be autonomy-evidence")
    return {
        "base_sha": base_sha,
        "changed_paths": sorted(set(changed_paths)),
        "head_sha": head_sha,
        "objective": f"pull-request-{number}",
        "ref": env["GITHUB_REF"],
        "repository": repository,
        "risk": classify_risk(changed_paths),
        "run_attempt": int(env["GITHUB_RUN_ATTEMPT"]),
        "run_id": str(env["GITHUB_RUN_ID"]),
        "workflow": workflow,
        "workflow_ref": env["GITHUB_WORKFLOW_REF"],
    }


def changed_paths(repo_root: Path, base_sha: str, head_sha: str) -> list[str]:
    process = subprocess.run(
        [
            "git",
            "diff",
            "--name-status",
            "-z",
            "--find-renames",
            f"{base_sha}...{head_sha}",
        ],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError("cannot derive changed paths from base/head commits")
    try:
        fields = process.stdout.decode("utf-8").split("\0")
    except UnicodeDecodeError as exc:
        raise RuntimeError("git returned a non-UTF-8 changed path") from exc
    if not fields or fields[-1] != "":
        raise RuntimeError("git returned a truncated changed-path inventory")
    fields.pop()
    paths: set[str] = set()
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if not re.fullmatch(r"(?:[ACDMRTUXB]|[RC][0-9]{1,3})", status):
            raise RuntimeError("git returned an unknown changed-path status")
        path_count = 2 if status.startswith(("R", "C")) else 1
        if index + path_count > len(fields):
            raise RuntimeError("git returned a truncated rename/copy inventory")
        for path in fields[index : index + path_count]:
            if not path or path.startswith("/") or "\x00" in path:
                raise RuntimeError("git returned an invalid changed path")
            paths.add(path)
        index += path_count
    return sorted(paths)


def github_context(repo_root: Path, env: dict[str, str] | None = None) -> dict[str, object]:
    environment = dict(os.environ if env is None else env)
    paths = changed_paths(repo_root, environment["LF_BASE_SHA"], environment["LF_HEAD_SHA"])
    return context_from_environment(environment, changed_paths=paths)


def evidence_context(repo_root: Path, env: dict[str, str] | None = None) -> dict[str, object]:
    """Select the canonical context for PR preflight or trusted re-derivation."""
    environment = dict(os.environ if env is None else env)
    if environment.get("LF_TRUSTED_CONTEXT") == "1":
        return trusted_job_context(repo_root, environment)
    event = json.loads(Path(environment["GITHUB_EVENT_PATH"]).read_bytes())
    if isinstance(event.get("workflow_run"), dict):
        return workflow_run_context_from_environment(environment)
    return github_context(repo_root, environment)


def trusted_job_context(repo_root: Path, env: dict[str, str]) -> dict[str, object]:
    """Build evidence context from validated outputs of the isolated context job."""
    if env.get("GITHUB_REPOSITORY") != EXPECTED_REPOSITORY:
        raise ValueError(f"repository must be exactly {EXPECTED_REPOSITORY}")
    if env.get("GITHUB_WORKFLOW") != "autonomy-attest" or env.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("trusted derivation must run from autonomy-attest on main")
    base_sha, head_sha = env.get("LF_BASE_SHA", ""), env.get("LF_HEAD_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", base_sha) or not re.fullmatch(r"[0-9a-f]{40}", head_sha):
        raise ValueError("trusted derivation base/head commits are invalid")
    run_id = env.get("LF_REQUEST_RUN_ID", "")
    run_attempt = int(env.get("LF_REQUEST_RUN_ATTEMPT", "0"))
    number = int(env.get("LF_PR_NUMBER", "0"))
    if not run_id.isdigit() or run_attempt < 1 or number < 1:
        raise ValueError("trusted derivation request identity is invalid")
    token = env.get("GITHUB_TOKEN") or env.get("GH_TOKEN")
    if not token:
        raise ValueError("GitHub token unavailable for trusted path derivation")
    base_url = env.get("GITHUB_API_URL", "https://api.github.com")
    pull = _api_json(f"{base_url}/repos/{EXPECTED_REPOSITORY}/pulls/{number}", token)
    if not isinstance(pull, dict):
        raise RuntimeError("GitHub pull request API returned malformed data")
    if (
        pull.get("state") not in {None, "open"}
        or pull.get("base", {}).get("sha") != base_sha
        or pull.get("head", {}).get("sha") != head_sha
    ):
        raise ValueError("trusted derivation no longer matches the live pull request")
    files = _api_pages(
        f"{base_url}/repos/{EXPECTED_REPOSITORY}/pulls/{number}/files",
        token,
    )
    paths = _pull_file_paths(files)
    git_inventory = changed_paths(repo_root, base_sha, head_sha)
    if paths != git_inventory:
        raise ValueError("GitHub and git changed-path inventories disagree")
    ref = f"refs/pull/{number}/merge"
    return {
        "base_sha": base_sha,
        "changed_paths": paths,
        "head_sha": head_sha,
        "objective": f"pull-request-{number}",
        "ref": ref,
        "repository": EXPECTED_REPOSITORY,
        "risk": classify_risk(paths),
        "run_attempt": run_attempt,
        "run_id": run_id,
        "workflow": "autonomy-evidence",
        "workflow_ref": f"{EXPECTED_REPOSITORY}/.github/workflows/autonomy-evidence.yml@{ref}",
    }


def _catalog_map(catalog_path: Path) -> dict[str, str]:
    catalog = json.loads(catalog_path.read_bytes())
    if catalog.get("schema") != "lucidfence-agency-catalog/v1":
        raise ValueError("pinned agency catalog schema mismatch")
    if catalog.get("lock", {}).get("profiles") != catalog.get("profiles"):
        raise ValueError("pinned agency catalog embedded lock mismatch")
    return {item["path"]: item["sha256"] for item in catalog["profiles"]}


def _producer_for(kind: str) -> dict[str, str]:
    if kind in {"reality", "final-review"}:
        return _profile(FINAL)
    if kind in {"appsec", "appsec-primary"}:
        return _profile(APPSEC_PRIMARY)
    if kind == "appsec-secondary":
        return _profile(APPSEC_SECONDARY)
    return _profile(MAKER)


def _ensure_profile(profile: dict[str, str], catalog_path: Path) -> None:
    inventory = _catalog_map(catalog_path)
    if inventory.get(profile["path"]) != profile["sha256"]:
        raise ValueError(f"producer is not in pinned catalog: {profile['path']}")


def _reject_sensitive(raw: bytes, label: str) -> None:
    for pattern, description in SENSITIVE_PATTERNS:
        if pattern.search(raw):
            raise ValueError(f"{label} contains sensitive data: {description}")


def scan_changed_files_for_secrets(
    repo_root: Path,
    context: dict[str, object],
) -> dict[str, object]:
    """Scan exact changed-tree bytes without tokens or external executables."""
    findings: list[str] = []
    files_scanned = 0
    bytes_scanned = 0
    for relative in context["changed_paths"]:
        path = repo_root / relative
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_symlink() or not path.is_file():
            findings.append(f"{relative}: changed entry is not one regular file")
            continue
        size = path.stat().st_size
        if size > MAX_SECRET_SCAN_FILE:
            findings.append(f"{relative}: changed file exceeds the secret-scan bound")
            continue
        raw = path.read_bytes()
        files_scanned += 1
        bytes_scanned += len(raw)
        for pattern, description in SENSITIVE_PATTERNS:
            if pattern.search(raw):
                findings.append(f"{relative}: {description}")
    return {
        "bytes_scanned": bytes_scanned,
        "files_scanned": files_scanned,
        "findings": findings,
        "status": "pass" if not findings else "fail",
    }


def _normalize_distribution(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def validate_requirement_lock(
    lock_path: Path,
    *,
    allowed_packages: frozenset[str] | None = None,
) -> dict[str, dict[str, object]]:
    """Accept only exact, hash-pinned registry requirements with no redirects."""
    if lock_path.is_symlink() or not lock_path.is_file():
        raise ValueError("candidate requirement lock must be one regular file")
    raw = lock_path.read_bytes()
    if not raw or len(raw) > 1024 * 1024 or b"\x00" in raw:
        raise ValueError("candidate requirement lock size or encoding is invalid")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("candidate requirement lock is not UTF-8") from exc

    entries: list[str] = []
    current = ""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        continued = stripped.endswith("\\")
        fragment = stripped[:-1].rstrip() if continued else stripped
        current = f"{current} {fragment}".strip()
        if not continued:
            entries.append(current)
            current = ""
    if current or not entries:
        raise ValueError("candidate requirement lock has an incomplete entry")

    requirements: dict[str, dict[str, object]] = {}
    for entry in entries:
        match = LOCK_ENTRY.fullmatch(entry)
        if match is None:
            raise ValueError("candidate requirement lock contains a non-registry or unpinned entry")
        if match.group("extras"):
            raise ValueError("candidate requirement lock cannot expand package extras")
        name = _normalize_distribution(match.group("name"))
        if name in requirements:
            raise ValueError("candidate requirement lock contains a duplicate package")
        requirements[name] = {
            "hashes": frozenset(
                re.findall(r"--hash=sha256:([0-9a-f]{64})", match.group("hashes"))
            ),
            "version": match.group("version"),
        }
    if allowed_packages is not None:
        expected = {_normalize_distribution(name) for name in allowed_packages}
        actual = set(requirements)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ValueError(
                "candidate runtime package allowlist mismatch "
                f"(missing={missing}, extra={extra})"
            )
    return requirements


def validate_runtime_requirement_lock(lock_path: Path) -> dict[str, dict[str, object]]:
    """Bind the candidate runtime to the closed, reviewed distribution set."""
    return validate_requirement_lock(
        lock_path,
        allowed_packages=RUNTIME_PACKAGE_ALLOWLIST,
    )


def _wheel_identity(path: Path) -> tuple[str, str]:
    if not path.name.endswith(".whl"):
        raise ValueError(f"wheelhouse contains a non-wheel file: {path.name}")
    fields = path.name[:-4].split("-")
    if len(fields) < 5:
        raise ValueError(f"wheel filename is malformed: {path.name}")
    return _normalize_distribution(fields[0]), fields[1]


def _inspect_wheel_archive(path: Path, expected_name: str, expected_version: str) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len(names) != len(set(names)):
                raise ValueError(f"wheel contains duplicate archive members: {path.name}")
            total = 0
            metadata_members: list[zipfile.ZipInfo] = []
            wheel_members = 0
            record_members = 0
            for member in members:
                name = member.filename
                if not name or "\\" in name or "\x00" in name:
                    raise ValueError(f"wheel contains an invalid archive path: {path.name}")
                pure = PurePosixPath(name)
                if pure.is_absolute() or ".." in pure.parts:
                    raise ValueError(f"wheel contains path traversal: {path.name}")
                if member.flag_bits & 0x1:
                    raise ValueError(f"wheel contains encrypted content: {path.name}")
                unix_mode = (member.external_attr >> 16) & 0xFFFF
                if unix_mode & 0o170000 == 0o120000:
                    raise ValueError(f"wheel contains a symbolic link: {path.name}")
                total += member.file_size
                if total > MAX_WHEEL_UNCOMPRESSED:
                    raise ValueError(f"wheel expands beyond the safety bound: {path.name}")
                basename = pure.name.lower()
                if (
                    basename.endswith((".pth", ".egg-link"))
                    or basename in {"sitecustomize.py", "usercustomize.py"}
                ):
                    raise ValueError(
                        f"wheel contains forbidden Python startup hook {pure.name}: {path.name}"
                    )
                if name.endswith(".dist-info/METADATA"):
                    metadata_members.append(member)
                elif name.endswith(".dist-info/WHEEL"):
                    wheel_members += 1
                elif name.endswith(".dist-info/RECORD"):
                    record_members += 1
            if len(metadata_members) != 1 or wheel_members != 1 or record_members != 1:
                raise ValueError(f"wheel metadata inventory is incomplete: {path.name}")
            metadata_member = metadata_members[0]
            if metadata_member.file_size > 1024 * 1024:
                raise ValueError(f"wheel metadata exceeds the safety bound: {path.name}")
            try:
                metadata_text = archive.read(metadata_member).decode("utf-8")
            except (KeyError, UnicodeDecodeError) as exc:
                raise ValueError(f"wheel metadata is unreadable: {path.name}") from exc
            metadata = Parser().parsestr(metadata_text)
            metadata_name = metadata.get("Name", "")
            metadata_version = metadata.get("Version", "")
            if (
                _normalize_distribution(metadata_name) != expected_name
                or metadata_version != expected_version
            ):
                raise ValueError(f"wheel filename and metadata identity disagree: {path.name}")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"wheel archive is invalid: {path.name}") from exc


def inspect_wheelhouse(
    lock_path: Path,
    wheelhouse: Path,
    *,
    allowed_packages: frozenset[str] | None = None,
) -> dict[str, str]:
    """Verify exact wheels, hashes, metadata and inert archive contents pre-install."""
    requirements = validate_requirement_lock(
        lock_path,
        allowed_packages=allowed_packages,
    )
    if wheelhouse.is_symlink() or not wheelhouse.is_dir():
        raise ValueError("wheelhouse must be one real directory")
    entries = sorted(wheelhouse.iterdir(), key=lambda item: item.name)
    if len(entries) != len(requirements):
        raise ValueError("wheelhouse does not contain exactly one wheel per requirement")
    inspected: dict[str, str] = {}
    for path in entries:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_WHEEL_SIZE:
            raise ValueError(f"wheelhouse contains an invalid wheel file: {path.name}")
        name, version = _wheel_identity(path)
        if name not in requirements or name in inspected:
            raise ValueError(f"wheelhouse package inventory mismatch: {path.name}")
        expected = requirements[name]
        if version != expected["version"]:
            raise ValueError(f"wheel version does not match the lock: {path.name}")
        digest = sha256_file(path)
        if digest not in expected["hashes"]:
            raise ValueError(f"wheel digest does not match the lock: {path.name}")
        _inspect_wheel_archive(path, name, version)
        inspected[name] = digest
    if set(inspected) != set(requirements):
        raise ValueError("wheelhouse package inventory is incomplete")
    return dict(sorted(inspected.items()))


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def emit_artifact(
    kind: str,
    log_path: Path,
    output_path: Path,
    context: dict[str, object],
    catalog_path: Path,
) -> dict:
    if kind not in ALL_KINDS:
        raise ValueError(f"unknown evidence kind: {kind}")
    if log_path.name != f"{kind}.log":
        raise ValueError(f"{kind} command log must be named {kind}.log")
    raw = log_path.read_bytes()
    _reject_sensitive(raw, f"{kind} command log")
    producer = _producer_for(kind)
    _ensure_profile(producer, catalog_path)
    result: dict[str, object] = {
        "check": kind,
        "command_id": COMMAND_IDS[kind],
        "exit_code": 0,
        "output_bytes": len(raw),
        "output_sha256": hashlib.sha256(raw).hexdigest(),
        "status": "pass",
    }
    if kind == "overlap":
        overlap = json.loads(raw)
        if overlap.get("status") != "pass" or overlap.get("overlaps") != [] or overlap.get("conflicts") != []:
            raise ValueError("overlap check did not pass cleanly")
        snapshot_sha256 = overlap.get("snapshot_sha256")
        if not isinstance(snapshot_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", snapshot_sha256
        ):
            raise ValueError("overlap check has no canonical live snapshot digest")
        result["overlaps"] = []
        result["conflicts"] = []
        result["snapshot_sha256"] = snapshot_sha256
    document = {
        "base_sha": context["base_sha"],
        "generated_at": _format_time(_now()),
        "head_sha": context["head_sha"],
        "kind": kind,
        "objective": context["objective"],
        "producer": producer,
        "ref": context["ref"],
        "repository": context["repository"],
        "result": result,
        "run_attempt": context["run_attempt"],
        "run_id": context["run_id"],
        "schema": EVIDENCE_SCHEMA,
        "workflow": context["workflow"],
        "workflow_ref": context["workflow_ref"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(canonical_document(document))
    return document


def _conventional_ci_context_binding(
    context: dict[str, object],
    *,
    trusted_run_id: str,
    trusted_run_attempt: int,
    trusted_source_sha: str,
) -> dict[str, object]:
    base_sha = context.get("base_sha")
    head_sha = context.get("head_sha")
    request_run_id = str(context.get("run_id", ""))
    request_run_attempt = context.get("run_attempt")
    if context.get("repository") != EXPECTED_REPOSITORY:
        raise ValueError("conventional CI context repository is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", str(base_sha)) or not re.fullmatch(
        r"[0-9a-f]{40}", str(head_sha)
    ):
        raise ValueError("conventional CI context commits are invalid")
    if (
        not request_run_id.isdigit()
        or not isinstance(request_run_attempt, int)
        or isinstance(request_run_attempt, bool)
        or request_run_attempt < 1
        or not trusted_run_id.isdigit()
        or not isinstance(trusted_run_attempt, int)
        or isinstance(trusted_run_attempt, bool)
        or trusted_run_attempt < 1
        or not re.fullmatch(r"[0-9a-f]{40}", trusted_source_sha)
    ):
        raise ValueError("conventional CI request or trusted run identity is invalid")
    return {
        "base_sha": base_sha,
        "head_sha": head_sha,
        "request_run_attempt": request_run_attempt,
        "request_run_id": request_run_id,
        "trusted_run_attempt": trusted_run_attempt,
        "trusted_run_id": trusted_run_id,
        "trusted_source_sha": trusted_source_sha,
    }


def _read_canonical_json(path: Path, label: str, *, maximum_bytes: int) -> tuple[bytes, dict]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} is missing or is not one regular file")
    size = path.stat().st_size
    if not 1 <= size <= maximum_bytes:
        raise ValueError(f"{label} size is outside the safety bound")
    raw = path.read_bytes()
    _reject_sensitive(raw, label)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is malformed") from exc
    if not isinstance(value, dict) or raw != canonical_document(value):
        raise ValueError(f"{label} is not canonical JSON")
    return raw, value


def _positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _validate_conventional_ci_snapshot(
    snapshot_path: Path,
    context: dict[str, object],
) -> tuple[bytes, dict[str, object]]:
    raw, snapshot = _read_canonical_json(
        snapshot_path,
        "GitHub conventional CI snapshot",
        maximum_bytes=MAX_CONVENTIONAL_CI_SNAPSHOT,
    )
    if set(snapshot) != {
        "checks",
        "control_files",
        "jobs",
        "repository",
        "run",
        "schema",
        "source",
    }:
        raise ValueError("GitHub conventional CI snapshot fields are not exact")
    if (
        snapshot.get("schema") != CONVENTIONAL_CI_SNAPSHOT_SCHEMA
        or snapshot.get("source") != CONVENTIONAL_CI_SOURCE
        or snapshot.get("repository") != EXPECTED_REPOSITORY
        or context.get("repository") != EXPECTED_REPOSITORY
    ):
        raise ValueError("GitHub conventional CI snapshot identity is invalid")

    run = snapshot.get("run")
    expected_run_keys = {
        "check_suite_id",
        "conclusion",
        "event",
        "head_sha",
        "id",
        "name",
        "path",
        "pull_requests",
        "run_attempt",
        "status",
    }
    if not isinstance(run, dict) or set(run) != expected_run_keys:
        raise ValueError("GitHub conventional CI run fields are not exact")
    run_id = _positive_int(run.get("id"), "GitHub conventional CI run ID")
    run_attempt = _positive_int(
        run.get("run_attempt"), "GitHub conventional CI run attempt"
    )
    check_suite_id = _positive_int(
        run.get("check_suite_id"), "GitHub conventional CI check suite ID"
    )
    if (
        run.get("name") != "CI"
        or run.get("path") != ".github/workflows/ci.yml"
        or run.get("event") != "pull_request"
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("head_sha") != context.get("head_sha")
    ):
        raise ValueError("GitHub conventional CI run did not pass for the requested head")
    pulls = run.get("pull_requests")
    if not isinstance(pulls, list) or len(pulls) != 1 or not isinstance(pulls[0], dict):
        raise ValueError("GitHub conventional CI run must bind exactly one pull request")
    pull = pulls[0]
    if set(pull) != {"base_sha", "head_sha", "number"}:
        raise ValueError("GitHub conventional CI pull request fields are not exact")
    objective = re.fullmatch(r"pull-request-([1-9][0-9]*)", str(context.get("objective", "")))
    if (
        objective is None
        or pull.get("number") != int(objective.group(1))
        or pull.get("base_sha") != context.get("base_sha")
        or pull.get("head_sha") != context.get("head_sha")
    ):
        raise ValueError("GitHub conventional CI pull request context does not match")

    wrappers: dict[str, dict] = {}
    for label in ("jobs", "checks"):
        wrapper = snapshot.get(label)
        if not isinstance(wrapper, dict) or set(wrapper) != {"items", "total_count"}:
            raise ValueError(f"GitHub conventional CI {label} fields are not exact")
        items = wrapper.get("items")
        if (
            not isinstance(items, list)
            or not all(isinstance(item, dict) for item in items)
            or wrapper.get("total_count") != len(items)
            or len(items) != len(CONVENTIONAL_CI_CHECKS)
        ):
            raise ValueError(f"GitHub conventional CI {label} inventory is incomplete")
        if tuple(item.get("name") for item in items) != CONVENTIONAL_CI_CHECKS:
            raise ValueError(f"GitHub conventional CI {label} inventory is not exact")
        wrappers[label] = wrapper

    job_ids: set[int] = set()
    expected_job_keys = {
        "conclusion",
        "head_sha",
        "id",
        "name",
        "run_attempt",
        "run_id",
        "status",
    }
    for job in wrappers["jobs"]["items"]:
        if set(job) != expected_job_keys:
            raise ValueError("GitHub conventional CI job fields are not exact")
        job_id = _positive_int(job.get("id"), "GitHub conventional CI job ID")
        if job_id in job_ids:
            raise ValueError("GitHub conventional CI job IDs are duplicated")
        job_ids.add(job_id)
        if (
            job.get("run_id") != run_id
            or job.get("run_attempt") != run_attempt
            or job.get("head_sha") != context.get("head_sha")
            or job.get("status") != "completed"
            or job.get("conclusion") != "success"
        ):
            raise ValueError("GitHub conventional CI job did not pass for the canonical run")

    check_ids: set[int] = set()
    expected_check_keys = {
        "check_suite_id",
        "conclusion",
        "head_sha",
        "id",
        "name",
        "status",
    }
    for check in wrappers["checks"]["items"]:
        if set(check) != expected_check_keys:
            raise ValueError("GitHub conventional CI check fields are not exact")
        check_id = _positive_int(check.get("id"), "GitHub conventional CI check ID")
        if check_id in check_ids:
            raise ValueError("GitHub conventional CI check IDs are duplicated")
        check_ids.add(check_id)
        if (
            check.get("check_suite_id") != check_suite_id
            or check.get("head_sha") != context.get("head_sha")
            or check.get("status") != "completed"
            or check.get("conclusion") != "success"
        ):
            raise ValueError("GitHub conventional CI check did not pass for the canonical suite")

    control_files = snapshot.get("control_files")
    if not isinstance(control_files, list) or tuple(
        item.get("path") if isinstance(item, dict) else None for item in control_files
    ) != CONVENTIONAL_CI_CONTROL_FILES:
        raise ValueError("conventional CI protected workflow inventory is not exact")
    for item in control_files:
        if set(item) != {"base", "head", "path"}:
            raise ValueError("conventional CI protected workflow fields are not exact")
        for side in ("base", "head"):
            identity = item.get(side)
            if (
                not isinstance(identity, dict)
                or set(identity) != {"bytes", "commit_sha", "sha256"}
                or not isinstance(identity.get("bytes"), int)
                or isinstance(identity.get("bytes"), bool)
                or not 1 <= identity["bytes"] <= MAX_CONVENTIONAL_CI_SNAPSHOT
                or identity.get("commit_sha") != context.get(f"{side}_sha")
                or not re.fullmatch(r"[0-9a-f]{64}", str(identity.get("sha256", "")))
            ):
                raise ValueError("conventional CI protected workflow identity is invalid")
        if (
            item["base"]["bytes"] != item["head"]["bytes"]
            or item["base"]["sha256"] != item["head"]["sha256"]
        ):
            raise ValueError(
                f"candidate {item['path']} does not match the trusted base byte-for-byte"
            )

    checks = [
        {
            "check_id": check["id"],
            "job_id": job["id"],
            "name": name,
        }
        for name, job, check in zip(
            CONVENTIONAL_CI_CHECKS,
            wrappers["jobs"]["items"],
            wrappers["checks"]["items"],
            strict=True,
        )
    ]
    return raw, {
        "check_suite_id": check_suite_id,
        "checks": checks,
        "control_files_sha256": hashlib.sha256(canonical_bytes(control_files)).hexdigest(),
        "inventory_sha256": hashlib.sha256(
            canonical_bytes({"checks": wrappers["checks"], "jobs": wrappers["jobs"]})
        ).hexdigest(),
        "run_attempt": run_attempt,
        "run_id": str(run_id),
    }


def emit_conventional_ci_receipt(
    snapshot_path: Path,
    output_path: Path,
    context: dict[str, object],
    *,
    trusted_run_id: str,
    trusted_run_attempt: int,
    trusted_source_sha: str,
) -> dict[str, object]:
    """Validate GitHub API state without loading or executing the PR checkout."""
    binding = _conventional_ci_context_binding(
        context,
        trusted_run_id=trusted_run_id,
        trusted_run_attempt=trusted_run_attempt,
        trusted_source_sha=trusted_source_sha,
    )
    raw, validated = _validate_conventional_ci_snapshot(snapshot_path, context)
    receipt: dict[str, object] = {
        "checks": validated["checks"],
        "ci": {
            "check_suite_id": validated["check_suite_id"],
            "control_files_sha256": validated["control_files_sha256"],
            "inventory_sha256": validated["inventory_sha256"],
            "run_attempt": validated["run_attempt"],
            "run_id": validated["run_id"],
            "workflow": "CI",
            "workflow_path": ".github/workflows/ci.yml",
        },
        "context": binding,
        "output": {
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "receipt_digest": {"algorithm": "sha256", "value": "0" * 64},
        "repository": EXPECTED_REPOSITORY,
        "schema": CONVENTIONAL_CI_RECEIPT_SCHEMA,
        "source": CONVENTIONAL_CI_SOURCE,
        "status": "pass",
    }
    receipt["receipt_digest"]["value"] = hashlib.sha256(canonical_bytes(receipt)).hexdigest()
    if output_path.is_symlink():
        raise ValueError("conventional CI receipt output cannot be a symbolic link")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(canonical_document(receipt))
    return receipt


def _validate_conventional_ci_receipt(
    path: Path,
    context: dict[str, object],
    *,
    trusted_run_id: str,
    trusted_run_attempt: int,
    trusted_source_sha: str,
) -> dict[str, object]:
    _, receipt = _read_canonical_json(
        path,
        "trusted conventional CI receipt",
        maximum_bytes=MAX_CONVENTIONAL_CI_SNAPSHOT,
    )
    if set(receipt) != {
        "checks",
        "ci",
        "context",
        "output",
        "receipt_digest",
        "repository",
        "schema",
        "source",
        "status",
    }:
        raise ValueError("trusted conventional CI receipt fields are not exact")
    if (
        receipt.get("schema") != CONVENTIONAL_CI_RECEIPT_SCHEMA
        or receipt.get("repository") != EXPECTED_REPOSITORY
        or receipt.get("source") != CONVENTIONAL_CI_SOURCE
        or receipt.get("status") != "pass"
    ):
        raise ValueError("trusted conventional CI receipt identity is invalid")
    digest = receipt.get("receipt_digest")
    if (
        not isinstance(digest, dict)
        or set(digest) != {"algorithm", "value"}
        or digest.get("algorithm") != "sha256"
        or not re.fullmatch(r"[0-9a-f]{64}", str(digest.get("value", "")))
    ):
        raise ValueError("trusted conventional CI receipt digest is malformed")
    claimed_digest = digest["value"]
    clone = json.loads(json.dumps(receipt))
    clone["receipt_digest"]["value"] = "0" * 64
    if hashlib.sha256(canonical_bytes(clone)).hexdigest() != claimed_digest:
        raise ValueError("trusted conventional CI receipt self-digest mismatch")
    expected_binding = _conventional_ci_context_binding(
        context,
        trusted_run_id=trusted_run_id,
        trusted_run_attempt=trusted_run_attempt,
        trusted_source_sha=trusted_source_sha,
    )
    if receipt.get("context") != expected_binding:
        raise ValueError("trusted conventional CI receipt context binding mismatch")

    ci = receipt.get("ci")
    if not isinstance(ci, dict) or set(ci) != {
        "check_suite_id",
        "control_files_sha256",
        "inventory_sha256",
        "run_attempt",
        "run_id",
        "workflow",
        "workflow_path",
    }:
        raise ValueError("trusted conventional CI receipt run fields are not exact")
    if (
        ci.get("workflow") != "CI"
        or ci.get("workflow_path") != ".github/workflows/ci.yml"
        or not str(ci.get("run_id", "")).isdigit()
        or not isinstance(ci.get("run_attempt"), int)
        or isinstance(ci.get("run_attempt"), bool)
        or ci["run_attempt"] < 1
        or not isinstance(ci.get("check_suite_id"), int)
        or isinstance(ci.get("check_suite_id"), bool)
        or ci["check_suite_id"] < 1
        or not re.fullmatch(r"[0-9a-f]{64}", str(ci.get("inventory_sha256", "")))
        or not re.fullmatch(r"[0-9a-f]{64}", str(ci.get("control_files_sha256", "")))
    ):
        raise ValueError("trusted conventional CI receipt run binding is invalid")
    checks = receipt.get("checks")
    if not isinstance(checks, list) or tuple(
        item.get("name") if isinstance(item, dict) else None for item in checks
    ) != CONVENTIONAL_CI_CHECKS:
        raise ValueError("trusted conventional CI receipt check inventory is not exact")
    check_ids: set[int] = set()
    job_ids: set[int] = set()
    for item in checks:
        if set(item) != {"check_id", "job_id", "name"}:
            raise ValueError("trusted conventional CI receipt check fields are not exact")
        check_id = _positive_int(item.get("check_id"), "conventional CI receipt check ID")
        job_id = _positive_int(item.get("job_id"), "conventional CI receipt job ID")
        if check_id in check_ids or job_id in job_ids:
            raise ValueError("trusted conventional CI receipt IDs are duplicated")
        check_ids.add(check_id)
        job_ids.add(job_id)
    output = receipt.get("output")
    if (
        not isinstance(output, dict)
        or set(output) != {"bytes", "sha256"}
        or not isinstance(output.get("bytes"), int)
        or isinstance(output.get("bytes"), bool)
        or not 1 <= output["bytes"] <= MAX_CONVENTIONAL_CI_SNAPSHOT
        or not re.fullmatch(r"[0-9a-f]{64}", str(output.get("sha256", "")))
    ):
        raise ValueError("trusted conventional CI receipt output binding is invalid")
    return output


def emit_job_artifact(
    kind: str,
    jobs_path: Path,
    job_log_path: Path,
    output_path: Path,
    context: dict[str, object],
    catalog_path: Path,
    *,
    trusted_run_id: str,
    trusted_run_attempt: int,
    trusted_source_sha: str,
    supervisor_receipt_path: Path | None = None,
    conventional_ci_receipt_path: Path | None = None,
    preflight_receipt_path: Path | None = None,
    supervisor_target_path: Path | None = None,
) -> dict:
    """Derive a receipt from immutable GitHub job state on a fresh runner."""
    if kind not in ALL_KINDS or kind == "overlap":
        raise ValueError(f"GitHub-job evidence kind is not supported: {kind}")
    if job_log_path.name != f"{kind}.job.log":
        raise ValueError(f"{kind} GitHub job log must be named {kind}.job.log")
    if (
        not trusted_run_id.isdigit()
        or isinstance(trusted_run_attempt, bool)
        or trusted_run_attempt < 1
        or not re.fullmatch(
        r"[0-9a-f]{40}", trusted_source_sha
        )
    ):
        raise ValueError("trusted GitHub job run identity is invalid")
    jobs_document = json.loads(jobs_path.read_bytes())
    if not isinstance(jobs_document, dict) or not isinstance(jobs_document.get("jobs"), list):
        raise ValueError("GitHub job listing is malformed")
    jobs = jobs_document["jobs"]
    if jobs_document.get("total_count") != len(jobs):
        raise ValueError("GitHub job listing is incomplete or paginated")
    matches = [job for job in jobs if job.get("name") == f"trusted-evidence-{kind}"]
    if len(matches) != 1 or not isinstance(matches[0], dict):
        raise ValueError(f"GitHub job listing must contain exactly one trusted-evidence-{kind}")
    job = matches[0]
    if (
        job.get("status") != "completed"
        or job.get("conclusion") != "success"
        or str(job.get("run_id")) != trusted_run_id
        or job.get("head_sha") != trusted_source_sha
        or not isinstance(job.get("id"), int)
        or isinstance(job.get("id"), bool)
        or job["id"] < 1
    ):
        raise ValueError(f"trusted-evidence-{kind} did not complete successfully")
    steps = job.get("steps")
    fixed_steps = (
        [step for step in steps if step.get("name") == "Execute one fixed check and discard raw output"]
        if isinstance(steps, list) and all(isinstance(step, dict) for step in steps)
        else []
    )
    if (
        len(fixed_steps) != 1
        or fixed_steps[0].get("status") != "completed"
        or fixed_steps[0].get("conclusion") != "success"
    ):
        raise ValueError(f"trusted-evidence-{kind} fixed command step is not successful")
    raw_log = job_log_path.read_bytes()
    if not raw_log or len(raw_log) > 50 * 1024 * 1024:
        raise ValueError(f"trusted-evidence-{kind} job log size is invalid")
    _reject_sensitive(raw_log, f"trusted-evidence-{kind} GitHub job log")
    trusted_output: dict[str, object] | None = None
    if kind == "ci":
        if supervisor_receipt_path is not None or preflight_receipt_path is not None:
            raise ValueError("trusted-evidence-ci cannot use a candidate execution receipt")
        if conventional_ci_receipt_path is None:
            raise ValueError("trusted-evidence-ci conventional CI receipt is absent")
        trusted_output = _validate_conventional_ci_receipt(
            conventional_ci_receipt_path,
            context,
            trusted_run_id=trusted_run_id,
            trusted_run_attempt=trusted_run_attempt,
            trusted_source_sha=trusted_source_sha,
        )
    elif kind in SUPERVISED_KINDS:
        if conventional_ci_receipt_path is not None or preflight_receipt_path is not None:
            raise ValueError(f"trusted-evidence-{kind} has an unexpected conventional CI receipt")
        if supervisor_receipt_path is None:
            raise ValueError(f"trusted-evidence-{kind} supervisor receipt is absent")
        trusted_output = _validate_supervisor_receipt(
            supervisor_receipt_path,
            kind,
            context,
            catalog_path.parents[1],
            trusted_run_id=trusted_run_id,
            trusted_run_attempt=trusted_run_attempt,
            trusted_source_sha=trusted_source_sha,
            candidate_target_path=supervisor_target_path,
        )
    else:
        if supervisor_receipt_path is not None or conventional_ci_receipt_path is not None:
            raise ValueError(f"trusted-evidence-{kind} has an unexpected trusted receipt")
        if preflight_receipt_path is None:
            raise ValueError(f"trusted-evidence-{kind} preflight receipt is absent")
        trusted_output = _validate_preflight_receipt(
            preflight_receipt_path,
            kind,
            context,
            catalog_path,
        )
    producer = _producer_for(kind)
    _ensure_profile(producer, catalog_path)
    document = {
        "base_sha": context["base_sha"],
        "generated_at": _format_time(_now()),
        "head_sha": context["head_sha"],
        "kind": kind,
        "objective": context["objective"],
        "producer": producer,
        "ref": context["ref"],
        "repository": context["repository"],
        "result": {
            "check": kind,
            "command_id": COMMAND_IDS[kind],
            "exit_code": 0,
            "output_bytes": (
                trusted_output["bytes"] if trusted_output is not None else len(raw_log)
            ),
            "output_sha256": (
                trusted_output["sha256"]
                if trusted_output is not None
                else hashlib.sha256(raw_log).hexdigest()
            ),
            "status": "pass",
        },
        "run_attempt": context["run_attempt"],
        "run_id": context["run_id"],
        "schema": EVIDENCE_SCHEMA,
        "workflow": context["workflow"],
        "workflow_ref": context["workflow_ref"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(canonical_document(document))
    return document


def _validate_supervisor_receipt(
    path: Path,
    kind: str,
    context: dict[str, object],
    trusted_root: Path,
    *,
    trusted_run_id: str,
    trusted_run_attempt: int,
    trusted_source_sha: str,
    candidate_target_path: Path | None = None,
) -> dict[str, object]:
    del trusted_run_id, trusted_run_attempt
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("trusted supervisor receipt is missing or outside the safety bound")
    raw = path.read_bytes()
    _reject_sensitive(raw, "trusted supervisor receipt")
    try:
        receipt = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("trusted supervisor receipt is malformed") from exc
    if not isinstance(receipt, dict) or raw != canonical_document(receipt):
        raise ValueError("trusted supervisor receipt is not canonical JSON")
    expected_keys = {
        "command_id",
        "context",
        "kind",
        "observation",
        "observer",
        "receipt_digest",
        "result",
        "schema",
        "status",
        "target",
    }
    if set(receipt) != expected_keys:
        raise ValueError("trusted supervisor receipt fields are not exact")
    if (
        receipt.get("schema") != SUPERVISOR_SCHEMA
        or receipt.get("kind") != kind
        or receipt.get("command_id") != COMMAND_IDS[kind]
        or receipt.get("status") != "pass"
    ):
        raise ValueError("trusted supervisor receipt did not record normal success")
    digest = receipt.get("receipt_digest")
    if not isinstance(digest, dict) or set(digest) != {"algorithm", "value"}:
        raise ValueError("trusted supervisor receipt digest is malformed")
    claimed_digest = digest.get("value")
    if digest.get("algorithm") != "sha256" or not re.fullmatch(
        r"[0-9a-f]{64}", str(claimed_digest)
    ):
        raise ValueError("trusted supervisor receipt digest is malformed")
    clone = json.loads(json.dumps(receipt))
    clone["receipt_digest"]["value"] = "0" * 64
    if hashlib.sha256(canonical_bytes(clone)).hexdigest() != claimed_digest:
        raise ValueError("trusted supervisor receipt self-digest mismatch")
    expected_context = {
        "base_sha": context["base_sha"],
        "head_sha": context["head_sha"],
        "request_run_attempt": context["run_attempt"],
        "request_run_id": str(context["run_id"]),
        "trusted_source_sha": context["base_sha"],
    }
    if trusted_source_sha != context["base_sha"] or receipt.get("context") != expected_context:
        raise ValueError("trusted supervisor receipt context binding mismatch")
    observer = receipt.get("observer")
    if (
        not isinstance(observer, dict)
        or set(observer) != {"path", "sha256"}
        or observer.get("path") != "scripts/supervise_autonomy_check.py"
        or observer.get("sha256")
        != sha256_file(trusted_root / "scripts" / "supervise_autonomy_check.py")
    ):
        raise ValueError("trusted supervisor executable digest mismatch")
    target_path = candidate_target_path or (trusted_root / "saas_server.py")
    if target_path.is_symlink() or not target_path.is_file():
        raise ValueError("trusted supervisor target snapshot is invalid")
    target = receipt.get("target")
    if (
        not isinstance(target, dict)
        or set(target) != {"path", "sha256"}
        or target.get("path") != "saas_server.py"
        or target.get("sha256") != sha256_file(target_path)
    ):
        raise ValueError("trusted supervisor target digest mismatch")
    output = receipt.get("observation")
    if (
        not isinstance(output, dict)
        or set(output) != {"bytes", "sha256"}
        or not isinstance(output.get("bytes"), int)
        or isinstance(output.get("bytes"), bool)
        or not 1 <= output["bytes"] <= MAX_SUPERVISED_OUTPUT
        or not re.fullmatch(r"[0-9a-f]{64}", str(output.get("sha256", "")))
    ):
        raise ValueError("trusted supervisor output binding is invalid")
    result = receipt.get("result")
    expected_total = 2 if kind == "runtime" else 7
    if (
        not isinstance(result, dict)
        or set(result) != {"passed", "total"}
        or not isinstance(result.get("passed"), int)
        or isinstance(result.get("passed"), bool)
        or not isinstance(result.get("total"), int)
        or isinstance(result.get("total"), bool)
        or result["passed"] != result["total"]
        or result["total"] != expected_total
    ):
        raise ValueError("trusted supervisor result inventory is invalid")
    return output


def _validate_preflight_receipt(
    path: Path,
    kind: str,
    context: dict[str, object],
    catalog_path: Path,
) -> dict[str, object]:
    if kind in SUPERVISED_KINDS or kind in {"ci", "overlap", "final-review"}:
        raise ValueError(f"{kind} cannot use a generic preflight receipt")
    raw, receipt = _read_canonical_json(
        path,
        f"{kind} preflight receipt",
        maximum_bytes=1024 * 1024,
    )
    expected_fields = {
        "base_sha",
        "generated_at",
        "head_sha",
        "kind",
        "objective",
        "producer",
        "ref",
        "repository",
        "result",
        "run_attempt",
        "run_id",
        "schema",
        "workflow",
        "workflow_ref",
    }
    if set(receipt) != expected_fields:
        raise ValueError(f"{kind} preflight receipt fields are not exact")
    for field in (
        "base_sha",
        "head_sha",
        "objective",
        "ref",
        "repository",
        "run_attempt",
        "run_id",
        "workflow",
        "workflow_ref",
    ):
        if receipt.get(field) != context.get(field):
            raise ValueError(f"{kind} preflight receipt context binding mismatch")
    if receipt.get("schema") != EVIDENCE_SCHEMA or receipt.get("kind") != kind:
        raise ValueError(f"{kind} preflight receipt identity is invalid")
    producer = _producer_for(kind)
    _ensure_profile(producer, catalog_path)
    if receipt.get("producer") != producer:
        raise ValueError(f"{kind} preflight receipt producer is not canonical")
    generated = receipt.get("generated_at")
    try:
        timestamp = datetime.fromisoformat(str(generated).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{kind} preflight receipt timestamp is invalid") from exc
    age = _now() - timestamp.astimezone(timezone.utc)
    if age < timedelta(minutes=-5) or age > timedelta(days=1):
        raise ValueError(f"{kind} preflight receipt is expired")
    result = receipt.get("result")
    if (
        not isinstance(result, dict)
        or set(result)
        != {"check", "command_id", "exit_code", "output_bytes", "output_sha256", "status"}
        or result.get("check") != kind
        or result.get("command_id") != COMMAND_IDS[kind]
        or result.get("exit_code") != 0
        or result.get("status") != "pass"
        or not isinstance(result.get("output_bytes"), int)
        or isinstance(result.get("output_bytes"), bool)
        or not 1 <= result["output_bytes"] <= 50 * 1024 * 1024
        or not re.fullmatch(r"[0-9a-f]{64}", str(result.get("output_sha256", "")))
    ):
        raise ValueError(f"{kind} preflight result is invalid")
    _reject_sensitive(raw, f"{kind} preflight receipt")
    return {"bytes": result["output_bytes"], "sha256": result["output_sha256"]}


def _api_json(url: str, token: str):
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "lucidfence-autonomy-evidence",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed GitHub API origin
            return json.load(response)
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"GitHub overlap API failed: {type(exc).__name__}") from exc


def _api_pages(url: str, token: str) -> list[dict]:
    """Read every GitHub list page, failing closed on malformed/truncated data."""
    values: list[dict] = []
    separator = "&" if "?" in url else "?"
    for page in range(1, 101):
        payload = _api_json(f"{url}{separator}per_page=100&page={page}", token)
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
            raise RuntimeError("GitHub overlap API returned malformed list data")
        values.extend(payload)
        if len(payload) < 100:
            return values
    raise RuntimeError("GitHub overlap API pagination exceeded safety limit")


def workflow_run_context_from_environment(env: dict[str, str]) -> dict[str, object]:
    """Derive producer context from GitHub's trusted ``workflow_run`` payload."""
    if env.get("GITHUB_REPOSITORY") != EXPECTED_REPOSITORY:
        raise ValueError(f"repository must be exactly {EXPECTED_REPOSITORY}")
    token = env.get("GITHUB_TOKEN") or env.get("GH_TOKEN")
    if not token:
        raise ValueError("GitHub token unavailable for trusted context derivation")
    event = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_bytes())
    run = event.get("workflow_run")
    if not isinstance(run, dict):
        raise ValueError("trusted assembly requires a workflow_run event")
    if (
        run.get("name") != "autonomy-evidence"
        or run.get("event") != "pull_request"
        or run.get("conclusion") != "success"
        or run.get("path") != ".github/workflows/autonomy-evidence.yml"
        or run.get("head_repository", {}).get("full_name") != EXPECTED_REPOSITORY
    ):
        raise ValueError("workflow_run is not the successful canonical autonomy-evidence producer")
    pulls = run.get("pull_requests")
    if not isinstance(pulls, list) or len(pulls) != 1 or not isinstance(pulls[0], dict):
        raise ValueError("workflow_run must bind exactly one pull request")
    number = pulls[0].get("number")
    if not isinstance(number, int) or number <= 0:
        raise ValueError("workflow_run pull request number is invalid")
    run_id = run.get("id")
    run_attempt = run.get("run_attempt")
    run_head_sha = run.get("head_sha")
    snapshot_base_sha = pulls[0].get("base", {}).get("sha")
    snapshot_head_sha = pulls[0].get("head", {}).get("sha")
    if (
        not isinstance(run_id, int)
        or run_id <= 0
        or not isinstance(run_attempt, int)
        or isinstance(run_attempt, bool)
        or run_attempt < 1
        or not re.fullmatch(r"[0-9a-f]{40}", str(run_head_sha))
        or not re.fullmatch(r"[0-9a-f]{40}", str(snapshot_base_sha))
        or not re.fullmatch(r"[0-9a-f]{40}", str(snapshot_head_sha))
    ):
        raise ValueError("workflow_run immutable identity is invalid")
    base_url = env.get("GITHUB_API_URL", "https://api.github.com")
    pull = _api_json(f"{base_url}/repos/{EXPECTED_REPOSITORY}/pulls/{number}", token)
    if not isinstance(pull, dict):
        raise RuntimeError("GitHub pull request API returned malformed data")
    base_sha = pull.get("base", {}).get("sha")
    head_sha = pull.get("head", {}).get("sha")
    if not re.fullmatch(r"[0-9a-f]{40}", str(base_sha)) or not re.fullmatch(
        r"[0-9a-f]{40}", str(head_sha)
    ):
        raise ValueError("GitHub pull request base/head commits are invalid")
    if (
        run_head_sha != head_sha
        or snapshot_head_sha != head_sha
        or snapshot_base_sha != base_sha
    ):
        raise ValueError("workflow_run no longer matches the live pull request commits")
    files = _api_pages(
        f"{base_url}/repos/{EXPECTED_REPOSITORY}/pulls/{number}/files", token
    )
    paths = _pull_file_paths(files)
    ref = f"refs/pull/{number}/merge"
    return {
        "base_sha": base_sha,
        "changed_paths": sorted(set(paths)),
        "head_sha": head_sha,
        "objective": f"pull-request-{number}",
        "ref": ref,
        "repository": EXPECTED_REPOSITORY,
        "risk": classify_risk(paths),
        "run_attempt": run_attempt,
        "run_id": str(run_id),
        "workflow": "autonomy-evidence",
        "workflow_ref": (
            f"{EXPECTED_REPOSITORY}/.github/workflows/autonomy-evidence.yml@{ref}"
        ),
    }


def trusted_signer_context(env: dict[str, str]) -> dict[str, object]:
    """Validate and return immutable signer identity from the current trusted run."""
    if env.get("GITHUB_WORKFLOW") != "autonomy-attest":
        raise ValueError("trusted signer workflow must be autonomy-attest")
    source_digest = env.get("GITHUB_SHA", "")
    workflow_digest = env.get("GITHUB_WORKFLOW_SHA", "")
    source_ref = env.get("GITHUB_REF", "")
    workflow_ref = env.get("GITHUB_WORKFLOW_REF", "")
    if not re.fullmatch(r"[0-9a-f]{40}", source_digest):
        raise ValueError("trusted signer source digest is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", workflow_digest):
        raise ValueError("trusted signer workflow digest is invalid")
    if source_ref != "refs/heads/main":
        raise ValueError("trusted signer must execute from refs/heads/main")
    expected_workflow_ref = (
        f"{EXPECTED_REPOSITORY}/.github/workflows/autonomy-attest.yml@refs/heads/main"
    )
    if workflow_ref != expected_workflow_ref:
        raise ValueError("trusted signer workflow ref mismatch")
    run_id = env.get("GITHUB_RUN_ID", "")
    run_attempt = int(env.get("GITHUB_RUN_ATTEMPT", "0"))
    if not run_id.isdigit() or run_attempt < 1:
        raise ValueError("trusted signer run identity is invalid")
    return {
        "ref": source_ref,
        "run_attempt": run_attempt,
        "run_id": run_id,
        "source_digest": source_digest,
        "workflow_digest": workflow_digest,
        "workflow_ref": workflow_ref,
    }


def conventional_ci_request_context_from_environment(env: dict[str, str]) -> dict[str, object]:
    """Build only the request binding needed for an API-derived CI receipt."""
    if env.get("GITHUB_REPOSITORY") != EXPECTED_REPOSITORY:
        raise ValueError(f"repository must be exactly {EXPECTED_REPOSITORY}")
    base_sha = env.get("LF_BASE_SHA", "")
    head_sha = env.get("LF_HEAD_SHA", "")
    run_id = env.get("LF_REQUEST_RUN_ID", "")
    try:
        run_attempt = int(env.get("LF_REQUEST_RUN_ATTEMPT", "0"))
        number = int(env.get("LF_PR_NUMBER", "0"))
    except ValueError as exc:
        raise ValueError("conventional CI request environment is invalid") from exc
    context = {
        "base_sha": base_sha,
        "head_sha": head_sha,
        "objective": f"pull-request-{number}",
        "repository": EXPECTED_REPOSITORY,
        "run_attempt": run_attempt,
        "run_id": run_id,
    }
    _conventional_ci_context_binding(
        context,
        trusted_run_id=env.get("GITHUB_RUN_ID", ""),
        trusted_run_attempt=int(env.get("GITHUB_RUN_ATTEMPT", "0")),
        trusted_source_sha=env.get("GITHUB_SHA", ""),
    )
    if number < 1:
        raise ValueError("conventional CI pull request number is invalid")
    return context


def _normalized_text(*values: object) -> str:
    raw = " ".join(value for value in values if isinstance(value, str))
    folded = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", folded.lower()).split())


def _objective_categories(title: object, body: object) -> set[str]:
    text = _normalized_text(title, body)
    categories: set[str] = set()
    if "agency agents" in text and re.search(r"\bcatalog(?:o|ue)?\b", text):
        categories.add("agency-catalog")
    if re.search(r"\b(?:autonomy|autonomia|mode|modo)\s+b\b", text):
        categories.add("autonomy-b")
    if "night shift" in text or "overnight" in text or re.search(r"\bnocturn\w*\b", text):
        categories.add("night-shift")
    if (
        "autonomy evidence" in text
        or "evidencia t4" in text
        or "artifact attestation" in text
        or "artifact attestations" in text
    ):
        categories.add("autonomy-evidence")
    return categories


def _owned_issue_ids(body: object) -> set[int]:
    if not isinstance(body, str):
        return set()
    ownership = re.compile(
        r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|claim(?:ed|s)?|"
        r"own(?:ed|s)?|issue|objective|cierra|cerrar|resuelve|resolver|"
        r"reclama|reclamar|objetivo)\s*:?[ \t]*(?:issue[ \t]+)?#([0-9]+)\b",
        re.IGNORECASE,
    )
    return {int(value) for value in ownership.findall(body)}


def _semantic_reasons(current: dict, candidate: dict) -> list[str]:
    shared = _objective_categories(current.get("title"), current.get("body")).intersection(
        _objective_categories(candidate.get("title"), candidate.get("body"))
    )
    specific = {"agency-catalog", "autonomy-b", "autonomy-evidence"}
    if not shared.intersection(specific):
        return []
    return [f"semantic:{category}" for category in sorted(shared)]


def _pull_file_paths(files: list[object]) -> list[str]:
    paths: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
            raise RuntimeError("GitHub pull request API returned an invalid changed path")
        paths.add(item["filename"])
        previous = item.get("previous_filename")
        if previous is not None:
            if not isinstance(previous, str) or item.get("status") != "renamed":
                raise RuntimeError("GitHub pull request API returned an invalid rename")
            paths.add(previous)
    return sorted(paths)


def _pull_snapshot(pull: dict, paths: list[str]) -> dict[str, object]:
    number = pull.get("number")
    if not isinstance(number, int) or number <= 0:
        raise RuntimeError("GitHub overlap API returned an invalid pull request ID")
    head_sha = pull.get("head", {}).get("sha") if isinstance(pull.get("head"), dict) else None
    if not re.fullmatch(r"[0-9a-f]{40}", str(head_sha)):
        raise RuntimeError("GitHub overlap API returned an invalid pull request head")
    metadata = canonical_bytes(
        {
            "body": pull.get("body") if isinstance(pull.get("body"), str) else "",
            "title": pull.get("title") if isinstance(pull.get("title"), str) else "",
        }
    )
    return {
        "head_sha": head_sha,
        "metadata_sha256": hashlib.sha256(metadata).hexdigest(),
        "number": number,
        "paths_sha256": hashlib.sha256(canonical_bytes(paths)).hexdigest(),
    }


def check_overlap(repo_root: Path, context: dict[str, object], env: dict[str, str]) -> dict:
    token = env.get("GITHUB_TOKEN") or env.get("GH_TOKEN")
    if not token:
        raise ValueError("GitHub token unavailable for overlap evidence")
    event = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_bytes())
    current = event.get("pull_request")
    current_number = current.get("number") if isinstance(current, dict) else None
    if not isinstance(current_number, int):
        match = re.fullmatch(r"pull-request-([1-9][0-9]*)", str(context.get("objective", "")))
        if not match:
            raise ValueError("GitHub pull request context is unavailable")
        current_number = int(match.group(1))
        base_url = env.get("GITHUB_API_URL", "https://api.github.com")
        current = _api_json(
            f"{base_url}/repos/{EXPECTED_REPOSITORY}/pulls/{current_number}", token
        )
        if not isinstance(current, dict):
            raise RuntimeError("GitHub current pull request API returned malformed data")
    if not isinstance(current_number, int) or current_number <= 0:
        raise ValueError("GitHub pull request number is invalid")
    base_url = env.get("GITHUB_API_URL", "https://api.github.com")
    pulls = _api_pages(f"{base_url}/repos/{EXPECTED_REPOSITORY}/pulls?state=open", token)
    current_paths = set(context["changed_paths"])
    current_issues = _owned_issue_ids(current.get("body"))
    overlaps: list[dict[str, object]] = []
    snapshots = [_pull_snapshot(current, sorted(current_paths))]
    for pull in pulls:
        number = pull.get("number")
        if number == current_number:
            continue
        if not isinstance(number, int) or number <= 0:
            raise RuntimeError("GitHub overlap API returned an invalid pull request ID")
        files = _api_pages(
            f"{base_url}/repos/{EXPECTED_REPOSITORY}/pulls/{number}/files", token
        )
        filenames = _pull_file_paths(files)
        snapshots.append(_pull_snapshot(pull, filenames))
        shared = sorted(current_paths.intersection(filenames))
        reasons = _semantic_reasons(current, pull)
        if shared:
            reasons.append("path-overlap")
        shared_issues = sorted(current_issues.intersection(_owned_issue_ids(pull.get("body"))))
        reasons.extend(f"issue-ownership:{issue_id}" for issue_id in shared_issues)
        reasons = sorted(set(reasons))
        if reasons:
            overlaps.append({"paths": shared, "pull_request": number, "reasons": reasons})
    overlaps.sort(key=lambda item: int(item["pull_request"]))
    snapshots.sort(key=lambda item: int(item["number"]))
    return {
        "conflicts": [dict(item) for item in overlaps],
        "overlaps": [dict(item) for item in overlaps],
        "snapshot_sha256": hashlib.sha256(canonical_bytes(snapshots)).hexdigest(),
        "status": "pass" if not overlaps else "fail",
    }


def guard_open_pull_requests(
    env: dict[str, str],
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    """Derive only fail-closed invalidations for live PR overlap or stale evidence."""
    token = env.get("GITHUB_TOKEN") or env.get("GH_TOKEN")
    if not token:
        raise ValueError("GitHub token unavailable for autonomy guard")
    current_time = (now or _now()).astimezone(timezone.utc)
    base_url = env.get("GITHUB_API_URL", "https://api.github.com")
    raw_pulls = _api_pages(
        f"{base_url}/repos/{EXPECTED_REPOSITORY}/pulls?state=open",
        token,
    )
    pulls: list[dict[str, object]] = []
    for pull in raw_pulls:
        number = pull.get("number")
        head = pull.get("head")
        base = pull.get("base")
        if (
            not isinstance(number, int)
            or number < 1
            or not isinstance(head, dict)
            or not isinstance(base, dict)
        ):
            raise RuntimeError("GitHub guard received malformed pull request identity")
        head_sha = head.get("sha")
        head_repo = head.get("repo")
        if base.get("ref") != "main":
            continue
        if not isinstance(head_repo, dict) or head_repo.get("full_name") != EXPECTED_REPOSITORY:
            continue
        if not re.fullmatch(r"[0-9a-f]{40}", str(head_sha)):
            raise RuntimeError("GitHub guard received malformed pull request head")
        files = _api_pages(
            f"{base_url}/repos/{EXPECTED_REPOSITORY}/pulls/{number}/files",
            token,
        )
        pulls.append(
            {
                "body": pull.get("body") if isinstance(pull.get("body"), str) else "",
                "head_sha": head_sha,
                "issues": _owned_issue_ids(pull.get("body")),
                "number": number,
                "paths": set(_pull_file_paths(files)),
                "pull": pull,
                "title": pull.get("title") if isinstance(pull.get("title"), str) else "",
            }
        )

    reasons_by_number: dict[int, set[str]] = {
        int(item["number"]): set() for item in pulls
    }
    for index, left in enumerate(pulls):
        for right in pulls[index + 1 :]:
            reasons = _semantic_reasons(left["pull"], right["pull"])
            shared_paths = left["paths"].intersection(right["paths"])
            if shared_paths:
                reasons.append("path-overlap")
            shared_issues = left["issues"].intersection(right["issues"])
            reasons.extend(f"issue-ownership:{issue_id}" for issue_id in sorted(shared_issues))
            if reasons:
                normalized = set(reasons)
                reasons_by_number[int(left["number"])].update(normalized)
                reasons_by_number[int(right["number"])].update(normalized)

    trusted_target = re.compile(
        rf"https://github\.com/{re.escape(EXPECTED_REPOSITORY)}/actions/runs/[1-9][0-9]*"
    )
    for pull in pulls:
        head_sha = str(pull["head_sha"])
        statuses = _api_pages(
            f"{base_url}/repos/{EXPECTED_REPOSITORY}/commits/{head_sha}/statuses",
            token,
        )
        latest = next(
            (item for item in statuses if item.get("context") == "autonomy-evidence"),
            None,
        )
        if latest is None or latest.get("state") != "success":
            continue
        number = int(pull["number"])
        created_at = latest.get("created_at")
        target_url = latest.get("target_url")
        description = latest.get("description")
        try:
            created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        except ValueError:
            reasons_by_number[number].add("invalid-success-status")
            continue
        if created.tzinfo is None:
            reasons_by_number[number].add("invalid-success-status")
            continue
        if (
            not isinstance(target_url, str)
            or trusted_target.fullmatch(target_url) is None
            or description != "Trusted evidence and attestation verified"
        ):
            reasons_by_number[number].add("untrusted-success-status")
        if current_time - created.astimezone(timezone.utc) >= GUARD_STATUS_MAX_AGE:
            reasons_by_number[number].add("evidence-expired")

    invalidations = [
        {
            "head_sha": str(item["head_sha"]),
            "pr_number": int(item["number"]),
            "reasons": sorted(reasons_by_number[int(item["number"])]),
        }
        for item in sorted(pulls, key=lambda value: int(value["number"]))
        if reasons_by_number[int(item["number"])]
    ]
    return {
        "evaluated_at": _format_time(current_time),
        "invalidations": invalidations,
        "schema": GUARD_SCHEMA,
        "status": "invalidate" if invalidations else "pass",
    }


def _review_workflow_boundaries(repo_root: Path) -> list[str]:
    """Independently enforce the producer/signer privilege separation."""
    findings: list[str] = []
    producer_path = repo_root / ".github" / "workflows" / "autonomy-evidence.yml"
    signer_path = repo_root / ".github" / "workflows" / "autonomy-attest.yml"
    guard_path = repo_root / ".github" / "workflows" / "autonomy-guard.yml"
    verifier_path = repo_root / "scripts" / "verify_autonomy_evidence.py"
    if (
        not producer_path.is_file()
        or not signer_path.is_file()
        or not guard_path.is_file()
        or not verifier_path.is_file()
    ):
        return [
            "canonical producer, trusted signer, expiry/overlap guard, "
            "or attestation verifier is absent"
        ]

    producer = producer_path.read_text(encoding="utf-8")
    signer = signer_path.read_text(encoding="utf-8")
    guard = guard_path.read_text(encoding="utf-8")
    verifier = verifier_path.read_text(encoding="utf-8")
    producer_surface, producer_advanced_yaml = _workflow_yaml_surfaces(producer)
    signer_surface, signer_advanced_yaml = _workflow_yaml_surfaces(signer)
    signer_lines = signer.splitlines()
    try:
        event_start = signer_lines.index("on:")
    except ValueError:
        signer_events: list[str] = []
    else:
        signer_events = ["on:"]
        for line in signer_lines[event_start + 1 :]:
            if line and not line[0].isspace():
                break
            if line:
                signer_events.append(line)
    expected_signer_events = [
        "on:",
        "  workflow_run:",
        "    workflows: [autonomy-evidence]",
        "    types: [requested, completed]",
    ]
    if signer_events != expected_signer_events:
        findings.append(
            "trusted signer must use only workflow_run for requested/completed autonomy-evidence"
        )
    if "  pull_request:\n" not in producer_surface:
        findings.append("producer is not bound to the pull_request event")
    for privilege in ("id-token", "attestations", "statuses"):
        pattern = re.compile(
            rf"(?ix)[\"']?{re.escape(privilege)}[\"']?\s*:\s*[\"']?write[\"']?"
        )
        if pattern.search(producer_surface):
            label = "OIDC" if privilege == "id-token" else f"{privilege}: write"
            findings.append(f"producer has forbidden {label} privilege")
    if (
        "pull_request_target:" in producer_surface
        or WRITE_ALL_PERMISSION.search(producer_surface)
        or SCALAR_WORKFLOW_PERMISSIONS.search(producer_surface)
        or producer_advanced_yaml
    ):
        findings.append("producer uses a privileged untrusted-code trigger or permission")

    required_signer_markers = {
        "workflow_run:": "workflow_run trusted trigger",
        "attestations: write": "artifact-attestation permission",
        "id-token: write": "OIDC permission",
        "statuses: write": "commit-status permission",
        "ref: ${{ github.sha }}": "trusted default-branch checkout",
        "--attestation-bundle": "offline official-bundle verification",
        "--trusted-root": "captured trusted-root verification",
    }
    for marker, description in required_signer_markers.items():
        if marker not in signer:
            findings.append(f"trusted signer lacks {description}")
    if "ref: ${{ github.event.workflow_run.head_sha }}" in signer_surface:
        findings.append("trusted signer checks out the untrusted producer head")
    if (
        "pull_request_target:" in signer_surface
        or WRITE_ALL_PERMISSION.search(signer_surface)
        or SCALAR_WORKFLOW_PERMISSIONS.search(signer_surface)
        or signer_advanced_yaml
    ):
        findings.append("trusted signer has an unsafe trigger or broad permission")
    for privilege in ("attestations", "id-token", "statuses"):
        count = len(
            re.findall(
                rf"(?im)^[ \t]+[\"']?{re.escape(privilege)}[\"']?"
                rf"\s*:\s*[\"']?write[\"']?\s*$",
                signer_surface,
            )
        )
        if count != 1:
            findings.append(f"trusted signer must declare {privilege}: write exactly once")
    if re.search(
        r"(?im)^[ \t]+[\"']?checks[\"']?\s*:\s*[\"']?write[\"']?\s*$",
        signer_surface,
    ):
        findings.append("trusted signer must not acquire checks: write")
    if (
        "name: autonomy-guard" not in guard
        or "workflow_run:" not in guard
        or "pull_request_target:" not in guard
        or "schedule:" not in guard
        or "pull_request:" in guard
        or len(re.findall(r"(?m)^\s+statuses:\s*write\s*$", guard)) != 1
        or "-f state=success" in guard
        or "-f state=failure" not in guard
    ):
        findings.append("trusted expiry/overlap guard can do more than invalidate")
    required_verifier_markers = {
        '"--bundle"': "offline official bundle enforcement",
        '"--custom-trusted-root"': "offline trusted-root enforcement",
        '"--deny-self-hosted-runners"': "GitHub-hosted attestation verification",
        '"--signer-digest"': "trusted signer workflow digest verification",
    }
    for marker, description in required_verifier_markers.items():
        if marker not in verifier:
            findings.append(f"attestation verifier lacks {description}")

    for relative, text in (
        (producer_path.name, producer),
        (signer_path.name, signer),
        (guard_path.name, guard),
    ):
        for reference in re.findall(r"^\s*-?\s*uses:\s*([^\s#]+)", text, re.MULTILINE):
            if not reference.startswith("./") and not re.search(r"@[0-9a-f]{40}$", reference):
                findings.append(f"{relative}: mutable action reference {reference}")
    return findings


def review_changed_files(
    repo_root: Path,
    context: dict[str, object],
    seat: str,
    *,
    trusted: bool = False,
) -> dict:
    findings: list[str] = []
    for relative in context["changed_paths"]:
        if trusted and relative in CONTROL_PLANE_ASSETS:
            findings.append(
                f"{relative}: trusted control-plane changes require a dedicated bootstrap"
            )
        path = repo_root / relative
        if relative in CONTROL_PLANE_ASSETS and (
            path.is_symlink() or not path.is_file()
        ):
            findings.append(f"{relative}: canonical control-plane asset is absent or renamed")
            continue
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if Path(relative).name in {"sitecustomize.py", "usercustomize.py"}:
            findings.append(f"{relative}: Python startup injection is forbidden")
        for pattern, description in SENSITIVE_PATTERNS:
            if pattern.search(raw):
                findings.append(f"{relative}: {description}")
        if relative.startswith(".github/workflows/"):
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                findings.append(f"{relative}: workflow is not valid UTF-8")
                continue
            workflow_surface, advanced_yaml = _workflow_yaml_surfaces(text)
            pull_request_trigger = _workflow_has_event(
                workflow_surface, "pull_request"
            )
            if (
                _workflow_has_event(workflow_surface, "pull_request_target")
                or WRITE_ALL_PERMISSION.search(workflow_surface)
                or SCALAR_WORKFLOW_PERMISSIONS.search(workflow_surface)
                or advanced_yaml
            ):
                findings.append(f"{relative}: unsafe workflow privilege pattern")
            if pull_request_trigger:
                if re.search(
                    r"(?im)^[ \t]+[A-Za-z][A-Za-z0-9-]*\s*:\s*write\s*$",
                    workflow_surface,
                ):
                    findings.append(
                        f"{relative}: pull_request workflow has a write permission"
                    )
                if re.search(r"(?m)^permissions:\s*(?:\{\})?\s*$", workflow_surface) is None:
                    findings.append(
                        f"{relative}: pull_request workflow lacks explicit bounded permissions"
                    )
            if (
                relative != ".github/workflows/autonomy-attest.yml"
                and FORBIDDEN_WORKFLOW_PERMISSION.search(workflow_surface)
            ):
                findings.append(
                    f"{relative}: non-signer workflow can perform status/check spoofing or signing"
                )
            for reference in re.findall(r"^\s*-?\s*uses:\s*([^\s#]+)", text, re.MULTILINE):
                if not reference.startswith("./") and not re.search(r"@[0-9a-f]{40}$", reference):
                    findings.append(f"{relative}: mutable action reference {reference}")
    if {"requirements.lock", "pyproject.toml"}.intersection(context["changed_paths"]):
        try:
            validate_runtime_requirement_lock(repo_root / "requirements.lock")
        except (OSError, ValueError) as exc:
            findings.append(f"requirements.lock: {exc}")
    if seat == "appsec-secondary":
        findings.extend(_review_workflow_boundaries(repo_root))
        codeowners = (repo_root / ".github" / "CODEOWNERS")
        if not codeowners.is_file() or "@adrimg3196" not in codeowners.read_text(encoding="utf-8"):
            findings.append("control-plane CODEOWNERS protection is absent")
    return {"findings": findings, "seat": seat, "status": "pass" if not findings else "fail"}


def final_review(evidence_dir: Path, context: dict[str, object]) -> dict:
    missing: list[str] = []
    invalid: list[str] = []
    kinds = list(REQUIRED_ARTIFACTS[:-1])
    if context["risk"] == "high":
        kinds.extend(HIGH_RISK_ARTIFACTS)
    for kind in kinds:
        path = evidence_dir / f"{kind}.json"
        if not path.is_file():
            missing.append(kind)
            continue
        document = json.loads(path.read_bytes())
        if document.get("kind") != kind or document.get("result", {}).get("status") != "pass":
            invalid.append(kind)
        for field in ("repository", "base_sha", "head_sha", "run_id", "run_attempt", "workflow", "workflow_ref", "ref"):
            if document.get(field) != context.get(field):
                invalid.append(f"{kind}:{field}")
    return {"invalid": sorted(set(invalid)), "missing": missing, "status": "pass" if not missing and not invalid else "fail"}


def assemble_manifest(
    evidence_dir: Path,
    output_path: Path,
    context: dict[str, object],
    signer: dict[str, object],
    catalog_path: Path,
    generated_at: datetime | None = None,
) -> dict:
    for profile in (PRODUCT, MAKER, FINAL, APPSEC_PRIMARY, APPSEC_SECONDARY):
        _ensure_profile(_profile(profile), catalog_path)
    required = list(REQUIRED_ARTIFACTS)
    if context["risk"] == "high":
        required.extend(HIGH_RISK_ARTIFACTS)
    artifacts: dict[str, dict[str, object]] = {}
    for kind in required:
        path = evidence_dir / f"{kind}.json"
        document = json.loads(path.read_bytes())
        _reject_sensitive(path.read_bytes(), f"artifact {kind}")
        artifacts[kind] = {
            "path": path.name,
            "producer": document["producer"],
            "sha256": sha256_file(path),
        }
    timestamp = (generated_at or _now()).astimezone(timezone.utc).replace(microsecond=0)
    manifest = {
        "artifacts": artifacts,
        "attestation": {
            "base_sha": context["base_sha"],
            "evidence_run": {
                "attempt": context["run_attempt"],
                "id": context["run_id"],
                "ref": context["ref"],
                "workflow": context["workflow"],
                "workflow_ref": context["workflow_ref"],
            },
            "head_sha": context["head_sha"],
            "predicate_type": "https://slsa.dev/provenance/v1",
            "repository": context["repository"],
            "signer": dict(signer),
        },
        "base_sha": context["base_sha"],
        "generated_at": _format_time(timestamp),
        "head_sha": context["head_sha"],
        "manifest_digest": {"algorithm": "sha256", "value": "0" * 64},
        "objective": {
            "changed_paths": context["changed_paths"],
            "id": context["objective"],
            "risk": context["risk"],
        },
        "participants": {
            "appsec_primary": _profile(APPSEC_PRIMARY),
            "appsec_secondary": _profile(APPSEC_SECONDARY),
            "final_reviewer": _profile(FINAL),
            "maker": _profile(MAKER),
            "product_owner": _profile(PRODUCT),
            "reality_checker": _profile(FINAL),
        },
        "ref": context["ref"],
        "repository": context["repository"],
        "run_attempt": context["run_attempt"],
        "run_id": context["run_id"],
        "schema": MANIFEST_SCHEMA,
        "validity": {
            "expires_at": _format_time(timestamp + timedelta(days=7)),
            "not_before": _format_time(timestamp),
            "policy": "P7D",
        },
        "workflow": context["workflow"],
        "workflow_ref": context["workflow_ref"],
    }
    seal_manifest(manifest)
    output_path.write_bytes(canonical_document(manifest))
    return manifest


def _write_result(path: Path, value: dict) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_document(value))
    return 0 if value.get("status") == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--catalog", type=Path, default=ROOT / "data" / "agency_catalog.json")
    sub = parser.add_subparsers(dest="command", required=True)
    emit = sub.add_parser("emit")
    emit.add_argument("--kind", choices=ALL_KINDS, required=True)
    emit.add_argument("--log", type=Path, required=True)
    emit.add_argument("--output", type=Path, required=True)
    job = sub.add_parser("emit-job")
    job.add_argument("--kind", choices=tuple(kind for kind in ALL_KINDS if kind != "overlap"), required=True)
    job.add_argument("--jobs-json", type=Path, required=True)
    job.add_argument("--job-log", type=Path, required=True)
    job.add_argument("--output", type=Path, required=True)
    job.add_argument("--supervisor-receipt", type=Path)
    job.add_argument("--conventional-ci-receipt", type=Path)
    job.add_argument("--preflight-receipt", type=Path)
    job.add_argument("--supervisor-target", type=Path)
    ci_receipt = sub.add_parser("emit-ci-receipt")
    ci_receipt.add_argument("--snapshot", type=Path, required=True)
    ci_receipt.add_argument("--output", type=Path, required=True)
    overlap = sub.add_parser("overlap")
    overlap.add_argument("--output", type=Path, required=True)
    review = sub.add_parser("review")
    review.add_argument("--seat", choices=("appsec", "appsec-primary", "appsec-secondary"), required=True)
    review.add_argument("--output", type=Path, required=True)
    review.add_argument("--protect-trust-root", action="store_true")
    secret_scan = sub.add_parser("scan-secrets")
    secret_scan.add_argument("--output", type=Path, required=True)
    guard = sub.add_parser("guard-open-prs")
    guard.add_argument("--output", type=Path, required=True)
    final = sub.add_parser("final-review")
    final.add_argument("--evidence-dir", type=Path, required=True)
    final.add_argument("--output", type=Path, required=True)
    assemble = sub.add_parser("assemble")
    assemble.add_argument("--evidence-dir", type=Path, required=True)
    assemble.add_argument("--output", type=Path, required=True)
    changed = sub.add_parser("changed-paths")
    changed.add_argument("--output", type=Path, required=True)
    sub.add_parser("validate-lock")
    inspect = sub.add_parser("inspect-wheelhouse")
    inspect.add_argument("--lock", type=Path, required=True)
    inspect.add_argument("--wheelhouse", type=Path, required=True)
    inspect.add_argument("--runtime", action="store_true")
    args = parser.parse_args(argv)

    root = args.repo_root.resolve()
    catalog_path = args.catalog.resolve()
    if args.command == "validate-lock":
        validate_runtime_requirement_lock(root / "requirements.lock")
        return 0
    if args.command == "inspect-wheelhouse":
        inspect_wheelhouse(
            args.lock.resolve(),
            args.wheelhouse.resolve(),
            allowed_packages=RUNTIME_PACKAGE_ALLOWLIST if args.runtime else None,
        )
        return 0
    if args.command == "emit":
        context = evidence_context(root)
        emit_artifact(args.kind, args.log, args.output, context, catalog_path)
        return 0
    if args.command == "emit-ci-receipt":
        environment = dict(os.environ)
        context = conventional_ci_request_context_from_environment(environment)
        signer = trusted_signer_context(environment)
        emit_conventional_ci_receipt(
            args.snapshot,
            args.output,
            context,
            trusted_run_id=str(signer["run_id"]),
            trusted_run_attempt=int(signer["run_attempt"]),
            trusted_source_sha=str(signer["source_digest"]),
        )
        return 0
    if args.command == "emit-job":
        context = evidence_context(root)
        emit_job_artifact(
            args.kind,
            args.jobs_json,
            args.job_log,
            args.output,
            context,
            catalog_path,
            trusted_run_id=os.environ.get("GITHUB_RUN_ID", ""),
            trusted_run_attempt=int(os.environ.get("GITHUB_RUN_ATTEMPT", "0")),
            trusted_source_sha=os.environ.get("GITHUB_SHA", ""),
            supervisor_receipt_path=args.supervisor_receipt,
            conventional_ci_receipt_path=args.conventional_ci_receipt,
            preflight_receipt_path=args.preflight_receipt,
            supervisor_target_path=args.supervisor_target,
        )
        return 0
    if args.command == "overlap":
        context = evidence_context(root)
        return _write_result(args.output, check_overlap(root, context, dict(os.environ)))
    if args.command == "scan-secrets":
        context = evidence_context(root)
        return _write_result(args.output, scan_changed_files_for_secrets(root, context))
    if args.command == "guard-open-prs":
        result = guard_open_pull_requests(dict(os.environ))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical_document(result))
        return 0
    if args.command == "review":
        context = evidence_context(root)
        return _write_result(
            args.output,
            review_changed_files(
                root,
                context,
                args.seat,
                trusted=(
                    args.protect_trust_root
                    or os.environ.get("LF_TRUSTED_CONTEXT") == "1"
                ),
            ),
        )
    if args.command == "final-review":
        context = evidence_context(root)
        return _write_result(args.output, final_review(args.evidence_dir, context))
    if args.command == "assemble":
        environment = dict(os.environ)
        context = evidence_context(root, environment)
        signer = trusted_signer_context(environment)
        assemble_manifest(args.evidence_dir, args.output, context, signer, catalog_path)
        return 0
    if args.command == "changed-paths":
        context = evidence_context(root)
        args.output.write_bytes(canonical_document(context["changed_paths"]))
        return 0
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"FALLO: {exc}", file=sys.stderr)
        raise SystemExit(1)
