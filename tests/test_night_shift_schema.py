"""Structural trust tests for the durable night-shift manifest schema.

These tests intentionally use only the standard library.  The offline evidence
verifier enforces cross-field and temporal relationships; this suite makes sure
the published JSON Schema remains a strict, machine-readable envelope.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "night-shift-manifest.schema.json"

SHA256 = "^[0-9a-f]{64}$"
COMMIT_SHA = "^[0-9a-f]{40}$"
BASE_ARTIFACTS = {
    "ci",
    "runtime",
    "secrets",
    "dependencies",
    "license",
    "appsec",
    "reality",
    "overlap",
    "final-review",
}
HIGH_RISK_ARTIFACTS = {"appsec-primary", "appsec-secondary"}
PROFILES = {
    "productOwner": (
        "product/product-manager.md",
        "4a3fe4661e72e5173877bcba7c362392181774b20efc27ac1789171e98676c9d",
    ),
    "maker": (
        "engineering/engineering-api-platform-engineer.md",
        "278798c42d7a7cf4f42d3973795765403105ce60d518d647abfdaa522d862d8e",
    ),
    "finalReviewer": (
        "testing/testing-reality-checker.md",
        "6d32fcdb114233e13902ec6372d50293b120e85d490b5e81d372c29808f988a1",
    ),
    "appsecPrimary": (
        "security/security-appsec-engineer.md",
        "f3ee22350c9e0e7289d2d4747e7c1a8fe196d70340feec7b176b13bacc3deb77",
    ),
    "appsecSecondary": (
        "security/security-architect.md",
        "b1a68e9614f7adb43938f5bd9964f6e41250febc9a57f691eefcbab58d5b1df1",
    ),
}


def _schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _ref_name(value):
    prefix = "#/$defs/"
    reference = value["$ref"]
    assert reference.startswith(prefix), reference
    return reference.removeprefix(prefix)


def test_night_shift_schema_is_draft_2020_12_and_closes_every_object():
    schema = _schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema"]["const"] == "lucidfence-night-shift-manifest/v1"
    assert schema["additionalProperties"] is False

    def walk(value):
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value.get("additionalProperties") is False, value
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(schema)


def test_participants_are_exact_pinned_canonical_profiles():
    schema = _schema()
    participants = schema["properties"]["participants"]
    expected_roles = {
        "product_owner": "productOwner",
        "maker": "maker",
        "final_reviewer": "finalReviewer",
        "reality_checker": "finalReviewer",
        "appsec_primary": "appsecPrimary",
        "appsec_secondary": "appsecSecondary",
    }
    assert participants["additionalProperties"] is False
    assert set(participants["required"]) == set(expected_roles)
    assert set(participants["properties"]) == set(expected_roles)
    for role, definition in expected_roles.items():
        assert _ref_name(participants["properties"][role]) == definition

    for definition, (path, digest) in PROFILES.items():
        profile = schema["$defs"][definition]
        assert profile["additionalProperties"] is False
        assert set(profile["required"]) == {"path", "sha256"}
        assert profile["properties"]["path"]["const"] == path
        assert profile["properties"]["sha256"] == {
            "const": digest,
            "pattern": SHA256,
            "type": "string",
        }


def test_context_and_attestation_are_complete_and_fail_closed():
    schema = _schema()
    required = {
        "schema",
        "repository",
        "base_sha",
        "head_sha",
        "run_id",
        "run_attempt",
        "workflow",
        "workflow_ref",
        "ref",
        "objective",
        "participants",
        "artifacts",
        "generated_at",
        "validity",
        "attestation",
        "manifest_digest",
    }
    assert set(schema["required"]) == required
    assert schema["properties"]["repository"]["const"] == "adrimg3196/lucidfence"
    assert schema["properties"]["base_sha"]["pattern"] == COMMIT_SHA
    assert schema["properties"]["head_sha"]["pattern"] == COMMIT_SHA
    assert schema["properties"]["workflow"]["const"] == "autonomy-evidence"

    attestation = schema["properties"]["attestation"]
    context = {"repository", "base_sha", "head_sha", "evidence_run", "signer"}
    assert attestation["additionalProperties"] is False
    assert set(attestation["required"]) == context | {"predicate_type"}
    assert set(attestation["properties"]) == context | {"predicate_type"}
    assert attestation["properties"]["repository"]["const"] == "adrimg3196/lucidfence"
    evidence_run = attestation["properties"]["evidence_run"]
    assert evidence_run["additionalProperties"] is False
    assert evidence_run["properties"]["workflow"]["const"] == "autonomy-evidence"
    signer = attestation["properties"]["signer"]
    assert signer["additionalProperties"] is False
    assert set(signer["required"]) == {
        "ref",
        "run_attempt",
        "run_id",
        "source_digest",
        "workflow_digest",
        "workflow_ref",
    }
    assert signer["properties"]["ref"]["const"] == "refs/heads/main"
    assert signer["properties"]["workflow_digest"]["pattern"] == COMMIT_SHA
    assert signer["properties"]["source_digest"]["pattern"] == COMMIT_SHA
    assert signer["properties"]["workflow_ref"]["const"].endswith(
        "/.github/workflows/autonomy-attest.yml@refs/heads/main"
    )
    assert attestation["properties"]["predicate_type"]["const"] == "https://slsa.dev/provenance/v1"


def test_artifacts_are_exact_independent_basenames_with_sha256_and_producers():
    schema = _schema()
    artifacts = schema["properties"]["artifacts"]
    all_artifacts = BASE_ARTIFACTS | HIGH_RISK_ARTIFACTS
    producer_by_kind = {
        "ci": "maker",
        "runtime": "maker",
        "secrets": "maker",
        "dependencies": "maker",
        "license": "maker",
        "appsec": "appsecPrimary",
        "reality": "finalReviewer",
        "overlap": "maker",
        "final-review": "finalReviewer",
        "appsec-primary": "appsecPrimary",
        "appsec-secondary": "appsecSecondary",
    }
    assert artifacts["additionalProperties"] is False
    assert set(artifacts["required"]) == BASE_ARTIFACTS
    assert set(artifacts["properties"]) == all_artifacts

    for kind in all_artifacts:
        descriptor = artifacts["properties"][kind]
        assert _ref_name(descriptor["allOf"][0]) == "artifactDescriptor"
        restrictions = descriptor["allOf"][1]["properties"]
        assert restrictions["path"]["const"] == f"{kind}.json"
        assert _ref_name(restrictions["producer"]) == producer_by_kind[kind]

    descriptor = schema["$defs"]["artifactDescriptor"]
    assert descriptor["additionalProperties"] is False
    assert set(descriptor["required"]) == {"path", "producer", "sha256"}
    assert descriptor["properties"]["path"]["pattern"] == "^[A-Za-z0-9][A-Za-z0-9._-]*\\.json$"
    assert descriptor["properties"]["sha256"]["pattern"] == SHA256

    conditional = schema["allOf"][0]
    assert conditional["if"]["properties"]["objective"]["properties"]["risk"]["const"] == "high"
    assert set(conditional["then"]["properties"]["artifacts"]["required"]) == HIGH_RISK_ARTIFACTS
    forbidden = conditional["else"]["properties"]["artifacts"]["properties"]
    assert forbidden == {"appsec-primary": False, "appsec-secondary": False}


def test_validity_and_manifest_digest_are_explicit_sha256_contracts():
    schema = _schema()
    validity = schema["properties"]["validity"]
    assert validity["additionalProperties"] is False
    assert set(validity["required"]) == {"not_before", "expires_at", "policy"}
    assert validity["properties"]["policy"] == {"const": "P7D", "type": "string"}
    for field in ("not_before", "expires_at"):
        assert validity["properties"][field]["format"] == "date-time"

    digest = schema["properties"]["manifest_digest"]
    assert digest["additionalProperties"] is False
    assert set(digest["required"]) == {"algorithm", "value"}
    assert digest["properties"]["algorithm"] == {"const": "sha256", "type": "string"}
    assert digest["properties"]["value"]["pattern"] == SHA256
