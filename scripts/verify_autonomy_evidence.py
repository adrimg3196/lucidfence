#!/usr/bin/env python3
"""Offline verifier for LucidFence autonomy-B manifests and evidence.

The verifier treats every downloaded artifact as hostile input.  It validates
the raw JSON emitted by ``gh attestation verify`` rather than trusting a local
``verified`` boolean, and it independently receives the changed-path inventory
used to derive risk.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


MANIFEST_SCHEMA = "lucidfence-night-shift-manifest/v1"
EVIDENCE_SCHEMA = "lucidfence-autonomy-evidence/v1"
CATALOG_SCHEMA = "lucidfence-agency-catalog/v1"
CATALOG_LOCK_SCHEMA = "lucidfence-agency-agents-lock/v1"
CATALOG_REPOSITORY = "msitarzewski/agency-agents"
CATALOG_COMMIT = "ebe9c99acb5c96f9468de368d8bead775387d1a7"
CATALOG_LICENSE_SHA256 = "9a45258434d5cedf0af73c9ad4771373701225038d246c49219026c33677f66f"
CATALOG_INVENTORY_SHA256 = "068aa4b13c1292b27c451955d194fa8ecd027bb6243bef5d813207f90395adda"
CATALOG_DIVISIONS = (
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
CATALOG_PROFILE_COUNT = 270
REQUIRED_ARTIFACTS = (
    "ci",
    "runtime",
    "secrets",
    "dependencies",
    "license",
    "appsec",
    "reality",
    "overlap",
    "final-review",
)
HIGH_RISK_ARTIFACTS = ("appsec-primary", "appsec-secondary")
EXPECTED_COMMAND_IDS = {
    "ci": "github-ci-run",
    "runtime": "blackbox-runtime",
    "secrets": "trusted-secret-pattern-scan",
    "dependencies": "pip-audit-lock",
    "license": "license-and-pinned-catalog",
    "appsec": "appsec-policy-scan",
    "reality": "blackbox-reality",
    "overlap": "github-open-pr-overlap",
    "final-review": "manifest-independent-review",
    "appsec-primary": "appsec-engineer-independent-review",
    "appsec-secondary": "security-architect-independent-review",
}
HIGH_RISK_PREFIXES = (
    ".gitleaks.toml",
    ".github/",
    "config/",
    "data/agency_catalog.json",
    "data/night_shift/",
    "scripts/",
    "requirements.lock",
    "pyproject.toml",
    "sitecustomize.py",
    "usercustomize.py",
    "lucidfence/saas/auth",
    "lucidfence/core/actions",
    "SECURITY.md",
)
EXPECTED_PROFILES = {
    "product_owner": (
        "product/product-manager.md",
        "4a3fe4661e72e5173877bcba7c362392181774b20efc27ac1789171e98676c9d",
    ),
    "maker": (
        "engineering/engineering-api-platform-engineer.md",
        "278798c42d7a7cf4f42d3973795765403105ce60d518d647abfdaa522d862d8e",
    ),
    "final_reviewer": (
        "testing/testing-reality-checker.md",
        "6d32fcdb114233e13902ec6372d50293b120e85d490b5e81d372c29808f988a1",
    ),
    "reality_checker": (
        "testing/testing-reality-checker.md",
        "6d32fcdb114233e13902ec6372d50293b120e85d490b5e81d372c29808f988a1",
    ),
    "appsec_primary": (
        "security/security-appsec-engineer.md",
        "f3ee22350c9e0e7289d2d4747e7c1a8fe196d70340feec7b176b13bacc3deb77",
    ),
    "appsec_secondary": (
        "security/security-architect.md",
        "b1a68e9614f7adb43938f5bd9964f6e41250febc9a57f691eefcbab58d5b1df1",
    ),
}
SELF_DIGEST_ZERO = "0" * 64
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
DURABLE_BUNDLE_NAME = re.compile(
    r"^run-(?P<run_id>[1-9][0-9]*)-attempt-(?P<attempt>[1-9][0-9]*)-"
    r"head-(?P<head>[0-9a-f]{40})$"
)
DURABLE_BUNDLE_FILES = {
    "attestation.bundle.jsonl",
    "evidence",
    "manifest.json",
    "trusted-root.jsonl",
}
SENSITIVE_PATTERNS = (
    (re.compile(rb"ghp_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(rb"ghs_[A-Za-z0-9]{20,}"), "GitHub installation token"),
    (re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"), "GitHub fine-grained token"),
    (re.compile(rb"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"), "OpenAI API key"),
    (re.compile(rb"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b"), "Stripe live API key"),
    (re.compile(rb"\bxox[a-z]-[A-Za-z0-9-]{20,}\b"), "Slack token"),
    (re.compile(rb"\bAIza[0-9A-Za-z_-]{35}\b"), "Google API key"),
    (
        re.compile(rb"(?i)\bAccountKey=[A-Za-z0-9+/]{32,}={0,2}(?:;|\s|$)"),
        "Azure Storage account key",
    ),
    (
        re.compile(
            rb"(?i)(?:\?|&|\b)sv=[0-9-]{8,16}&[^\s#]{0,2048}"
            rb"(?:&|%26)sig=[A-Za-z0-9%+/=_-]{16,}"
        ),
        "Azure shared access signature",
    ),
    (re.compile(rb"\bnpm_[A-Za-z0-9]{20,}\b"), "npm access token"),
    (
        re.compile(
            rb"(?i)//registry\.npmjs\.org/:_authToken=[A-Za-z0-9._-]{16,}"
        ),
        "npm registry authentication token",
    ),
    (re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key"),
    (re.compile(b"REAL_TENANT_" + b"PRIVATE_DATA"), "known private tenant marker"),
    (re.compile(b"TENANT_SECRET_" + b"TEST_VALUE"), "known tenant secret marker"),
)


def classify_risk(changed_paths: list[str]) -> str:
    """Derive risk from an independently obtained, canonical path list."""
    return "high" if any(path.startswith(HIGH_RISK_PREFIXES) for path in changed_paths) else "normal"


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_document(value: object) -> bytes:
    return canonical_bytes(value) + b"\n"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seal_manifest(manifest: dict) -> str:
    field = manifest.setdefault(
        "manifest_digest", {"algorithm": "sha256", "value": SELF_DIGEST_ZERO}
    )
    field["algorithm"] = "sha256"
    field["value"] = SELF_DIGEST_ZERO
    value = hashlib.sha256(canonical_bytes(manifest)).hexdigest()
    field["value"] = value
    return value


def _parse_time(value: object, field: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str):
        errors.append(f"{field} must be an RFC3339 string")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} is not valid RFC3339")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{field} must include a timezone")
        return None
    return parsed.astimezone(timezone.utc)


def _load_json(path: Path, label: str, errors: list[str], canonical: bool = True):
    try:
        raw = path.read_bytes()
    except OSError as exc:
        errors.append(f"missing {label}: {exc}")
        return None, b""
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid {label}: {exc}")
        return None, raw
    if canonical and raw != canonical_document(document):
        errors.append(f"{label} is not canonical JSON")
    return document, raw


_SUPPORTED_SCHEMA_KEYWORDS = {
    "$defs",
    "$id",
    "$ref",
    "$schema",
    "additionalProperties",
    "allOf",
    "const",
    "else",
    "enum",
    "format",
    "if",
    "items",
    "maxLength",
    "minItems",
    "minLength",
    "minimum",
    "oneOf",
    "pattern",
    "properties",
    "required",
    "then",
    "title",
    "type",
    "uniqueItems",
}


def _check_supported_schema(schema: object, path: str = "$") -> list[str]:
    """Reject schema keywords our dependency-free validator cannot enforce."""
    if isinstance(schema, bool):
        return []
    if not isinstance(schema, dict):
        return [f"{path} must be a JSON object or boolean schema"]
    errors = [
        f"{path} uses unsupported keyword {key!r}"
        for key in schema
        if key not in _SUPPORTED_SCHEMA_KEYWORDS
    ]
    for container in ("$defs", "properties"):
        values = schema.get(container, {})
        if isinstance(values, dict):
            for name, child in values.items():
                errors.extend(_check_supported_schema(child, f"{path}/{container}/{name}"))
    for keyword in ("additionalProperties", "items", "if", "then", "else"):
        if keyword in schema:
            errors.extend(_check_supported_schema(schema[keyword], f"{path}/{keyword}"))
    for keyword in ("allOf", "oneOf"):
        values = schema.get(keyword, [])
        if isinstance(values, list):
            for index, child in enumerate(values):
                errors.extend(_check_supported_schema(child, f"{path}/{keyword}/{index}"))
    return errors


def _resolve_local_ref(root_schema: dict, reference: object) -> object:
    if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
        raise ValueError("only local #/$defs JSON Pointer references are allowed")
    current: object = root_schema
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"unresolved schema reference {reference!r}")
        current = current[part]
    return current


def _matches_json_type(instance: object, expected: str) -> bool:
    return {
        "array": isinstance(instance, list),
        "boolean": isinstance(instance, bool),
        "integer": isinstance(instance, int) and not isinstance(instance, bool),
        "null": instance is None,
        "number": isinstance(instance, (int, float)) and not isinstance(instance, bool),
        "object": isinstance(instance, dict),
        "string": isinstance(instance, str),
    }.get(expected, False)


def _json_equal(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return left == right


def _validate_schema_instance(
    instance: object,
    schema: object,
    root_schema: dict,
    path: str = "$",
) -> list[str]:
    """Validate the complete Draft 2020-12 subset used by the pinned schema."""
    if schema is True:
        return []
    if schema is False:
        return [f"{path} is forbidden"]
    if not isinstance(schema, dict):
        return [f"{path} encountered an invalid schema node"]

    errors: list[str] = []
    if "$ref" in schema:
        try:
            target = _resolve_local_ref(root_schema, schema["$ref"])
        except ValueError as exc:
            return [f"{path}: {exc}"]
        errors.extend(_validate_schema_instance(instance, target, root_schema, path))

    expected_type = schema.get("type")
    if expected_type is not None:
        choices = expected_type if isinstance(expected_type, list) else [expected_type]
        if not all(isinstance(choice, str) for choice in choices):
            return errors + [f"{path} schema has an invalid type declaration"]
        if not any(_matches_json_type(instance, choice) for choice in choices):
            return errors + [f"{path} has the wrong JSON type"]

    if "const" in schema and not _json_equal(instance, schema["const"]):
        errors.append(f"{path} does not match const")
    if "enum" in schema:
        enum = schema["enum"]
        if not isinstance(enum, list) or not any(_json_equal(instance, item) for item in enum):
            errors.append(f"{path} is not in enum")

    for child in schema.get("allOf", []):
        errors.extend(_validate_schema_instance(instance, child, root_schema, path))
    if "oneOf" in schema:
        candidates = schema["oneOf"]
        matches = sum(
            not _validate_schema_instance(instance, child, root_schema, path)
            for child in candidates
        )
        if matches != 1:
            errors.append(f"{path} must match exactly one oneOf branch")
    if "if" in schema:
        condition_matches = not _validate_schema_instance(
            instance, schema["if"], root_schema, path
        )
        branch = "then" if condition_matches else "else"
        if branch in schema:
            errors.extend(
                _validate_schema_instance(instance, schema[branch], root_schema, path)
            )

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{path} is missing required property {key!r}")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, child in properties.items():
                if key in instance:
                    errors.extend(
                        _validate_schema_instance(
                            instance[key], child, root_schema, f"{path}/{key}"
                        )
                    )
            extras = set(instance) - set(properties)
            additional = schema.get("additionalProperties", True)
            if additional is False:
                for key in sorted(extras):
                    errors.append(f"{path} has forbidden additional property {key!r}")
            elif isinstance(additional, dict):
                for key in sorted(extras):
                    errors.extend(
                        _validate_schema_instance(
                            instance[key], additional, root_schema, f"{path}/{key}"
                        )
                    )

    if isinstance(instance, list):
        minimum_items = schema.get("minItems")
        if isinstance(minimum_items, int) and len(instance) < minimum_items:
            errors.append(f"{path} has fewer than minItems")
        if schema.get("uniqueItems") is True:
            encoded = [canonical_bytes(item) for item in instance]
            if len(set(encoded)) != len(encoded):
                errors.append(f"{path} does not contain unique items")
        if "items" in schema:
            for index, item in enumerate(instance):
                errors.extend(
                    _validate_schema_instance(
                        item, schema["items"], root_schema, f"{path}/{index}"
                    )
                )

    if isinstance(instance, str):
        if isinstance(schema.get("minLength"), int) and len(instance) < schema["minLength"]:
            errors.append(f"{path} is shorter than minLength")
        if isinstance(schema.get("maxLength"), int) and len(instance) > schema["maxLength"]:
            errors.append(f"{path} is longer than maxLength")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, instance) is None:
            errors.append(f"{path} does not match pattern")
        if schema.get("format") == "date-time":
            rfc3339 = re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
                instance,
            )
            try:
                if not rfc3339:
                    raise ValueError
                datetime.fromisoformat(instance.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"{path} is not an RFC3339 date-time")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and instance < minimum:
            errors.append(f"{path} is below minimum")
    return errors


def _validate_manifest_schema(
    manifest: dict, schema_path: Path, errors: list[str]
) -> None:
    schema, _raw = _load_json(
        schema_path, "night-shift manifest JSON Schema", errors, canonical=False
    )
    if not isinstance(schema, dict):
        errors.append("night-shift manifest JSON Schema must be an object")
        return
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("night-shift manifest JSON Schema draft mismatch")
        return
    unsupported = _check_supported_schema(schema)
    if unsupported:
        errors.extend(f"manifest JSON Schema cannot be enforced: {item}" for item in unsupported)
        return
    violations = _validate_schema_instance(manifest, schema, schema)
    errors.extend(f"manifest JSON Schema violation: {item}" for item in violations)


def _catalog_profiles(catalog_path: Path, errors: list[str]) -> dict[str, str]:
    catalog, _raw = _load_json(catalog_path, "agency catalog", errors)
    if not isinstance(catalog, dict) or catalog.get("schema") != CATALOG_SCHEMA:
        errors.append("agency catalog schema mismatch")
        return {}
    lock = catalog.get("lock")
    if not isinstance(lock, dict) or catalog.get("profiles") != lock.get("profiles"):
        errors.append("agency catalog embedded lock/profile inventory mismatch")
        return {}
    if set(catalog) != {"lock", "profiles", "schema"}:
        errors.append("agency catalog fields do not match the closed schema")
    if lock.get("schema") != CATALOG_LOCK_SCHEMA:
        errors.append("agency catalog lock schema mismatch")
    if lock.get("catalog_schema") != CATALOG_SCHEMA:
        errors.append("agency catalog schema binding mismatch")
    if lock.get("source") != {
        "commit": CATALOG_COMMIT,
        "license": "MIT",
        "license_sha256": CATALOG_LICENSE_SHA256,
        "repository": CATALOG_REPOSITORY,
    }:
        errors.append("agency catalog source pin or MIT license mismatch")
    if lock.get("divisions") != list(CATALOG_DIVISIONS):
        errors.append("agency catalog division inventory mismatch")
    if lock.get("division_count") != len(CATALOG_DIVISIONS):
        errors.append("agency catalog division count must be exactly 17")
    raw_profiles = catalog.get("profiles")
    if not isinstance(raw_profiles, list):
        errors.append("agency catalog profiles must be a list")
        return {}
    if (
        lock.get("profile_count") != CATALOG_PROFILE_COUNT
        or len(raw_profiles) != CATALOG_PROFILE_COUNT
    ):
        errors.append("agency catalog profile count must be exactly 270")
    inventory_digest = hashlib.sha256(canonical_bytes(raw_profiles)).hexdigest()
    if lock.get("inventory_sha256") != inventory_digest:
        errors.append("agency catalog profile inventory digest mismatch")
    if lock.get("inventory_sha256") != CATALOG_INVENTORY_SHA256:
        errors.append("agency catalog differs from the fixed profile inventory")
    profiles: dict[str, str] = {}
    ordered_paths: list[str] = []
    for profile in raw_profiles:
        if not isinstance(profile, dict):
            errors.append("agency catalog profile entry is not an object")
            continue
        if set(profile) != {"bytes", "division", "path", "sha256"}:
            errors.append("agency catalog profile fields do not match the closed schema")
        path = profile.get("path")
        digest = profile.get("sha256")
        division = profile.get("division")
        size = profile.get("bytes")
        if (
            not isinstance(path, str)
            or not path.endswith(".md")
            or division not in CATALOG_DIVISIONS
            or not path.startswith(f"{division}/")
            or not isinstance(digest, str)
            or SHA64.fullmatch(digest) is None
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 1
        ):
            errors.append("agency catalog contains an invalid canonical profile")
            continue
        ordered_paths.append(path)
        profiles[path] = digest
    if ordered_paths != sorted(ordered_paths) or len(set(ordered_paths)) != len(ordered_paths):
        errors.append("agency catalog profile paths are unsorted or duplicated")
    return profiles


def _canonical_profile(
    value: object, profiles: dict[str, str], label: str, errors: list[str]
) -> tuple[str, str] | None:
    if not isinstance(value, dict):
        errors.append(f"{label} is not a canonical producer object")
        return None
    path, digest = value.get("path"), value.get("sha256")
    if not isinstance(path, str) or profiles.get(path) != digest:
        errors.append(f"{label} is not a canonical producer from the pinned catalog")
        return None
    if set(value) != {"path", "sha256"}:
        errors.append(f"{label} must contain only canonical path and SHA-256")
    return path, digest


def _scan_sensitive(raw: bytes, label: str, errors: list[str]) -> None:
    for pattern, description in SENSITIVE_PATTERNS:
        if pattern.search(raw):
            errors.append(f"{label} contains sensitive data: {description}")


def _verify_official_attestation_offline(
    manifest_path: str | Path,
    bundle_path: str | Path,
    trusted_root_path: str | Path,
    *,
    repository: str,
    source_digest: str,
    source_ref: str,
    workflow_ref: str,
    signer_digest: str,
) -> tuple[object, bytes]:
    """Cryptographically verify the official bundle without network access.

    GitHub CLI performs Sigstore verification against an explicitly captured
    trusted root.  Only its freshly generated stdout enters the policy layer;
    callers cannot provide a pre-asserted ``verificationResult`` JSON file.
    """
    manifest_path = Path(manifest_path)
    bundle_path = Path(bundle_path)
    trusted_root_path = Path(trusted_root_path)
    for path, label, limit in (
        (manifest_path, "manifest", 10 * 1024 * 1024),
        (bundle_path, "official attestation bundle", 10 * 1024 * 1024),
        (trusted_root_path, "trusted root", 20 * 1024 * 1024),
    ):
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"{label} is missing or is not a regular file")
        if path.stat().st_size < 1 or path.stat().st_size > limit:
            raise RuntimeError(f"{label} size is outside the fail-closed bound")
    if repository != "adrimg3196/lucidfence":
        raise RuntimeError("attestation repository identity is invalid")
    if not SHA40.fullmatch(source_digest) or not SHA40.fullmatch(signer_digest):
        raise RuntimeError("attestation source or signer digest is invalid")
    expected_workflow_ref = (
        f"{repository}/.github/workflows/autonomy-attest.yml@refs/heads/main"
    )
    if workflow_ref != expected_workflow_ref or source_ref != "refs/heads/main":
        raise RuntimeError("attestation trusted workflow identity is invalid")
    signer_workflow = workflow_ref.rsplit("@", 1)[0]
    command = [
        "gh",
        "attestation",
        "verify",
        str(manifest_path),
        "--repo",
        repository,
        "--bundle",
        str(bundle_path),
        "--custom-trusted-root",
        str(trusted_root_path),
        "--cert-identity",
        f"https://github.com/{workflow_ref}",
        "--signer-workflow",
        signer_workflow,
        "--signer-digest",
        signer_digest,
        "--source-ref",
        source_ref,
        "--source-digest",
        source_digest,
        "--predicate-type",
        "https://slsa.dev/provenance/v1",
        "--deny-self-hosted-runners",
        "--format",
        "json",
    ]
    environment = {
        "GH_NO_UPDATE_NOTIFIER": "1",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "NO_COLOR": "1",
        "PATH": os.environ.get("PATH", ""),
    }
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            env=environment,
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            f"offline cryptographic attestation verifier unavailable: {type(exc).__name__}"
        ) from exc
    if completed.returncode != 0:
        raise RuntimeError(
            f"offline cryptographic attestation verification failed (exit {completed.returncode})"
        )
    raw = completed.stdout
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("offline cryptographic verifier returned invalid JSON") from exc
    if not isinstance(document, list) or not document:
        raise RuntimeError("offline cryptographic verifier returned no verified attestation")
    return document, raw


def verify_manifest(
    manifest_path: str | Path,
    evidence_dir: str | Path,
    *,
    repository: str,
    base_sha: str,
    head_sha: str,
    run_id: str,
    run_attempt: int,
    workflow: str,
    workflow_ref: str,
    ref: str,
    changed_paths: list[str],
    now: datetime,
    catalog_path: str | Path,
    attestation_receipt_path: str | Path | None,
    attestation_source_digest: str | None = None,
    attestation_source_ref: str | None = None,
    attestation_run_id: str | None = None,
    attestation_run_attempt: int | None = None,
    attestation_workflow_ref: str | None = None,
    attestation_signer_digest: str | None = None,
    schema_path: str | Path | None = None,
) -> list[str]:
    errors: list[str] = []
    manifest_path = Path(manifest_path)
    evidence_dir = Path(evidence_dir)
    manifest, raw_manifest = _load_json(manifest_path, "manifest", errors)
    profiles = _catalog_profiles(Path(catalog_path), errors)
    if not isinstance(manifest, dict):
        return errors
    resolved_schema_path = (
        Path(schema_path)
        if schema_path is not None
        else Path(__file__).resolve().parents[1]
        / "config"
        / "night-shift-manifest.schema.json"
    )
    _validate_manifest_schema(manifest, resolved_schema_path, errors)

    expected_manifest_keys = {
        "artifacts",
        "attestation",
        "base_sha",
        "generated_at",
        "head_sha",
        "manifest_digest",
        "objective",
        "participants",
        "ref",
        "repository",
        "run_attempt",
        "run_id",
        "schema",
        "validity",
        "workflow",
        "workflow_ref",
    }
    if set(manifest) != expected_manifest_keys:
        errors.append("manifest fields do not match the closed schema")

    expected_context = {
        "repository": repository,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "run_id": str(run_id),
        "run_attempt": run_attempt,
        "workflow": workflow,
        "workflow_ref": workflow_ref,
        "ref": ref,
    }
    if manifest.get("schema") != MANIFEST_SCHEMA:
        errors.append("manifest schema mismatch")
    if not SHA40.fullmatch(base_sha) or not SHA40.fullmatch(head_sha):
        errors.append("expected base/head SHA must be lowercase 40-hex commits")
    for field, expected in expected_context.items():
        actual = manifest.get(field)
        if field == "run_id":
            actual = str(actual)
        if actual != expected:
            errors.append(f"manifest {field} mismatch: expected {expected!r}, got {actual!r}")

    digest_field = manifest.get("manifest_digest")
    if not isinstance(digest_field, dict) or digest_field.get("algorithm") != "sha256":
        errors.append("manifest_digest must use SHA-256")
    else:
        if set(digest_field) != {"algorithm", "value"}:
            errors.append("manifest_digest fields do not match the closed schema")
        claimed = digest_field.get("value")
        candidate = copy.deepcopy(manifest)
        candidate["manifest_digest"]["value"] = SELF_DIGEST_ZERO
        actual = hashlib.sha256(canonical_bytes(candidate)).hexdigest()
        if claimed != actual:
            errors.append("manifest self digest mismatch")

    _scan_sensitive(raw_manifest, "manifest", errors)
    generated = _parse_time(manifest.get("generated_at"), "generated_at", errors)
    validity = manifest.get("validity")
    if not isinstance(validity, dict):
        errors.append("validity policy is missing")
        not_before = expires = None
    else:
        if set(validity) != {"expires_at", "not_before", "policy"}:
            errors.append("validity fields do not match the closed schema")
        if validity.get("policy") != "P7D":
            errors.append("validity policy must be P7D")
        not_before = _parse_time(validity.get("not_before"), "validity.not_before", errors)
        expires = _parse_time(validity.get("expires_at"), "validity.expires_at", errors)
    check_now = now.astimezone(timezone.utc)
    if not_before and check_now < not_before:
        errors.append("evidence is not yet valid")
    if expires and check_now >= expires:
        errors.append("evidence is expired")
    if generated and not_before and generated != not_before:
        errors.append("generated_at must equal validity.not_before")
    if not_before and expires and expires - not_before != timedelta(days=7):
        errors.append("evidence validity must be exactly seven days")

    canonical_changed_paths = sorted(set(changed_paths))
    if canonical_changed_paths != changed_paths:
        errors.append("expected changed paths must be unique and sorted")

    participants = manifest.get("participants")
    participant_values: dict[str, tuple[str, str] | None] = {}
    if not isinstance(participants, dict):
        errors.append("participants are missing")
        participants = {}
    expected_participant_keys = set(EXPECTED_PROFILES)
    if set(participants) != expected_participant_keys:
        errors.append("participants must contain exactly the canonical autonomy-B seats")
    for role in EXPECTED_PROFILES:
        participant_values[role] = _canonical_profile(
            participants.get(role), profiles, f"participant {role}", errors
        )
        if participant_values[role] != EXPECTED_PROFILES[role]:
            errors.append(f"participant {role} does not match the pinned canonical seat")
    maker = participant_values.get("maker")
    final_reviewer = participant_values.get("final_reviewer")
    if maker and final_reviewer and maker[0] == final_reviewer[0]:
        errors.append("maker and final reviewer must be different canonical profiles")
    reality = participant_values.get("reality_checker")
    if reality and reality[0] != "testing/testing-reality-checker.md":
        errors.append("Reality Checker must always be the canonical testing profile")

    objective = manifest.get("objective")
    risk = objective.get("risk") if isinstance(objective, dict) else None
    derived_risk = classify_risk(canonical_changed_paths)
    if not isinstance(objective, dict):
        errors.append("objective is missing")
    else:
        if set(objective) != {"changed_paths", "id", "risk"}:
            errors.append("objective fields do not match the closed schema")
        if objective.get("changed_paths") != canonical_changed_paths:
            errors.append("objective changed_paths differ from independently derived paths")
        if risk != derived_risk:
            errors.append(f"objective risk mismatch: expected {derived_risk}, got {risk}")
    required = list(REQUIRED_ARTIFACTS)
    if derived_risk == "high":
        required.extend(HIGH_RISK_ARTIFACTS)
        primary, secondary = participant_values.get("appsec_primary"), participant_values.get("appsec_secondary")
        if (
            not primary
            or not secondary
            or primary[0] == secondary[0]
            or (maker and primary[0] == maker[0])
            or (maker and secondary[0] == maker[0])
        ):
            errors.append("high-risk AppSec reviewers must be canonical, independent, and distinct from maker")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("artifact inventory is missing")
        artifacts = {}
    if set(artifacts) != set(required):
        errors.append("artifact inventory must contain exactly the artifacts required for derived risk")
    for kind in required:
        if kind not in artifacts:
            errors.append(f"missing required artifact: {kind}")
    paths_seen: set[str] = set()
    for kind, descriptor in artifacts.items():
        if kind not in set(REQUIRED_ARTIFACTS + HIGH_RISK_ARTIFACTS):
            errors.append(f"unknown artifact kind: {kind}")
            continue
        if not isinstance(descriptor, dict):
            errors.append(f"artifact descriptor is invalid: {kind}")
            continue
        if set(descriptor) != {"path", "producer", "sha256"}:
            errors.append(f"artifact descriptor fields are not exact: {kind}")
        relative = descriptor.get("path")
        if not isinstance(relative, str) or Path(relative).name != relative or relative != f"{kind}.json":
            errors.append(f"artifact path must be a basename: {kind}")
            continue
        if relative in paths_seen:
            errors.append(f"artifacts must use independent files: {relative}")
        paths_seen.add(relative)
        artifact_path = evidence_dir / relative
        artifact, raw = _load_json(artifact_path, f"artifact {kind}", errors)
        if not raw:
            continue
        digest = sha256_file(artifact_path)
        if descriptor.get("sha256") != digest or not SHA64.fullmatch(str(descriptor.get("sha256", ""))):
            errors.append(f"artifact digest mismatch: {kind}")
        _scan_sensitive(raw, f"artifact {kind}", errors)
        descriptor_producer = _canonical_profile(
            descriptor.get("producer"), profiles, f"artifact {kind} descriptor producer", errors
        )
        if not isinstance(artifact, dict):
            continue
        expected_artifact_keys = {
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
        if set(artifact) != expected_artifact_keys:
            errors.append(f"artifact fields do not match the closed schema: {kind}")
        if artifact.get("schema") != EVIDENCE_SCHEMA:
            errors.append(f"artifact schema mismatch: {kind}")
        if artifact.get("kind") != kind:
            errors.append(f"artifact kind mismatch: {kind}")
        result = artifact.get("result")
        if not isinstance(result, dict) or result.get("status") != "pass":
            errors.append(f"artifact does not pass: {kind}")
            result = {}
        if result.get("check") != kind:
            errors.append(f"artifact exact check name mismatch: {kind}")
        if result.get("command_id") != EXPECTED_COMMAND_IDS[kind]:
            errors.append(f"artifact command identity mismatch: {kind}")
        if result.get("exit_code") != 0:
            errors.append(f"artifact command did not exit cleanly: {kind}")
        output_bytes = result.get("output_bytes")
        if not isinstance(output_bytes, int) or isinstance(output_bytes, bool) or output_bytes < 1:
            errors.append(f"artifact output byte count is invalid: {kind}")
        if not SHA64.fullmatch(str(result.get("output_sha256", ""))):
            errors.append(f"artifact output digest is invalid: {kind}")
        expected_result_keys = {
            "check", "command_id", "exit_code", "output_bytes", "output_sha256", "status"
        }
        if kind == "overlap":
            expected_result_keys.update({"conflicts", "overlaps", "snapshot_sha256"})
        if set(result) != expected_result_keys:
            errors.append(f"artifact result fields are not exact: {kind}")
        artifact_generated = _parse_time(
            artifact.get("generated_at"), f"artifact {kind} generated_at", errors
        )
        if artifact_generated and generated and artifact_generated > generated:
            errors.append(f"artifact generated after manifest assembly: {kind}")
        if artifact_generated and generated and generated - artifact_generated > timedelta(days=1):
            errors.append(f"artifact is stale relative to manifest assembly: {kind}")
        for field, expected in expected_context.items():
            actual = artifact.get(field)
            if field == "run_id":
                actual = str(actual)
            if actual != expected:
                errors.append(f"artifact {kind} {field} mismatch")
        if isinstance(objective, dict) and artifact.get("objective") != objective.get("id"):
            errors.append(f"artifact {kind} objective mismatch")
        artifact_producer = _canonical_profile(
            artifact.get("producer"), profiles, f"artifact {kind} canonical producer", errors
        )
        if artifact.get("producer") != descriptor.get("producer"):
            errors.append(f"artifact producer differs from manifest descriptor: {kind}")
        if descriptor_producer and artifact_producer and descriptor_producer != artifact_producer:
            errors.append(f"artifact producer identity mismatch: {kind}")
        expected_role = {
            "ci": "maker",
            "runtime": "maker",
            "secrets": "maker",
            "dependencies": "maker",
            "license": "maker",
            "overlap": "maker",
            "appsec": "appsec_primary",
            "final-review": "final_reviewer",
            "reality": "reality_checker",
            "appsec-primary": "appsec_primary",
            "appsec-secondary": "appsec_secondary",
        }.get(kind)
        if expected_role and participant_values.get(expected_role) and artifact_producer != participant_values[expected_role]:
            errors.append(f"artifact {kind} is not produced by participant {expected_role}")
        if kind == "overlap" and isinstance(result, dict):
            overlaps, conflicts = result.get("overlaps"), result.get("conflicts")
            if overlaps != [] or conflicts != []:
                errors.append("overlap evidence reports an overlapping or conflicting objective")
            if not SHA64.fullmatch(str(result.get("snapshot_sha256", ""))):
                errors.append("overlap evidence live snapshot digest is invalid")

    expected_attestation = manifest.get("attestation")
    signer_context = {
        "source_digest": attestation_source_digest,
        "source_ref": attestation_source_ref,
        "run_id": str(attestation_run_id) if attestation_run_id is not None else None,
        "run_attempt": attestation_run_attempt,
        "workflow_ref": attestation_workflow_ref,
        "workflow_digest": attestation_signer_digest,
    }
    if not isinstance(expected_attestation, dict):
        errors.append("attestation binding is missing from manifest")
    else:
        expected_attestation_keys = {
            "base_sha", "evidence_run", "head_sha", "predicate_type", "repository", "signer"
        }
        if set(expected_attestation) != expected_attestation_keys:
            errors.append("attestation fields do not match the closed schema")
        if expected_attestation.get("repository") != repository:
            errors.append("manifest attestation repository mismatch")
        if expected_attestation.get("base_sha") != base_sha:
            errors.append("manifest attestation base_sha mismatch")
        if expected_attestation.get("head_sha") != head_sha:
            errors.append("manifest attestation head_sha mismatch")
        evidence_run = expected_attestation.get("evidence_run")
        expected_evidence_run = {
            "id": str(run_id),
            "attempt": run_attempt,
            "workflow": workflow,
            "workflow_ref": workflow_ref,
            "ref": ref,
        }
        if evidence_run != expected_evidence_run:
            errors.append("manifest attestation evidence-run binding mismatch")
        if isinstance(evidence_run, dict) and set(evidence_run) != set(expected_evidence_run):
            errors.append("evidence-run fields do not match the closed schema")
        signer = expected_attestation.get("signer")
        expected_signer = {
            "run_id": signer_context["run_id"],
            "run_attempt": signer_context["run_attempt"],
            "workflow_ref": signer_context["workflow_ref"],
            "workflow_digest": signer_context["workflow_digest"],
            "ref": signer_context["source_ref"],
            "source_digest": signer_context["source_digest"],
        }
        if signer != expected_signer:
            errors.append("manifest attestation trusted-signer binding mismatch")
        if isinstance(signer, dict) and set(signer) != set(expected_signer):
            errors.append("trusted-signer fields do not match the closed schema")
        if expected_attestation.get("predicate_type") != "https://slsa.dev/provenance/v1":
            errors.append("attestation predicate type mismatch")

    if attestation_receipt_path is not None:
        receipt_path = Path(attestation_receipt_path)
        receipt, raw_receipt = _load_json(
            receipt_path, "attestation verification receipt", errors, canonical=False
        )
        _scan_sensitive(raw_receipt, "attestation verification receipt", errors)
        if not isinstance(receipt, list) or not receipt:
            errors.append("official attestation verification output must be a non-empty JSON array")
        else:
            manifest_sha256 = hashlib.sha256(raw_manifest).hexdigest()
            expected_repository_uri = f"https://github.com/{repository}"
            expected_signer_uri = (
                f"https://github.com/{attestation_workflow_ref}"
                if attestation_workflow_ref
                else None
            )
            expected_run_uri = (
                f"https://github.com/{repository}/actions/runs/{attestation_run_id}"
                f"/attempts/{attestation_run_attempt}"
            )
            verified = False
            for entry in receipt:
                if not isinstance(entry, dict):
                    continue
                result = entry.get("verificationResult")
                if not isinstance(result, dict):
                    continue
                statement = result.get("statement")
                signature = result.get("signature")
                certificate = signature.get("certificate") if isinstance(signature, dict) else None
                if not isinstance(statement, dict) or not isinstance(certificate, dict):
                    continue
                subjects = statement.get("subject")
                subject_matches = isinstance(subjects, list) and any(
                    isinstance(subject, dict)
                    and isinstance(subject.get("digest"), dict)
                    and subject["digest"].get("sha256") == manifest_sha256
                    for subject in subjects
                )
                certificate_matches = (
                    certificate.get("issuer") == "https://token.actions.githubusercontent.com"
                    and certificate.get("runnerEnvironment") == "github-hosted"
                    and certificate.get("sourceRepositoryURI") == expected_repository_uri
                    and certificate.get("sourceRepositoryDigest") == attestation_source_digest
                    and certificate.get("sourceRepositoryRef") == attestation_source_ref
                    and certificate.get("buildConfigURI") == expected_signer_uri
                    and certificate.get("buildSignerDigest") == attestation_signer_digest
                    and certificate.get("subjectAlternativeName") == expected_signer_uri
                    and certificate.get("runInvocationURI") == expected_run_uri
                )
                timestamps = result.get("verifiedTimestamps")
                if (
                    subject_matches
                    and certificate_matches
                    and isinstance(timestamps, list)
                    and timestamps
                    and statement.get("predicateType") == "https://slsa.dev/provenance/v1"
                ):
                    verified = True
                    break
            if not verified:
                errors.append(
                    "official attestation output does not bind manifest, repository, trusted signer, source, and run"
                )
    return errors


def _durable_manifest_inputs(
    manifest: dict,
    bundle_name: str,
    *,
    current_time: datetime,
) -> tuple[dict[str, object] | None, list[str]]:
    """Extract closed verification inputs from one self-describing archive manifest."""
    errors: list[str] = []
    match = DURABLE_BUNDLE_NAME.fullmatch(bundle_name)
    if match is None:
        return None, ["durable v1 bundle name is invalid"]
    objective = manifest.get("objective")
    attestation = manifest.get("attestation")
    signer = attestation.get("signer") if isinstance(attestation, dict) else None
    changed_paths = objective.get("changed_paths") if isinstance(objective, dict) else None
    generated_errors: list[str] = []
    generated_at = _parse_time(
        manifest.get("generated_at"), "durable manifest generated_at", generated_errors
    )
    if generated_errors:
        errors.extend(generated_errors)
    elif generated_at and generated_at > current_time.astimezone(timezone.utc) + timedelta(minutes=5):
        errors.append("durable manifest generated_at is in the future")

    required_strings = {
        "base_sha": manifest.get("base_sha"),
        "head_sha": manifest.get("head_sha"),
        "ref": manifest.get("ref"),
        "repository": manifest.get("repository"),
        "run_id": manifest.get("run_id"),
        "workflow": manifest.get("workflow"),
        "workflow_ref": manifest.get("workflow_ref"),
    }
    run_attempt = manifest.get("run_attempt")
    if (
        required_strings["repository"] != "adrimg3196/lucidfence"
        or required_strings["workflow"] != "autonomy-evidence"
        or not SHA40.fullmatch(str(required_strings["base_sha"] or ""))
        or not SHA40.fullmatch(str(required_strings["head_sha"] or ""))
        or not isinstance(required_strings["run_id"], str)
        or not str(required_strings["run_id"]).isdigit()
        or not isinstance(run_attempt, int)
        or isinstance(run_attempt, bool)
        or run_attempt < 1
        or not isinstance(required_strings["ref"], str)
        or not isinstance(required_strings["workflow_ref"], str)
        or not isinstance(changed_paths, list)
        or not all(isinstance(path, str) for path in changed_paths)
        or not isinstance(signer, dict)
        or generated_at is None
    ):
        errors.append("durable manifest cannot derive a closed verification context")
        return None, errors
    if (
        match.group("run_id") != required_strings["run_id"]
        or int(match.group("attempt")) != run_attempt
        or match.group("head") != required_strings["head_sha"]
    ):
        errors.append("durable bundle name does not bind manifest run identity")

    signer_values = {
        "run_attempt": signer.get("run_attempt"),
        "run_id": signer.get("run_id"),
        "source_digest": signer.get("source_digest"),
        "source_ref": signer.get("ref"),
        "workflow_digest": signer.get("workflow_digest"),
        "workflow_ref": signer.get("workflow_ref"),
    }
    if (
        not isinstance(signer_values["run_id"], str)
        or not str(signer_values["run_id"]).isdigit()
        or not isinstance(signer_values["run_attempt"], int)
        or isinstance(signer_values["run_attempt"], bool)
        or int(signer_values["run_attempt"]) < 1
        or not SHA40.fullmatch(str(signer_values["source_digest"] or ""))
        or not SHA40.fullmatch(str(signer_values["workflow_digest"] or ""))
        or not isinstance(signer_values["source_ref"], str)
        or not isinstance(signer_values["workflow_ref"], str)
    ):
        errors.append("durable manifest signer identity is malformed")
        return None, errors
    return {
        **required_strings,
        "archive_time": generated_at,
        "changed_paths": changed_paths,
        "run_attempt": run_attempt,
        "signer": signer_values,
    }, errors


def _verify_durable_bundle(
    bundle: Path,
    *,
    now: datetime,
    catalog_path: Path,
    schema_path: Path,
    trusted_root_path: Path,
) -> list[str]:
    """Verify one exact v1 archive bundle, including its official attestation."""
    errors: list[str] = []
    if bundle.is_symlink() or not bundle.is_dir():
        return ["durable v1 entry is not one regular bundle directory"]
    try:
        entries = list(bundle.iterdir())
    except OSError:
        return ["durable bundle inventory is unreadable"]
    if {entry.name for entry in entries} != DURABLE_BUNDLE_FILES:
        errors.append("durable bundle inventory is not exact")
    for entry in entries:
        if entry.name == "evidence":
            if entry.is_symlink() or not entry.is_dir():
                errors.append("durable bundle evidence entry is invalid")
        elif entry.name in DURABLE_BUNDLE_FILES and (entry.is_symlink() or not entry.is_file()):
            errors.append("durable bundle file entry is invalid")
    manifest_path = bundle / "manifest.json"
    evidence_dir = bundle / "evidence"
    attestation_bundle = bundle / "attestation.bundle.jsonl"
    recorded_trusted_root = bundle / "trusted-root.jsonl"
    if errors or not manifest_path.is_file() or not evidence_dir.is_dir():
        return errors or ["durable bundle inventory is incomplete"]
    if manifest_path.stat().st_size < 1 or manifest_path.stat().st_size > 10 * 1024 * 1024:
        return ["durable manifest size is outside the fail-closed bound"]
    manifest_errors: list[str] = []
    manifest, _raw = _load_json(manifest_path, "durable manifest", manifest_errors)
    errors.extend(manifest_errors)
    if not isinstance(manifest, dict):
        return errors

    artifacts = manifest.get("artifacts")
    expected_evidence: set[str] = set()
    if isinstance(artifacts, dict):
        for kind, descriptor in artifacts.items():
            if (
                isinstance(kind, str)
                and isinstance(descriptor, dict)
                and descriptor.get("path") == f"{kind}.json"
            ):
                expected_evidence.add(f"{kind}.json")
    else:
        errors.append("durable manifest artifact inventory is malformed")
    try:
        evidence_entries = list(evidence_dir.iterdir())
    except OSError:
        errors.append("durable evidence inventory is unreadable")
        return errors
    if {entry.name for entry in evidence_entries} != expected_evidence:
        errors.append("durable evidence inventory is not exact")
    if any(entry.is_symlink() or not entry.is_file() for entry in evidence_entries):
        errors.append("durable evidence contains a non-regular entry")

    inputs, input_errors = _durable_manifest_inputs(
        manifest,
        bundle.name,
        current_time=now,
    )
    errors.extend(input_errors)
    for path, label, maximum in (
        (attestation_bundle, "durable attestation bundle", 10 * 1024 * 1024),
        (recorded_trusted_root, "durable recorded trusted root", 20 * 1024 * 1024),
    ):
        if path.is_symlink() or not path.is_file():
            errors.append(f"{label} is missing or invalid")
            continue
        size = path.stat().st_size
        if not 1 <= size <= maximum:
            errors.append(f"{label} size is outside the fail-closed bound")
            continue
        _scan_sensitive(path.read_bytes(), label, errors)
    if inputs is None or errors:
        return errors
    signer = inputs["signer"]
    assert isinstance(signer, dict)
    archive_time = inputs["archive_time"]
    assert isinstance(archive_time, datetime)
    verification_args = {
        "repository": str(inputs["repository"]),
        "base_sha": str(inputs["base_sha"]),
        "head_sha": str(inputs["head_sha"]),
        "run_id": str(inputs["run_id"]),
        "run_attempt": int(inputs["run_attempt"]),
        "workflow": str(inputs["workflow"]),
        "workflow_ref": str(inputs["workflow_ref"]),
        "ref": str(inputs["ref"]),
        "changed_paths": list(inputs["changed_paths"]),
        "now": archive_time,
        "catalog_path": catalog_path,
        "attestation_source_digest": str(signer["source_digest"]),
        "attestation_source_ref": str(signer["source_ref"]),
        "attestation_run_id": str(signer["run_id"]),
        "attestation_run_attempt": int(signer["run_attempt"]),
        "attestation_workflow_ref": str(signer["workflow_ref"]),
        "attestation_signer_digest": str(signer["workflow_digest"]),
        "schema_path": schema_path,
    }
    pre_errors = verify_manifest(
        manifest_path,
        evidence_dir,
        attestation_receipt_path=None,
        **verification_args,
    )
    if pre_errors:
        return pre_errors
    try:
        _document, raw_receipt = _verify_official_attestation_offline(
            manifest_path,
            attestation_bundle,
            trusted_root_path,
            repository=str(inputs["repository"]),
            source_digest=str(signer["source_digest"]),
            source_ref=str(signer["source_ref"]),
            workflow_ref=str(signer["workflow_ref"]),
            signer_digest=str(signer["workflow_digest"]),
        )
    except RuntimeError as exc:
        return [str(exc)]
    with tempfile.TemporaryDirectory(prefix="lucidfence-durable-verify-") as temp:
        receipt_path = Path(temp) / "verification.json"
        receipt_path.write_bytes(raw_receipt)
        return verify_manifest(
            manifest_path,
            evidence_dir,
            attestation_receipt_path=receipt_path,
            **verification_args,
        )


def verify_durable_store(
    runs_path: str | Path,
    *,
    now: datetime,
    catalog_path: str | Path,
    schema_path: str | Path,
    trusted_root_path: str | Path | None = None,
) -> list[str]:
    """Verify every committed durable v1 bundle; an empty history is valid."""
    root = Path(runs_path)
    if root.is_symlink() or not root.is_dir():
        return ["durable runs directory is missing or invalid"]
    try:
        entries = list(root.iterdir())
    except OSError:
        return ["durable runs inventory is unreadable"]
    names = {entry.name for entry in entries}
    if names not in ({"README.md"}, {"README.md", "v1"}):
        root_errors = ["durable runs inventory is not exact"]
    else:
        root_errors = []
    readme = root / "README.md"
    if readme.is_symlink() or not readme.is_file():
        root_errors.append("durable runs README is missing or invalid")
    version = root / "v1"
    if not version.exists():
        return root_errors
    if version.is_symlink() or not version.is_dir():
        return root_errors + ["durable v1 store is not one real directory"]
    try:
        bundles = sorted(version.iterdir(), key=lambda item: item.name)
    except OSError:
        return root_errors + ["durable v1 inventory is unreadable"]
    if not bundles:
        return root_errors + ["durable v1 inventory is empty"]
    if trusted_root_path is None:
        return root_errors + ["external attestation trusted root is required"]
    external_root = Path(trusted_root_path)
    if external_root.is_symlink() or not external_root.is_file():
        return root_errors + ["external attestation trusted root is missing or invalid"]
    try:
        resolved_runs = root.resolve(strict=True)
        resolved_external_root = external_root.resolve(strict=True)
    except (OSError, RuntimeError):
        return root_errors + ["external attestation trusted root cannot be resolved"]
    if resolved_external_root == resolved_runs or resolved_runs in resolved_external_root.parents:
        return root_errors + ["attestation trusted root must be external to durable runs"]
    external_root_size = resolved_external_root.stat().st_size
    if not 1 <= external_root_size <= 20 * 1024 * 1024:
        return root_errors + [
            "external attestation trusted root size is outside the fail-closed bound"
        ]
    external_root_errors: list[str] = []
    _scan_sensitive(
        resolved_external_root.read_bytes(),
        "external attestation trusted root",
        external_root_errors,
    )
    if external_root_errors:
        return root_errors + external_root_errors
    errors = list(root_errors)
    for bundle in bundles:
        bundle_errors = _verify_durable_bundle(
            bundle,
            now=now,
            catalog_path=Path(catalog_path),
            schema_path=Path(schema_path),
            trusted_root_path=resolved_external_root,
        )
        errors.extend(f"{bundle.name}: {error}" for error in bundle_errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "config"
        / "night-shift-manifest.schema.json",
    )
    parser.add_argument("--attestation-bundle", type=Path)
    parser.add_argument("--trusted-root", type=Path)
    parser.add_argument("--write-attestation-receipt", type=Path)
    parser.add_argument("--pre-attestation", action="store_true")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", type=int, required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--workflow-ref", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--changed-paths-file", type=Path, required=True)
    parser.add_argument("--attestation-source-digest", required=True)
    parser.add_argument("--attestation-source-ref", required=True)
    parser.add_argument("--attestation-run-id", required=True)
    parser.add_argument("--attestation-run-attempt", type=int, required=True)
    parser.add_argument("--attestation-workflow-ref", required=True)
    parser.add_argument("--attestation-signer-digest", required=True)
    parser.add_argument("--now")
    args = parser.parse_args(argv)
    offline_inputs = (
        args.attestation_bundle,
        args.trusted_root,
        args.write_attestation_receipt,
    )
    if not args.pre_attestation and any(value is None for value in offline_inputs):
        parser.error(
            "--attestation-bundle, --trusted-root and --write-attestation-receipt "
            "are required unless --pre-attestation is set"
        )
    if args.pre_attestation and any(value is not None for value in offline_inputs):
        parser.error("offline attestation inputs are not valid with --pre-attestation")
    now = (
        datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        if args.now
        else datetime.now(timezone.utc)
    )
    try:
        changed_paths = json.loads(args.changed_paths_file.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        parser.error(f"cannot read --changed-paths-file: {exc}")
    if not isinstance(changed_paths, list) or not all(isinstance(path, str) for path in changed_paths):
        parser.error("--changed-paths-file must contain a JSON array of strings")
    receipt_path: Path | None = None
    if not args.pre_attestation:
        try:
            _receipt, raw_receipt = _verify_official_attestation_offline(
                args.manifest,
                args.attestation_bundle,
                args.trusted_root,
                repository=args.repository,
                source_digest=args.attestation_source_digest,
                source_ref=args.attestation_source_ref,
                workflow_ref=args.attestation_workflow_ref,
                signer_digest=args.attestation_signer_digest,
            )
        except RuntimeError as exc:
            print(f"FALLO: {exc}", file=sys.stderr)
            return 1
        receipt_path = args.write_attestation_receipt
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_bytes(raw_receipt)
    errors = verify_manifest(
        args.manifest,
        args.evidence_dir,
        repository=args.repository,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
        workflow=args.workflow,
        workflow_ref=args.workflow_ref,
        ref=args.ref,
        changed_paths=changed_paths,
        now=now,
        catalog_path=args.catalog,
        attestation_receipt_path=receipt_path,
        attestation_source_digest=args.attestation_source_digest,
        attestation_source_ref=args.attestation_source_ref,
        attestation_run_id=args.attestation_run_id,
        attestation_run_attempt=args.attestation_run_attempt,
        attestation_workflow_ref=args.attestation_workflow_ref,
        attestation_signer_digest=args.attestation_signer_digest,
        schema_path=args.schema,
    )
    for error in errors:
        print(f"FALLO: {error}", file=sys.stderr)
    if errors:
        return 1
    print("AUTONOMY EVIDENCE: APTO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
