"""Tests del export de evidencia con cadena de hashes (P1.7)."""
from __future__ import annotations

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.evidence_export import (
    GENESIS,
    build_evidence_report,
    verify_evidence_report,
)

DEVICES = [
    {"device_id": "dev-1", "name": "Tablet A", "platform": "android", "compliant": True,
     "fence_state": "inside", "risk_score": 12.0, "risk_severity": "low",
     "apps": [{"name": "x"}], "last_report_ts": "2026-08-14T10:00:00Z"},
    {"device_id": "dev-2", "name": "Portátil B", "platform": "windows", "compliant": False,
     "fence_state": "outside", "risk_score": 65.0, "risk_severity": "high",
     "apps": [], "last_report_ts": "2026-08-14T10:00:00Z"},
]
EVENTS = [
    {"ts": "2026-08-13T09:00:00Z", "event": "exit", "device_id": "dev-2"},
    {"ts": "2026-08-14T09:00:00Z", "event": "enter", "device_id": "dev-1"},
    {"ts": "2026-08-20T09:00:00Z", "event": "exit", "device_id": "dev-1"},  # fuera de periodo
]
ACTIONS = [
    {"ts": "2026-08-13T09:01:00Z", "action": "lock", "device_id": "dev-2"},
]


def _report():
    return build_evidence_report(
        org="acme", devices=DEVICES, events=EVENTS, actions=ACTIONS,
        cve_summary={"apps_total": 1}, audit_integrity={"ok": True},
        since="2026-08-13T00:00:00Z", until="2026-08-15T00:00:00Z",
        generated_at="2026-08-15T12:00:00Z",
    )


def test_report_chains_all_records_and_verifies() -> None:
    report = _report()
    # 2 device_state + 2 eventos en periodo + 1 acción; el evento del día 20 queda fuera.
    assert len(report["records"]) == 5
    assert report["totals"] == {"devices": 2, "compliant": 1, "compliance_percent": 50.0,
                                "events": 2, "actions": 1}
    assert report["records"][0]["previous_hash"] == GENESIS
    assert report["chain_head"] == report["records"][-1]["hash"]
    assert verify_evidence_report(report) == {"ok": True, "records": 5}


def test_report_is_deterministic_and_json_serializable() -> None:
    a, b = _report(), _report()
    assert a == b
    assert json.loads(json.dumps(a, ensure_ascii=False)) == a


def test_tampering_record_content_breaks_chain() -> None:
    report = _report()
    tampered = copy.deepcopy(report)
    tampered["records"][1]["compliant"] = True  # maquillar el no-conforme
    result = verify_evidence_report(tampered)
    assert result["ok"] is False and "alterado" in result["error"]


def test_removing_or_reordering_records_breaks_chain() -> None:
    report = _report()
    dropped = copy.deepcopy(report)
    del dropped["records"][2]
    assert verify_evidence_report(dropped)["ok"] is False
    swapped = copy.deepcopy(report)
    swapped["records"][0], swapped["records"][1] = swapped["records"][1], swapped["records"][0]
    assert verify_evidence_report(swapped)["ok"] is False


def test_tampering_report_metadata_breaks_digest() -> None:
    report = _report()
    tampered = copy.deepcopy(report)
    tampered["totals"]["compliance_percent"] = 100.0  # maquillar el resumen
    result = verify_evidence_report(tampered)
    assert result["ok"] is False and "report_digest" in result["error"]


def test_report_declares_honest_guarantees_and_controls() -> None:
    report = _report()
    assert "does_not_provide" in report["guarantees"]
    ids = {c["id"] for c in report["controls"]}
    assert "ISO-A.8.15" in ids  # logging con auditoría hash-chained
    assert all(c["disclaimer"] for c in report["controls"])


def test_verify_never_raises_on_garbage() -> None:
    # Basura de todo tipo: falla con motivo, jamás con excepción.
    assert verify_evidence_report({})["ok"] is False
    assert verify_evidence_report({"records": "no-lista"})["ok"] is False
    assert verify_evidence_report({"records": [{"hash": "x"}]})["ok"] is False
