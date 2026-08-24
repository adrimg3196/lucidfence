"""Fail-closed tests for durable autonomy-B evidence manifests."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from scripts import verify_autonomy_evidence as evidence


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "adrimg3196/lucidfence"
BASE_SHA = "539027a7b5a0a92c1e8508f471a0da405fdf4fb1"
HEAD_SHA = "1111111111111111111111111111111111111111"
RUN_ID = "32590000000"
RUN_ATTEMPT = 1
WORKFLOW = "autonomy-evidence"
WORKFLOW_REF = "adrimg3196/lucidfence/.github/workflows/autonomy-evidence.yml@refs/pull/264/merge"
REF = "refs/pull/264/merge"
CHANGED_PATHS = [".github/workflows/autonomy-evidence.yml"]
ATTESTATION_SOURCE_DIGEST = "2" * 40
ATTESTATION_SOURCE_REF = "refs/heads/main"
ATTESTATION_RUN_ID = "32590000001"
ATTESTATION_RUN_ATTEMPT = 1
ATTESTATION_WORKFLOW_REF = (
    "adrimg3196/lucidfence/.github/workflows/autonomy-attest.yml@refs/heads/main"
)
ATTESTATION_SIGNER_DIGEST = "3" * 40
NOW = datetime(2026, 8, 24, 0, 0, tzinfo=timezone.utc)

PRODUCT = {
    "path": "product/product-manager.md",
    "sha256": "4a3fe4661e72e5173877bcba7c362392181774b20efc27ac1789171e98676c9d",
}
MAKER = {
    "path": "engineering/engineering-api-platform-engineer.md",
    "sha256": "278798c42d7a7cf4f42d3973795765403105ce60d518d647abfdaa522d862d8e",
}
FINAL = {
    "path": "testing/testing-reality-checker.md",
    "sha256": "6d32fcdb114233e13902ec6372d50293b120e85d490b5e81d372c29808f988a1",
}
APPSEC_PRIMARY = {
    "path": "security/security-appsec-engineer.md",
    "sha256": "f3ee22350c9e0e7289d2d4747e7c1a8fe196d70340feec7b176b13bacc3deb77",
}
APPSEC_SECONDARY = {
    "path": "security/security-architect.md",
    "sha256": "b1a68e9614f7adb43938f5bd9964f6e41250febc9a57f691eefcbab58d5b1df1",
}

BASE_KINDS = (
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
HIGH_RISK_KINDS = ("appsec-primary", "appsec-secondary")


def _producer(kind):
    if kind == "final-review" or kind == "reality":
        return FINAL
    if kind == "appsec-primary":
        return APPSEC_PRIMARY
    if kind == "appsec-secondary":
        return APPSEC_SECONDARY
    if kind == "appsec":
        return APPSEC_PRIMARY
    return MAKER


def _artifact(kind, raw_log):
    result = {
        "check": kind,
        "command_id": evidence.EXPECTED_COMMAND_IDS[kind],
        "exit_code": 0,
        "output_bytes": len(raw_log),
        "output_sha256": hashlib.sha256(raw_log).hexdigest(),
        "status": "pass",
    }
    if kind == "overlap":
        result.update({"conflicts": [], "overlaps": [], "snapshot_sha256": "0" * 64})
    return {
        "base_sha": BASE_SHA,
        "generated_at": "2026-08-23T21:00:00Z",
        "head_sha": HEAD_SHA,
        "kind": kind,
        "objective": "bootstrap/autonomy-b-control-plane",
        "producer": copy.deepcopy(_producer(kind)),
        "ref": REF,
        "repository": REPOSITORY,
        "result": result,
        "run_attempt": RUN_ATTEMPT,
        "run_id": RUN_ID,
        "schema": "lucidfence-autonomy-evidence/v1",
        "workflow": WORKFLOW,
        "workflow_ref": WORKFLOW_REF,
    }


def _write_json(path, value):
    path.write_bytes(evidence.canonical_document(value))


def _bind_receipt_to_manifest(receipt_path, manifest_path):
    receipt = json.loads(receipt_path.read_bytes())
    receipt[0]["verificationResult"]["statement"]["subject"][0]["digest"][
        "sha256"
    ] = evidence.sha256_file(manifest_path)
    _write_json(receipt_path, receipt)


def _fixture(tmp_path):
    root = Path(tmp_path)
    evidence_dir = root / "evidence"
    evidence_dir.mkdir(parents=True)
    artifacts = {}
    for kind in BASE_KINDS + HIGH_RISK_KINDS:
        raw_log = f"{kind}: independently derived pass\n".encode()
        path = evidence_dir / f"{kind}.json"
        document = _artifact(kind, raw_log)
        _write_json(path, document)
        artifacts[kind] = {
            "path": path.name,
            "producer": copy.deepcopy(document["producer"]),
            "sha256": evidence.sha256_file(path),
        }
    manifest = {
        "artifacts": artifacts,
        "attestation": {
            "base_sha": BASE_SHA,
            "evidence_run": {
                "attempt": RUN_ATTEMPT,
                "id": RUN_ID,
                "ref": REF,
                "workflow": WORKFLOW,
                "workflow_ref": WORKFLOW_REF,
            },
            "head_sha": HEAD_SHA,
            "predicate_type": "https://slsa.dev/provenance/v1",
            "repository": REPOSITORY,
            "signer": {
                "ref": ATTESTATION_SOURCE_REF,
                "run_attempt": ATTESTATION_RUN_ATTEMPT,
                "run_id": ATTESTATION_RUN_ID,
                "source_digest": ATTESTATION_SOURCE_DIGEST,
                "workflow_digest": ATTESTATION_SIGNER_DIGEST,
                "workflow_ref": ATTESTATION_WORKFLOW_REF,
            },
        },
        "base_sha": BASE_SHA,
        "generated_at": "2026-08-23T21:00:00Z",
        "head_sha": HEAD_SHA,
        "manifest_digest": {"algorithm": "sha256", "value": "0" * 64},
        "objective": {
            "changed_paths": CHANGED_PATHS,
            "id": "bootstrap/autonomy-b-control-plane",
            "risk": "high",
        },
        "participants": {
            "appsec_primary": copy.deepcopy(APPSEC_PRIMARY),
            "appsec_secondary": copy.deepcopy(APPSEC_SECONDARY),
            "final_reviewer": copy.deepcopy(FINAL),
            "maker": copy.deepcopy(MAKER),
            "product_owner": copy.deepcopy(PRODUCT),
            "reality_checker": copy.deepcopy(FINAL),
        },
        "ref": REF,
        "repository": REPOSITORY,
        "run_attempt": RUN_ATTEMPT,
        "run_id": RUN_ID,
        "schema": "lucidfence-night-shift-manifest/v1",
        "validity": {
            "expires_at": "2026-08-30T21:00:00Z",
            "not_before": "2026-08-23T21:00:00Z",
            "policy": "P7D",
        },
        "workflow": WORKFLOW,
        "workflow_ref": WORKFLOW_REF,
    }
    evidence.seal_manifest(manifest)
    manifest_path = root / "manifest.json"
    _write_json(manifest_path, manifest)
    signer_uri = f"https://github.com/{ATTESTATION_WORKFLOW_REF}"
    receipt = [
        {
            "attestation": {"mediaType": "application/vnd.dev.sigstore.bundle+json;version=0.3"},
            "verificationResult": {
                "signature": {
                    "certificate": {
                        "buildConfigURI": signer_uri,
                        "buildSignerDigest": ATTESTATION_SIGNER_DIGEST,
                        "issuer": "https://token.actions.githubusercontent.com",
                        "runnerEnvironment": "github-hosted",
                        "runInvocationURI": (
                            f"https://github.com/{REPOSITORY}/actions/runs/"
                            f"{ATTESTATION_RUN_ID}/attempts/{ATTESTATION_RUN_ATTEMPT}"
                        ),
                        "sourceRepositoryDigest": ATTESTATION_SOURCE_DIGEST,
                        "sourceRepositoryRef": ATTESTATION_SOURCE_REF,
                        "sourceRepositoryURI": f"https://github.com/{REPOSITORY}",
                        "subjectAlternativeName": signer_uri,
                    }
                },
                "statement": {
                    "predicate": {},
                    "predicateType": "https://slsa.dev/provenance/v1",
                    "subject": [
                        {"digest": {"sha256": evidence.sha256_file(manifest_path)}, "name": "manifest.json"}
                    ],
                },
                "verifiedTimestamps": [{"timestamp": "2026-08-23T21:00:01Z", "type": "Tlog"}],
            },
        }
    ]
    receipt_path = root / "attestation-verification.json"
    _write_json(receipt_path, receipt)
    return root, manifest_path, evidence_dir, receipt_path


def _durable_fixture(tmp_path):
    root = Path(tmp_path)
    source, manifest, artifacts, receipt = _fixture(root / "source")
    runs = root / "runs"
    bundle = (
        runs
        / "v1"
        / f"run-{RUN_ID}-attempt-{RUN_ATTEMPT}-head-{HEAD_SHA}"
    )
    (bundle / "evidence").mkdir(parents=True)
    (runs / "README.md").write_text("# Durable evidence\n", encoding="utf-8")
    shutil.copy2(manifest, bundle / "manifest.json")
    for artifact in artifacts.iterdir():
        shutil.copy2(artifact, bundle / "evidence" / artifact.name)
    (bundle / "attestation.bundle.jsonl").write_text(
        '{"mediaType":"application/vnd.dev.sigstore.bundle+json;version=0.3"}\n',
        encoding="utf-8",
    )
    (bundle / "trusted-root.jsonl").write_text(
        '{"mediaType":"application/vnd.dev.sigstore.trustedroot+json;version=0.1"}\n',
        encoding="utf-8",
    )
    external_trusted_root = root / "official-trusted-root.jsonl"
    shutil.copy2(bundle / "trusted-root.jsonl", external_trusted_root)
    return source, runs, bundle, receipt, external_trusted_root


class _OfflineVerificationResult:
    returncode = 0
    stderr = b""

    def __init__(self, stdout):
        self.stdout = stdout


def _verify(manifest_path, evidence_dir, receipt_path, **overrides):
    expected = {
        "repository": REPOSITORY,
        "base_sha": BASE_SHA,
        "head_sha": HEAD_SHA,
        "run_id": RUN_ID,
        "run_attempt": RUN_ATTEMPT,
        "workflow": WORKFLOW,
        "workflow_ref": WORKFLOW_REF,
        "ref": REF,
        "changed_paths": CHANGED_PATHS,
        "now": NOW,
        "catalog_path": ROOT / "data" / "agency_catalog.json",
        "attestation_receipt_path": receipt_path,
        "attestation_source_digest": ATTESTATION_SOURCE_DIGEST,
        "attestation_source_ref": ATTESTATION_SOURCE_REF,
        "attestation_run_id": ATTESTATION_RUN_ID,
        "attestation_run_attempt": ATTESTATION_RUN_ATTEMPT,
        "attestation_workflow_ref": ATTESTATION_WORKFLOW_REF,
        "attestation_signer_digest": ATTESTATION_SIGNER_DIGEST,
    }
    expected.update(overrides)
    return evidence.verify_manifest(manifest_path, evidence_dir, **expected)


def _mutate_artifact(manifest_path, evidence_dir, kind, mutator):
    manifest = json.loads(manifest_path.read_bytes())
    artifact_path = evidence_dir / manifest["artifacts"][kind]["path"]
    artifact = json.loads(artifact_path.read_bytes())
    mutator(artifact)
    _write_json(artifact_path, artifact)
    manifest["artifacts"][kind]["producer"] = copy.deepcopy(artifact["producer"])
    manifest["artifacts"][kind]["sha256"] = evidence.sha256_file(artifact_path)
    evidence.seal_manifest(manifest)
    _write_json(manifest_path, manifest)
    return manifest


def test_valid_high_risk_manifest_is_accepted():
    with tempfile.TemporaryDirectory(prefix="autonomy-valid-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        assert _verify(manifest, artifacts, receipt) == []


def test_offline_verifier_rejects_partial_or_rewritten_agency_catalog():
    with tempfile.TemporaryDirectory(prefix="autonomy-partial-catalog-") as tmp:
        root, manifest, artifacts, receipt = _fixture(tmp)
        catalog = json.loads((ROOT / "data" / "agency_catalog.json").read_bytes())
        catalog["profiles"] = catalog["profiles"][:5]
        catalog["lock"]["profiles"] = copy.deepcopy(catalog["profiles"])
        catalog["lock"]["profile_count"] = len(catalog["profiles"])
        catalog["lock"]["inventory_sha256"] = hashlib.sha256(
            evidence.canonical_bytes(catalog["profiles"])
        ).hexdigest()
        catalog_path = root / "partial-agency-catalog.json"
        _write_json(catalog_path, catalog)

        errors = _verify(
            manifest,
            artifacts,
            receipt,
            catalog_path=catalog_path,
        )
        assert any("exactly 270" in error for error in errors), errors
        assert any("fixed profile inventory" in error for error in errors), errors


def test_pre_attestation_validation_accepts_core_evidence_without_receipt():
    with tempfile.TemporaryDirectory(prefix="autonomy-pre-attest-") as tmp:
        _root, manifest, artifacts, _receipt = _fixture(tmp)
        errors = _verify(manifest, artifacts, None, attestation_receipt_path=None)
        assert errors == [], errors


def test_rejects_one_byte_artifact_tamper():
    with tempfile.TemporaryDirectory(prefix="autonomy-tamper-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        with (artifacts / "ci.json").open("ab") as fh:
            fh.write(b" ")
        errors = _verify(manifest, artifacts, receipt)
        assert any("digest" in error for error in errors), errors


def test_rejects_manifest_or_artifact_fields_outside_closed_schema():
    with tempfile.TemporaryDirectory(prefix="autonomy-extra-fields-") as tmp:
        _root, manifest_path, artifacts, receipt = _fixture(tmp)
        manifest = json.loads(manifest_path.read_bytes())
        manifest["unexpected_root_field"] = True
        evidence.seal_manifest(manifest)
        _write_json(manifest_path, manifest)
        errors = _verify(manifest_path, artifacts, receipt)
        assert any("closed schema" in error for error in errors), errors

    with tempfile.TemporaryDirectory(prefix="autonomy-extra-artifact-field-") as tmp:
        _root, manifest_path, artifacts, receipt = _fixture(tmp)
        _mutate_artifact(
            manifest_path,
            artifacts,
            "ci",
            lambda artifact: artifact.__setitem__("unexpected", True),
        )
        errors = _verify(manifest_path, artifacts, receipt)
        assert any("artifact fields" in error and "ci" in error for error in errors), errors


def test_rejects_missing_required_artifact():
    with tempfile.TemporaryDirectory(prefix="autonomy-missing-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        (artifacts / "runtime.json").unlink()
        errors = _verify(manifest, artifacts, receipt)
        assert any("runtime" in error and "missing" in error for error in errors), errors


def test_rejects_expired_evidence():
    with tempfile.TemporaryDirectory(prefix="autonomy-expired-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        errors = _verify(manifest, artifacts, receipt, now=datetime(2026, 9, 1, tzinfo=timezone.utc))
        assert any("expired" in error for error in errors), errors


def test_rejects_evidence_exactly_at_expiry_boundary():
    with tempfile.TemporaryDirectory(prefix="autonomy-expiry-boundary-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        errors = _verify(
            manifest,
            artifacts,
            receipt,
            now=datetime(2026, 8, 30, 21, 0, tzinfo=timezone.utc),
        )
        assert any("expired" in error for error in errors), errors


def test_executes_full_manifest_schema_fail_closed():
    mutations = (
        ("non-Z timestamp", lambda manifest: manifest.__setitem__("generated_at", "2026-08-23T21:00:00+00:00")),
        ("zero run id", lambda manifest: manifest.__setitem__("run_id", "0")),
        ("empty objective", lambda manifest: manifest["objective"].__setitem__("id", "")),
        (
            "overlong objective",
            lambda manifest: manifest["objective"].__setitem__("id", "a" * 129),
        ),
        (
            "parent path",
            lambda manifest: manifest["objective"].__setitem__("changed_paths", ["../secret"]),
        ),
        (
            "duplicate paths",
            lambda manifest: manifest["objective"].__setitem__(
                "changed_paths", [CHANGED_PATHS[0], CHANGED_PATHS[0]]
            ),
        ),
    )
    for label, mutate in mutations:
        with tempfile.TemporaryDirectory(prefix="autonomy-schema-") as tmp:
            _root, manifest_path, artifacts, receipt = _fixture(tmp)
            manifest = json.loads(manifest_path.read_bytes())
            mutate(manifest)
            evidence.seal_manifest(manifest)
            _write_json(manifest_path, manifest)
            errors = _verify(manifest_path, artifacts, receipt)
            assert any("JSON Schema" in error for error in errors), (label, errors)


def test_schema_forbids_high_risk_receipts_on_normal_objective():
    with tempfile.TemporaryDirectory(prefix="autonomy-normal-schema-") as tmp:
        _root, manifest_path, artifacts, receipt = _fixture(tmp)
        manifest = json.loads(manifest_path.read_bytes())
        manifest["objective"] = {
            "changed_paths": ["docs/guide.md"],
            "id": "bootstrap/autonomy-b-control-plane",
            "risk": "normal",
        }
        primary = manifest["artifacts"].pop("appsec-primary")
        manifest["artifacts"].pop("appsec-secondary")
        evidence.seal_manifest(manifest)
        _write_json(manifest_path, manifest)
        _bind_receipt_to_manifest(receipt, manifest_path)
        assert _verify(
            manifest_path,
            artifacts,
            receipt,
            changed_paths=["docs/guide.md"],
        ) == []

        manifest["artifacts"]["appsec-primary"] = primary
        evidence.seal_manifest(manifest)
        _write_json(manifest_path, manifest)
        _bind_receipt_to_manifest(receipt, manifest_path)
        errors = _verify(
            manifest_path,
            artifacts,
            receipt,
            changed_paths=["docs/guide.md"],
        )
        assert any("JSON Schema" in error and "forbidden" in error for error in errors), errors


def test_schema_validator_rejects_an_unsupported_keyword():
    with tempfile.TemporaryDirectory(prefix="autonomy-schema-keyword-") as tmp:
        root, manifest, artifacts, receipt = _fixture(tmp)
        schema = json.loads(
            (ROOT / "config" / "night-shift-manifest.schema.json").read_bytes()
        )
        schema["unevaluatedProperties"] = False
        schema_path = root / "schema.json"
        _write_json(schema_path, schema)
        errors = _verify(manifest, artifacts, receipt, schema_path=schema_path)
        assert any("cannot be enforced" in error for error in errors), errors


def test_rejects_wrong_base_sha():
    with tempfile.TemporaryDirectory(prefix="autonomy-base-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        errors = _verify(manifest, artifacts, receipt, base_sha="2" * 40)
        assert any("base_sha" in error for error in errors), errors


def test_rejects_wrong_head_sha():
    with tempfile.TemporaryDirectory(prefix="autonomy-head-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        errors = _verify(manifest, artifacts, receipt, head_sha="3" * 40)
        assert any("head_sha" in error for error in errors), errors


def test_rejects_wrong_run_id_or_attempt():
    with tempfile.TemporaryDirectory(prefix="autonomy-run-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        assert any("run_id" in error for error in _verify(manifest, artifacts, receipt, run_id="9"))
        assert any("run_attempt" in error for error in _verify(manifest, artifacts, receipt, run_attempt=2))


def test_rejects_noncanonical_producer_alias():
    with tempfile.TemporaryDirectory(prefix="autonomy-alias-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        _mutate_artifact(
            manifest,
            artifacts,
            "reality",
            lambda artifact: artifact.__setitem__("producer", {"path": "Reality Checker", "sha256": FINAL["sha256"]}),
        )
        errors = _verify(manifest, artifacts, receipt)
        assert any("canonical producer" in error for error in errors), errors


def test_rejects_same_profile_as_maker_and_final_reviewer():
    with tempfile.TemporaryDirectory(prefix="autonomy-maker-final-") as tmp:
        _root, manifest_path, artifacts, receipt = _fixture(tmp)
        manifest = _mutate_artifact(
            manifest_path,
            artifacts,
            "final-review",
            lambda artifact: artifact.__setitem__("producer", copy.deepcopy(MAKER)),
        )
        manifest["participants"]["final_reviewer"] = copy.deepcopy(MAKER)
        evidence.seal_manifest(manifest)
        _write_json(manifest_path, manifest)
        errors = _verify(manifest_path, artifacts, receipt)
        assert any("maker and final reviewer" in error for error in errors), errors


def test_rejects_high_risk_without_two_independent_appsec_reviews():
    with tempfile.TemporaryDirectory(prefix="autonomy-appsec-") as tmp:
        _root, manifest_path, artifacts, receipt = _fixture(tmp)
        manifest = json.loads(manifest_path.read_bytes())
        manifest["participants"]["appsec_secondary"] = copy.deepcopy(APPSEC_PRIMARY)
        evidence.seal_manifest(manifest)
        _write_json(manifest_path, manifest)
        errors = _verify(manifest_path, artifacts, receipt)
        assert any("AppSec reviewers" in error for error in errors), errors


def test_rejects_high_risk_downgrade_even_when_appsec_artifacts_are_removed():
    with tempfile.TemporaryDirectory(prefix="autonomy-risk-downgrade-") as tmp:
        _root, manifest_path, artifacts, receipt = _fixture(tmp)
        manifest = json.loads(manifest_path.read_bytes())
        manifest["objective"]["risk"] = "normal"
        manifest["artifacts"].pop("appsec-primary")
        manifest["artifacts"].pop("appsec-secondary")
        evidence.seal_manifest(manifest)
        _write_json(manifest_path, manifest)
        errors = _verify(manifest_path, artifacts, receipt)
        assert any("risk mismatch" in error for error in errors), errors
        assert any("artifact inventory" in error for error in errors), errors


def test_rejects_canonical_but_wrong_profiles_in_appsec_seats():
    with tempfile.TemporaryDirectory(prefix="autonomy-wrong-appsec-") as tmp:
        _root, manifest_path, artifacts, receipt = _fixture(tmp)
        manifest = json.loads(manifest_path.read_bytes())
        manifest["participants"]["appsec_primary"] = copy.deepcopy(PRODUCT)
        manifest["participants"]["appsec_secondary"] = copy.deepcopy(FINAL)
        evidence.seal_manifest(manifest)
        _write_json(manifest_path, manifest)
        errors = _verify(manifest_path, artifacts, receipt)
        assert any("appsec_primary" in error and "pinned canonical" in error for error in errors), errors
        assert any("appsec_secondary" in error and "pinned canonical" in error for error in errors), errors


def test_rejects_overlapping_or_conflicting_objective():
    with tempfile.TemporaryDirectory(prefix="autonomy-overlap-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        _mutate_artifact(
            manifest,
            artifacts,
            "overlap",
            lambda artifact: artifact["result"]["conflicts"].append("scripts/verify.py"),
        )
        errors = _verify(manifest, artifacts, receipt)
        assert any("overlap" in error or "conflict" in error for error in errors), errors


def test_rejects_attestation_for_wrong_repository_or_signer_commit():
    with tempfile.TemporaryDirectory(prefix="autonomy-attestation-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        document = json.loads(receipt.read_bytes())
        certificate = document[0]["verificationResult"]["signature"]["certificate"]
        certificate["sourceRepositoryURI"] = "https://github.com/attacker/example"
        certificate["sourceRepositoryDigest"] = "4" * 40
        _write_json(receipt, document)
        errors = _verify(manifest, artifacts, receipt)
        assert any("official attestation output" in error for error in errors), errors


def test_rejects_attestation_from_wrong_trusted_workflow_digest():
    with tempfile.TemporaryDirectory(prefix="autonomy-signer-digest-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        document = json.loads(receipt.read_bytes())
        certificate = document[0]["verificationResult"]["signature"]["certificate"]
        certificate["buildSignerDigest"] = "9" * 40
        _write_json(receipt, document)
        errors = _verify(manifest, artifacts, receipt)
        assert any("official attestation output" in error for error in errors), errors


def test_rejects_locally_asserted_attestation_receipt():
    with tempfile.TemporaryDirectory(prefix="autonomy-forged-receipt-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        _write_json(receipt, {"verified": True, "subject_sha256": evidence.sha256_file(manifest)})
        errors = _verify(manifest, artifacts, receipt)
        assert any("non-empty JSON array" in error for error in errors), errors


def test_offline_attestation_verification_uses_bundle_and_trusted_root():
    with tempfile.TemporaryDirectory(prefix="autonomy-offline-attestation-") as tmp:
        root, manifest, _artifacts, receipt = _fixture(tmp)
        bundle = root / "bundle.json"
        trusted_root = root / "trusted-root.jsonl"
        bundle.write_text('{"mediaType":"application/vnd.dev.sigstore.bundle+json;version=0.3"}\n')
        trusted_root.write_text('{"mediaType":"application/vnd.dev.sigstore.trustedroot+json;version=0.1"}\n')
        expected_stdout = receipt.read_bytes()
        calls = []
        original = evidence.subprocess.run

        class Result:
            returncode = 0
            stdout = expected_stdout
            stderr = b""

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            return Result()

        evidence.subprocess.run = fake_run
        try:
            document, raw = evidence._verify_official_attestation_offline(
                manifest,
                bundle,
                trusted_root,
                repository=REPOSITORY,
                source_digest=ATTESTATION_SOURCE_DIGEST,
                source_ref=ATTESTATION_SOURCE_REF,
                workflow_ref=ATTESTATION_WORKFLOW_REF,
                signer_digest=ATTESTATION_SIGNER_DIGEST,
            )
        finally:
            evidence.subprocess.run = original

        assert document == json.loads(expected_stdout)
        assert raw == expected_stdout
        command, kwargs = calls[0]
        assert command[:3] == ["gh", "attestation", "verify"]
        assert command[3] == str(manifest)
        assert command[command.index("--bundle") + 1] == str(bundle)
        assert command[command.index("--custom-trusted-root") + 1] == str(trusted_root)
        assert command[command.index("--signer-digest") + 1] == ATTESTATION_SIGNER_DIGEST
        assert command[command.index("--source-digest") + 1] == ATTESTATION_SOURCE_DIGEST
        assert "GH_TOKEN" not in kwargs["env"] and "GITHUB_TOKEN" not in kwargs["env"]


def test_offline_attestation_failure_never_echoes_verifier_stderr():
    with tempfile.TemporaryDirectory(prefix="autonomy-offline-attestation-fail-") as tmp:
        root, manifest, _artifacts, _receipt = _fixture(tmp)
        bundle = root / "bundle.json"
        trusted_root = root / "trusted-root.jsonl"
        bundle.write_text("{}\n")
        trusted_root.write_text("{}\n")
        original = evidence.subprocess.run

        class Result:
            returncode = 1
            stdout = b""
            stderr = b"TOKEN_MUST_NEVER_BE_REPEATED"

        evidence.subprocess.run = lambda *_args, **_kwargs: Result()
        try:
            try:
                evidence._verify_official_attestation_offline(
                    manifest,
                    bundle,
                    trusted_root,
                    repository=REPOSITORY,
                    source_digest=ATTESTATION_SOURCE_DIGEST,
                    source_ref=ATTESTATION_SOURCE_REF,
                    workflow_ref=ATTESTATION_WORKFLOW_REF,
                    signer_digest=ATTESTATION_SIGNER_DIGEST,
                )
            except RuntimeError as exc:
                assert "TOKEN_MUST_NEVER_BE_REPEATED" not in str(exc)
            else:
                raise AssertionError("failed cryptographic verification must fail closed")
        finally:
            evidence.subprocess.run = original


def test_durable_store_accepts_only_a_complete_officially_verified_v1_bundle():
    with tempfile.TemporaryDirectory(prefix="autonomy-durable-valid-") as tmp:
        _source, runs, bundle, receipt, trusted_root = _durable_fixture(tmp)
        calls = []
        original = evidence.subprocess.run

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            return _OfflineVerificationResult(receipt.read_bytes())

        evidence.subprocess.run = fake_run
        try:
            errors = evidence.verify_durable_store(
                runs,
                now=NOW,
                catalog_path=ROOT / "data" / "agency_catalog.json",
                schema_path=ROOT / "config" / "night-shift-manifest.schema.json",
                trusted_root_path=trusted_root,
            )
        finally:
            evidence.subprocess.run = original

        assert errors == [], errors
        assert len(calls) == 1
        command, kwargs = calls[0]
        assert command[:3] == ["gh", "attestation", "verify"]
        assert "--bundle" in command
        assert "--custom-trusted-root" in command
        trusted_root_argument = command[command.index("--custom-trusted-root") + 1]
        assert trusted_root_argument == str(trusted_root.resolve())
        assert trusted_root_argument != str(bundle / "trusted-root.jsonl")
        assert "GH_TOKEN" not in kwargs["env"] and "GITHUB_TOKEN" not in kwargs["env"]


def test_durable_store_rejects_loose_or_unexpected_run_files_before_crypto():
    with tempfile.TemporaryDirectory(prefix="autonomy-durable-inventory-") as tmp:
        _source, runs, bundle, _receipt, trusted_root = _durable_fixture(tmp)
        (runs / "arbitrary-manifest.json").write_text("{}\n", encoding="utf-8")
        (bundle / "unexpected.json").write_text("{}\n", encoding="utf-8")
        original = evidence.subprocess.run
        evidence.subprocess.run = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("structurally invalid durable state must not reach gh")
        )
        try:
            errors = evidence.verify_durable_store(
                runs,
                now=NOW,
                catalog_path=ROOT / "data" / "agency_catalog.json",
                schema_path=ROOT / "config" / "night-shift-manifest.schema.json",
                trusted_root_path=trusted_root,
            )
        finally:
            evidence.subprocess.run = original

        assert any("runs inventory" in error for error in errors), errors
        assert any("bundle inventory" in error for error in errors), errors


def test_durable_store_requires_an_external_trusted_root_before_crypto():
    with tempfile.TemporaryDirectory(prefix="autonomy-durable-root-required-") as tmp:
        _source, runs, _bundle, _receipt, _trusted_root = _durable_fixture(tmp)
        original = evidence.subprocess.run
        evidence.subprocess.run = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("missing external trust root must fail before gh")
        )
        try:
            errors = evidence.verify_durable_store(
                runs,
                now=NOW,
                catalog_path=ROOT / "data" / "agency_catalog.json",
                schema_path=ROOT / "config" / "night-shift-manifest.schema.json",
            )
        finally:
            evidence.subprocess.run = original

        assert errors == ["external attestation trusted root is required"], errors


def test_durable_store_rejects_a_trusted_root_from_inside_the_store():
    with tempfile.TemporaryDirectory(prefix="autonomy-durable-root-circular-") as tmp:
        _source, runs, bundle, _receipt, _trusted_root = _durable_fixture(tmp)
        original = evidence.subprocess.run
        evidence.subprocess.run = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("circular trust root must fail before gh")
        )
        try:
            errors = evidence.verify_durable_store(
                runs,
                now=NOW,
                catalog_path=ROOT / "data" / "agency_catalog.json",
                schema_path=ROOT / "config" / "night-shift-manifest.schema.json",
                trusted_root_path=bundle / "trusted-root.jsonl",
            )
        finally:
            evidence.subprocess.run = original

        assert errors == ["attestation trusted root must be external to durable runs"], errors


def test_durable_store_requires_v1_to_be_absent_until_the_first_complete_bundle():
    with tempfile.TemporaryDirectory(prefix="autonomy-durable-empty-v1-") as tmp:
        runs = Path(tmp) / "runs"
        (runs / "v1").mkdir(parents=True)
        (runs / "README.md").write_text("# Durable evidence\n", encoding="utf-8")

        errors = evidence.verify_durable_store(
            runs,
            now=NOW,
            catalog_path=ROOT / "data" / "agency_catalog.json",
            schema_path=ROOT / "config" / "night-shift-manifest.schema.json",
        )

        assert errors == ["durable v1 inventory is empty"], errors


def test_durable_store_rejects_tampered_artifact_after_official_manifest_verification():
    with tempfile.TemporaryDirectory(prefix="autonomy-durable-tamper-") as tmp:
        _source, runs, bundle, receipt, trusted_root = _durable_fixture(tmp)
        with (bundle / "evidence" / "ci.json").open("ab") as handle:
            handle.write(b" ")
        original = evidence.subprocess.run
        evidence.subprocess.run = lambda *_args, **_kwargs: _OfflineVerificationResult(
            receipt.read_bytes()
        )
        try:
            errors = evidence.verify_durable_store(
                runs,
                now=NOW,
                catalog_path=ROOT / "data" / "agency_catalog.json",
                schema_path=ROOT / "config" / "night-shift-manifest.schema.json",
                trusted_root_path=trusted_root,
            )
        finally:
            evidence.subprocess.run = original

        assert any("artifact digest mismatch: ci" in error for error in errors), errors


def test_durable_store_fails_closed_when_offline_cryptographic_verification_fails():
    with tempfile.TemporaryDirectory(prefix="autonomy-durable-attestation-") as tmp:
        _source, runs, _bundle, _receipt, trusted_root = _durable_fixture(tmp)
        original = evidence.subprocess.run

        class Failure:
            returncode = 1
            stdout = b""
            stderr = b"SECRET_OUTPUT_MUST_NOT_ESCAPE"

        evidence.subprocess.run = lambda *_args, **_kwargs: Failure()
        try:
            errors = evidence.verify_durable_store(
                runs,
                now=NOW,
                catalog_path=ROOT / "data" / "agency_catalog.json",
                schema_path=ROOT / "config" / "night-shift-manifest.schema.json",
                trusted_root_path=trusted_root,
            )
        finally:
            evidence.subprocess.run = original

        assert any("offline cryptographic attestation verification failed" in error for error in errors)
        assert all("SECRET_OUTPUT_MUST_NOT_ESCAPE" not in error for error in errors)


def test_durable_store_rejects_sensitive_attestation_inputs_before_crypto():
    with tempfile.TemporaryDirectory(prefix="autonomy-durable-sensitive-") as tmp:
        _source, runs, bundle, _receipt, trusted_root = _durable_fixture(tmp)
        (bundle / "trusted-root.jsonl").write_text(
            "ghp_" + "A" * 24 + "\n", encoding="utf-8"
        )
        original = evidence.subprocess.run
        evidence.subprocess.run = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("sensitive archive bytes must fail before gh")
        )
        try:
            errors = evidence.verify_durable_store(
                runs,
                now=NOW,
                catalog_path=ROOT / "data" / "agency_catalog.json",
                schema_path=ROOT / "config" / "night-shift-manifest.schema.json",
                trusted_root_path=trusted_root,
            )
        finally:
            evidence.subprocess.run = original

        assert any("trusted root contains sensitive data" in error for error in errors), errors


def test_rejects_fabricated_command_output_receipt():
    with tempfile.TemporaryDirectory(prefix="autonomy-output-receipt-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        _mutate_artifact(
            manifest,
            artifacts,
            "runtime",
            lambda artifact: artifact["result"].update(
                {"exit_code": 1, "output_bytes": 0, "output_sha256": "not-a-digest"}
            ),
        )
        errors = _verify(manifest, artifacts, receipt)
        assert any("did not exit cleanly" in error for error in errors), errors
        assert any("output byte count" in error for error in errors), errors
        assert any("output digest" in error for error in errors), errors


def test_rejects_fabricated_check_or_command_identity():
    with tempfile.TemporaryDirectory(prefix="autonomy-command-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        _mutate_artifact(
            manifest,
            artifacts,
            "ci",
            lambda artifact: artifact["result"].update({"check": "green", "command_id": "echo-pass"}),
        )
        errors = _verify(manifest, artifacts, receipt)
        assert any("exact check name mismatch" in error for error in errors), errors
        assert any("command identity mismatch" in error for error in errors), errors


def test_rejects_known_test_secret_or_private_tenant_marker():
    with tempfile.TemporaryDirectory(prefix="autonomy-secret-") as tmp:
        _root, manifest, artifacts, receipt = _fixture(tmp)
        _mutate_artifact(
            manifest,
            artifacts,
            "secrets",
            lambda artifact: artifact["result"].__setitem__(
                "detail", "REAL_TENANT_" + "PRIVATE_DATA"
            ),
        )
        errors = _verify(manifest, artifacts, receipt)
        assert any("sensitive" in error for error in errors), errors
