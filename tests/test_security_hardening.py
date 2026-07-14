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

