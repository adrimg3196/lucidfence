"""Behavioral and policy tests for the Actions evidence producer."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone

from scripts import emit_autonomy_evidence as producer
from scripts import supervise_autonomy_check as supervisor


ROOT = Path(__file__).resolve().parents[1]


def _context():
    return {
        "base_sha": "539027a7b5a0a92c1e8508f471a0da405fdf4fb1",
        "changed_paths": [".github/workflows/autonomy-evidence.yml"],
        "head_sha": "1" * 40,
        "objective": "pull-request-264",
        "ref": "refs/pull/264/merge",
        "repository": "adrimg3196/lucidfence",
        "risk": "high",
        "run_attempt": 1,
        "run_id": "32590000000",
        "workflow": "autonomy-evidence",
        "workflow_ref": "adrimg3196/lucidfence/.github/workflows/autonomy-evidence.yml@refs/pull/264/merge",
    }


CONVENTIONAL_CHECK_NAMES = (
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


def _conventional_ci_snapshot() -> dict[str, object]:
    run_id = 32589999990
    run_attempt = 1
    suite_id = 77112233
    jobs = [
        {
            "conclusion": "success",
            "head_sha": _context()["head_sha"],
            "id": 88000000 + index,
            "name": name,
            "run_attempt": run_attempt,
            "run_id": run_id,
            "status": "completed",
        }
        for index, name in enumerate(CONVENTIONAL_CHECK_NAMES, start=1)
    ]
    checks = [
        {
            "check_suite_id": suite_id,
            "conclusion": "success",
            "head_sha": _context()["head_sha"],
            "id": 99000000 + index,
            "name": name,
            "status": "completed",
        }
        for index, name in enumerate(CONVENTIONAL_CHECK_NAMES, start=1)
    ]
    return {
        "checks": {"items": checks, "total_count": len(checks)},
        "control_files": [
            {
                "base": {
                    "bytes": 4821,
                    "commit_sha": _context()["base_sha"],
                    "sha256": "a" * 64,
                },
                "head": {
                    "bytes": 4821,
                    "commit_sha": _context()["head_sha"],
                    "sha256": "a" * 64,
                },
                "path": ".github/workflows/autonomy-evidence.yml",
            },
            {
                "base": {
                    "bytes": 5912,
                    "commit_sha": _context()["base_sha"],
                    "sha256": "b" * 64,
                },
                "head": {
                    "bytes": 5912,
                    "commit_sha": _context()["head_sha"],
                    "sha256": "b" * 64,
                },
                "path": ".github/workflows/ci.yml",
            },
        ],
        "jobs": {"items": jobs, "total_count": len(jobs)},
        "repository": "adrimg3196/lucidfence",
        "run": {
            "check_suite_id": suite_id,
            "conclusion": "success",
            "event": "pull_request",
            "head_sha": _context()["head_sha"],
            "id": run_id,
            "name": "CI",
            "path": ".github/workflows/ci.yml",
            "pull_requests": [
                {
                    "base_sha": _context()["base_sha"],
                    "head_sha": _context()["head_sha"],
                    "number": 264,
                }
            ],
            "run_attempt": run_attempt,
            "status": "completed",
        },
        "schema": "lucidfence-github-ci-snapshot/v1",
        "source": "github-rest-api/2022-11-28",
    }


def _trusted_job_listing(kind: str) -> dict[str, object]:
    return {
        "jobs": [
            {
                "conclusion": "success",
                "head_sha": "3" * 40,
                "id": 99112233,
                "name": f"trusted-evidence-{kind}",
                "run_id": 88776655,
                "status": "completed",
                "steps": [
                    {
                        "conclusion": "success",
                        "name": "Execute one fixed check and discard raw output",
                        "status": "completed",
                    }
                ],
            }
        ],
        "total_count": 1,
    }


def _overlap_env(tmp: str, *, body: str = "Closes #234") -> dict[str, str]:
    event = Path(tmp) / "event.json"
    event.write_text(
        json.dumps(
            {
                "pull_request": {
                    "body": body,
                    "head": {"sha": "1" * 40},
                    "number": 264,
                    "title": "Bootstrap autonomy B Agency Agents evidence control plane",
                }
            }
        ),
        encoding="utf-8",
    )
    return {
        "GH_TOKEN": "redacted-test-credential",
        "GITHUB_API_URL": "https://api.github.test",
        "GITHUB_EVENT_PATH": str(event),
    }


def _workflow_run_env(tmp: str, *, conclusion: str = "success") -> dict[str, str]:
    event = Path(tmp) / "workflow-run-event.json"
    event.write_text(
        json.dumps(
            {
                "workflow_run": {
                    "conclusion": conclusion,
                    "event": "pull_request",
                    "head_sha": _context()["head_sha"],
                    "head_repository": {"full_name": "adrimg3196/lucidfence"},
                    "id": 32590000000,
                    "name": "autonomy-evidence",
                    "path": ".github/workflows/autonomy-evidence.yml",
                    "pull_requests": [
                        {
                            "base": {"sha": _context()["base_sha"]},
                            "head": {"sha": _context()["head_sha"]},
                            "number": 264,
                        }
                    ],
                    "run_attempt": 1,
                }
            }
        ),
        encoding="utf-8",
    )
    return {
        "GITHUB_API_URL": "https://api.github.test",
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_REPOSITORY": "adrimg3196/lucidfence",
        "GITHUB_TOKEN": "redacted-test-credential",
    }


def test_context_is_derived_only_from_github_environment_and_event():
    with tempfile.TemporaryDirectory(prefix="autonomy-event-") as tmp:
        event = Path(tmp) / "event.json"
        event.write_text(json.dumps({"pull_request": {"number": 264}}), encoding="utf-8")
        env = {
            "GITHUB_EVENT_PATH": str(event),
            "GITHUB_REF": "refs/pull/264/merge",
            "GITHUB_REPOSITORY": "adrimg3196/lucidfence",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_RUN_ID": "32590000000",
            "GITHUB_WORKFLOW": "autonomy-evidence",
            "GITHUB_WORKFLOW_REF": "adrimg3196/lucidfence/.github/workflows/autonomy-evidence.yml@refs/pull/264/merge",
            "LF_BASE_SHA": "539027a7b5a0a92c1e8508f471a0da405fdf4fb1",
            "LF_HEAD_SHA": "1" * 40,
        }
        context = producer.context_from_environment(
            env, changed_paths=[".github/workflows/autonomy-evidence.yml"]
        )
        assert context == _context()


def test_trusted_workflow_run_context_reloads_live_pr_identity_and_files():
    with tempfile.TemporaryDirectory(prefix="autonomy-workflow-run-") as tmp:
        env = _workflow_run_env(tmp)
        original = producer._api_json

        def fake_api(url, _token):
            if url.endswith("/pulls/264"):
                return {
                    "base": {"sha": _context()["base_sha"]},
                    "head": {"sha": _context()["head_sha"]},
                }
            if "/pulls/264/files?" in url:
                return [{"filename": ".github/workflows/autonomy-evidence.yml"}]
            raise AssertionError(url)

        producer._api_json = fake_api
        try:
            context = producer.workflow_run_context_from_environment(env)
        finally:
            producer._api_json = original

    assert context == _context()


def test_trusted_workflow_run_context_fails_closed_for_unsuccessful_producer():
    with tempfile.TemporaryDirectory(prefix="autonomy-workflow-run-fail-") as tmp:
        env = _workflow_run_env(tmp, conclusion="failure")
        try:
            producer.workflow_run_context_from_environment(env)
        except ValueError as exc:
            assert "successful canonical" in str(exc)
        else:
            raise AssertionError("failed producer run must be rejected before API access")


def test_trusted_workflow_run_context_rejects_pr_head_race():
    with tempfile.TemporaryDirectory(prefix="autonomy-workflow-run-race-") as tmp:
        env = _workflow_run_env(tmp)
        original = producer._api_json

        def fake_api(url, _token):
            if url.endswith("/pulls/264"):
                return {
                    "base": {"sha": _context()["base_sha"]},
                    "head": {"sha": "2" * 40},
                }
            raise AssertionError(url)

        producer._api_json = fake_api
        try:
            try:
                producer.workflow_run_context_from_environment(env)
            except ValueError as exc:
                assert "no longer matches" in str(exc)
            else:
                raise AssertionError("a successful run for commit A must never attest commit B")
        finally:
            producer._api_json = original


def test_trusted_signer_binds_source_commit_and_workflow_file_digest():
    env = {
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "2",
        "GITHUB_RUN_ID": "32590000001",
        "GITHUB_SHA": "2" * 40,
        "GITHUB_WORKFLOW": "autonomy-attest",
        "GITHUB_WORKFLOW_REF": (
            "adrimg3196/lucidfence/.github/workflows/autonomy-attest.yml@refs/heads/main"
        ),
        "GITHUB_WORKFLOW_SHA": "3" * 40,
    }
    assert producer.trusted_signer_context(env) == {
        "ref": "refs/heads/main",
        "run_attempt": 2,
        "run_id": "32590000001",
        "source_digest": "2" * 40,
        "workflow_digest": "3" * 40,
        "workflow_ref": (
            "adrimg3196/lucidfence/.github/workflows/autonomy-attest.yml@refs/heads/main"
        ),
    }

    env["GITHUB_WORKFLOW_SHA"] = ""
    try:
        producer.trusted_signer_context(env)
    except ValueError as exc:
        assert "workflow digest" in str(exc)
    else:
        raise AssertionError("missing workflow digest must be rejected")


def test_conventional_ci_snapshot_emits_a_canonical_context_bound_receipt():
    with tempfile.TemporaryDirectory(prefix="autonomy-conventional-ci-") as tmp:
        root = Path(tmp)
        snapshot_path = root / "ci-snapshot.json"
        receipt_path = root / "ci-receipt.json"
        snapshot_path.write_bytes(
            producer.canonical_document(_conventional_ci_snapshot())
        )

        original_run = producer.subprocess.run
        producer.subprocess.run = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("the trusted CI signer must not execute candidate code")
        )
        try:
            receipt = producer.emit_conventional_ci_receipt(
                snapshot_path,
                receipt_path,
                _context(),
                trusted_run_id="88776655",
                trusted_run_attempt=2,
                trusted_source_sha="3" * 40,
            )
        finally:
            producer.subprocess.run = original_run

        assert receipt_path.read_bytes() == producer.canonical_document(receipt)
        assert receipt["schema"] == "lucidfence-conventional-ci-receipt/v1"
        assert receipt["context"] == {
            "base_sha": _context()["base_sha"],
            "head_sha": _context()["head_sha"],
            "request_run_attempt": 1,
            "request_run_id": _context()["run_id"],
            "trusted_run_attempt": 2,
            "trusted_run_id": "88776655",
            "trusted_source_sha": "3" * 40,
        }
        assert receipt["ci"] == {
            "check_suite_id": 77112233,
            "control_files_sha256": hashlib.sha256(
                producer.canonical_bytes(_conventional_ci_snapshot()["control_files"])
            ).hexdigest(),
            "inventory_sha256": hashlib.sha256(
                producer.canonical_bytes(
                    {
                        "checks": _conventional_ci_snapshot()["checks"],
                        "jobs": _conventional_ci_snapshot()["jobs"],
                    }
                )
            ).hexdigest(),
            "run_attempt": 1,
            "run_id": "32589999990",
            "workflow": "CI",
            "workflow_path": ".github/workflows/ci.yml",
        }
        assert receipt["output"] == {
            "bytes": len(snapshot_path.read_bytes()),
            "sha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
        }
        assert tuple(item["name"] for item in receipt["checks"]) == CONVENTIONAL_CHECK_NAMES
        assert receipt["receipt_digest"]["value"] != "0" * 64


def test_conventional_ci_snapshot_rejects_context_drift_and_nonexact_inventory():
    rejection_cases = {
        "wrong repository": lambda value: value.__setitem__("repository", "fork/lucidfence"),
        "wrong workflow": lambda value: value["run"].__setitem__("path", ".github/workflows/fake.yml"),
        "wrong event": lambda value: value["run"].__setitem__("event", "workflow_dispatch"),
        "failed run": lambda value: value["run"].__setitem__("conclusion", "failure"),
        "wrong head": lambda value: value["run"].__setitem__("head_sha", "2" * 40),
        "wrong base": lambda value: value["run"]["pull_requests"][0].__setitem__(
            "base_sha", "2" * 40
        ),
        "wrong PR": lambda value: value["run"]["pull_requests"][0].__setitem__("number", 265),
        "missing job": lambda value: (
            value["jobs"]["items"].pop(),
            value["jobs"].__setitem__("total_count", 8),
        ),
        "extra job": lambda value: (
            value["jobs"]["items"].append(
                {
                    **value["jobs"]["items"][0],
                    "id": 88111111,
                    "name": "Unreviewed conventional check",
                }
            ),
            value["jobs"].__setitem__("total_count", 10),
        ),
        "failed job": lambda value: value["jobs"]["items"][0].__setitem__(
            "conclusion", "failure"
        ),
        "wrong job run": lambda value: value["jobs"]["items"][0].__setitem__("run_id", 7),
        "missing check": lambda value: (
            value["checks"]["items"].pop(),
            value["checks"].__setitem__("total_count", 8),
        ),
        "duplicate check": lambda value: (
            value["checks"]["items"].append(dict(value["checks"]["items"][0])),
            value["checks"].__setitem__("total_count", 10),
        ),
        "failed check": lambda value: value["checks"]["items"][0].__setitem__(
            "status", "in_progress"
        ),
        "wrong check suite": lambda value: value["checks"]["items"][0].__setitem__(
            "check_suite_id", 1
        ),
        "candidate evidence workflow differs": lambda value: value["control_files"][0][
            "head"
        ].__setitem__("sha256", "c" * 64),
        "candidate CI workflow differs": lambda value: value["control_files"][1][
            "head"
        ].__setitem__("bytes", 5913),
        "missing protected workflow": lambda value: value["control_files"].pop(),
        "wrong protected workflow base ref": lambda value: value["control_files"][0][
            "base"
        ].__setitem__("commit_sha", "d" * 40),
    }
    with tempfile.TemporaryDirectory(prefix="autonomy-conventional-ci-reject-") as tmp:
        root = Path(tmp)
        snapshot_path = root / "ci-snapshot.json"
        receipt_path = root / "ci-receipt.json"
        for label, mutate in rejection_cases.items():
            candidate = json.loads(json.dumps(_conventional_ci_snapshot()))
            mutate(candidate)
            snapshot_path.write_bytes(producer.canonical_document(candidate))
            receipt_path.unlink(missing_ok=True)
            try:
                producer.emit_conventional_ci_receipt(
                    snapshot_path,
                    receipt_path,
                    _context(),
                    trusted_run_id="88776655",
                    trusted_run_attempt=2,
                    trusted_source_sha="3" * 40,
                )
            except ValueError:
                pass
            else:
                raise AssertionError(f"{label} must fail closed")
            assert not receipt_path.exists(), label

        snapshot_path.write_text(
            json.dumps(_conventional_ci_snapshot(), indent=2), encoding="utf-8"
        )
        try:
            producer.emit_conventional_ci_receipt(
                snapshot_path,
                receipt_path,
                _context(),
                trusted_run_id="88776655",
                trusted_run_attempt=2,
                trusted_source_sha="3" * 40,
            )
        except ValueError as exc:
            assert "canonical" in str(exc).lower()
        else:
            raise AssertionError("a non-canonical API snapshot must fail closed")


def test_ci_job_artifact_requires_and_validates_the_conventional_ci_receipt():
    with tempfile.TemporaryDirectory(prefix="autonomy-ci-job-receipt-") as tmp:
        root = Path(tmp)
        snapshot_path = root / "ci-snapshot.json"
        receipt_path = root / "ci-receipt.json"
        jobs_path = root / "jobs.json"
        log_path = root / "ci.job.log"
        evidence_path = root / "ci.json"
        snapshot_path.write_bytes(producer.canonical_document(_conventional_ci_snapshot()))
        jobs_path.write_bytes(producer.canonical_document(_trusted_job_listing("ci")))
        log_path.write_bytes(b"trusted receipt assembly completed\n")
        producer.emit_conventional_ci_receipt(
            snapshot_path,
            receipt_path,
            _context(),
            trusted_run_id="88776655",
            trusted_run_attempt=2,
            trusted_source_sha="3" * 40,
        )

        document = producer.emit_job_artifact(
            "ci",
            jobs_path,
            log_path,
            evidence_path,
            _context(),
            ROOT / "data" / "agency_catalog.json",
            trusted_run_id="88776655",
            trusted_run_attempt=2,
            trusted_source_sha="3" * 40,
            conventional_ci_receipt_path=receipt_path,
        )
        assert document["result"]["output_sha256"] == hashlib.sha256(
            snapshot_path.read_bytes()
        ).hexdigest()

        for kwargs in ({}, {"supervisor_receipt_path": receipt_path}):
            try:
                producer.emit_job_artifact(
                    "ci",
                    jobs_path,
                    log_path,
                    evidence_path,
                    _context(),
                    ROOT / "data" / "agency_catalog.json",
                    trusted_run_id="88776655",
                    trusted_run_attempt=2,
                    trusted_source_sha="3" * 40,
                    **kwargs,
                )
            except ValueError:
                pass
            else:
                raise AssertionError("CI must never fall back to candidate execution evidence")

        tampered = json.loads(receipt_path.read_bytes())
        tampered["context"]["request_run_attempt"] = 7
        tampered["receipt_digest"]["value"] = "0" * 64
        tampered["receipt_digest"]["value"] = hashlib.sha256(
            producer.canonical_bytes(tampered)
        ).hexdigest()
        receipt_path.write_bytes(producer.canonical_document(tampered))
        try:
            producer.emit_job_artifact(
                "ci",
                jobs_path,
                log_path,
                evidence_path,
                _context(),
                ROOT / "data" / "agency_catalog.json",
                trusted_run_id="88776655",
                trusted_run_attempt=2,
                trusted_source_sha="3" * 40,
                conventional_ci_receipt_path=receipt_path,
            )
        except ValueError as exc:
            assert "context" in str(exc).lower()
        else:
            raise AssertionError("a re-sealed receipt for another request run must fail closed")


def test_trusted_derivation_context_reloads_api_inventory_and_binds_fixed_outputs():
    env = {
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": "adrimg3196/lucidfence",
        "GITHUB_TOKEN": "redacted-test-credential",
        "GITHUB_WORKFLOW": "autonomy-attest",
        "LF_BASE_SHA": _context()["base_sha"],
        "LF_HEAD_SHA": _context()["head_sha"],
        "LF_PR_NUMBER": "264",
        "LF_REQUEST_RUN_ATTEMPT": "1",
        "LF_REQUEST_RUN_ID": "32590000000",
        "LF_TRUSTED_CONTEXT": "1",
    }
    original = producer.changed_paths
    original_api = producer._api_json
    producer.changed_paths = lambda _root, _base, _head: [
        ".github/workflows/autonomy-evidence.yml"
    ]

    def fake_api(url, _token):
        if url.endswith("/pulls/264"):
            return {
                "base": {"sha": _context()["base_sha"]},
                "head": {"sha": _context()["head_sha"]},
                "state": "open",
            }
        if "/pulls/264/files?" in url:
            return [{"filename": ".github/workflows/autonomy-evidence.yml"}]
        raise AssertionError(url)

    producer._api_json = fake_api
    try:
        context = producer.evidence_context(ROOT, env)
    finally:
        producer.changed_paths = original
        producer._api_json = original_api
    assert context == _context()


def test_fresh_trusted_runner_derives_receipt_from_github_job_and_logs():
    with tempfile.TemporaryDirectory(prefix="autonomy-job-receipt-") as tmp:
        root = Path(tmp)
        jobs = root / "jobs.json"
        log = root / "license.job.log"
        preflight_log = root / "license.log"
        preflight = root / "license.preflight.json"
        output = root / "license.json"
        jobs.write_bytes(
            producer.canonical_document(
                {
                    "jobs": [
                        {
                            "conclusion": "success",
                            "head_sha": "3" * 40,
                            "id": 99112233,
                            "name": "trusted-evidence-license",
                            "run_id": 88776655,
                            "status": "completed",
                            "steps": [
                                {
                                    "conclusion": "success",
                                    "name": "Execute one fixed check and discard raw output",
                                    "status": "completed",
                                }
                            ],
                        }
                    ],
                    "total_count": 1,
                }
            )
        )
        log.write_bytes(b"trusted GitHub job log without private material\n")
        preflight_log.write_bytes(log.read_bytes())
        producer.emit_artifact(
            "license",
            preflight_log,
            preflight,
            _context(),
            ROOT / "data" / "agency_catalog.json",
        )
        document = producer.emit_job_artifact(
            "license",
            jobs,
            log,
            output,
            _context(),
            ROOT / "data" / "agency_catalog.json",
            trusted_run_id="88776655",
            trusted_run_attempt=1,
            trusted_source_sha="3" * 40,
            preflight_receipt_path=preflight,
        )
        assert document["result"]["output_sha256"] == hashlib.sha256(log.read_bytes()).hexdigest()
        assert set(document["result"]) == {
            "check", "command_id", "exit_code", "output_bytes", "output_sha256", "status"
        }

        job_document = json.loads(jobs.read_bytes())
        job_document["jobs"][0]["conclusion"] = "failure"
        jobs.write_bytes(producer.canonical_document(job_document))
        try:
            producer.emit_job_artifact(
                "license",
                jobs,
                log,
                output,
                _context(),
                ROOT / "data" / "agency_catalog.json",
                trusted_run_id="88776655",
                trusted_run_attempt=1,
                trusted_source_sha="3" * 40,
                preflight_receipt_path=preflight,
            )
        except ValueError as exc:
            assert "did not complete successfully" in str(exc)
        else:
            raise AssertionError("failed GitHub job must never produce a passing receipt")

        rejection_cases = {
            "incomplete listing": lambda value: value.__setitem__("total_count", 2),
            "duplicate job": lambda value: (
                value["jobs"].append(json.loads(json.dumps(value["jobs"][0]))),
                value.__setitem__("total_count", 2),
            ),
            "wrong run": lambda value: value["jobs"][0].__setitem__("run_id", 1),
            "wrong trusted head": lambda value: value["jobs"][0].__setitem__(
                "head_sha", "4" * 40
            ),
            "missing fixed step": lambda value: value["jobs"][0].__setitem__("steps", []),
            "duplicate fixed step": lambda value: value["jobs"][0].__setitem__(
                "steps", value["jobs"][0]["steps"] * 2
            ),
            "incomplete fixed step": lambda value: value["jobs"][0]["steps"][0].__setitem__(
                "status", "in_progress"
            ),
        }
        clean_document = json.loads(
            producer.canonical_document(
                {
                    "jobs": [
                        {
                            "conclusion": "success",
                            "head_sha": "3" * 40,
                            "id": 99112233,
                            "name": "trusted-evidence-license",
                            "run_id": 88776655,
                            "status": "completed",
                            "steps": [
                                {
                                    "conclusion": "success",
                                    "name": "Execute one fixed check and discard raw output",
                                    "status": "completed",
                                }
                            ],
                        }
                    ],
                    "total_count": 1,
                }
            )
        )
        for label, mutate in rejection_cases.items():
            candidate = json.loads(json.dumps(clean_document))
            mutate(candidate)
            jobs.write_bytes(producer.canonical_document(candidate))
            try:
                producer.emit_job_artifact(
                    "license",
                    jobs,
                    log,
                    output,
                    _context(),
                    ROOT / "data" / "agency_catalog.json",
                    trusted_run_id="88776655",
                    trusted_run_attempt=1,
                    trusted_source_sha="3" * 40,
                    preflight_receipt_path=preflight,
                )
            except ValueError:
                pass
            else:
                raise AssertionError(f"{label} must never produce a passing receipt")

        jobs.write_bytes(producer.canonical_document(clean_document))
        log.write_bytes(b"runner accidentally logged ghs_" + b"A" * 40 + b"\n")
        try:
            producer.emit_job_artifact(
                "license",
                jobs,
                log,
                output,
                _context(),
                ROOT / "data" / "agency_catalog.json",
                trusted_run_id="88776655",
                trusted_run_attempt=1,
                trusted_source_sha="3" * 40,
                preflight_receipt_path=preflight,
            )
        except ValueError as exc:
            assert "sensitive" in str(exc)
        else:
            raise AssertionError("a GitHub installation token in a job log must fail closed")


def test_producer_cli_starts_from_repository_root():
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    process = subprocess.run(
        [sys.executable, "scripts/emit_autonomy_evidence.py", "--help"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert "emit-ci-receipt" in process.stdout


def test_control_plane_paths_are_always_high_risk():
    assert producer.classify_risk([".github/CODEOWNERS"]) == "high"
    assert producer.classify_risk([".gitleaks.toml"]) == "high"
    assert producer.classify_risk(["scripts/verify_autonomy_evidence.py"]) == "high"
    assert producer.classify_risk(["config/night-shift-manifest.schema.json"]) == "high"
    assert producer.classify_risk(["requirements.lock"]) == "high"
    assert producer.classify_risk(["pyproject.toml"]) == "high"
    assert producer.classify_risk(["sitecustomize.py"]) == "high"
    assert producer.classify_risk(["docs/README.md"]) == "normal"


def test_candidate_requirement_lock_is_hash_pinned_and_cannot_redirect_installation():
    producer.validate_runtime_requirement_lock(ROOT / "requirements.lock")
    producer.validate_requirement_lock(ROOT / "config" / "autonomy-tools.lock")
    unsafe = (
        "dependency==1.0 \\\n"
        "    --hash=sha256:" + "a" * 64 + "\n"
        "--extra-index-url https://attacker.invalid/simple\n"
    )
    with tempfile.TemporaryDirectory(prefix="autonomy-lock-") as tmp:
        lock = Path(tmp) / "requirements.lock"
        lock.write_text(unsafe, encoding="utf-8")
        try:
            producer.validate_requirement_lock(lock)
        except ValueError as exc:
            assert "lock" in str(exc).lower()
        else:
            raise AssertionError("installer redirection in requirements.lock must fail closed")


def test_runtime_lock_rejects_an_unapproved_package_even_when_hash_pinned():
    with tempfile.TemporaryDirectory(prefix="autonomy-lock-allowlist-") as tmp:
        lock = Path(tmp) / "requirements.lock"
        lock.write_text(
            "unapproved-runtime-hook==1.0 --hash=sha256:" + "a" * 64 + "\n",
            encoding="utf-8",
        )
        try:
            producer.validate_runtime_requirement_lock(lock)
        except ValueError as exc:
            assert "allowlist" in str(exc)
        else:
            raise AssertionError("a candidate cannot expand the runtime dependency trust root")


def test_wheel_inspector_rejects_pth_startup_code_before_installation():
    with tempfile.TemporaryDirectory(prefix="autonomy-wheel-inspect-") as tmp:
        root = Path(tmp)
        wheelhouse = root / "wheels"
        wheelhouse.mkdir()
        wheel = wheelhouse / "requests-1.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("startup.pth", "import os; os._exit(0)\n")
            archive.writestr("requests/__init__.py", "")
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        lock = root / "requirements.lock"
        lock.write_text(
            f"requests==1.0 --hash=sha256:{digest}\n",
            encoding="utf-8",
        )
        try:
            producer.inspect_wheelhouse(
                lock,
                wheelhouse,
                allowed_packages=frozenset({"requests"}),
            )
        except ValueError as exc:
            assert ".pth" in str(exc)
        else:
            raise AssertionError("wheel startup hooks must fail before pip install")


def _write_test_wheel(path: Path, *, member: str = "requests/__init__.py") -> str:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member, "")
        archive.writestr(
            "requests-1.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: requests\nVersion: 1.0\n",
        )
        archive.writestr(
            "requests-1.0.dist-info/WHEEL",
            "Wheel-Version: 1.0\nGenerator: autonomy-test\nRoot-Is-Purelib: true\n"
            "Tag: py3-none-any\n",
        )
        archive.writestr("requests-1.0.dist-info/RECORD", "")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wheel_inspector_accepts_one_exact_safe_wheel_per_allowed_requirement():
    with tempfile.TemporaryDirectory(prefix="autonomy-wheel-safe-") as tmp:
        root = Path(tmp)
        wheelhouse = root / "wheels"
        wheelhouse.mkdir()
        wheel = wheelhouse / "requests-1.0-py3-none-any.whl"
        digest = _write_test_wheel(wheel)
        lock = root / "requirements.lock"
        lock.write_text(
            f"requests==1.0 --hash=sha256:{digest}\n",
            encoding="utf-8",
        )
        inspected = producer.inspect_wheelhouse(
            lock,
            wheelhouse,
            allowed_packages=frozenset({"requests"}),
        )
    assert inspected == {"requests": digest}


def test_wheel_inspector_rejects_archive_path_traversal():
    with tempfile.TemporaryDirectory(prefix="autonomy-wheel-traversal-") as tmp:
        root = Path(tmp)
        wheelhouse = root / "wheels"
        wheelhouse.mkdir()
        wheel = wheelhouse / "requests-1.0-py3-none-any.whl"
        digest = _write_test_wheel(wheel, member="../sitecustomize.py")
        lock = root / "requirements.lock"
        lock.write_text(
            f"requests==1.0 --hash=sha256:{digest}\n",
            encoding="utf-8",
        )
        try:
            producer.inspect_wheelhouse(
                lock,
                wheelhouse,
                allowed_packages=frozenset({"requests"}),
            )
        except ValueError as exc:
            assert "path" in str(exc).lower()
        else:
            raise AssertionError("wheel archive traversal must fail before installation")


def _trusted_supervisor_context() -> dict[str, object]:
    return {
        "base_sha": _context()["base_sha"],
        "head_sha": _context()["head_sha"],
        "request_run_attempt": 1,
        "request_run_id": _context()["run_id"],
        "trusted_source_sha": _context()["base_sha"],
    }


def _prepare_http_supervisor_fixture(root: Path) -> Path:
    root.chmod(0o755)
    scripts = root / "scripts"
    scripts.mkdir(mode=0o755)
    shutil.copy2(ROOT / "scripts" / "supervise_autonomy_check.py", scripts)
    server = root / "saas_server.py"
    server.write_text(
        "import json\n"
        "import os\n"
        "import time\n"
        "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
        "\n"
        "class Handler(BaseHTTPRequestHandler):\n"
        "    def do_GET(self):\n"
        "        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())\n"
        "        if self.path == '/api/health':\n"
        "            payload = {'status': 'ok', 'service': 'lucidfence', "
        "'desktop_nonce': '', 'ts': now}\n"
        "        elif self.path == '/api/readyz':\n"
        "            payload = {'ready': True, 'service': 'lucidfence', "
        "'tenants_loaded': 0, 'cluster_mode': 'single', 'leader': True, 'ts': now}\n"
        "        else:\n"
        "            self.send_error(404)\n"
        "            return\n"
        "        raw = json.dumps(payload, sort_keys=True).encode('utf-8')\n"
        "        self.send_response(200)\n"
        "        self.send_header('Content-Type', 'application/json; charset=utf-8')\n"
        "        self.send_header('Content-Length', str(len(raw)))\n"
        "        self.end_headers()\n"
        "        self.wfile.write(raw)\n"
        "\n"
        "    def log_message(self, *_args):\n"
        "        pass\n"
        "\n"
        "ThreadingHTTPServer(('127.0.0.1', int(os.environ['LUCIDFENCE_PORT'])), "
        "Handler).serve_forever()\n",
        encoding="utf-8",
    )
    return server


def _run_minimal_http_supervisor(root: Path, receipt_path: Path) -> dict[str, object]:
    _prepare_http_supervisor_fixture(root)
    sandbox = root / "sandbox"
    return _run_test_supervisor(root, receipt_path, sandbox)


def _run_test_supervisor(
    root: Path,
    receipt_path: Path,
    sandbox: Path,
) -> dict[str, object]:
    """Run HTTP behavior tests in containers that cannot map the nobody UID."""
    original_identity = supervisor._child_identity
    supervisor._child_identity = lambda _user: (None, None)
    try:
        return supervisor.run_supervised_check(
            "reality",
            root,
            Path(sys.executable),
            receipt_path,
            timeout_seconds=30,
            untrusted_user="nobody",
            sandbox_dir=sandbox,
            context=_trusted_supervisor_context(),
        )
    finally:
        supervisor._child_identity = original_identity


def test_trusted_supervisor_requires_a_root_parent_and_unprivileged_child():
    try:
        supervisor._child_identity(None)
    except RuntimeError as exc:
        assert "unprivileged" in str(exc).lower()
    else:
        raise AssertionError("the supervisor must never run candidate code as itself")

    if os.geteuid() == 0:
        uid, gid = supervisor._child_identity("nobody")
        assert uid not in (None, 0)
        assert gid not in (None, 0)
    else:
        try:
            supervisor._child_identity("nobody")
        except RuntimeError as exc:
            assert "root" in str(exc).lower()
        else:
            raise AssertionError("privilege dropping needs a real root supervisor")


def test_trusted_supervisor_rejects_stdout_green_and_zero_without_http_server():
    with tempfile.TemporaryDirectory(prefix="autonomy-supervisor-") as tmp:
        root = Path(tmp)
        root.chmod(0o755)
        (root / "saas_server.py").write_text(
            "import json\n"
            "import os\n"
            "import sys\n"
            "from pathlib import Path\n"
            "Path(__file__).with_name('candidate-view.json').write_text(\n"
            "    json.dumps({'argv': sys.argv, 'environment': dict(os.environ)}))\n"
            "print('GREEN: all checks passed')\n"
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )
        sandbox = root / "sandbox"
        output = root / "receipt.json"
        try:
            _run_test_supervisor(root, output, sandbox)
        except RuntimeError as exc:
            assert "http" in str(exc).lower()
        else:
            raise AssertionError("stdout and exit zero must not create trusted HTTP evidence")
        candidate_view = json.loads(
            (root / "candidate-view.json").read_text(encoding="utf-8")
        )
        assert candidate_view["argv"] == [str(root / "saas_server.py")]
        assert not any(
            key.startswith("GITHUB") or "TOKEN" in key or "SECRET" in key
            for key in candidate_view["environment"]
        )
        exposed = json.dumps(candidate_view, sort_keys=True)
        assert str(output) not in exposed
        assert _context()["base_sha"] not in exposed
        assert _context()["head_sha"] not in exposed
        assert "supervise_autonomy_check.py" not in exposed
        assert not sandbox.exists()
        assert not output.exists()


def test_trusted_supervisor_accepts_minimal_valid_http_server():
    with tempfile.TemporaryDirectory(prefix="autonomy-supervisor-http-") as tmp:
        root = Path(tmp)
        receipt_path = root / "receipt.json"
        receipt = _run_minimal_http_supervisor(root, receipt_path)

        output = producer._validate_supervisor_receipt(
            receipt_path,
            "reality",
            _context(),
            root,
            trusted_run_id="88776655",
            trusted_run_attempt=2,
            trusted_source_sha=_context()["base_sha"],
        )

        assert receipt["status"] == "pass"
        assert receipt["result"] == {"passed": 7, "total": 7}
        assert set(receipt) == {
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
        receipt_text = receipt_path.read_text(encoding="utf-8")
        assert "desktop_nonce" not in receipt_text
        assert "tenants_loaded" not in receipt_text
        assert "set-cookie" not in receipt_text.lower()
        assert "bearer" not in receipt_text.lower()
        assert output == receipt["observation"]


def test_trusted_supervisor_receipt_and_context_tampering_fail_closed():
    with tempfile.TemporaryDirectory(prefix="autonomy-supervisor-receipt-") as tmp:
        root = Path(tmp)
        receipt_path = root / "receipt.json"
        _run_minimal_http_supervisor(root, receipt_path)
        original = receipt_path.read_bytes()

        mismatched_context = _context()
        mismatched_context["head_sha"] = "4" * 40
        try:
            producer._validate_supervisor_receipt(
                receipt_path,
                "reality",
                mismatched_context,
                root,
                trusted_run_id="88776655",
                trusted_run_attempt=2,
                trusted_source_sha=_context()["base_sha"],
            )
        except ValueError as exc:
            assert "context" in str(exc).lower()
        else:
            raise AssertionError("a receipt must not validate for a different context")

        tampered = json.loads(original)
        tampered["context"]["head_sha"] = "4" * 40
        receipt_path.write_bytes(producer.canonical_document(tampered))
        try:
            producer._validate_supervisor_receipt(
                receipt_path,
                "reality",
                _context(),
                root,
                trusted_run_id="88776655",
                trusted_run_attempt=2,
                trusted_source_sha=_context()["base_sha"],
            )
        except ValueError as exc:
            assert "digest" in str(exc).lower()
        else:
            raise AssertionError("a modified receipt must fail its self-digest")


def test_evidence_uses_log_bytes_but_never_copies_log_text():
    with tempfile.TemporaryDirectory(prefix="autonomy-emit-") as tmp:
        log = Path(tmp) / "ci.log"
        out = Path(tmp) / "ci.json"
        log.write_text("real command output without secrets\n", encoding="utf-8")
        producer.emit_artifact(
            "ci",
            log,
            out,
            _context(),
            ROOT / "data" / "agency_catalog.json",
        )
        document = json.loads(out.read_bytes())
        assert document["result"]["status"] == "pass"
        assert document["result"]["output_bytes"] == len(log.read_bytes())
        assert document["result"]["output_sha256"] == hashlib.sha256(log.read_bytes()).hexdigest()
        assert "real command output" not in out.read_text(encoding="utf-8")
        assert document["producer"]["path"] == "engineering/engineering-api-platform-engineer.md"


def test_secret_scan_fails_without_copying_sensitive_bytes():
    private_marker = "TENANT_SECRET_TEST_VALUE"
    with tempfile.TemporaryDirectory(prefix="autonomy-secret-scan-") as tmp:
        root = Path(tmp)
        candidate = root / "candidate.txt"
        candidate.write_text(private_marker, encoding="utf-8")
        context = dict(_context())
        context["changed_paths"] = ["candidate.txt"]
        failed = producer.scan_changed_files_for_secrets(root, context)
        candidate.write_text("ordinary public fixture\n", encoding="utf-8")
        passed = producer.scan_changed_files_for_secrets(root, context)
    assert failed["status"] == "fail"
    assert private_marker not in json.dumps(failed)
    assert passed == {
        "bytes_scanned": len(b"ordinary public fixture\n"),
        "files_scanned": 1,
        "findings": [],
        "status": "pass",
    }


def test_secret_scan_covers_common_cloud_and_registry_credentials_without_leaking_them():
    markers = {
        "openai-project": b"sk" + b"-proj-" + b"A" * 48,
        "openai-legacy": b"sk" + b"-" + b"B" * 48,
        "stripe-live": b"sk" + b"_live_" + b"C" * 24,
        "stripe-restricted": b"rk" + b"_live_" + b"D" * 24,
        "slack": b"xox" + b"b-123456789012-" + b"E" * 32,
        "google": b"AI" + b"za" + b"F" * 35,
        "azure-storage": (
            b"DefaultEndpointsProtocol=https;"
            + b"AccountName=fixture;"
            + b"Account"
            + b"Key="
            + b"G" * 64
            + b";EndpointSuffix=core.windows.net"
        ),
        "azure-sas": (
            b"sv="
            + b"2024-11-04&ss=b&srt=sco&sp=r&se=2099-01-01T00%3A00%3A00Z"
            + b"&sig="
            + b"H" * 44
        ),
        "npm-access": b"npm" + b"_" + b"I" * 36,
        "npm-auth-config": (
            b"//registry.npmjs.org/:_"
            + b"authToken="
            + b"J" * 36
        ),
    }
    with tempfile.TemporaryDirectory(prefix="autonomy-secret-families-") as tmp:
        root = Path(tmp)
        candidate = root / "candidate.txt"
        for label, marker in markers.items():
            candidate.write_bytes(b"fixture=" + marker + b"\n")
            context = dict(_context())
            context["changed_paths"] = ["candidate.txt"]

            result = producer.scan_changed_files_for_secrets(root, context)

            assert result["status"] == "fail", label
            serialized = json.dumps(result).encode("utf-8")
            assert marker not in serialized, label


def test_overlap_rejects_open_pr_145_by_normalized_semantic_objective_without_body_leak():
    """Removing semantic comparison would accept the known overlapping PR #145."""
    private_marker = "PRIVATE_REVIEW_CONTEXT_MUST_NOT_APPEAR"
    pull_145 = {
        "body": (
            "Integración versionada del catálogo completo de Agency Agents. "
            "Empresa autónoma nocturna en modo B. Gates automáticos AppSec y "
            f"Reality Checker. {private_marker}"
        ),
        "head": {"sha": "2" * 40},
        "number": 145,
        "title": "docs: design autonomous LucidFence night shift",
    }

    with tempfile.TemporaryDirectory(prefix="autonomy-overlap-145-") as tmp:
        env = _overlap_env(
            tmp,
            body=(
                "Closes #234. Bootstrap autonomy B night shift with the pinned "
                "Agency Agents catalog and official autonomy evidence."
            ),
        )
        original = producer._api_json

        def fake_api(url, _token):
            if "/pulls?" in url:
                return [pull_145]
            if "/pulls/145/files?" in url:
                return []
            raise AssertionError(url)

        producer._api_json = fake_api
        try:
            result = producer.check_overlap(ROOT, _context(), env)
        finally:
            producer._api_json = original

    assert re.fullmatch(r"[0-9a-f]{64}", result.pop("snapshot_sha256"))
    assert result == {
        "conflicts": [
            {
                "paths": [],
                "pull_request": 145,
                "reasons": [
                    "semantic:agency-catalog",
                    "semantic:autonomy-b",
                    "semantic:night-shift",
                ],
            }
        ],
        "overlaps": [
            {
                "paths": [],
                "pull_request": 145,
                "reasons": [
                    "semantic:agency-catalog",
                    "semantic:autonomy-b",
                    "semantic:night-shift",
                ],
            }
        ],
        "status": "fail",
    }
    assert private_marker not in json.dumps(result)


