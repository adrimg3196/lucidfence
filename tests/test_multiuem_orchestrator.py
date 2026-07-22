from datetime import datetime, timedelta, timezone
from threading import Event, Thread

from core.multiuem import (
    LocationEvidence,
    MultiUEMOrchestrator,
    NormalizedDevice,
    ProviderBinding,
    ProviderCapabilities,
    ProviderHealth,
)


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def device(
    provider,
    remote_id,
    *,
    serial=None,
    imei=None,
    compliant=None,
    location=None,
    inventory=None,
    name=None,
):
    return NormalizedDevice(
        canonical_id=f"{provider}:{remote_id}",
        provider=provider,
        provider_device_id=remote_id,
        name=name or remote_id,
        platform="ios",
        serial_number=serial,
        imei=imei,
        compliant=compliant,
        location=location,
        inventory=inventory or {},
    )


def binding(name, devices_or_fetch, *, actions=frozenset(), execute=None):
    fetch = devices_or_fetch if callable(devices_or_fetch) else lambda: devices_or_fetch
    return ProviderBinding(
        name=name,
        capabilities=ProviderCapabilities(location=True, actions=actions),
        fetch_devices=fetch,
        execute_action=execute,
    )


def evidence(provider, observed_at, accuracy=25):
    return LocationEvidence(40.42, -3.71, observed_at, accuracy, provider, "gps")


def assert_value_error(expected, callback):
    try:
        callback()
    except ValueError as exc:
        assert str(exc) == expected
    else:
        raise AssertionError("ValueError not raised")


def test_constructor_rejects_invalid_or_duplicate_bindings_deterministically():
    valid = binding("intune", [])
    invalid_names = [None, "", "Intune", "intune!", "íntune", "-intune"]
    for invalid_name in invalid_names:
        malformed = ProviderBinding(
            name=invalid_name,
            capabilities=ProviderCapabilities(),
            fetch_devices=lambda: [],
        )
        assert_value_error(
            "invalid provider name at index 0",
            lambda malformed=malformed: MultiUEMOrchestrator([malformed]),
        )

    assert_value_error(
        "duplicate provider name: intune",
        lambda: MultiUEMOrchestrator([valid, valid]),
    )
    assert_value_error(
        "invalid capabilities for provider intune",
        lambda: MultiUEMOrchestrator([
            ProviderBinding("intune", None, lambda: []),
        ]),
    )
    assert_value_error(
        "invalid fetch_devices callback for provider intune",
        lambda: MultiUEMOrchestrator([
            ProviderBinding("intune", ProviderCapabilities(), None),
        ]),
    )
    assert_value_error(
        "invalid execute_action callback for provider intune",
        lambda: MultiUEMOrchestrator([
            ProviderBinding("intune", ProviderCapabilities(), lambda: [], "not-callable"),
        ]),
    )


def test_sync_isolates_sanitized_failure_and_merges_strong_identity_deterministically():
    stale = evidence("applivery", (NOW - timedelta(seconds=901)).isoformat(), 10)
    fresh = evidence("intune", NOW.isoformat(), 30)

    def fail():
        raise TimeoutError("token=must-not-leak")

    orchestrator = MultiUEMOrchestrator(
        [
            binding("jamf", fail),
            binding(
                "intune",
                [device("intune", "b-7", serial="ser1", compliant=True, location=fresh,
                        inventory={"department": "ops"})],
            ),
            binding(
                "applivery",
                [device("applivery", "a-1", serial="SER-1", compliant=False, location=stale,
                        inventory={"owner": "alice"})],
            ),
        ],
        max_location_age_seconds=900,
        max_accuracy_m=500,
    )

    result = orchestrator.sync(now=NOW)

    assert len(result.devices) == 1
    merged = result.devices[0]
    assert merged.provider_refs == {"applivery": "a-1", "intune": "b-7"}
    assert merged.location.provider == "intune"
    assert merged.compliant is False
    assert merged.inventory == {"department": "ops", "owner": "alice"}
    assert merged.provenance["department"] == "intune"
    assert merged.provenance["owner"] == "applivery"
    assert result.health["jamf"].status == "error"
    assert result.health["jamf"].detail == "TimeoutError"
    assert "token=" not in result.health["jamf"].detail
    assert result.status == "degraded"


def test_placeholder_identities_never_merge():
    result = MultiUEMOrchestrator(
        [
            binding("applivery", [device("applivery", "a", serial="N/A")]),
            binding("intune", [device("intune", "b", serial="N/A")]),
        ]
    ).sync(now=NOW)

    assert len(result.devices) == 2
    assert all(not item.identity_conflict for item in result.devices)


def test_cross_key_conflict_never_merges_and_marks_every_involved_record():
    records = [
        binding("alpha", [device("alpha", "a", serial="SER-1")]),
        binding("beta", [device("beta", "b", imei="IMEI-1")]),
        binding("bridge", [device("bridge", "c", serial="SER-1", imei="IMEI-1")]),
    ]

    forward = MultiUEMOrchestrator(records).sync(now=NOW).devices
    reverse = MultiUEMOrchestrator(list(reversed(records))).sync(now=NOW).devices

    assert len(forward) == len(reverse) == 3
    assert all(item.identity_conflict for item in forward)
    assert [(d.canonical_id, d.identity_conflict) for d in forward] == [
        (d.canonical_id, d.identity_conflict) for d in reverse
    ]


