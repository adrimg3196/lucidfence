"""Tests for ChromeOSAdapter (issue #20).

Validates the read-only report contract on Google's Admin SDK / Directory API
path:
- mock mode returns deterministic synthetic report
- dry_run never issues HTTP
- live mode without creds returns ok=False with auth_error
- unsupported actions return structured error
- response shape includes required keys
"""

from __future__ import annotations

import sys
sys.path.insert(0, ".")

from core.adapters import ChromeOSAdapter


class _Device:
    device_id = "croso-001"
    name = "Pixelbook Go"
    platform = "chromeos"


class _DictDevice(dict):
    def __init__(self):
        super().__init__(device_id="croso-002", name="Dict Chromebook", platform="chromeos")


def check(cond, msg):
    assert cond, f"FAIL: {msg}"


def test_mock_report_shape():
    a = ChromeOSAdapter()
    out = a.execute(_Device(), "report", {})
    check(out["ok"] is True, f"mock report should succeed: {out!r}")
    check(out["mode"] == "mock", f"mode should be mock: {out!r}")
    check("count" in out and out["count"] == 1, f"count should be 1: {out!r}")
    check("devices" in out and isinstance(out["devices"], list), f"devices list missing: {out!r}")
    d = out["devices"][0]
    check(d["device_id"] == "croso-001", f"device_id passthrough failed: {d!r}")
    check("compliant" in d and isinstance(d["compliant"], bool), f"compliant must be bool: {d!r}")
    check("verified_boot" in out["summary"], f"summary.verified_boot missing: {out!r}")


def test_dict_device_input():
    a = ChromeOSAdapter()
    out = a.execute(_DictDevice(), "report", {})
    check(out["ok"] is True, f"dict device should work: {out!r}")
    check(out["devices"][0]["device_id"] == "croso-002", f"dict device_id not picked up: {out!r}")


def test_unsupported_action_returns_structured_error():
    a = ChromeOSAdapter()
    for bad in ("lock", "wipe", "message", "locate"):
        out = a.execute(_Device(), bad, {})
        check(out["ok"] is False, f"{bad} should fail: {out!r}")
        check(out.get("error_type") == "unsupported_action",
              f"{bad} should map to unsupported_action: {out!r}")


def test_dry_run_does_not_call_http():
    a = ChromeOSAdapter(
        live=True, refresh_token="rt", client_id="cid", client_secret="csec"
    )
    out = a.execute(_Device(), "report", {}, dry_run=True)
    check(out["ok"] is True, f"dry_run should succeed: {out!r}")
    check(out.get("mode") == "dry_run", f"expected dry_run mode: {out!r}")
    check("would_send" in out, f"dry_run should expose would_send: {out!r}")
    ws = out["would_send"]
    check(ws.get("method") == "GET", f"GET expected, got {ws!r}")
    check("/chromeos" in ws.get("url", ""), f"URL should hit chromeos: {ws!r}")


def test_live_no_creds_returns_auth_error():
    a = ChromeOSAdapter(live=True)
    out = a.execute(_Device(), "report", {})
    check(out["ok"] is False, f"live without creds should fail: {out!r}")
    check(out.get("error_type") == "auth_error", f"auth_error expected: {out!r}")


def test_deterministic_mock_per_device():
    a = ChromeOSAdapter()
    out1 = a.execute(_Device(), "report", {})
    out2 = a.execute(_Device(), "report", {})
    check(out1["devices"][0]["compliant"] == out2["devices"][0]["compliant"],
          f"non-deterministic mock: {out1['devices'][0]} vs {out2['devices'][0]}")
    check(out1["summary"]["verified_boot"] == out2["summary"]["verified_boot"],
          f"non-deterministic mock: {out1['summary']} vs {out2['summary']}")


def test_build_from_config_helper():
    from core.adapters import build_chromeos_adapter_from_config
    a = build_chromeos_adapter_from_config({
        "mdm": {"chromeos": {"live": True, "refresh_token": "rt", "client_id": "cid",
                             "client_secret": "csec", "customer_id": "C0123"}}
    })
    check(a.live is True, f"live flag not propagated: {a!r}")
    check(a.refresh_token == "rt", f"refresh_token not propagated: {a!r}")
    check(a.customer_id == "C0123", f"customer_id not propagated: {a!r}")


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
    print(f"\n{'OK' if failures == 0 else f'{failures} FAILURES'} ({len(tests)} chromeos tests)")
    sys.exit(0 if failures == 0 else 1)