def test_overlap_paginates_pr_files_and_rejects_path_found_after_first_page():
    """Dropping file pagination would miss an exact conflict after file 100."""
    pull = {
        "body": "Unrelated maintenance",
        "head": {"sha": "3" * 40},
        "number": 300,
        "title": "Maintenance",
    }
    first_page = [{"filename": f"docs/generated-{index:03d}.md"} for index in range(100)]

    with tempfile.TemporaryDirectory(prefix="autonomy-overlap-files-") as tmp:
        env = _overlap_env(tmp)
        original = producer._api_json

        def fake_api(url, _token):
            if "/pulls?" in url:
                return [pull]
            if "/pulls/300/files?" in url and "&page=1" in url:
                return first_page
            if "/pulls/300/files?" in url and "&page=2" in url:
                return [{"filename": ".github/workflows/autonomy-evidence.yml"}]
            raise AssertionError(url)

        producer._api_json = fake_api
        try:
            result = producer.check_overlap(ROOT, _context(), env)
        finally:
            producer._api_json = original

    assert result["status"] == "fail"
    assert result["overlaps"] == [
        {
            "paths": [".github/workflows/autonomy-evidence.yml"],
            "pull_request": 300,
            "reasons": ["path-overlap"],
        }
    ]


def test_overlap_paginates_open_prs_and_rejects_shared_issue_ownership():
    """Dropping PR pagination or ownership matching would accept a second owner of #234."""
    first_page = [
        {
            "body": "Unrelated",
            "head": {"sha": f"{1000 + index:040x}"},
            "number": 1000 + index,
            "title": "Maintenance",
        }
        for index in range(100)
    ]
    competing = {
        "body": "Resolves #234",
        "head": {"sha": "4" * 40},
        "number": 145,
        "title": "Alternative control plane",
    }

    with tempfile.TemporaryDirectory(prefix="autonomy-overlap-prs-") as tmp:
        env = _overlap_env(tmp, body="Closes #234")
        original = producer._api_json

        def fake_api(url, _token):
            if "/pulls?" in url and "&page=1" in url:
                return first_page
            if "/pulls?" in url and "&page=2" in url:
                return [competing]
            if "/files?" in url:
                return []
            raise AssertionError(url)

        producer._api_json = fake_api
        try:
            result = producer.check_overlap(ROOT, _context(), env)
        finally:
            producer._api_json = original

    assert result["status"] == "fail"
    assert result["overlaps"] == [
        {
            "paths": [],
            "pull_request": 145,
            "reasons": ["issue-ownership:234"],
        }
    ]


