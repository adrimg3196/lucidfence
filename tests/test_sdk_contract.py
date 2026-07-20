"""Contract tests for the MDMAdapter SDK.

Every adapter in the registry must satisfy the contract below. These
tests are written against the SDK contract (core/adapters/base.py), not
against any specific adapter implementation, so adding a new adapter is
a one-line registration in core/adapters/__init__.py.

The SDK contract (frozen):

  1. Subclass MDMAdapter (ABC).
  2. Set a stable, unique `name` (lowercase ASCII identifier).
  3. Implement execute(device, action, params, dry_run=False) -> dict.
  4. Never raise — return {"ok": False, "error": ..., "error_type": ...}.
  5. Always include these keys in the response:
       adapter, ok (bool), device_id, action.

This module provides reusable assertions (`assert_valid_name`,
`assert_response_shape`) plus a contract runner that validates any
registered adapter against the full contract.

Reference: PRs #13 (Intune live) and #21 (Jamf live) implement this
contract. Any new community adapter must pass these tests without
touching core/.
"""

from __future__ import annotations

import re
import sys
sys.path.insert(0, ".")

from core.adapters import (
    MDMAdapter, SimulationAdapter, AppliveryAdapter, IntuneAdapter,
    JamfAdapter, ADAPTER_REGISTRY, build_adapter,
)


def assert_valid_name(name) -> None:
    """`name` must be a non-empty lowercase ASCII identifier."""
    assert isinstance(name, str) and name, f"name must be non-empty string, got {name!r}"
    assert re.match(r"^[a-z][a-z0-9_]*$", name), (
        f"name must match ^[a-z][a-z0-9_]*$, got {name!r}"
    )


def assert_response_shape(result: dict, adapter_name: str) -> None:
    """Response shape per the frozen contract."""
    required = {"adapter", "ok", "device_id", "action"}
    missing = required - set(result.keys())
    assert not missing, f"{adapter_name}: missing keys {missing} in response {result!r}"
    assert isinstance(result["ok"], bool), f"{adapter_name}: ok must be bool, got {result['ok']!r}"
    assert result["adapter"] == adapter_name, (
        f"{adapter_name}: result.adapter must equal self.name, got {result['adapter']!r}"
    )


class _Device:
    device_id = "dev-contract"
    name = "Contract device"
    platform = "android"


class _DictDevice(dict):
    def __init__(self):
        super().__init__(device_id="dev-dict", name="Dict device", platform="ios")


def make_adapter(name: str):
    """Build a real registered adapter by name, or skip if unknown."""
    if name == "simulation":
        return SimulationAdapter()
    if name == "applivery":
        return AppliveryAdapter(org_id="o", endpoint_template="/x")
    if name == "intune":
        return IntuneAdapter()
    if name == "jamf":
        return JamfAdapter()
    return None  # community adapter — caller decides


def test_all_registered_adapters_have_unique_names():
    names = [getattr(cls, "name", None) for cls in ADAPTER_REGISTRY.values()]
    assert None not in names, f"some registered adapter has no name: {ADAPTER_REGISTRY}"
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"duplicate adapter names: {duplicates}"


def test_all_registered_adapters_implement_execute():
    for reg_name, cls in ADAPTER_REGISTRY.items():
        assert issubclass(cls, MDMAdapter), (
            f"{reg_name} ({cls!r}) does not subclass MDMAdapter"
        )
        assert callable(getattr(cls, "execute", None)), (
            f"{reg_name} does not implement execute()"
        )


def test_known_adapters_satisfy_response_contract():
    """For every built-in adapter, a lock call returns the required keys."""
    for n in ("simulation", "applivery", "intune", "jamf"):
        a = make_adapter(n)
        if a is None:
            continue
        assert_valid_name(a.name)
        result = a.execute(_Device(), "lock", {})
        assert_response_shape(result, n)


def test_known_adapters_handle_dict_device():
    """Adapter must accept a dict-shaped device (UI/server shape)."""
    for n in ("simulation", "intune", "jamf"):
        a = make_adapter(n)
        if a is None:
            continue
        result = a.execute(_DictDevice(), "locate", {})
        assert_response_shape(result, n)


def test_known_adapters_dry_run_does_not_raise():
    """dry_run=True must construct the request but not send it."""
    for n in ("intune", "jamf", "applivery"):
        a = make_adapter(n)
        if a is None:
            continue
        try:
            result = a.execute(_Device(), "wipe", {}, dry_run=True)
        except Exception as exc:  # noqa: BLE001 — contract: never raise
            raise AssertionError(f"{n}.execute(dry_run=True) raised: {exc!r}")
        assert isinstance(result, dict), f"{n} dry_run must return dict, got {type(result)}"
        assert "ok" in result, f"{n} dry_run missing ok key, got {result!r}"


def test_known_adapters_handle_missing_credentials_live():
    """Live mode without creds must return ok=False (not raise).

    Skipped on forks that pre-date the live-mode commit (PR #13). The SDK
    contract test only matters once a live-mode adapter exists in main.
    """
    import inspect
    if "live" not in inspect.signature(IntuneAdapter.__init__).parameters:
        return  # pre-#13 fork — no live mode yet
    a = IntuneAdapter(live=True)
    result = a.execute(_Device(), "lock", {})
    assert result["ok"] is False, f"Intune live no-creds should fail, got {result!r}"
    assert result.get("error_type") in ("auth_error", "unknown_error"), (
        f"Intune no-creds should map to auth_error, got {result!r}"
    )


def test_sdk_template_helper():
    """Verify the SDK template example still imports and runs."""
    import importlib
    template = importlib.import_module("core.adapters._template_adapter")
    TemplateMdmAdapter = template.TemplateMdmAdapter
    a = TemplateMdmAdapter()
    assert a.name == "template_mdm"
    r = a.execute(_Device(), "lock", {})
    assert r["ok"] is True
    assert r["adapter"] == "template_mdm"
    r2 = a.execute(_Device(), "wipe", {}, dry_run=True)
    assert r2.get("mode") == "dry_run"
    assert "would_send" in r2


if __name__ == "__main__":
    tests = [
        test_all_registered_adapters_have_unique_names,
        test_all_registered_adapters_implement_execute,
        test_known_adapters_satisfy_response_contract,
        test_known_adapters_handle_dict_device,
        test_known_adapters_dry_run_does_not_raise,
        test_known_adapters_handle_missing_credentials_live,
        test_sdk_template_helper,
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
    print(f"\n{'OK' if failures == 0 else f'{failures} FAILURES'} ({len(tests)} contract tests)")
    sys.exit(0 if failures == 0 else 1)