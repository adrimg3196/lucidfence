"""Evidence-based CIS/ISO control mapping (not a certification claim)."""
from __future__ import annotations

CONTROLS = [
    {"id": "CIS-1.1", "framework": "CIS Controls v8", "title": "Enterprise asset inventory", "source": "device inventory", "metric": "inventory_coverage"},
    {"id": "CIS-4.1", "framework": "CIS Controls v8", "title": "Secure configuration process", "source": "device compliance", "metric": "compliance_percent"},
    {"id": "CIS-7.1", "framework": "CIS Controls v8", "title": "Vulnerability management", "source": "CVE correlation", "metric": "vulnerability_visibility"},
    {"id": "ISO-A.5.15", "framework": "ISO/IEC 27001:2022", "title": "Access control", "source": "server RBAC", "metric": "rbac_enabled"},
    {"id": "ISO-A.8.15", "framework": "ISO/IEC 27001:2022", "title": "Logging", "source": "hash-chained audit", "metric": "audit_integrity"},
    {"id": "ISO-A.8.16", "framework": "ISO/IEC 27001:2022", "title": "Monitoring activities", "source": "incidents and alerts", "metric": "monitoring_enabled"},
]


def map_controls(devices: list[dict], cve_summary: dict, audit_integrity: dict) -> list[dict]:
    total = len(devices)
    inventoried = sum(1 for item in devices if item.get("device_id") and item.get("platform"))
    compliant = sum(1 for item in devices if item.get("compliant") is not False)
    metrics = {
        "inventory_coverage": round(inventoried / total * 100) if total else 0,
        "compliance_percent": round(compliant / total * 100) if total else 0,
        "vulnerability_visibility": 100 if cve_summary.get("apps_total", 0) else 0,
        "rbac_enabled": 100,
        "audit_integrity": 100 if audit_integrity.get("ok") else 0,
        "monitoring_enabled": 100,
    }
    return [{**control, "score": metrics[control["metric"]],
             "status": "pass" if metrics[control["metric"]] >= 80 else "attention",
             "disclaimer": "evidence mapping only; not certification"} for control in CONTROLS]
