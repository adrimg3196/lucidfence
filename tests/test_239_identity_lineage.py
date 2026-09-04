from datetime import datetime, timezone
from tempfile import TemporaryDirectory

from lucidfence.core.engine import Engine
from lucidfence.core.cloud_publisher import serialize
from lucidfence.core.multiuem import MultiUEMOrchestrator, NormalizedDevice, ProviderBinding, ProviderCapabilities
from lucidfence.core.state_store import DeviceState


NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


def device(provider, remote_id, *, serial=None, hardware=None, alias=None, ownership=None, mode=None):
    inventory = {}
    if hardware is not None:
        inventory["hardware_identity"] = hardware
    if alias is not None:
        inventory["asset_alias"] = alias
    return NormalizedDevice(
        canonical_id=f"{provider}:{remote_id}",
        provider=provider,
        provider_device_id=remote_id,
        name=f"{provider}-{remote_id}",
        platform="ios",
        serial_number=serial,
        inventory=inventory,
        ownership=ownership,
        management_mode=mode,
    )


def binding(name, devices):
    return ProviderBinding(name, ProviderCapabilities(), lambda: devices)


def test_same_device_in_two_uems_merges_with_explainable_reversible_lineage():
    result = MultiUEMOrchestrator([
        binding("jamf", [device("jamf", "j-1", serial="SER-1", hardware="hw-1", ownership="company", mode="mdm")]),
        binding("intune", [device("intune", "i-9", serial="ser1", hardware="hw-1", ownership="company", mode="fully_managed")]),
    ]).sync(now=NOW)

    assert len(result.devices) == 1
    merged = result.devices[0]
    assert merged.provider_refs == {"intune": "i-9", "jamf": "j-1"}
    assert merged.identity_graph["primary_identifier"] == {"type": "hardware", "value": "HW1"}
    assert merged.identity_graph["merge_rule"] == "deterministic"
    assert merged.identity_graph["reversible"] is True
    assert merged.identity_graph["precedence"] == ["hardware", "serial", "imei", "uem_id", "alias"]
    assert {edge["source"] for edge in merged.identity_graph["signals"]} == {"jamf", "intune"}
    assert {edge["original_identifier"] for edge in merged.identity_graph["signals"]} >= {"SER-1", "ser1", "j-1", "i-9"}
    assert merged.identity_findings == []


def test_recycled_serial_keeps_devices_separate_and_marks_visible_ambiguity():
    result = MultiUEMOrchestrator([
        binding("jamf", [device("jamf", "j-old", serial="SER-RECYCLED", hardware="hw-old")]),
        binding("intune", [device("intune", "i-new", serial="SER-RECYCLED", hardware="hw-new")]),
    ]).sync(now=NOW)

    assert len(result.devices) == 2
    assert all(item.identity_conflict for item in result.devices)
    findings = [finding for item in result.devices for finding in item.identity_findings]
    assert any(f["type"] == "identity_conflict" and f["reason"] == "conflicting_hardware" for f in findings)


def test_restored_device_and_uem_id_collision_preserve_lineage_without_auto_merging_ambiguous_candidates():
    restored = MultiUEMOrchestrator([
        binding("jamf", [device("jamf", "old-uem", serial="SER-RESTORE", hardware="hw-restored", ownership="employee_owned", mode="user_enrollment")]),
        binding("intune", [device("intune", "new-uem", serial="SER-RESTORE", hardware="hw-restored", ownership="company", mode="fully_managed")]),
    ]).sync(now=NOW).devices[0]
    assert restored.provider_refs == {"intune": "new-uem", "jamf": "old-uem"}
    assert {event["field"] for event in restored.identity_graph["lineage"]} >= {"ownership", "management_mode"}

    collided = MultiUEMOrchestrator([
        binding("jamf", [
            device("jamf", "same-uem-id", serial="SER-A", hardware="hw-a"),
            device("jamf", "same-uem-id", serial="SER-B", hardware="hw-b"),
        ]),
    ]).sync(now=NOW)
    assert len(collided.devices) == 2
    assert all(item.identity_conflict for item in collided.devices)
    assert any(
        finding["reason"] == "colliding_uem_id"
        for item in collided.devices
        for finding in item.identity_findings
    )