def test_overlap_path_inventory_includes_both_sides_of_a_rename():
    assert producer._pull_file_paths(
        [
            {
                "filename": "scripts/new-name.py",
                "previous_filename": "scripts/old-name.py",
                "status": "renamed",
            }
        ]
    ) == ["scripts/new-name.py", "scripts/old-name.py"]


def test_guard_invalidates_both_sides_of_live_overlap_and_stale_success():
    private_marker = "PRIVATE_BODY_MUST_NOT_LEAK"
    first = {
        "base": {"ref": "main"},
        "body": f"Closes #900. Autonomy B. {private_marker}",
        "head": {"repo": {"full_name": "adrimg3196/lucidfence"}, "sha": "6" * 40},
        "number": 401,
        "title": "Autonomy B maintenance",
    }
    second = {
        "base": {"ref": "main"},
        "body": "Resolves #900. Autonomy B.",
        "head": {"repo": {"full_name": "adrimg3196/lucidfence"}, "sha": "7" * 40},
        "number": 402,
        "title": "Competing autonomy B maintenance",
    }
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    original = producer._api_json

    def fake_api(url, _token):
        if "/pulls?" in url:
            return [first, second]
        if "/pulls/401/files?" in url or "/pulls/402/files?" in url:
            return [{"filename": "shared-control-file.json"}]
        if f"/commits/{'6' * 40}/statuses?" in url:
            return [
                {
                    "context": "autonomy-evidence",
                    "created_at": "2026-08-24T11:00:00Z",
                    "description": "Trusted evidence and attestation verified",
                    "id": 601,
                    "state": "success",
                    "target_url": "https://github.com/adrimg3196/lucidfence/actions/runs/601",
                }
            ]
        if f"/commits/{'7' * 40}/statuses?" in url:
            return [
                {
                    "context": "autonomy-evidence",
                    "created_at": "2026-08-18T11:00:00Z",
                    "description": "Trusted evidence and attestation verified",
                    "id": 701,
                    "state": "success",
                    "target_url": "https://github.com/adrimg3196/lucidfence/actions/runs/701",
                }
            ]
        raise AssertionError(url)

    producer._api_json = fake_api
    try:
        result = producer.guard_open_pull_requests(
            {"GH_TOKEN": "test-only", "GITHUB_API_URL": "https://api.github.test"},
            now=now,
        )
    finally:
        producer._api_json = original

    assert result["schema"] == "lucidfence-autonomy-guard/v1"
    assert result["status"] == "invalidate"
    assert result["invalidations"] == [
        {
            "head_sha": "6" * 40,
            "pr_number": 401,
            "reasons": ["issue-ownership:900", "path-overlap", "semantic:autonomy-b"],
        },
        {
            "head_sha": "7" * 40,
            "pr_number": 402,
            "reasons": [
                "evidence-expired",
                "issue-ownership:900",
                "path-overlap",
                "semantic:autonomy-b",
            ],
        },
    ]
    assert private_marker not in json.dumps(result)


