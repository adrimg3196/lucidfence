from __future__ import annotations

import json
import tempfile
from pathlib import Path

from core.adapter_marketplace import verify_index
from core.cluster import ClusterLease
from core.compliance_controls import map_controls
from saas.auth import AuthStore, ROLE_CAPS
from scripts.benchmark_10k import benchmark
from scripts.generate_sbom import build_sbom

ROOT = Path(__file__).resolve().parents[1]


def test_active_passive_cluster_lease_fails_over_cleanly():
    with tempfile.TemporaryDirectory() as td:
        first = ClusterLease(Path(td), "node-a")
        second = ClusterLease(Path(td), "node-b")
        assert first.acquire() is True
        assert second.acquire() is False
        first.release()
        assert second.acquire() is True
        second.release()


def test_auditor_is_read_only_with_export_and_audit_capability():
    caps = ROLE_CAPS["auditor"]
    assert {"report:read", "report:export", "audit:read"} <= caps
    assert not any(cap in caps for cap in ("device:write", "device:action", "fence:write", "workflow:write"))
    assert AuthStore.can("auditor", "report:export") is True


def test_compliance_control_mapping_is_evidence_based_and_not_certification():
    controls = map_controls([{"device_id": "d1", "platform": "ios", "compliant": True}],
                            {"apps_total": 1}, {"ok": True})
    assert len(controls) >= 6
    assert {item["framework"] for item in controls} == {"CIS Controls v8", "ISO/IEC 27001:2022"}
    assert all("not certification" in item["disclaimer"] for item in controls)


def test_adapter_marketplace_manifest_is_hash_verified():
    result = verify_index(ROOT)
    assert result == {"ok": True, "entries": 6}


def test_sbom_contains_locked_dependencies_and_source_manifest():
    sbom = build_sbom(ROOT)
    assert sbom["bomFormat"] == "CycloneDX" and sbom["specVersion"] == "1.5"
    purls = {item["purl"] for item in sbom["components"]}
    assert "pkg:pypi/requests@2.33.0" in purls and "pkg:pypi/urllib3@2.7.0" in purls
    assert any(item["name"] == "lucidfence:source-manifest-sha256" for item in sbom["properties"])


def test_10k_geofence_kernel_benchmark_meets_budget():
    result = benchmark(10_000, 2)
    assert result["devices"] == 10_000 and result["pass"] is True
    assert result["p95_seconds"] < result["threshold_seconds"]


def test_installer_and_enterprise_governance_artifacts_are_real():
    installer = (ROOT / "scripts" / "service_install.sh").read_text()
    assert "/api/readyz" in installer and "/health\"" not in installer
    assert (ROOT / "docs" / "THREAT_MODEL.md").stat().st_size > 1500
    assert (ROOT / "docs" / "PILOT_RUNBOOK.md").stat().st_size > 1500
    schema = json.loads((ROOT / "docs" / "openapi.json").read_text())
    assert schema["openapi"] == "3.1.0" and len(schema["paths"]) >= 10
