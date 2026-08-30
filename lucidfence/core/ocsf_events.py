"""OCSF 1.10.0 event mapping for LucidFence risk, geofence and evidence events.

LucidFence is a local-first geofencing + explainable-risk layer on top of a UEM.
It produces operational events (risk recalculations, geofence enter/exit,
location-integrity discrepancies, approved remediation actions, compliance
evidence). This module maps those local events to the Open Cybersecurity Schema
Framework (OCSF) so they can flow into a SIEM that already speaks OCSF, without
re-implementing a parallel taxonomy.

Design contract (issue #254):
  * Reuse existing OCSF classes; do NOT invent a parallel LucidFence taxonomy.
  * Pin a schema_version and validate fixtures against that pin.
  * LucidFence "unknown" MUST NOT become an OCSF fail/critical. OCSF severity 0
    (Unknown) is the honest mapping for "signal absent / not evaluated".
  * Events keep tenant scoping and evidence references intact.
  * No exact coordinates (lat/lng) and no secrets are emitted by default.

The module is pure-stdlib, read-only, never raises for caller data: a malformed
input yields a validation report (`is_valid=False`) rather than an exception, so
the transport channel (#59) can decide how to handle it.

OCSF class UIDs used (https://schema.ocsf.io, schema 1.10.0):
  * 5001 inventory_info                         (category discovery = 5)
  * 5019 device_config_state_change             (category discovery = 5)
  * 2003 compliance_finding                     (category findings = 2)
  * 2004 detection_finding                      (category findings = 2)
  * 3004 entity_management                      (category iam = 3)
  * 7001 remediation_activity                   (category remediation = 7)

Severity mapping (OCSF severity_id):
  0 Unknown | 1 Info | 2 Low | 3 Medium | 4 High | 5 Critical
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Pinned schema version. The acceptance criterion requires the schema version to
# be fixed and updates to pass a compatibility test. We pin to 1.10.0 and the
# validator below asserts the fixtures target exactly this version.
# ---------------------------------------------------------------------------
OCSF_SCHEMA_VERSION = "1.10.0"

# OCSF category_uids (from categories.json).
CAT_DISCOVERY = 5
CAT_FINDINGS = 2
CAT_IAM = 3
CAT_REMEDIATION = 7

# OCSF class_uids.
CLASS_INVENTORY_INFO = 5001
CLASS_DEVICE_CONFIG_STATE_CHANGE = 5019
CLASS_COMPLIANCE_FINDING = 2003
CLASS_DETECTION_FINDING = 2004
CLASS_ENTITY_MANAGEMENT = 3004
CLASS_REMEDIATION_ACTIVITY = 7001

# Severity enum (OCSF severity_id). 0 is the honest mapping for "unknown".
SEVERITY_UNKNOWN = 0
SEVERITY_INFO = 1
SEVERITY_LOW = 2
SEVERITY_MEDIUM = 3
SEVERITY_HIGH = 4
SEVERITY_CRITICAL = 5

# LucidFence native fence states -> OCSF severity (never flips unknown->fail).
# unknown is a *missing signal*, not a violation; it maps to severity 0 (Unknown),
# not to 4/5. This is the explicit acceptance criterion.
_FENCE_STATE_SEVERITY = {
    "inside": SEVERITY_INFO,
    "outside": SEVERITY_HIGH,       # geofence violation
    "unknown": SEVERITY_UNKNOWN,    # signal lost; NOT a fail
    "none": SEVERITY_INFO,
}

# LucidFence risk severity band -> OCSF severity_id.
_RISK_SEVERITY_SEVERITY = {
    "low": SEVERITY_LOW,
    "medium": SEVERITY_MEDIUM,
    "high": SEVERITY_HIGH,
    "critical": SEVERITY_CRITICAL,
    "unknown": SEVERITY_UNKNOWN,    # not evaluated -> Unknown, not fail
}

# LucidFence native transition vocabulary (engine.py "from"/"to" keys).
# Each key is "<fence_id>:<fence_state>". We only care about the state half.
_VALID_FENCE_STATES = ("inside", "outside", "unknown", "none")

# LucidFence action "when" vocabulary (engine.py _fire_actions).
_VALID_WHEN = ("on_enter", "on_exit", "on_unknown", "route_exit")

_PRODUCT_NAME = "LucidFence"
_PRODUCT_VENDOR = "LucidFence"

# LucidFence extension namespace. Any field prefixed with this is an explicit,
# documented extension to the base OCSF class (acceptance: "declare extension
# explicitly"). Values are listed in LUCIDFENCE_EXTENSIONS below so a consumer
# can audit exactly what we add beyond OCSF.
EXT_NS = "lucidfence"


def _now_ms() -> int:
    """Unix epoch milliseconds (UTC). The canonical OCSF `time` field."""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _iso(ts_ms: Optional[int]) -> Optional[str]:
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def _severity_from_fence_state(state: Optional[str]) -> int:
    """Map a LucidFence fence_state to OCSF severity_id.

    Explicitly: `unknown` -> SEVERITY_UNKNOWN (0), never a fail/critical.
    """
    if state is None:
        return SEVERITY_UNKNOWN
    return _FENCE_STATE_SEVERITY.get(state, SEVERITY_UNKNOWN)


def _severity_from_risk(risk: Optional[dict]) -> int:
    """Map a LucidFence risk dict ({score, severity}) to OCSF severity_id.

    If the risk severity is missing/unknown, map to SEVERITY_UNKNOWN (0) — never
    fabricate a fail.
    """
    if not isinstance(risk, dict):
        return SEVERITY_UNKNOWN
    sev = (risk.get("severity") or "unknown").lower()
    return _RISK_SEVERITY_SEVERITY.get(sev, SEVERITY_UNKNOWN)


def _split_state_key(key: str) -> tuple[Optional[str], Optional[str]]:
    """Split a LucidFence '<fence_id>:<fence_state>' key into (fence_id, state)."""
    if not key or ":" not in key:
        return (None, None)
    fid, _, state = key.partition(":")
    return (fid or None, state or None)


def _metadata(tenant_id: Optional[str]) -> dict:
    """Build the OCSF `metadata` object. Tenant scoping is preserved in
    `metadata.tenant_uid` so a multi-tenant SIEM keeps LucidFence boundaries."""
    meta = {
        "version": OCSF_SCHEMA_VERSION,
        "product": {
            "name": _PRODUCT_NAME,
            "vendor_name": _PRODUCT_VENDOR,
        },
    }
    if tenant_id:
        # LucidFence tenants are locally scoped; carry the id for SIEM routing.
        meta["tenant_uid"] = tenant_id
    return meta


def _base(class_uid: int, category_uid: int, severity_id: int,
          ts_ms: Optional[int], tenant_id: Optional[str]) -> dict:
    ev: dict[str, Any] = {
        "class_uid": class_uid,
        "category_uid": category_uid,
        "severity_id": severity_id,
        "time": ts_ms if ts_ms is not None else _now_ms(),
        "metadata": _metadata(tenant_id),
    }
    return ev


# ---------------------------------------------------------------------------
# Event builders
# ---------------------------------------------------------------------------
def risk_event(device: dict, risk: dict, fence_state: Optional[str] = None,
               tenant_id: Optional[str] = None, ts_ms: Optional[int] = None,
               evidence_refs: Optional[list[str]] = None) -> dict:
    """Map a LucidFence risk evaluation to OCSF Detection Finding (2004).

    `risk` is the LucidFence policy engine output: {score: int, severity: str,
    reasons: [str], ...}. `fence_state` is the device's current geofence state.
    `evidence_refs` are opaque references into LucidFence's evidence store
    (e.g. evidence report ids) preserved verbatim.
    """
    severity_id = _severity_from_risk(risk)
    ev = _base(CLASS_DETECTION_FINDING, CAT_FINDINGS, severity_id, ts_ms, tenant_id)
    score = (risk or {}).get("risk_score", (risk or {}).get("score"))
    reasons = (risk or {}).get("reasons") or (risk or {}).get("signals") or []
    ev.update({
        "risk_score": score,
        "risk_level": (risk or {}).get("severity"),
        "title": "LucidFence device risk evaluation",
        "message": "; ".join(reasons) if reasons else "risk evaluation",
        # Explicit LucidFence extension: fence state context, never replaces
        # OCSF semantics.
        f"{EXT_NS}.fence_state": fence_state,
        f"{EXT_NS}.device_id": device.get("device_id"),
        f"{EXT_NS}.platform": device.get("platform"),
    })
    if fence_state is not None:
        ev[f"{EXT_NS}.fence_state"] = fence_state
    if evidence_refs:
        ev[f"{EXT_NS}.evidence_refs"] = list(evidence_refs)
    return ev


def geofence_event(device: dict, transition: dict,
                   tenant_id: Optional[str] = None, ts_ms: Optional[int] = None,
                   evidence_refs: Optional[list[str]] = None) -> dict:
    """Map a LucidFence geofence enter/exit/unknown transition to OCSF.

    LucidFence transition vocabulary (engine.py): `transition` carries
    {"from": "<fence_id>:<state>", "to": "<fence_id>:<state>"}. The `to` state
    drives severity; `unknown` maps to OCSF Unknown (0), never a fail.

    We use Device Config State Change (5019) — a discovery-class event that
    records a change in the observed device/position state — because a geofence
    enter/exit is fundamentally "the device's location-state changed". This is a
    documented extension choice (no exact OCSF geofence class exists).
    """
    to_fid, to_state = _split_state_key(transition.get("to", ""))
    from_fid, from_state = _split_state_key(transition.get("from", ""))
    severity_id = _severity_from_fence_state(to_state)
    ev = _base(CLASS_DEVICE_CONFIG_STATE_CHANGE, CAT_DISCOVERY, severity_id,
               ts_ms, tenant_id)
    ev.update({
        "title": "LucidFence geofence state change",
        "message": f"geofence {from_state or '?'} -> {to_state or '?'}",
        # Explicit LucidFence extensions (documented, not a parallel taxonomy).
        f"{EXT_NS}.device_id": device.get("device_id"),
        f"{EXT_NS}.device_name": device.get("name") or device.get("device_name"),
        f"{EXT_NS}.fence_id": to_fid,
        f"{EXT_NS}.fence_state_from": from_state,
        f"{EXT_NS}.fence_state_to": to_state,
        f"{EXT_NS}.route_id": transition.get("route_id"),
        f"{EXT_NS}.deviation_m": transition.get("deviation_m"),
    })
    if evidence_refs:
        ev[f"{EXT_NS}.evidence_refs"] = list(evidence_refs)
    return ev


def discrepancy_event(device: dict, integrity: dict,
                      tenant_id: Optional[str] = None, ts_ms: Optional[int] = None,
                      evidence_refs: Optional[list[str]] = None) -> dict:
    """Map a LucidFence location-integrity discrepancy to OCSF Detection Finding.

    `integrity` is the location_integrity signal dict: {checks: [str],
    spoofing_score, ...}. A discrepancy (e.g. impossible_speed) is a detection,
    severity scales with how confident the discrepancy is — but an *absent*
    integrity signal is Unknown, not a fail.
    """
    checks = (integrity or {}).get("checks") or []
    if checks:
        # Concrete discrepancy present -> at least Medium; impossible_speed is High.
        severity_id = SEVERITY_HIGH if any(
            "impossible" in c or "spoof" in c for c in checks) else SEVERITY_MEDIUM
    else:
        severity_id = SEVERITY_UNKNOWN
    ev = _base(CLASS_DETECTION_FINDING, CAT_FINDINGS, severity_id, ts_ms, tenant_id)
    ev.update({
        "title": "LucidFence location-integrity discrepancy",
        "message": "; ".join(checks) if checks else "no integrity signal",
        f"{EXT_NS}.device_id": device.get("device_id"),
        f"{EXT_NS}.integrity_checks": list(checks),
        f"{EXT_NS}.spoofing_score": (integrity or {}).get("spoofing_score"),
    })
    if evidence_refs:
        ev[f"{EXT_NS}.evidence_refs"] = list(evidence_refs)
    return ev


def approved_action_event(device: dict, action: dict,
                         tenant_id: Optional[str] = None, ts_ms: Optional[int] = None,
                         evidence_refs: Optional[list[str]] = None) -> dict:
    """Map a LucidFence approved/executed action to OCSF Entity Management (3004)
    or Remediation Activity (7001).

    LucidFence actions are operator-approved automations (notify, lock, locate,
    flag_app, ...). We map "informational" actions to Entity Management and
    "remediation" actions (lock/quarantine/wipe-class) to Remediation Activity,
    per the OCSF category intent. `action` carries {action, when, params,
    approved_by?, status?}.
    """
    act_name = (action or {}).get("action") or "unknown"
    remediation_actions = {"lock", "quarantine", "wipe", "remediate", "isolate"}
    if act_name in remediation_actions:
        ev = _base(CLASS_REMEDIATION_ACTIVITY, CAT_REMEDIATION, SEVERITY_MEDIUM,
                   ts_ms, tenant_id)
        ev["activity_id"] = 1  # 1 = Remediate (OCSF remediation_activity)
        ev["title"] = f"LucidFence remediation: {act_name}"
    else:
        ev = _base(CLASS_ENTITY_MANAGEMENT, CAT_IAM, SEVERITY_INFO, ts_ms, tenant_id)
        ev["activity_id"] = 2  # 2 = Update (managed entity changed)
        ev["title"] = f"LucidFence approved action: {act_name}"
    ev.update({
        "message": (action or {}).get("detail") or act_name,
        f"{EXT_NS}.device_id": device.get("device_id"),
        f"{EXT_NS}.action": act_name,
        f"{EXT_NS}.when": action.get("when"),
        f"{EXT_NS}.approved_by": (action or {}).get("approved_by"),
        f"{EXT_NS}.status": (action or {}).get("status", "approved"),
    })
    if evidence_refs:
        ev[f"{EXT_NS}.evidence_refs"] = list(evidence_refs)
    return ev


def compliance_evidence_event(device: dict, evidence: dict,
                              tenant_id: Optional[str] = None,
                              ts_ms: Optional[int] = None) -> dict:
    """Map a LucidFence compliance-evidence record to OCSF Compliance Finding
    (2003). `evidence` is the build_evidence_report() output shape
    {report_id, report_version, report_digest, guarantees, records_count}.
    """
    ev = _base(CLASS_COMPLIANCE_FINDING, CAT_FINDINGS, SEVERITY_INFO, ts_ms,
               tenant_id)
    ev.update({
        "title": "LucidFence compliance evidence report",
        "message": f"evidence report {evidence.get('report_id')}",
        "finding_info": {
            "uid": evidence.get("report_id"),
            "title": "LucidFence tamper-evident evidence report",
        },
        f"{EXT_NS}.report_version": evidence.get("report_version"),
        f"{EXT_NS}.report_digest": evidence.get("report_digest"),
        f"{EXT_NS}.records_count": evidence.get("records_count"),
        f"{EXT_NS}.device_id": device.get("device_id"),
    })
    # Guarantees are declarative metadata — keep them verbatim but namespaced.
    guarantees = evidence.get("guarantees")
    if isinstance(guarantees, dict):
        ev[f"{EXT_NS}.guarantees_provides"] = guarantees.get("provides")
        ev[f"{EXT_NS}.guarantees_does_not_provide"] = guarantees.get("does_not_provide")
    return ev


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_event(event: dict) -> dict:
    """Fail-closed validation against the pinned OCSF schema_version.

    Returns {is_valid, errors, schema_version}. A malformed event is reported,
    never raised. The only hard requirements are the universal OCSF fields:
    class_uid, category_uid, severity_id, time, metadata.version == pinned.
    """
    errors: list[str] = []
    if not isinstance(event, dict):
        return {"is_valid": False, "errors": ["event is not an object"],
                "schema_version": OCSF_SCHEMA_VERSION}
    if event.get("metadata", {}).get("version") != OCSF_SCHEMA_VERSION:
        errors.append(
            f"metadata.version must be {OCSF_SCHEMA_VERSION}, got "
            f"{event.get('metadata', {}).get('version')!r}")
    for fld in ("class_uid", "category_uid", "severity_id", "time"):
        if fld not in event:
            errors.append(f"missing universal field {fld}")
        elif not isinstance(event[fld], int):
            errors.append(f"field {fld} must be integer")
    if not (0 <= event.get("severity_id", -1) <= 5):
        errors.append("severity_id out of range 0-5")
    return {
        "is_valid": not errors,
        "errors": errors,
        "schema_version": OCSF_SCHEMA_VERSION,
    }


# The set of LucidFence extensions this module can emit, for consumer audit.
LUCIDFENCE_EXTENSIONS = {
    "fence_state", "fence_state_from", "fence_state_to", "fence_id",
    "device_id", "device_name", "platform", "route_id", "deviation_m",
    "evidence_refs", "integrity_checks", "spoofing_score", "action", "when",
    "approved_by", "status", "risk_level", "report_version", "report_digest",
    "records_count", "guarantees_provides", "guarantees_does_not_provide",
}


def export_json(events: list[dict], indent: int = 2) -> str:
    """Serialize a batch of OCSF events as a JSON array (transport-ready)."""
    return json.dumps(events, ensure_ascii=False, indent=indent if indent else None)


def batch_to_records(events: list[dict]) -> dict:
    """Wrap a batch with an envelope that carries the pinned schema version and
    the LucidFence extension audit list, so a SIEM can verify compatibility."""
    return {
        "schema": "ocsf",
        "schema_version": OCSF_SCHEMA_VERSION,
        "generated_at": _now_ms(),
        "lucidfence_extensions": sorted(LUCIDFENCE_EXTENSIONS),
        "count": len(events),
        "events": events,
    }