def test_workflows_separate_unprivileged_evidence_from_trusted_official_attestation():
    tools_lock = (ROOT / "config" / "autonomy-tools.lock").read_text(
        encoding="utf-8"
    )
    ci_workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    docker_workflow = (ROOT / ".github" / "workflows" / "docker.yml").read_text(
        encoding="utf-8"
    )
    guard_workflow = (ROOT / ".github" / "workflows" / "autonomy-guard.yml").read_text(
        encoding="utf-8"
    )
    producer_workflow = (ROOT / ".github" / "workflows" / "autonomy-evidence.yml").read_text(
        encoding="utf-8"
    )
    signer_workflow = (ROOT / ".github" / "workflows" / "autonomy-attest.yml").read_text(
        encoding="utf-8"
    )
    verifier = (ROOT / "scripts" / "verify_autonomy_evidence.py").read_text(
        encoding="utf-8"
    )
    uses = re.findall(
        r"^\s*-?\s*uses:\s*([^\s#]+)",
        ci_workflow
        + docker_workflow
        + guard_workflow
        + producer_workflow
        + signer_workflow,
        re.MULTILINE,
    )
    assert uses
    for reference in uses:
        if reference.startswith("./"):
            continue
        assert re.search(r"@[0-9a-f]{40}$", reference), reference
    for artifact in (
        "ci", "runtime", "secrets", "dependencies", "license", "appsec",
        "reality", "overlap", "final-review", "appsec-primary", "appsec-secondary",
    ):
        assert artifact in producer_workflow + signer_workflow
    assert "name: autonomy-evidence" in producer_workflow
    assert "permissions:\n  contents: read" in docker_workflow
    assert "persist-credentials: false" in docker_workflow
    assert "permissions: {}" in producer_workflow
    assert "github.token" not in producer_workflow
    assert "secrets.GITHUB_TOKEN" not in producer_workflow
    assert "GITHUB_TOKEN:" not in producer_workflow
    assert "contents: read" not in producer_workflow
    assert "pull-requests: read" not in producer_workflow
    assert "Clone exact public PR commits without credentials" in producer_workflow
    assert "--protect-trust-root" in producer_workflow
    assert "scan-secrets" in producer_workflow
    assert "gitleaks/gitleaks-action" not in producer_workflow
    assert "attestations: write" not in producer_workflow
    assert "id-token: write" not in producer_workflow
    assert "workflow_run:" in signer_workflow
    assert "types: [requested, completed]" in signer_workflow
    assert "cancel-in-progress: true" in signer_workflow
    assert "name: autonomy-attest" in signer_workflow
    assert "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6" in signer_workflow
    assert "gh attestation trusted-root" in signer_workflow
    assert "--attestation-bundle" in signer_workflow
    assert "--trusted-root" in signer_workflow
    assert "--write-attestation-receipt" in signer_workflow
    assert "\n            --attestation-receipt " not in signer_workflow
    assert "_verify_official_attestation_offline" in verifier
    assert '"--custom-trusted-root"' in verifier
    assert "gh-attestation-verification.json" in signer_workflow
    assert "Revalidate live PR identity and overlap, then publish success" in signer_workflow
    success_step = signer_workflow.split(
        "- name: Revalidate live PR identity and overlap, then publish success", 1
    )[1].split("- name: Publish failed trusted status", 1)[0]
    assert "state=success" in success_step
    assert "scripts/emit_autonomy_evidence.py overlap" in success_step
    assert "JOB_STATUS" not in signer_workflow
    assert signer_workflow.count("group: autonomy-live-gate") == 1
    assert guard_workflow.count("group: autonomy-live-gate") == 1
    assert signer_workflow.count("cancel-in-progress: false") == 1
    assert guard_workflow.count("cancel-in-progress: false") == 1
    assert "attestations: write" in signer_workflow
    assert "id-token: write" in signer_workflow
    assert "statuses: write" in signer_workflow
    assert "normalize-evidence-${{ matrix.kind }}" in signer_workflow
    assert "actions/jobs/$job_id/logs" in signer_workflow
    assert "/attempts/$GITHUB_RUN_ATTEMPT/jobs?per_page=100" in signer_workflow
    assert "emit-job" in signer_workflow
    assert "execution-marker-${{ matrix.kind }}" not in signer_workflow
    assert "Clone control plane from exact public PR base" in producer_workflow
    assert "config/autonomy-tools.lock" in producer_workflow
    assert (
        "playwright==1.62.0 "
        "--hash=sha256:ba33bae6a13b3d9d354c751cb618af357d20fe1d57767cbcce52079bbef17ad3"
    ) in tools_lock
    assert "--isolated download" in producer_workflow
    assert "--no-index --find-links" in producer_workflow
    assert "--only-binary=:all:" in producer_workflow
    assert "--no-deps" in producer_workflow
    assert "--require-hashes" in producer_workflow
    assert "validate-lock" in producer_workflow
    assert "inspect-wheelhouse" in producer_workflow
    assert "supervise_autonomy_check.py" in producer_workflow
    assert "autonomy-trusted-tools" in producer_workflow
    assert "autonomy-candidate-runtime" in producer_workflow
    assert "steps.trusted_python.outputs.python-path" in producer_workflow
    assert '"$TRUSTED_PYTHON" -I -S -m venv' in producer_workflow
    assert "python3 -m venv" not in producer_workflow
    assert "--untrusted-user nobody" in producer_workflow
    assert "Checkout exact PR head" not in signer_workflow
    assert "ref: ${{ needs.context.outputs.head_sha }}" not in signer_workflow
    assert "Fetch candidate object without checkout or execution" in signer_workflow
    assert '--depth=1 origin "$HEAD_SHA"' not in signer_workflow
    assert signer_workflow.count('git fetch --no-tags origin "$HEAD_SHA"') == 2
    assert signer_workflow.count('git merge-base --is-ancestor "$BASE_SHA" "$HEAD_SHA"') == 2
    assert "Download parent-owned black-box observation" in signer_workflow
    assert '[[ "$base_sha" == "$GITHUB_SHA" ]]' in signer_workflow
    assert 'run.get("head_sha") != head_sha' in signer_workflow
    assert 'pull.get("base", {}).get("sha") != os.environ["BASE_SHA"]' in signer_workflow
    assert 'pull.get("head", {}).get("sha") != os.environ["HEAD_SHA"]' in signer_workflow
    assert "Upload one independent structured receipt" in signer_workflow
    assert "*.log" not in producer_workflow + signer_workflow
    assert '"--signer-digest"' in verifier
    assert '--attestation-signer-digest "$GITHUB_WORKFLOW_SHA"' in signer_workflow
    assert "continue-on-error" not in producer_workflow + signer_workflow
    assert "name: autonomy-guard" in guard_workflow
    assert "workflow_run:" in guard_workflow
    assert "types: [requested, completed]" in guard_workflow
    assert "pull_request_target:" in guard_workflow
    assert "schedule:" in guard_workflow
    assert "statuses: write" in guard_workflow
    assert "state=failure" in guard_workflow
    assert "state=success" not in guard_workflow
    assert "guard-open-prs" in guard_workflow