def test_alias_only_match_stays_separate_with_visible_review_finding():
    result = MultiUEMOrchestrator([
        binding("jamf", [device("jamf", "j-alias", alias="shared-cart")]),
        binding("intune", [device("intune", "i-alias", alias="shared-cart")]),
    ]).sync(now=NOW)

    assert len(result.devices) == 2
    assert all(item.identity_conflict for item in result.devices)
    assert all(item.identity_graph["merge_rule"] == "separated_for_review" for item in result.devices)
    findings = [finding for item in result.devices for finding in item.identity_findings]
    assert any(finding["reason"] == "ambiguous_alias" for finding in findings)
    assert all(
        any(signal["type"] == "alias" and signal["value"] == "SHAREDCART" for signal in item.identity_graph["signals"])
        for item in result.devices
    )


def test_alias_only_candidate_does_not_join_strong_identity_cluster():
    result = MultiUEMOrchestrator([
        binding("jamf", [
            device("jamf", "j-strong", hardware="hw-1", alias="shared-cart"),
        ]),
        binding("intune", [
            device("intune", "i-strong", hardware="hw-1"),
        ]),
        binding("applivery", [
            device("applivery", "a-alias-only", alias="shared-cart"),
        ]),
    ]).sync(now=NOW)

    assert len(result.devices) == 2
    strong = next(item for item in result.devices if item.provider_refs.get("jamf") == "j-strong")
    alias_only = next(item for item in result.devices if item.provider == "applivery")
    assert strong.provider_refs == {"intune": "i-strong", "jamf": "j-strong"}
    assert "applivery" not in strong.provider_refs
    assert alias_only.identity_conflict is True
    assert any(finding["reason"] == "ambiguous_alias" for finding in alias_only.identity_findings)


def test_engine_temporal_uem_handoff_preserves_prior_identity_lineage():
    with TemporaryDirectory() as tmpdir:
        eng = Engine({"mode": "simulation", "data_dir": tmpdir})
        eng.source = MultiUEMOrchestrator([
            binding("jamf", [
                device(
                    "jamf",
                    "old-uem",
                    hardware="hw-temporal",
                    ownership="employee_owned",
                    mode="user_enrollment",
                )
            ]),
        ])
        eng.run_once()

        eng.source = MultiUEMOrchestrator([
            binding("intune", [
                device(
                    "intune",
                    "new-uem",
                    hardware="hw-temporal",
                    ownership="company",
                    mode="fully_managed",
                )
            ]),
        ])
        eng.run_once()

        snapshot = eng.store.snapshot()
        assert sorted(snapshot) == ["intune:new-uem"]
        handoff = snapshot["intune:new-uem"]
        assert handoff.provider_refs == {"intune": "new-uem", "jamf": "old-uem"}
        assert handoff.identity_lineage["merge_rule"] == "temporal_handoff"
        assert {signal["source"] for signal in handoff.identity_lineage["signals"]} == {"intune", "jamf"}
        assert {event["field"] for event in handoff.identity_lineage["lineage"]} >= {"ownership", "management_mode"}


def test_identity_identifiers_stay_out_of_cloud_snapshot():
    class EngineStub:
        org_id = "demo"
        def status(self):
            return {"fences": [], "incidents": []}
        class Store:
            def snapshot(self):
                return {
                    "asset": DeviceState(
                        device_id="asset-1", name="asset", platform="ios",
                        serial_number="SER-SENSITIVE", imei="IMEI-SENSITIVE",
                        provider_refs={"jamf": "JAMF-SENSITIVE"},
                        identity_lineage={
                            "signals": [{"original_identifier": "SER-SENSITIVE", "source": "jamf"}],
                        },
                    )
                }
        store = Store()

    payload = serialize(EngineStub(), "demo")
    rendered = str(payload)
    assert "SER-SENSITIVE" not in rendered
    assert "IMEI-SENSITIVE" not in rendered
    assert "JAMF-SENSITIVE" not in rendered
    assert "identity_lineage" not in rendered


if __name__ == "__main__":
    test_same_device_in_two_uems_merges_with_explainable_reversible_lineage()
    test_recycled_serial_keeps_devices_separate_and_marks_visible_ambiguity()
    test_restored_device_and_uem_id_collision_preserve_lineage_without_auto_merging_ambiguous_candidates()
    test_alias_only_match_stays_separate_with_visible_review_finding()
    test_alias_only_candidate_does_not_join_strong_identity_cluster()
    test_engine_temporal_uem_handoff_preserves_prior_identity_lineage()
    test_identity_identifiers_stay_out_of_cloud_snapshot()
    print("identity-lineage tests passed")
