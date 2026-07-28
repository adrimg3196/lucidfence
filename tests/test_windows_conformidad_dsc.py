"""Unit tests for Windows Conformidad PowerShell DSC support.

Validates pure Python document generation, Test/Set idempotency checks,
compliance readback status parsing, and adapter operations.
"""

from __future__ import annotations

import json
import sys
import unittest

sys.path.insert(0, ".")

from lucidfence.core.adapters.windows_conformidad import WindowsConformidadAdapter
from lucidfence.core.dsc import (
    generate_dsc_v3_manifest,
    generate_classic_dsc_ps1,
    generate_classic_dsc_mof,
    verify_policy_idempotency,
    parse_dsc_status_output,
)
from lucidfence.core.policies import Policy


class _Device:
    device_id = "win-dsc-001"
    name = "Test Windows Device"
    platform = "windows"


class TestWindowsConformidadDSC(unittest.TestCase):
    def setUp(self):
        self.policy = Policy(
            id="pol-offshift-outside",
            name="Fuera de geocerca fuera de turno",
            description="Dispositivo fuera de su geocerca permitida y fuera del turno asignado.",
            severity="high",
            enabled=True,
            when=[
                {"field": "fence_state", "op": "eq", "value": "outside"},
                {"field": "signal:shift_match.shift_match", "op": "eq", "value": False},
            ],
            actions=[
                {"action": "notify", "params": {"channel": "security", "msg": "Out of geofence"}},
                {"action": "lock", "params": {}},
            ],
        )

    def test_dsc_v3_manifest_generation(self):
        """Verify DSC v3 document manifest structure and content."""
        manifest = generate_dsc_v3_manifest(self.policy)
        self.assertIn("$schema", manifest)
        self.assertIn("resources", manifest)
        self.assertEqual(len(manifest["resources"]), 1)

        resource = manifest["resources"][0]
        self.assertEqual(resource["type"], "LucidFence/GeofenceCompliance")
        self.assertEqual(resource["name"], "LucidFencePolicy_pol-offshift-outside")

        props = resource["properties"]
        self.assertEqual(props["policyId"], "pol-offshift-outside")
        self.assertEqual(props["name"], "Fuera de geocerca fuera de turno")
        self.assertEqual(props["severity"], "high")
        self.assertTrue(props["enabled"])
        self.assertEqual(len(props["when"]), 2)
        self.assertEqual(len(props["actions"]), 2)

    def test_classic_dsc_ps1_generation(self):
        """Verify classic DSC .ps1 generation includes configuration block."""
        ps1 = generate_classic_dsc_ps1(self.policy)
        self.assertIn("Configuration LucidFenceDSC_pol-offshift-outside", ps1)
        self.assertIn("Import-DscResource -ModuleName LucidFenceDSC", ps1)
        self.assertIn('LucidFencePolicy "pol-offshift-outside"', ps1)
        self.assertIn('Severity = "high"', ps1)
        self.assertIn("Enabled = $true", ps1)
        self.assertIn("Ensure = \"Present\"", ps1)

    def test_classic_dsc_mof_generation(self):
        """Verify classic DSC .mof generation includes standard MOF instances."""
        mof = generate_classic_dsc_mof(self.policy)
        self.assertIn("instance of LucidFencePolicy as $LucidFencePolicy1", mof)
        self.assertIn('PolicyId = "pol-offshift-outside";', mof)
        self.assertIn('Severity = "high";', mof)
        self.assertIn("Enabled = true;", mof)
        self.assertIn('ModuleName = "LucidFenceDSC";', mof)

    def test_idempotency_test_set_semantics(self):
        """Verify Test/Set semantics for checking unchanged policies."""
        # Current state perfectly matches desired state
        current_properties = {
            "policyId": "pol-offshift-outside",
            "name": "Fuera de geocerca fuera de turno",
            "description": "Dispositivo fuera de su geocerca permitida y fuera del turno asignado.",
            "severity": "high",
            "enabled": True,
            "when": [
                {"field": "fence_state", "op": "eq", "value": "outside"},
                {"field": "signal:shift_match.shift_match", "op": "eq", "value": False},
            ],
            "actions": [
                {"action": "notify", "params": {"channel": "security", "msg": "Out of geofence"}},
                {"action": "lock", "params": {}},
            ],
        }
        self.assertTrue(verify_policy_idempotency(current_properties, self.policy))

        # Change in severity (should be detected as drift)
        drift_properties = dict(current_properties, severity="critical")
        self.assertFalse(verify_policy_idempotency(drift_properties, self.policy))

        # Change in enabled status (should be detected as drift)
        drift_properties = dict(current_properties, enabled=False)
        self.assertFalse(verify_policy_idempotency(drift_properties, self.policy))

        # Change in policyId (should be detected as drift)
        drift_properties = dict(current_properties, policyId="pol-other")
        self.assertFalse(verify_policy_idempotency(drift_properties, self.policy))

        # Change in structure: when block (should be detected as drift)
        drift_properties = dict(current_properties, when=[])
        self.assertFalse(verify_policy_idempotency(drift_properties, self.policy))

    def test_parse_dsc_status_output_v3(self):
        """Verify parsing of DSC v3 JSON status output."""
        v3_output = {
            "results": [
                {
                    "name": "LucidFencePolicy_pol-offshift-outside",
                    "type": "LucidFence/GeofenceCompliance",
                    "status": "InDesiredState",
                    "inDesiredState": True,
                    "properties": {
                        "policyId": "pol-offshift-outside",
                        "compliant": True,
                    }
                }
            ]
        }
        parsed = parse_dsc_status_output(json.dumps(v3_output))
        self.assertTrue(parsed["compliant"])
        self.assertEqual(parsed["policy_id"], "pol-offshift-outside")
        self.assertEqual(parsed["mode"], "dsc")

        # Non-compliant case
        v3_output_non_compliant = {
            "results": [
                {
                    "name": "LucidFencePolicy_pol-offshift-outside",
                    "type": "LucidFence/GeofenceCompliance",
                    "status": "NotDesiredState",
                    "inDesiredState": False,
                    "properties": {
                        "policyId": "pol-offshift-outside",
                        "compliant": False,
                    }
                }
            ]
        }
        parsed = parse_dsc_status_output(json.dumps(v3_output_non_compliant))
        self.assertFalse(parsed["compliant"])

    def test_parse_dsc_status_output_classic(self):
        """Verify parsing of classic DSC JSON status output."""
        classic_output = [
            {
                "ResourceName": "LucidFencePolicy",
                "PolicyId": "pol-offshift-outside",
                "InDesiredState": True,
                "InCompliance": True,
            }
        ]
        parsed = parse_dsc_status_output(json.dumps(classic_output))
        self.assertTrue(parsed["compliant"])
        self.assertEqual(parsed["policy_id"], "pol-offshift-outside")
        self.assertEqual(parsed["mode"], "dsc_v2")

    def test_parse_dsc_status_output_plaintext(self):
        """Verify parsing of plain-text DSC status outputs (PowerShell console outputs)."""
        stdout_compliant = "ResourceName : LucidFencePolicy\nInDesiredState : True\nInCompliance : True"
        parsed = parse_dsc_status_output(stdout_compliant)
        self.assertTrue(parsed["compliant"])

        stdout_non_compliant = "ResourceName : LucidFencePolicy\nInDesiredState : False\nInCompliance : False"
        parsed = parse_dsc_status_output(stdout_non_compliant)
        self.assertFalse(parsed["compliant"])

    def test_adapter_supports_dsc(self):
        """Verify WindowsConformidadAdapter advertises DSC support."""
        adapter = WindowsConformidadAdapter()
        self.assertTrue(hasattr(adapter, "supports_dsc"))
        self.assertTrue(adapter.supports_dsc)
        self.assertIn("apply_dsc", adapter.SUPPORTED_ACTIONS)

    def test_adapter_apply_dsc(self):
        """Verify apply_dsc action on adapter generates expected documents."""
        adapter = WindowsConformidadAdapter()
        device = _Device()

        # Test dry-run
        res_dry = adapter.execute(device, "apply_dsc", {"policy": self.policy}, dry_run=True)
        self.assertTrue(res_dry["ok"])
        self.assertEqual(res_dry["mode"], "dry_run")
        self.assertEqual(res_dry["action"], "apply_dsc")
        self.assertIn("dsc_v3", res_dry)
        self.assertIn("dsc_classic_ps1", res_dry)
        self.assertIn("dsc_classic_mof", res_dry)

        # Test mock execution
        res_mock = adapter.execute(device, "apply_dsc", {"policy": self.policy}, dry_run=False)
        self.assertTrue(res_mock["ok"])
        self.assertEqual(res_mock["mode"], "mock")
        self.assertTrue(res_mock["applied"])
        self.assertIn("dsc_v3", res_mock)

    def test_adapter_report_compliance_readback(self):
        """Verify report action with dsc_status_output parameter correctly parses and updates state."""
        adapter = WindowsConformidadAdapter()
        device = _Device()

        v3_output = {
            "results": [
                {
                    "name": "LucidFencePolicy_pol-offshift-outside",
                    "status": "InDesiredState",
                    "inDesiredState": True,
                    "properties": {
                        "policyId": "pol-offshift-outside",
                    }
                }
            ]
        }

        # Execute report with DSC status input
        report = adapter.execute(device, "report", {"dsc_status_output": json.dumps(v3_output)})
        self.assertTrue(report["ok"])
        self.assertEqual(report["count"], 1)

        dev_report = report["devices"][0]
        self.assertTrue(dev_report["compliant"])
        self.assertIn("geofence_compliance", dev_report)
        self.assertEqual(dev_report["geofence_compliance"]["policy_id"], "pol-offshift-outside")


if __name__ == "__main__":
    unittest.main()