def test_secondary_appsec_independently_enforces_workflow_privilege_boundary():
    with tempfile.TemporaryDirectory(prefix="autonomy-appsec-boundary-") as tmp:
        root = Path(tmp)
        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        scripts = root / "scripts"
        scripts.mkdir()
        shutil.copy2(ROOT / ".github" / "CODEOWNERS", root / ".github" / "CODEOWNERS")
        shutil.copy2(
            ROOT / ".github" / "workflows" / "autonomy-evidence.yml",
            workflows / "autonomy-evidence.yml",
        )
        shutil.copy2(
            ROOT / ".github" / "workflows" / "autonomy-attest.yml",
            workflows / "autonomy-attest.yml",
        )
        shutil.copy2(
            ROOT / ".github" / "workflows" / "autonomy-guard.yml",
            workflows / "autonomy-guard.yml",
        )
        shutil.copy2(
            ROOT / "scripts" / "verify_autonomy_evidence.py",
            scripts / "verify_autonomy_evidence.py",
        )
        context = _context()

        clean = producer.review_changed_files(root, context, "appsec-secondary")
        assert clean == {"findings": [], "seat": "appsec-secondary", "status": "pass"}

        candidate = workflows / "autonomy-evidence.yml"
        candidate.write_text(
            candidate.read_text(encoding="utf-8").replace(
                "permissions: {}", "permissions:\n  id-token: write"
            ),
            encoding="utf-8",
        )
        unsafe = producer.review_changed_files(root, context, "appsec-secondary")
        assert unsafe["status"] == "fail"
        assert any("producer" in finding and "OIDC" in finding for finding in unsafe["findings"])

        signer = workflows / "autonomy-attest.yml"
        signer.write_text(
            signer.read_text(encoding="utf-8").replace(
                "on:\n  workflow_run:\n",
                "on:\n  pull_request:\n  workflow_run:\n",
                1,
            ),
            encoding="utf-8",
        )
        trigger_spoof = producer.review_changed_files(root, context, "appsec-secondary")
        assert trigger_spoof["status"] == "fail"
        assert any("only workflow_run" in finding for finding in trigger_spoof["findings"])


