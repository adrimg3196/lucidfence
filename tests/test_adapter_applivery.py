"""Tests for the Applivery UEM (MDM) live adapter.

Covers, with ``requests`` fully mocked (no real network, no real tenant):

  * Auth        : Bearer header shape, missing-key failure, test_connection auth.
  * Push fence  : native command POST 2xx -> ok; URL/body shape; dry-run.
  * Error paths : native 4xx/5xx -> webhook delegation (delegated True);
                  native 4xx + no webhook -> not delegated (never raises);
                  webhook POST raising -> handled, never raises.

The adapter MUST never raise (the dashboard must not 500). Every path is
asserted to return a normalized dict.

Mirrors the coverage of test_adapter_fleet.py / test_adapters_intune_live.py /
test_adapters_jamf_live.py so Applivery is at parity with the other adapters.
Discovered automatically by tests/run_tests.py (CI: ``python3 tests/run_tests.py``).
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import requests as _requests  # patched at module-level so BOTH the adapter's
                              # `requests.post` AND base.test_connection's
                              # `import requests` (real module) are intercepted.

from lucidfence.core.adapters import AppliveryAdapter, ADAPTER_REGISTRY
from tests.test_sdk_contract import assert_valid_name, assert_response_shape


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
class _Resp:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, status_code: int = 200, text: str = ""):
        self.status_code = status_code
        self.text = text

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        raise ValueError("no json body in mock")


class FakeRequests:
    """Routes POSTs by URL so command vs webhook get different responses.

    Command calls hit the Applivery API host; webhook calls hit a sentinel
    host we control (``hook.local``). Optionally raises on a URL substring to
    simulate a transport failure.
    """

    def __init__(self, command_status: int = 200, get_status: int = 200,
                 webhook_status: int = 200, raise_on_url: str | None = None):
        self.command_status = command_status
        self.get_status = get_status
        self.webhook_status = webhook_status
        self.raise_on_url = raise_on_url
        self.post_calls: list[tuple[str, dict]] = []
        self.get_calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.get_calls.append((url, kwargs))
        return _Resp(self.get_status)

    def post(self, url: str, **kwargs):
        self.post_calls.append((url, kwargs))
        if self.raise_on_url and self.raise_on_url in url:
            raise RuntimeError("simulated transport failure")
        if "hook.local" in url:
            return _Resp(self.webhook_status)
        return _Resp(self.command_status)

    def install(self):
        self._orig = (_requests.get, _requests.post)
        _requests.get = self.get
        _requests.post = self.post

    def restore(self):
        if getattr(self, "_orig", None) is not None:
            _requests.get, _requests.post = self._orig


WEBHOOK_URL = "https://hook.local/remediation"
API_BASE = "https://api.applivery.io/v1"
DEFAULT_CMD_PATH = "/organizations/{org_id}/mdm/devices/{device_id}/commands"


def _adapter(org_id: str = "org-1", api_key: str = "APPLITESTKEY12345678",
             webhook_url: str = "", endpoint_template: str = "") -> AppliveryAdapter:
    return AppliveryAdapter(
        org_id=org_id,
        endpoint_template=endpoint_template,
        webhook_url=webhook_url,
        api_key=api_key,
    )


def check(cond, msg):
    assert cond, f"FAIL: {msg}"


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
def test_applivery_registered_and_named():
    check("applivery" in ADAPTER_REGISTRY, "applivery missing from ADAPTER_REGISTRY")
    assert_valid_name(AppliveryAdapter(org_id="o", endpoint_template="").name)


def test_applivery_auth_header_is_bearer():
    fake = FakeRequests(get_status=200)
    fake.install()
    try:
        a = _adapter()
        # test_connection exercises Auth via the real _headers() (Bearer token)
        # and issues a GET to the live test endpoint.
        res = a.test_connection()
    finally:
        fake.restore()
    check(res.get("ok") is True, f"test_connection should succeed with valid key: {res!r}")
    check(res.get("verified") == "live", f"expected live verification: {res!r}")
    check(fake.get_calls, "test_connection must issue a GET")
    sent_headers = fake.get_calls[0][1].get("headers", {})
    auth = sent_headers.get("Authorization", "")
    check(auth.startswith("Bearer "), f"Authorization must be Bearer, got {auth!r}")
    check("APPLITESTKEY" in auth, f"Bearer token missing api_key: {auth!r}")


def test_applivery_missing_api_key_returns_failure_not_raise():
    a = AppliveryAdapter(org_id="org-1", endpoint_template="", api_key="")  # no key, no env
    # ensure no inherited env key leaks in
    import os
    old = os.environ.pop("APPLIVERY_API_KEY", None)
    old2 = os.environ.pop("applivery_api_key", None)
    try:
        res = a.execute({"device_id": "d1"}, "lock", {})
    finally:
        if old is not None:
            os.environ["APPLIVERY_API_KEY"] = old
        if old2 is not None:
            os.environ["applivery_api_key"] = old2
    check(res.get("ok") is False, f"missing key must fail, got {res!r}")
    check("APPLIVERY_API_KEY" in (res.get("error") or ""), f"error should mention missing key: {res!r}")
    check(res.get("adapter") == "applivery", "adapter label must be set even on failure")


def test_applivery_test_connection_auth_failure_returns_error():
    import os
    # No api_key -> _headers() raises RuntimeError, which test_connection must
    # catch and map to an auth error (never propagate the exception).
    a = AppliveryAdapter(org_id="org-1", endpoint_template="", api_key="")
    old = os.environ.pop("APPLIVERY_API_KEY", None)
    old2 = os.environ.pop("applivery_api_key", None)
    try:
        res = a.test_connection()
    finally:
        if old is not None:
            os.environ["APPLIVERY_API_KEY"] = old
        if old2 is not None:
            os.environ["applivery_api_key"] = old2
    check(res.get("ok") is False, f"no-key test_connection must fail: {res!r}")
    check(res.get("error_type") == "auth", f"expected auth error_type: {res!r}")


# --------------------------------------------------------------------------
# Push fence (happy path + shape)
# --------------------------------------------------------------------------
def test_applivery_push_fence_native_ok():
    fake = FakeRequests(command_status=201)  # 2xx -> native success
    fake.install()
    try:
        a = _adapter()
        res = a.execute({"device_id": "dev-42"}, "lock", {"message": "out of fence"})
    finally:
        fake.restore()
    assert_response_shape(res, "applivery")
    check(res["ok"] is True, f"native 2xx must be ok: {res!r}")
    check(res.get("status_code") == 201, f"status_code must pass through: {res!r}")
    check("delegation" not in res or not res.get("delegated"),
          f"should not delegate on native success: {res!r}")
    # The native command POST must have carried the Bearer auth header.
    cmd_posts = [c for c in fake.post_calls if "hook.local" not in c[0]]
    check(cmd_posts, "a native command POST must have been issued")
    cmd_headers = cmd_posts[0][1].get("headers", {})
    check(cmd_headers.get("Authorization", "").startswith("Bearer "),
          f"command POST must be authenticated: {cmd_headers!r}")


def test_applivery_push_fence_url_and_body_shape():
    fake = FakeRequests(command_status=200)
    fake.install()
    try:
        a = _adapter(org_id="my-org")
        res = a.execute({"device_id": "dev/99"}, "wipe", {"foo": "bar"})
    finally:
        fake.restore()
    check(res["ok"] is True, f"expected ok: {res!r}")
    url = res.get("url", "")
    check(url.startswith(API_BASE), f"URL must start with API base: {url!r}")
    check("/organizations/my-org/mdm/devices/dev%2F99/commands" in url,
          f"URL must encode org_id + device_id: {url!r}")
    # body carried the command + params
    cmd_posts = [c for c in fake.post_calls if "hook.local" not in c[0]]
    body = cmd_posts[0][1].get("json", {})
    check(body.get("command") == "wipe", f"body.command wrong: {body!r}")
    check(body.get("params", {}).get("foo") == "bar", f"body.params wrong: {body!r}")


def test_applivery_dry_run_builds_request_no_send():
    fake = FakeRequests()
    fake.install()
    try:
        a = _adapter(org_id="org-x")
        res = a.execute({"device_id": "d1"}, "lock", {}, dry_run=True)
    finally:
        fake.restore()
    check(res.get("dry_run") is True, f"expected dry_run True: {res!r}")
    check("url" in res and "body" in res, f"dry_run must build url+body: {res!r}")
    check(not fake.post_calls, f"dry_run must NOT issue HTTP: {fake.post_calls!r}")
    check(res["ok"] is True, f"dry_run must report ok: {res!r}")


# --------------------------------------------------------------------------
# Error paths
# --------------------------------------------------------------------------
def test_applivery_native_404_delegates_to_webhook():
    fake = FakeRequests(command_status=404, webhook_status=200)
    fake.install()
    try:
        a = _adapter(webhook_url=WEBHOOK_URL)
        res = a.execute({"device_id": "d1"}, "lock", {})
    finally:
        fake.restore()
    check(res["ok"] is False, f"native 404 must not be ok: {res!r}")
    check(res.get("delegated") is True, f"must delegate to webhook on 404: {res!r}")
    check(res.get("delegation", {}).get("delegated") is True, f"delegation flag: {res!r}")
    # The remediation webhook POST must have been issued.
    hook_posts = [c for c in fake.post_calls if "hook.local" in c[0]]
    check(hook_posts, "webhook POST must be issued on native failure")
    hook_body = hook_posts[0][1].get("data", "")
    check("geofence_remediation" in str(hook_body), f"webhook payload wrong: {hook_body!r}")


def test_applivery_native_500_no_webhook_no_delegation():
    fake = FakeRequests(command_status=500)
    fake.install()
    try:
        a = _adapter(webhook_url="")  # no remediation webhook configured
        res = a.execute({"device_id": "d1"}, "wipe", {})
    finally:
        fake.restore()
    check(res["ok"] is False, f"native 500 must not be ok: {res!r}")
    check(res.get("delegated") is False, f"no webhook -> not delegated: {res!r}")
    check("no remediation webhook" in (res.get("note") or "").lower(),
          f"note should explain no webhook: {res!r}")
    hook_posts = [c for c in fake.post_calls if "hook.local" in c[0]]
    check(not hook_posts, f"must NOT call webhook when unconfigured: {hook_posts!r}")


def test_applivery_webhook_post_failure_handled():
    # Native command fails AND the webhook POST itself raises -> must be
    # handled gracefully, never propagate the exception.
    fake = FakeRequests(command_status=403, raise_on_url="hook.local")
    fake.install()
    try:
        a = _adapter(webhook_url=WEBHOOK_URL)
        res = a.execute({"device_id": "d1"}, "lock", {})
    finally:
        fake.restore()
    check(res["ok"] is False, f"should remain not-ok: {res!r}")
    check(res.get("delegated") is False, f"webhook failure -> not delegated: {res!r}")
    check("webhook failed" in str(res.get("delegation", {}).get("error", "")),
          f"webhook error must be captured: {res!r}")


def test_applivery_native_post_transport_error_delegates():
    # Native command POST raises (network down) -> delegation path.
    fake = FakeRequests(raise_on_url="api.applivery.io")
    fake.install()
    try:
        a = _adapter(webhook_url=WEBHOOK_URL)
        res = a.execute({"device_id": "d1"}, "lock", {})
    finally:
        fake.restore()
    check(res["ok"] is False, f"transport error must not be ok: {res!r}")
    check(res.get("delegated") is True, f"should delegate after transport error: {res!r}")


def main():
    tests = [
        test_applivery_registered_and_named,
        test_applivery_auth_header_is_bearer,
        test_applivery_missing_api_key_returns_failure_not_raise,
        test_applivery_test_connection_auth_failure_returns_error,
        test_applivery_push_fence_native_ok,
        test_applivery_push_fence_url_and_body_shape,
        test_applivery_dry_run_builds_request_no_send,
        test_applivery_native_404_delegates_to_webhook,
        test_applivery_native_500_no_webhook_no_delegation,
        test_applivery_webhook_post_failure_handled,
        test_applivery_native_post_transport_error_delegates,
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