def test_merge_uses_parsed_timestamps_and_provider_ties_not_binding_order():
    # 12:00+02:00 is 10:00 UTC, so the lexicographically smaller 11:00Z is newer.
    alpha = device(
        "alpha", "1", serial="S-1", compliant=None,
        location=evidence("alpha", "2026-07-22T12:00:00+02:00", 5),
        inventory={"owner": "alpha-value"},
    )
    beta = device(
        "beta", "2", serial="S-1", compliant=True,
        location=evidence("beta", "2026-07-22T11:00:00Z", 20),
        inventory={"owner": "beta-value"},
    )

    first = MultiUEMOrchestrator([binding("beta", [beta]), binding("alpha", [alpha])]).sync(NOW)
    second = MultiUEMOrchestrator([binding("alpha", [alpha]), binding("beta", [beta])]).sync(NOW)

    for merged in (first.devices[0], second.devices[0]):
        assert merged.location.provider == "beta"
        assert merged.inventory["owner"] == "alpha-value"
        assert merged.provenance["owner"] == "alpha"
        assert merged.compliant is True
        assert merged.provider_refs == {"alpha": "1", "beta": "2"}
    assert first.devices[0].canonical_id == second.devices[0].canonical_id


def test_location_tie_prefers_accuracy_then_provider_name():
    same_time = NOW.isoformat()
    devices = [
        device("zeta", "z", serial="S", location=evidence("zeta", same_time, 10)),
        device("beta", "b", serial="S", location=evidence("beta", same_time, 5)),
        device("alpha", "a", serial="S", location=evidence("alpha", same_time, 5)),
    ]
    result = MultiUEMOrchestrator(
        [binding(item.provider, [item]) for item in reversed(devices)]
    ).sync(NOW)

    assert result.devices[0].location.provider == "alpha"


def test_fetch_returns_location_reports_with_routing_metadata_and_rejected_coordinates_omitted():
    stale = device(
        "alpha",
        "remote-1",
        serial="SER",
        location=evidence("alpha", (NOW - timedelta(days=1)).isoformat(), 10),
    )
    orchestrator = MultiUEMOrchestrator(
        [binding("alpha", [stale])], max_location_age_seconds=900
    )

    reports = orchestrator.fetch(now=NOW)

    assert len(reports) == 1
    report = reports[0]
    assert report.device_id == "alpha:remote-1"
    assert report.lat is None and report.lng is None
    assert report.raw["provider"] == "alpha"
    assert report.raw["provider_device_id"] == "remote-1"
    assert report.raw["provider_refs"] == {"alpha": "remote-1"}
    assert report.raw["location_quality"] == "rejected"
    assert report.raw["location_rejection_reason"] == "stale"


def test_execute_routes_remote_provider_id_and_preserves_dry_run():
    calls = []

    def execute(remote_id, action, params, dry_run):
        calls.append((remote_id, action, params, dry_run))
        return {"ok": True, "request_id": "safe-id"}

    orchestrator = MultiUEMOrchestrator(
        [binding("intune", [], actions=frozenset({"lock"}), execute=execute)]
    )
    response = orchestrator.execute(
        {
            "device_id": "canonical-1",
            "provider": "intune",
            "provider_device_id": "b-7",
        },
        "lock",
        {},
        dry_run=True,
    )

    assert calls == [("b-7", "lock", {}, True)]
    assert response == {"ok": True, "adapter": "intune"}


def test_execute_uses_provider_refs_for_merged_device():
    calls = []

    def execute(remote_id, action, params, dry_run):
        calls.append(remote_id)
        return {"ok": True}

    merged = device("applivery", "a-1", serial="S")
    merged.provider_refs = {"applivery": "a-1", "intune": "b-7"}
    orchestrator = MultiUEMOrchestrator(
        [binding("intune", [], actions=frozenset({"wipe"}), execute=execute)]
    )

    response = orchestrator.execute(merged, "wipe", {"reason": "lost"})

    assert calls == ["b-7"]
    assert response["adapter"] == "intune"


def test_execute_dict_routes_by_capability_and_uses_target_provider_reference():
    calls = []

    def execute(remote_id, action, params, dry_run):
        calls.append(remote_id)
        return {"ok": True}

    orchestrator = MultiUEMOrchestrator(
        [
            binding("applivery", [], actions=frozenset({"lock"}), execute=lambda *args: None),
            binding("intune", [], actions=frozenset({"wipe"}), execute=execute),
        ]
    )

    response = orchestrator.execute(
        {
            "provider": "applivery",
            "provider_device_id": "a-1",
            "provider_refs": {"applivery": "a-1", "intune": "b-7"},
        },
        "wipe",
        {},
    )

    assert calls == ["b-7"]
    assert response == {"ok": True, "adapter": "intune"}