def test_appsec_rejects_any_non_signer_workflow_that_can_spoof_required_status():
    with tempfile.TemporaryDirectory(prefix="autonomy-status-spoof-") as tmp:
        root = Path(tmp)
        workflow = root / ".github" / "workflows" / "spoof.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text(
            'name: spoof\non: pull_request\npermissions: {statuses: "write"}\njobs: {}\n',
            encoding="utf-8",
        )
        context = dict(_context())
        context["changed_paths"] = [".github/workflows/spoof.yml"]
        result = producer.review_changed_files(root, context, "appsec")
        assert result["status"] == "fail"
    assert any("status/check spoofing" in finding for finding in result["findings"])


def test_appsec_requires_explicit_read_only_permissions_for_pull_request_workflows():
    cases = {
        "implicit repository token": "",
        "explicit unrelated write": "permissions:\n  packages: write\n",
    }
    for label, permissions in cases.items():
        with tempfile.TemporaryDirectory(prefix="autonomy-pr-permissions-") as tmp:
            root = Path(tmp)
            workflow = root / ".github" / "workflows" / "candidate.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "name: candidate\non: pull_request\n" + permissions + "jobs: {}\n",
                encoding="utf-8",
            )
            context = dict(_context())
            context["changed_paths"] = [".github/workflows/candidate.yml"]
            result = producer.review_changed_files(root, context, "appsec")
        assert result["status"] == "fail", label
        assert any(
            "write permission" in finding or "explicit bounded permissions" in finding
            for finding in result["findings"]
        ), (label, result)


