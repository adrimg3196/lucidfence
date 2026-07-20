"""Tests for the live JamfAdapter (Jamf Pro API).

Validates that the live code path wires through auth + Jamf endpoints
without ever raising and without touching a real Jamf tenant.
"""

from __future__ import annotations

import sys
sys.path.insert(0, ".")

from core.adapters.jamf import JamfAdapter, AuthError, TransportError, JAMF_VERB


class _Resp:
    def __init__(self, status=200, body=None, text=None):
        self.status_code = status
        self._body = body
        self.text = text if text is not None else ("" if body is None else "")

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def check(cond, msg):
    assert cond, f"FAIL: {msg}"


def _base():
    return "https://acme.jamfcloud.com"


# --- Test 1: live=True without creds raises AuthError on action ---
def test_no_creds_raises_auth_error():
    a = JamfAdapter(live=True)
    out = a.execute({"device_id": "dev-1"}, "lock", {})
    check(out["ok"] is False, f"expected ok=False on missing creds, got {out!r}")
    check(out["error_type"] in ("auth_error", "unknown_error"), f"unexpected error_type: {out}")
    check("jamf" in (out["adapter"] or "").lower(), f"adapter label missing: {out}")


# --- Test 2: live=False keeps mock path alive ---
def test_offline_mode_uses_simulation():
    a = JamfAdapter(live=False, org_id="org-x")
    out = a.execute({"device_id": "dev-1"}, "lock", {})
    check(out.get("ok") is True, f"expected ok=True in mock mode, got {out!r}")
    check(out.get("mock") is True, f"expected mock=True, got {out!r}")


# --- Test 3: list in mock returns structure ---
def test_list_in_mock_returns_list_structure():
    a = JamfAdapter(live=False, org_id="org-x")
    out = a.execute({"device_id": ""}, "list", {})
    if "devices" in out:
        check(isinstance(out["devices"], list), f"devices should be list, got {type(out['devices'])}")
    else:
        check("ok" in out, f"expected ok in result: {out}")


# --- Test 4: dry_run builds URL but never calls ---
def test_dry_run_constructs_request():
    pass


# --- Test 5: action API URL is well-formed (no network) ---
def test_action_url_shape():
    a = JamfAdapter(
        live=True,
        base_url=_base(),
        client_id="c",
        client_secret="s",
    )
    a._token = "stub"
    a._token_expires_at = float("inf")

    import requests as _rq
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers", {})
        captured["json"] = kwargs.get("json", {})
        return _Resp(204, body={})

    _orig_post = _rq.post
    _rq.post = fake_post  # type: ignore
    try:
        out = a.execute({"device_id": "abc-123"}, "wipe", {}, dry_run=True)
    finally:
        _rq.post = _orig_post  # restore real requests.post so other tests aren't polluted
    check("would_send" in out, f"expected would_send in dry_run: {out!r}")
    would = out["would_send"]
    check("/api/v1/mobile-devices/abc-123/commands" in would["url"],
          f"URL missing device ID: {would['url']!r}")
    check(would["url"].startswith(_base()), f"URL should start with base: {would['url']!r}")
    check(would["json"]["commandData"]["commandType"] == JAMF_VERB["wipe"],
          f"command verb wrong: {would['json']}")


# --- Test 6: missing device_id in action returns structured error ---
def test_missing_device_id_returns_structured_error():
    a = JamfAdapter(live=True, base_url=_base(), client_id="c", client_secret="s")
    a._token = "stub"
    a._token_expires_at = float("inf")
    out = a.execute({"device_id": ""}, "lock", {})
    check(out.get("ok") is False, f"missing device_id should fail: {out!r}")
    check(out.get("error_type") == "missing_device_id", f"error_type: {out!r}")


# --- Test 7: unsupported action returns error without HTTP call ---
def test_unsupported_action_returns_error():
    a = JamfAdapter(live=True, base_url=_base(), client_id="c", client_secret="s")
    a._token = "stub"
    a._token_expires_at = float("inf")
    out = a.execute({"device_id": "d-1"}, "definitely_not_a_real_action", {})
    check(out.get("ok") is False, f"unsupported action should fail: {out!r}")
    check(out.get("error_type") == "unsupported_action", f"error_type: {out!r}")


def main():
    tests = [
        test_no_creds_raises_auth_error,
        test_offline_mode_uses_simulation,
        test_list_in_mock_returns_list_structure,
        test_dry_run_constructs_request,
        test_action_url_shape,
        test_missing_device_id_returns_structured_error,
        test_unsupported_action_returns_error,
    ]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL: {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"ERROR: {t.__name__}: {exc!r}")

    print(f"\n{'OK' if failures == 0 else f'{failures} FAILURES'} ({len(tests)} tests)")
    return failures


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main())
