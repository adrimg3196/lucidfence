"""Tests for WindowsConformidadAdapter (issue #21).

Validates the read-only report contract:
- mock mode returns deterministic synthetic report
- dry_run never issues HTTP
- live mode without creds returns ok=False with auth_error
- unsupported actions return structured error
- report always includes required keys
"""

from __future__ import annotations

import sys
sys.path.insert(0, ".")

from core.adapters import WindowsConformidadAdapter


class _Device:
    device_id = "win-001"
    name = "Surface Pro 9"
    platform = "windows"


class _DictDevice(dict):
    def __init__(self):
        super().__init__(device_id="win-002", name="Dict Win device", platform="windows")


def check(cond, msg):
    assert cond, f"FAIL: {msg}"


def test_mock_report_shape():
    a = WindowsConformidadAdapter()
    out = a.execute(_Device(), "report", {})
    check(out["ok"] is True, f"mock report should succeed: {out!r}")
    check(out["mode"] == "mock", f"mode should be mock: {out!r}")
    check("count" in out and out["count"] == 1, f"count should be 1: {out!r}")
    check("devices" in out and isinstance(out["devices"], list), f"devices list missing: {out!r}")
    d = out["devices"][0]
    check(d["device_id"] == "win-001", f"device_id passthrough failed: {d!r}")
    check("compliant" in d and isinstance(d["compliant"], bool), f"compliant must be bool: {d!r}")
    check("encrypted" in d and isinstance(d["encrypted"], bool), f"encrypted must be bool: {d!r}")
    check("summary" in out and "policy_id" in out["summary"], f"summary.policy_id missing: {out!r}")


def test_dict_device_input():
    a = WindowsConformidadAdapter()
    out = a.execute(_DictDevice(), "report", {})
    check(out["ok"] is True, f"dict device should work: {out!r}")
    check(out["devices"][0]["device_id"] == "win-002", f"dict device_id not picked up: {out!r}")


def test_unsupported_action_returns_structured_error():
    a = WindowsConformidadAdapter()
    for bad in ("lock", "wipe", "message", "reboot"):
        out = a.execute(_Device(), bad, {})
        check(out["ok"] is False, f"{bad} should fail: {out!r}")
        check(out.get("error_type") == "unsupported_action",
              f"{bad} should map to unsupported_action: {out!r}")


def test_dry_run_does_not_call_http():
    a = WindowsConformidadAdapter(live=True, tenant_id="t", client_id="c", client_secret="s")
    out = a.execute(_Device(), "report", {}, dry_run=True)
    check(out["ok"] is True, f"dry_run should succeed: {out!r}")
    check(out.get("mode") == "dry_run", f"expected dry_run mode: {out!r}")
    check("would_send" in out, f"dry_run should expose would_send: {out!r}")
    ws = out["would_send"]
    check(ws.get("method") == "GET", f"GET expected, got {ws!r}")
    check("managedDevices" in ws.get("url", ""), f"URL should hit managedDevices: {ws!r}")


def test_live_no_creds_returns_auth_error():
    a = WindowsConformidadAdapter(live=True)
    out = a.execute(_Device(), "report", {})
    check(out["ok"] is False, f"live without creds should fail: {out!r}")
    check(out.get("error_type") == "auth_error", f"auth_error expected: {out!r}")


def test_deterministic_mock_per_device():
    """Mock should be deterministic for the same device_id (callers can assert)."""
    a = WindowsConformidadAdapter()
    out1 = a.execute(_Device(), "report", {})
    out2 = a.execute(_Device(), "report", {})
    check(out1["devices"][0]["compliant"] == out2["devices"][0]["compliant"],
          f"non-deterministic mock: {out1['devices'][0]} vs {out2['devices'][0]}")
    check(out1["devices"][0]["encrypted"] == out2["devices"][0]["encrypted"],
          f"non-deterministic mock: {out1['devices'][0]} vs {out2['devices'][0]}")


def test_build_from_config_helper():
    from core.adapters import build_windows_conformidad_adapter_from_config
    a = build_windows_conformidad_adapter_from_config({
        "mdm": {"windows": {"live": True, "tenant_id": "t-uuid", "client_id": "c",
                            "client_secret": "s"}}
    })
    check(a.live is True, f"live flag not propagated: {a!r}")
    check(a.tenant_id == "t-uuid", f"tenant_id not propagated: {a!r}")


if __name__ == "__main__":
    tests = [
        test_mock_report_shape,
        test_dict_device_input,
        test_unsupported_action_returns_structured_error,
        test_dry_run_does_not_call_http,
        test_live_no_creds_returns_auth_error,
        test_deterministic_mock_per_device,
        test_build_from_config_helper,
    ]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"ERROR {t.__name__}: {exc!r}")
    print(f"\n{'OK' if failures == 0 else f'{failures} FAILURES'} ({len(tests)} windows tests)")
    sys.exit(0 if failures == 0 else 1)