def test_appsec_rejects_yaml_escaped_permission_keys_before_semantic_decoding():
    with tempfile.TemporaryDirectory(prefix="autonomy-status-escape-") as tmp:
        root = Path(tmp)
        workflow = root / ".github" / "workflows" / "spoof.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text(
            'name: spoof\non: pull_request\npermissions:\n  "statu\\x73es": write\n'
            "jobs: {}\n",
            encoding="utf-8",
        )
        context = dict(_context())
        context["changed_paths"] = [".github/workflows/spoof.yml"]
        result = producer.review_changed_files(root, context, "appsec")
    assert result["status"] == "fail"
    assert any("workflow privilege" in finding for finding in result["findings"])


def test_appsec_rejects_advanced_yaml_forms_that_can_hide_permissions():
    cases = {
        "flow escaped key": (
            'permissions: {"statu\\x73es": write}\n'
        ),
        "unicode escaped key": (
            'permissions:\n  "\\u0073tatuses": write\n'
        ),
        "explicit mapping key": (
            'permissions:\n  ? "statu\\x73es"\n  : write\n'
        ),
        "flow explicit mapping key": (
            'permissions: {? "statu\\x73es": write}\n'
        ),
        "compact flow explicit tagged key": (
            'permissions: {?!!str "statu\\x73es": write}\n'
        ),
        "compact flow tagged key": (
            'permissions: {!!str "statu\\x73es": write}\n'
        ),
        "non-specific tagged key": (
            'permissions: {! "statu\\x73es": write}\n'
        ),
        "unicode YAML line break": (
            'permissions:\u0085  "statu\\x73es": write\u0085'
        ),
        "carriage-return explicit key": (
            'permissions:\r  ? !!str "statu\\x73es"\r  : write\r'
        ),
        "anchor alias and merge": (
            'defaults: &privileged\n'
            '  "statu\\x73es": write\n'
            'permissions:\n'
            '  <<: *privileged\n'
        ),
        "anchor on permissions value": "permissions: &privileged {}\n",
        "alias as permissions value": "permissions: *privileged\n",
        "merge key without alias": "permissions:\n  <<: {}\n",
        "tagged mapping": "permissions: !!map {contents: read}\n",
    }
    for label, permission_yaml in cases.items():
        with tempfile.TemporaryDirectory(prefix="autonomy-yaml-guard-") as tmp:
            root = Path(tmp)
            workflow = root / ".github" / "workflows" / "spoof.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "name: spoof\non: pull_request\n" + permission_yaml + "jobs: {}\n",
                encoding="utf-8",
            )
            context = dict(_context())
            context["changed_paths"] = [".github/workflows/spoof.yml"]
            result = producer.review_changed_files(root, context, "appsec")
        assert result["status"] == "fail", label
        assert any("workflow privilege" in finding for finding in result["findings"]), label


def test_workflow_yaml_guard_ignores_shell_and_json_inside_block_scalars():
    with tempfile.TemporaryDirectory(prefix="autonomy-yaml-block-scalar-") as tmp:
        root = Path(tmp)
        workflow = root / ".github" / "workflows" / "safe.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text(
            "name: safe\n"
            "on: pull_request\n"
            '# permissions: {"statuses": write} &anchor *alias <<: !tag\n'
            "permissions: {}\n"
            "jobs:\n"
            "  inspect:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: |\n"
            "          printf '%s\\n' '{\"statuses\": \"write\", \"<<\": \"*alias\"}'\n"
            "          printf '%s\\n' '? \"id-token\": write &anchor !tag'\n",
            encoding="utf-8",
        )
        context = dict(_context())
        context["changed_paths"] = [".github/workflows/safe.yml"]
        result = producer.review_changed_files(root, context, "appsec")
    assert result == {"findings": [], "seat": "appsec", "status": "pass"}


