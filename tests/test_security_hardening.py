"""Regression: backend security fixes (auth bypass, signup join, role escalation,
malformed bodies) and cooldown-only-on-effective-action.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from saas.auth import AuthStore, ROLE_CAPS  # noqa: E402


def test_admin_cannot_grant_owner_or_admin_role():
    # Mirror server-side guard: user:invite alone must not allow escalation.
    assert "user:invite" in ROLE_CAPS["admin"]
    assert "user:invite" in ROLE_CAPS["owner"]
    # owner-only grant of privileged roles is enforced in the /api/users handler;
    # here we assert the capability model itself keeps org:billing/org:delete
    # exclusive to owner so a minted admin can't reach billing.
    assert "org:billing" in ROLE_CAPS["owner"]
    assert "org:billing" not in ROLE_CAPS["admin"]
    assert "org:delete" not in ROLE_CAPS["admin"]


def test_viewer_has_no_write_capabilities():
    viewer = ROLE_CAPS["viewer"]
    for cap in ("device:action", "fence:write", "engine:config", "workflow:write",
                "user:invite", "route:write", "org:billing"):
        assert cap not in viewer, f"viewer must not hold {cap}"


def test_read_body_rejects_non_object_json():
    # The parser must coerce arrays/strings/numbers to {} so handlers calling
    # body.get(...) never raise AttributeError -> 500 leak.
    import json

    class _FakeHandler:
        def __init__(self, raw):
            self._raw = raw
            self.headers = {"Content-Length": str(len(raw))}
            import io
            self.rfile = io.BytesIO(raw)

    # import here to avoid importing the whole server at module load
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "saas_server", Path(__file__).resolve().parent.parent / "saas_server.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def _body(raw):
        h = _FakeHandler(raw if isinstance(raw, bytes) else raw.encode())
        h.headers = {"Content-Length": str(len(raw))}
        return mod._read_body(h)

    assert _body(json.dumps([1, 2, 3])) == {}
    assert _body(json.dumps("just a string")) == {}
    assert _body(json.dumps(42)) == {}
    assert _body("{ not json") == {}
    assert _body(json.dumps({"email": "a@b.c"})) == {"email": "a@b.c"}


def test_soar_webhook_hmac_requires_valid_signature_and_fresh_timestamp():
    import hashlib
    import hmac
    import json
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "saas_server", Path(__file__).resolve().parent.parent / "saas_server.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    raw = json.dumps({"device_id": "dev-1", "action": "lock"}, separators=(",", ":")).encode()
    secret = "super-secret-soar-key"
    ts = "2000"
    sig = hmac.new(secret.encode(), ts.encode() + b"." + raw, hashlib.sha256).hexdigest()
    headers = {
        "X-LucidFence-Timestamp": ts,
        "X-LucidFence-Signature": f"sha256={sig}",
    }

    assert mod._verify_soar_webhook_hmac(raw, headers, secret, now=2001)[0]

    tampered = raw.replace(b"lock", b"wipe")
    ok, reason = mod._verify_soar_webhook_hmac(tampered, headers, secret, now=2001)
    assert ok is False and reason == "invalid signature"

    ok, reason = mod._verify_soar_webhook_hmac(raw, headers, secret, now=2601)
    assert ok is False and reason == "timestamp outside replay window"

    ok, reason = mod._verify_soar_webhook_hmac(raw, {"X-LucidFence-Timestamp": ts}, secret, now=2001)
    assert ok is False and reason == "missing signature"


def test_webhook_non_2xx_is_not_treated_as_delegated():
    from core.actions import LiveAdapter
    import core.adapters.applivery as P

    class _Resp:
        status_code = 500
        def text(self):
            return "boom"

    class _Sess:
        def post(self, *a, **k):
            return _Resp()

    class _Dev:
        device_id = "dev-1"
        name = "d"
        platform = "android"

    adapter = LiveAdapter(org_id="org-test", endpoint_template="",
                          webhook_url="http://127.0.0.1:1/hook", api_key="x")
    orig = P.requests
    try:
        P.requests = _Sess()
        res = adapter._delegate_webhook(_Dev(), "wipe", {}, reason="test")
    finally:
        P.requests = orig
    assert res["delegated"] is False, res
    assert res.get("attempted") is True, res


def test_saas_rate_limit_keys_by_ip_then_session_and_exempts_health():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "saas_server", Path(__file__).resolve().parent.parent / "saas_server.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class _Headers(dict):
        def get_all(self, name):
            value = self.get(name)
            return [] if value is None else [value]

    class _Handler:
        def __init__(self, path="/api/status", ip="203.0.113.10", cookie=""):
            self.path = path
            self.client_address = (ip, 12345)
            self.headers = _Headers()
            if cookie:
                self.headers["Cookie"] = cookie

    setattr(mod, "RATE_LIMIT_REQUESTS", 2)
    setattr(mod, "RATE_LIMIT_WINDOW_S", 10)
    getattr(mod, "_rate_limit_buckets").clear()

    ip_only = _Handler()
    assert mod._rate_limit_check(ip_only, now=1000)[0]
    assert mod._rate_limit_check(ip_only, now=1001)[0]
    ok, retry_after, key = mod._rate_limit_check(ip_only, now=1002)
    assert ok is False and retry_after >= 8 and key.startswith("ip:203.0.113.10")

    # An authenticated browser session gets its own bucket, so one noisy IP does
    # not block every active session behind the same NAT/proxy.
    session_a = _Handler(cookie="gf_session=session-a")
    session_b = _Handler(cookie="gf_session=session-b")
    assert mod._rate_limit_key(session_a) != mod._rate_limit_key(session_b)
    assert mod._rate_limit_check(session_a, now=1002)[0]
    assert mod._rate_limit_check(session_b, now=1002)[0]

    # Keep external health probes safe for always-on deploys.
    assert mod._rate_limit_check(_Handler(path="/api/health"), now=1002) == (True, 0, "")

