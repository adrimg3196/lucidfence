"""PowerShell Desired State Configuration (DSC) engine for LucidFence.

Provides document generation and status readback for Windows endpoints.
Supports DSC v3 (JSON resource manifests) and fallback classic DSC (.ps1/MOF).
Allows idempotent re-application of geofence policies via Test/Set mapping.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Union


def generate_dsc_v3_manifest(policy: Any) -> Dict[str, Any]:
    """Generates a DSC v3 JSON configuration document from a Policy or dict."""
    policy_dict = policy.to_dict() if hasattr(policy, "to_dict") else policy
    return {
        "$schema": "https://raw.githubusercontent.com/PowerShell/DSC/main/schemas/2024/04/config/document.json",
        "resources": [
            {
                "name": f"LucidFencePolicy_{policy_dict.get('id', 'policy')}",
                "type": "LucidFence/GeofenceCompliance",
                "properties": {
                    "policyId": policy_dict.get("id"),
                    "name": policy_dict.get("name"),
                    "description": policy_dict.get("description"),
                    "severity": policy_dict.get("severity"),
                    "enabled": policy_dict.get("enabled", True),
                    "when": policy_dict.get("when", []),
                    "actions": policy_dict.get("actions", []),
                },
            }
        ],
    }


def generate_classic_dsc_ps1(policy: Any) -> str:
    """Generates a classic PowerShell DSC (.ps1) script fallback."""
    policy_dict = policy.to_dict() if hasattr(policy, "to_dict") else policy
    policy_id = policy_dict.get("id", "policy")
    name = policy_dict.get("name", "")
    description = policy_dict.get("description", "")
    severity = policy_dict.get("severity", "medium")
    enabled = "$true" if policy_dict.get("enabled", True) else "$false"

    when_json = json.dumps(policy_dict.get("when", []), ensure_ascii=False).replace('"', '`"')
    actions_json = json.dumps(policy_dict.get("actions", []), ensure_ascii=False).replace('"', '`"')

    return f"""Configuration LucidFenceDSC_{policy_id} {{
    Import-DscResource -ModuleName LucidFenceDSC
    Node "localhost" {{
        LucidFencePolicy "{policy_id}" {{
            Name = "{name}"
            Description = "{description}"
            Severity = "{severity}"
            Enabled = {enabled}
            When = "{when_json}"
            Actions = "{actions_json}"
            Ensure = "Present"
        }}
    }}
}}"""


def generate_classic_dsc_mof(policy: Any) -> str:
    """Generates a classic DSC MOF document fallback."""
    policy_dict = policy.to_dict() if hasattr(policy, "to_dict") else policy
    policy_id = policy_dict.get("id", "policy")
    name = policy_dict.get("name", "")
    description = policy_dict.get("description", "")
    severity = policy_dict.get("severity", "medium")
    enabled = "true" if policy_dict.get("enabled", True) else "false"

    when_json = json.dumps(policy_dict.get("when", []), ensure_ascii=False).replace('"', '\\"')
    actions_json = json.dumps(policy_dict.get("actions", []), ensure_ascii=False).replace('"', '\\"')

    return f"""instance of LucidFencePolicy as $LucidFencePolicy1
{{
    ResourceID = "[LucidFencePolicy]{policy_id}";
    PolicyId = "{policy_id}";
    Name = "{name}";
    Description = "{description}";
    Severity = "{severity}";
    Enabled = {enabled};
    When = "{when_json}";
    Actions = "{actions_json}";
    ModuleName = "LucidFenceDSC";
    ModuleVersion = "1.0.0";
}};"""


def verify_policy_idempotency(current_state_properties: Dict[str, Any], target_policy: Any) -> bool:
    """Returns True if the current configuration/state matches the target policy.

    Implements Test/Set semantics for idempotency. If this returns True, re-applying
    the policy is a no-op because the current state matches the desired state.
    """
    policy_dict = target_policy.to_dict() if hasattr(target_policy, "to_dict") else target_policy

    # Check simple attributes
    curr_id = current_state_properties.get("policyId") or current_state_properties.get("id")
    if curr_id != policy_dict.get("id"):
        return False

    curr_enabled = current_state_properties.get("enabled")
    if curr_enabled is not None and bool(curr_enabled) != bool(policy_dict.get("enabled", True)):
        return False

    curr_severity = current_state_properties.get("severity")
    if curr_severity and curr_severity != policy_dict.get("severity"):
        return False

    curr_name = current_state_properties.get("name")
    if curr_name and curr_name != policy_dict.get("name"):
        return False

    # Check structural attributes ('when' and 'actions')
    curr_when = current_state_properties.get("when")
    target_when = policy_dict.get("when", [])
    if isinstance(curr_when, str):
        try:
            curr_when = json.loads(curr_when)
        except Exception:
            pass
    if curr_when != target_when:
        return False

    curr_actions = current_state_properties.get("actions")
    target_actions = policy_dict.get("actions", [])
    if isinstance(curr_actions, str):
        try:
            curr_actions = json.loads(curr_actions)
        except Exception:
            pass
    if curr_actions != target_actions:
        return False

    return True


def _is_truthy(val: Any) -> bool:
    """Helper to convert any input safely to a boolean, failing closed on 'False' strings and missing values."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        normalized = val.strip().lower()
        if normalized in ("false", "0", "no", "none", "null", ""):
            return False
        return normalized in ("true", "1", "yes", "indesiredstate", "incompliance")
    if isinstance(val, (int, float)):
        return val != 0
    return bool(val)