def test_workflow_yaml_guard_inspects_sibling_after_explicit_block_indent():
    with tempfile.TemporaryDirectory(prefix="autonomy-yaml-explicit-indent-") as tmp:
        root = Path(tmp)
        workflow = root / ".github" / "workflows" / "spoof.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text(
            "name: spoof\n"
            "on: pull_request\n"
            "permissions: {}\n"
            "jobs:\n"
            "  inspect:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: |2\n"
            "          printf '%s\\n' safe\n"
            "        permissions:\n"
            "          <<: {}\n",
            encoding="utf-8",
        )
        context = dict(_context())
        context["changed_paths"] = [".github/workflows/spoof.yml"]
        result = producer.review_changed_files(root, context, "appsec")
    assert result["status"] == "fail"
    assert any("workflow privilege" in finding for finding in result["findings"])


def test_workflow_yaml_guard_rejects_non_utf8_bytes_fail_closed():
    with tempfile.TemporaryDirectory(prefix="autonomy-yaml-encoding-") as tmp:
        root = Path(tmp)
        workflow = root / ".github" / "workflows" / "spoof.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_bytes(b"name: spoof\npermissions:\n  statuses: wr\xffite\n")
        context = dict(_context())
        context["changed_paths"] = [".github/workflows/spoof.yml"]
        result = producer.review_changed_files(root, context, "appsec")
    assert result["status"] == "fail"
    assert any("not valid UTF-8" in finding for finding in result["findings"])


def test_appsec_rejects_deleted_or_renamed_canonical_control_plane_assets():
    with tempfile.TemporaryDirectory(prefix="autonomy-control-delete-") as tmp:
        root = Path(tmp)
        context = dict(_context())
        context["changed_paths"] = ["scripts/emit_autonomy_evidence.py"]
        result = producer.review_changed_files(root, context, "appsec")
    assert result["status"] == "fail"
    assert any("canonical control-plane asset" in finding for finding in result["findings"])


def test_trusted_appsec_rejects_control_plane_mutation_after_bootstrap():
    with tempfile.TemporaryDirectory(prefix="autonomy-trust-root-change-") as tmp:
        root = Path(tmp)
        workflow = root / ".github" / "workflows" / "autonomy-attest.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: inert-candidate-copy\n", encoding="utf-8")
        context = dict(_context())
        context["changed_paths"] = [".github/workflows/autonomy-attest.yml"]
        result = producer.review_changed_files(
            root,
            context,
            "appsec-secondary",
            trusted=True,
        )
    assert result["status"] == "fail"
    assert any("dedicated bootstrap" in finding for finding in result["findings"])


def test_git_changed_paths_includes_both_sides_of_a_rename():
    with tempfile.TemporaryDirectory(prefix="autonomy-git-rename-") as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-q", root], check=True)
        scripts = root / "scripts"
        scripts.mkdir()
        old = scripts / "old-control.py"
        old.write_text("print('old')\n", encoding="utf-8")
        subprocess.run(["git", "-C", root, "add", "."], check=True)
        subprocess.run(
            [
                "git", "-C", root, "-c", "user.name=Autonomy Test",
                "-c", "user.email=autonomy-test@invalid", "commit", "-qm", "base",
            ],
            check=True,
        )
        base = subprocess.run(
            ["git", "-C", root, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        old.rename(scripts / "new-control.py")
        subprocess.run(["git", "-C", root, "add", "-A"], check=True)
        subprocess.run(
            [
                "git", "-C", root, "-c", "user.name=Autonomy Test",
                "-c", "user.email=autonomy-test@invalid", "commit", "-qm", "rename",
            ],
            check=True,
        )
        head = subprocess.run(
            ["git", "-C", root, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        paths = producer.changed_paths(root, base, head)
    assert paths == ["scripts/new-control.py", "scripts/old-control.py"]


def test_appsec_rejects_python_startup_injection():
    with tempfile.TemporaryDirectory(prefix="autonomy-python-startup-") as tmp:
        root = Path(tmp)
        injected = root / "scripts" / "sitecustomize.py"
        injected.parent.mkdir(parents=True)
        injected.write_text("raise SystemExit(0)\n", encoding="utf-8")
        context = dict(_context())
        context["changed_paths"] = ["scripts/sitecustomize.py"]
        result = producer.review_changed_files(root, context, "appsec")
        assert result["status"] == "fail"
        assert any("startup injection" in finding for finding in result["findings"])


def test_control_plane_codeowners_existing_owner_only():
    owners = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8").splitlines()
    expected = {
        "/.gitleaks.toml @adrimg3196",
        "/.github/workflows/ @adrimg3196",
        "/.github/CODEOWNERS @adrimg3196",
        "/config/agency-agents.lock.json @adrimg3196",
        "/config/night-shift-manifest.schema.json @adrimg3196",
        "/config/autonomy-tools.lock @adrimg3196",
        "/data/agency_catalog.json @adrimg3196",
        "/data/night_shift/ @adrimg3196",
        "/scripts/generate_agency_catalog.py @adrimg3196",
        "/scripts/emit_autonomy_evidence.py @adrimg3196",
        "/scripts/supervise_autonomy_check.py @adrimg3196",
        "/scripts/verify_autonomy_evidence.py @adrimg3196",
        "/scripts/verify.py @adrimg3196",
        "/scripts/runtime_validation.py @adrimg3196",
        "/tests/run_tests.py @adrimg3196",
        "/tests/test_agency_catalog.py @adrimg3196",
        "/tests/test_autonomy_evidence.py @adrimg3196",
        "/tests/test_autonomy_evidence_producer.py @adrimg3196",
        "/tests/test_night_shift_schema.py @adrimg3196",
        "/requirements.lock @adrimg3196",
        "/pyproject.toml @adrimg3196",
    }
    assert set(line for line in owners if line and not line.startswith("#")) == expected


def test_verify_py_includes_autonomy_control_plane_without_cli_breakage():
    spec = importlib.util.spec_from_file_location("verify_script", ROOT / "scripts" / "verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ok, detail = module.check_autonomy_control_plane()
    assert ok, detail
    assert "270 profiles" in detail


def test_verify_py_forwards_the_independently_supplied_attestation_trusted_root():
    spec = importlib.util.spec_from_file_location("verify_script", ROOT / "scripts" / "verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from scripts import verify_autonomy_evidence as verifier

    supplied_root = ROOT / "official-root-from-independent-channel.jsonl"
    calls = []
    original = verifier.verify_durable_store

    def fake_verify_durable_store(runs_path, **kwargs):
        calls.append((runs_path, kwargs))
        return []

    verifier.verify_durable_store = fake_verify_durable_store
    try:
        ok, detail = module.check_autonomy_control_plane(
            ROOT,
            trusted_root_path=supplied_root,
        )
    finally:
        verifier.verify_durable_store = original

    assert ok, detail
    assert len(calls) == 1
    assert calls[0][1]["trusted_root_path"] == supplied_root


def test_verify_cli_fails_closed_when_attestation_trusted_root_has_no_path():
    process = subprocess.run(
        [
            sys.executable,
            "scripts/verify.py",
            "--docs-only",
            "--attestation-trusted-root",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert process.returncode == 2
    assert "--attestation-trusted-root requires PATH" in process.stderr


def test_verify_py_rejects_unversioned_arbitrary_durable_manifest():
    spec = importlib.util.spec_from_file_location("verify_script", ROOT / "scripts" / "verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="verify-durable-store-") as tmp:
        root = Path(tmp)
        (root / "config").mkdir()
        (root / "data" / "night_shift" / "runs").mkdir(parents=True)
        shutil.copy2(
            ROOT / "config" / "agency-agents.lock.json",
            root / "config" / "agency-agents.lock.json",
        )
        shutil.copy2(
            ROOT / "config" / "night-shift-manifest.schema.json",
            root / "config" / "night-shift-manifest.schema.json",
        )
        shutil.copy2(ROOT / "data" / "agency_catalog.json", root / "data" / "agency_catalog.json")
        (root / "data" / "night_shift" / "trends.jsonl").write_text("", encoding="utf-8")
        (root / "data" / "night_shift" / "runs" / "README.md").write_text(
            "# Durable evidence\n", encoding="utf-8"
        )
        (root / "data" / "night_shift" / "runs" / "manifest.json").write_text(
            "{}\n", encoding="utf-8"
        )

        ok, detail = module.check_autonomy_control_plane(root)

    assert not ok
    assert "runs inventory" in detail
