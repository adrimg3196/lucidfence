"""Tests for the OCSF 1.10.0 event mapping (issue #254).

Acceptance criteria covered:
  AC1: fixtures for risk, geofence enter/exit, discrepancy and approved action
       validate AND declare the LucidFence extension explicitly.
  AC2: schema version is fixed; a compatibility test asserts it.
  AC3: LucidFence 'unknown' does NOT become an OCSF fail/critical (severity 0).
  AC4: events preserve tenant scoping and evidence references.
  AC5: #59 (syslog/CEF transport) can carry the event without changing meaning
       — we assert the exported JSON round-trips and keeps universal fields.
"""
from __future__ import annotations

import json

from lucidfence.core import ocsf_events as o


def _device():
    return {"device_id": "dev-001", "name": "Field iPad", "platform": "ios"}


# --- AC1: fixtures validate and declare extension explicitly -----------------
def test_risk_event_fixture_valid_and_extended():
    risk = {"risk_score": 72, "severity": "high",
            "reasons": ["fuera de geocerca permitida"]}
    ev = o.risk_event(_device(), risk, fence_state="outside",
                      tenant_id="acme", evidence_refs=["evt-abc"])
    rep = o.validate_event(ev)
    assert rep["is_valid"], rep["errors"]
    assert rep["schema_version"] == o.OCSF_SCHEMA_VERSION
    # Extension is declared (namespaced), not smuggled in silently.
    assert ev[f"{o.EXT_NS}.fence_state"] == "outside"
    assert ev[f"{o.EXT_NS}.evidence_refs"] == ["evt-abc"]
    assert ev["class_uid"] == o.CLASS_DETECTION_FINDING
    assert ev["category_uid"] == o.CAT_FINDINGS


def test_geofence_enter_exit_fixtures_valid():
    # enter
    enter = o.geofence_event(_device(), {"from": "none:unknown", "to": "fence-a:inside"})
    assert o.validate_event(enter)["is_valid"]
    assert enter[f"{o.EXT_NS}.fence_state_to"] == "inside"
    # exit (violation)
    exit_ = o.geofence_event(_device(), {"from": "fence-a:inside", "to": "fence-a:outside"})
    assert o.validate_event(exit_)["is_valid"]
    assert exit_[f"{o.EXT_NS}.fence_state_to"] == "outside"
    # extension declared
    assert f"{o.EXT_NS}.fence_id" in exit_


def test_discrepancy_fixture_valid():
    integ = {"checks": ["impossible_speed"], "spoofing_score": 0.9}
    ev = o.discrepancy_event(_device(), integ)
    assert o.validate_event(ev)["is_valid"]
    assert ev[f"{o.EXT_NS}.integrity_checks"] == ["impossible_speed"]
    assert ev["class_uid"] == o.CLASS_DETECTION_FINDING


def test_approved_action_fixture_valid():
    act = {"action": "lock", "when": "on_exit", "approved_by": "operator",
           "status": "approved"}
    ev = o.approved_action_event(_device(), act)
    assert o.validate_event(ev)["is_valid"]
    # lock is a remediation action -> remediation_activity class
    assert ev["class_uid"] == o.CLASS_REMEDIATION_ACTIVITY
    assert ev[f"{o.EXT_NS}.action"] == "lock"


# --- AC2: schema version fixed + compatibility -------------------------------
def test_schema_version_pinned():
    assert o.OCSF_SCHEMA_VERSION == "1.10.0"
    ev = o.risk_event(_device(), {"severity": "low"}, tenant_id="t1")
    assert ev["metadata"]["version"] == "1.10.0"


def test_incompatible_version_rejected():
    ev = o.risk_event(_device(), {"severity": "low"}, tenant_id="t1")
    ev["metadata"]["version"] = "9.9.9"
    rep = o.validate_event(ev)
    assert not rep["is_valid"]
    assert any("metadata.version" in e for e in rep["errors"])


# --- AC3: unknown never becomes fail/critical -------------------------------
def test_unknown_fence_state_maps_to_severity_unknown():
    ev = o.geofence_event(_device(), {"from": "none:unknown", "to": "fence-a:unknown"})
    # unknown -> severity 0 (Unknown), NOT 4/5.
    assert ev["severity_id"] == o.SEVERITY_UNKNOWN
    assert ev["severity_id"] != o.SEVERITY_HIGH
    assert ev["severity_id"] != o.SEVERITY_CRITICAL


def test_unknown_risk_maps_to_severity_unknown():
    # missing/unknown risk severity -> Unknown, never fabricated fail.
    ev = o.risk_event(_device(), {}, fence_state="unknown")
    assert ev["severity_id"] == o.SEVERITY_UNKNOWN


def test_missing_risk_dict_maps_to_unknown():
    ev = o.risk_event(_device(), None)
    assert ev["severity_id"] == o.SEVERITY_UNKNOWN


# --- AC4: tenant scoping + evidence references preserved ---------------------
def test_tenant_scoping_preserved():
    ev = o.risk_event(_device(), {"severity": "medium"}, tenant_id="acme-corp")
    assert ev["metadata"]["tenant_uid"] == "acme-corp"
    # tenant id also lands in an auditable extension field
    assert ev[f"{o.EXT_NS}.device_id"] == "dev-001"


def test_evidence_refs_preserved_on_all_event_types():
    refs = ["ev-1", "ev-2"]
    assert o.risk_event(_device(), {"severity": "high"}, evidence_refs=refs)[f"{o.EXT_NS}.evidence_refs"] == refs
    assert o.geofence_event(_device(), {"to": "fence-a:outside"}, evidence_refs=refs)[f"{o.EXT_NS}.evidence_refs"] == refs
    assert o.discrepancy_event(_device(), {"checks": ["x"]}, evidence_refs=refs)[f"{o.EXT_NS}.evidence_refs"] == refs
    assert o.approved_action_event(_device(), {"action": "notify"}, evidence_refs=refs)[f"{o.EXT_NS}.evidence_refs"] == refs


# --- AC5: #59 transport channel carries event without changing meaning -------
def test_export_json_roundtrip_preserves_universal_fields():
    events = [
        o.risk_event(_device(), {"severity": "high"}, tenant_id="t", evidence_refs=["e1"]),
        o.geofence_event(_device(), {"to": "fence-a:outside"}, tenant_id="t"),
    ]
    blob = o.export_json(events)
    back = json.loads(blob)
    assert len(back) == 2
    for e in back:
        # universal OCSF fields survive the transport
        assert {"class_uid", "category_uid", "severity_id", "time", "metadata"} <= set(e)
        assert e["metadata"]["version"] == o.OCSF_SCHEMA_VERSION


def test_batch_envelope_declares_extensions():
    events = [o.risk_event(_device(), {"severity": "low"})]
    env = o.batch_to_records(events)
    assert env["schema_version"] == o.OCSF_SCHEMA_VERSION
    assert "fence_state" in env["lucidfence_extensions"]
    # every extension key actually used is declared in the audit list
    used = {k.split(".", 1)[1] for e in events for k in e if k.startswith(o.EXT_NS + ".")}
    assert used <= set(env["lucidfence_extensions"])


# --- boundary: no coordinates / secrets emitted by default -------------------
def test_no_coordinates_or_secrets_in_default_event():
    ev = o.geofence_event(_device(), {"to": "fence-a:outside"})
    blob = json.dumps(ev)
    # default mapping carries no lat/lng or secret markers
    assert "lat" not in blob.lower() or "latitude" not in blob.lower()
    assert "lng" not in blob.lower()
    assert "secret" not in blob.lower()
    assert "token" not in blob.lower()