def parse_dsc_status_output(status_output: str) -> Dict[str, Any]:
    """Parses a PowerShell DSC status or DSC v3 test JSON output.

    Returns a normalized compliance status structure.
    """
    if not status_output:
        return {
            "compliant": False,
            "policy_id": "unknown",
            "mode": "dsc",
            "evidence": "Empty DSC status output",
        }

    try:
        data = json.loads(status_output)
    except Exception:
        # Fallback for plain text stdout
        # Check if compliant state is present and explicitly true, avoiding false matches
        stdout_normalized = status_output.lower()
        compliant = (
            "indesiredstate : true" in stdout_normalized
            or "incompliance : true" in stdout_normalized
            or "indesiredstate: true" in stdout_normalized
            or "incompliance: true" in stdout_normalized
        ) and not (
            "indesiredstate : false" in stdout_normalized
            or "incompliance : false" in stdout_normalized
            or "indesiredstate: false" in stdout_normalized
            or "incompliance: false" in stdout_normalized
        )
        return {
            "compliant": compliant,
            "policy_id": "unknown",
            "mode": "dsc",
            "evidence": f"Parsed from plain-text output (compliant={compliant})",
        }

    # Check DSC v3 results format
    if isinstance(data, dict) and "results" in data:
        results = data["results"]
        if not results:
            return {
                "compliant": False,
                "policy_id": "unknown",
                "mode": "dsc",
                "evidence": "No results in DSC v3 output",
            }
        all_compliant = True
        policy_ids = []
        for r in results:
            in_desired = r.get("inDesiredState")
            if in_desired is None:
                in_desired = r.get("in_desired_state")
            if in_desired is None and "status" in r:
                in_desired = r["status"] == "InDesiredState"
            if in_desired is None:
                props = r.get("properties", {})
                in_desired = props.get("compliant")
                if in_desired is None:
                    in_desired = props.get("inDesiredState")

            # Fail closed on absent or malformed/false values
            if in_desired is None or not _is_truthy(in_desired):
                all_compliant = False

            pid = (
                r.get("properties", {}).get("policyId")
                or r.get("name", "").replace("LucidFencePolicy_", "")
            )
            if pid:
                policy_ids.append(pid)

        return {
            "compliant": all_compliant,
            "policy_id": policy_ids[0] if policy_ids else "unknown",
            "mode": "dsc",
            "evidence": f"Parsed {len(results)} DSC v3 resource(s)",
            "results": results,
        }

    # Check classic DSC list format
    if isinstance(data, list):
        if not data:
            return {
                "compliant": False,
                "policy_id": "unknown",
                "mode": "dsc_v2",
                "evidence": "Empty classic DSC list",
            }
        all_compliant = True
        policy_ids = []
        for item in data:
            in_compliance = item.get("InCompliance")
            if in_compliance is None:
                in_compliance = item.get("InDesiredState")

            # Fail closed on absent or malformed/false values
            if in_compliance is None or not _is_truthy(in_compliance):
                all_compliant = False

            pid = item.get("PolicyId") or item.get("ResourceName")
            if pid:
                policy_ids.append(pid)

        return {
            "compliant": all_compliant,
            "policy_id": policy_ids[0] if policy_ids else "unknown",
            "mode": "dsc_v2",
            "evidence": f"Parsed {len(data)} classic DSC resource(s)",
            "results": data,
        }

    return {
        "compliant": False,
        "policy_id": "unknown",
        "mode": "dsc",
        "evidence": "Unknown JSON schema structure",
    }
