"""Export de evidencia de conformidad con cadena de hashes verificable offline.

Para el comprador con auditoría (ISO 27001, ENS, GDPR art. 32) el argumento
que desarma al procurement es "gratis + evidencia auditable": un informe por
periodo cuyo contenido no puede alterarse después de generado sin que la
verificación lo delate.

Diseño (tamper-evident, no tamper-proof — y lo declara):
- Cada registro (estado de dispositivo, evento, acción) se serializa en JSON
  canónico (sort_keys, sin espacios) y se encadena:
      hash_i = sha256(hash_{i-1} || canonical(record_i))
- `chain_head` es el hash del último registro; `report_digest` cubre el
  informe completo. verify_evidence_report() recomputa todo offline con
  stdlib — el receptor no necesita LucidFence ni red.
- La cadena prueba INTEGRIDAD POSTERIOR (nada se tocó tras el export), no que
  los datos fueran verdad en origen; el campo `guarantees` del informe lo
  dice explícitamente. Un informe honesto declara sus límites.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Optional

from lucidfence.core.compliance_controls import map_controls

REPORT_VERSION = "1.0"
GENESIS = "0" * 64

GUARANTEES = {
    "provides": ("integridad posterior al export: cualquier alteración de un "
                 "registro, su orden o su borrado rompe la cadena de hashes"),
    "does_not_provide": ("veracidad en origen: la evidencia refleja lo que el "
                         "engine observó, con su provenance por registro"),
    "verification": ("offline, sin LucidFence: recomputar "
                     "sha256(hash_previo || json_canonico(registro)) por orden"),
}


def _canonical(record: dict) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _chain(records: list[dict]) -> str:
    """Añade previous_hash/hash a cada registro (in place). Devuelve el head."""
    prev = GENESIS
    for record in records:
        record["previous_hash"] = prev
        payload = {k: v for k, v in record.items() if k != "hash"}
        record["hash"] = hashlib.sha256(prev.encode("ascii") + _canonical(payload)).hexdigest()
        prev = record["hash"]
    return prev


def _in_period(ts: Optional[str], since: Optional[str], until: Optional[str]) -> bool:
    if not ts:
        return False
    if since and ts < since:
        return False
    if until and ts > until:
        return False
    return True


def build_evidence_report(
    *,
    org: str,
    devices: list[dict],
    events: list[dict],
    actions: list[dict],
    cve_summary: Optional[dict] = None,
    audit_integrity: Optional[dict] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    generated_at: Optional[str] = None,
) -> dict:
    """Construye el informe de evidencia encadenado para un periodo.

    `since`/`until` son ISO-8601 UTC (comparación lexicográfica, como el resto
    del producto). `generated_at` es inyectable para tests deterministas.
    """
    events_in = [e for e in events if _in_period(e.get("ts"), since, until)]
    actions_in = [a for a in actions if _in_period(a.get("ts"), since, until)]

    records: list[dict] = []
    for d in devices:
        records.append({
            "type": "device_state",
            "device_id": d.get("device_id"),
            "name": d.get("name"),
            "platform": d.get("platform"),
            "compliant": d.get("compliant"),
            "fence_state": d.get("fence_state"),
            "fence_id": d.get("fence_id"),
            "risk_score": d.get("risk_score"),
            "risk_severity": d.get("risk_severity"),
            "encryption_enabled": d.get("encryption_enabled"),
            "location_integrity": d.get("location_integrity"),
            "evidence_freshness": d.get("evidence_freshness"),
            "last_report_ts": d.get("last_report_ts"),
        })
    for e in events_in:
        records.append({"type": "event", **e})
    for a in actions_in:
        records.append({"type": "action", **a})
    chain_head = _chain(records)

    known = [d for d in devices if d.get("compliant") is not None]
    compliant = sum(1 for d in known if d.get("compliant") is True)
    controls = map_controls(devices, cve_summary or {}, audit_integrity or {"ok": False})

    report = {
        "report_version": REPORT_VERSION,
        "generated_at": generated_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "org": org,
        "period": {"from": since, "to": until},
        "totals": {
            "devices": len(devices),
            "compliant": compliant,
            "compliance_percent": round(100 * compliant / len(known), 1) if known else 100.0,
            "events": len(events_in),
            "actions": len(actions_in),
        },
        "controls": controls,
        "guarantees": GUARANTEES,
        "records": records,
        "chain_head": chain_head,
    }
    report["report_digest"] = hashlib.sha256(
        _canonical({k: v for k, v in report.items() if k != "report_digest"})
    ).hexdigest()
    return report


def verify_evidence_report(report: dict) -> dict:
    """Verificación offline: recomputa la cadena y el digest. Nunca lanza."""
    try:
        records = report.get("records") or []
        prev = GENESIS
        for i, record in enumerate(records):
            if record.get("previous_hash") != prev:
                return {"ok": False, "records": i,
                        "error": f"registro {i}: previous_hash roto (cadena alterada o reordenada)"}
            payload = {k: v for k, v in record.items() if k != "hash"}
            expected = hashlib.sha256(prev.encode("ascii") + _canonical(payload)).hexdigest()
            if record.get("hash") != expected:
                return {"ok": False, "records": i,
                        "error": f"registro {i}: hash no coincide (contenido alterado)"}
            prev = record["hash"]
        if report.get("chain_head") != prev:
            return {"ok": False, "records": len(records), "error": "chain_head no coincide"}
        digest = hashlib.sha256(
            _canonical({k: v for k, v in report.items() if k != "report_digest"})
        ).hexdigest()
        if report.get("report_digest") != digest:
            return {"ok": False, "records": len(records),
                    "error": "report_digest no coincide (metadatos del informe alterados)"}
        return {"ok": True, "records": len(records)}
    except Exception as exc:  # noqa: BLE001 — verificación defensiva
        return {"ok": False, "records": 0, "error": f"{type(exc).__name__}: {exc}"}