def test_execute_capability_gate_rejects_unsupported_action_without_calling_provider():
    calls = []
    orchestrator = MultiUEMOrchestrator(
        [binding("intune", [], actions=frozenset({"lock"}), execute=lambda *args: calls.append(args))]
    )

    response = orchestrator.execute(
        {"provider": "intune", "provider_device_id": "b-7"}, "wipe", {}
    )

    assert calls == []
    assert response == {
        "ok": False,
        "error_type": "unsupported_action",
        "adapter": "intune",
    }


def test_execute_rejects_non_boolean_ok_and_sanitizes_callback_response():
    responses = [
        {"ok": "yes", "token": "secret"},
        {
            "ok": False,
            "adapter": "forged",
            "action": "lock",
            "mode": "delegated",
            "dry_run": True,
            "delegated": True,
            "error_type": "remote_error",
            "http_status": 409,
            "body": "token=secret",
            "headers": {"authorization": "secret"},
            "request": {"password": "secret"},
            "message": "secret",
        },
    ]

    def execute(*args):
        return responses.pop(0)

    orchestrator = MultiUEMOrchestrator(
        [binding("intune", [], actions=frozenset({"lock"}), execute=execute)]
    )

    invalid = orchestrator.execute(
        {"provider": "intune", "provider_device_id": "b-7"}, "lock", {}
    )
    sanitized = orchestrator.execute(
        {"provider": "intune", "provider_device_id": "b-7"}, "lock", {}
    )

    assert invalid == {"ok": False, "error_type": "invalid_response", "adapter": "intune"}
    assert sanitized == {
        "ok": False,
        "adapter": "intune",
        "action": "lock",
        "mode": "delegated",
        "dry_run": True,
        "delegated": True,
        "error_type": "remote_error",
        "http_status": 409,
    }


def test_execute_deepcopies_params_and_detaches_returned_response():
    retained = {}

    def execute(remote_id, action, params, dry_run):
        params["nested"]["changed"] = True
        response = {"ok": True, "mode": "delegated"}
        retained["response"] = response
        return response

    params = {"nested": {"changed": False}}
    orchestrator = MultiUEMOrchestrator(
        [binding("intune", [], actions=frozenset({"lock"}), execute=execute)]
    )

    result = orchestrator.execute(
        {"provider": "intune", "provider_device_id": "b-7"}, "lock", params
    )
    retained["response"]["mode"] = "mutated"

    assert params == {"nested": {"changed": False}}
    assert result == {"ok": True, "adapter": "intune", "mode": "delegated"}


def test_execute_unknown_provider_and_provider_failure_are_structured_and_sanitized():
    orchestrator = MultiUEMOrchestrator([])
    unknown = orchestrator.execute(
        {"provider": "missing", "provider_device_id": "x"}, "lock", {}
    )
    assert unknown == {
        "ok": False,
        "error_type": "unknown_provider",
        "adapter": "missing",
    }

    def fail(*args):
        raise RuntimeError("token=must-not-leak")

    failing = MultiUEMOrchestrator(
        [binding("intune", [], actions=frozenset({"lock"}), execute=fail)]
    ).execute({"provider": "intune", "provider_device_id": "b-7"}, "lock", {})
    assert failing == {
        "ok": False,
        "error_type": "provider_error",
        "adapter": "intune",
    }
    assert "token=" not in str(failing)


def test_sync_status_is_error_when_every_provider_fails_and_health_is_cached():
    def fail_value():
        raise ValueError("secret")

    def fail_runtime():
        raise RuntimeError("secret")

    orchestrator = MultiUEMOrchestrator(
        [binding("a", fail_value), binding("b", fail_runtime)]
    )
    result = orchestrator.sync(NOW)

    assert result.status == "error"
    assert orchestrator.health() == result.health


def test_sync_with_zero_bindings_is_explicit_error():
    result = MultiUEMOrchestrator([]).sync(NOW)

    assert result.status == "error"
    assert result.health == {}


def test_sync_result_and_health_are_detached_from_cached_state():
    orchestrator = MultiUEMOrchestrator([binding("intune", [])])

    result = orchestrator.sync(NOW)
    result.health.clear()
    health = orchestrator.health()
    health.clear()

    assert orchestrator.health() == {"intune": ProviderHealth("ok", 0)}


def test_concurrent_syncs_publish_health_in_execution_order():
    first_started = Event()
    second_started = Event()
    release_first = Event()
    calls = 0

    def fetch():
        nonlocal calls
        calls += 1
        call = calls
        if call == 1:
            first_started.set()
            assert release_first.wait(2)
        else:
            second_started.set()
        return [device("intune", str(index)) for index in range(call)]

    orchestrator = MultiUEMOrchestrator([binding("intune", fetch)])
    first = Thread(target=lambda: orchestrator.sync(NOW))
    second = Thread(target=lambda: orchestrator.sync(NOW))

    first.start()
    assert first_started.wait(2)
    second.start()
    serialized = not second_started.wait(0.1)
    release_first.set()
    first.join(2)
    second.join(2)

    assert serialized
    assert not first.is_alive() and not second.is_alive()
    assert calls == 2
    assert orchestrator.health()["intune"].devices == 2
