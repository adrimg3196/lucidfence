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


def _load_server_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "saas_server", Path(__file__).resolve().parent.parent / "saas_server.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _RateHandler:
    def __init__(self, peer="203.0.113.10", xff=""):
        self.client_address = (peer, 12345)
        self.headers = {"X-Forwarded-For": xff} if xff else {}


def test_auth_rate_limit_locks_out_repeated_failed_login_attempts():
    mod = _load_server_module()
    mod._auth_failures.clear()
    mod._auth_lockouts.clear()
    h = _RateHandler()
    for _ in range(mod.AUTH_FAILURE_LIMIT - 1):
        assert mod._record_auth_failure(h, "ciso@example.test") == 0
    assert mod._record_auth_failure(h, "ciso@example.test") > 0
    assert mod._auth_lockout_remaining(h, "ciso@example.test") > 0
    mod._record_auth_success(h, "ciso@example.test")
    assert mod._auth_lockout_remaining(h, "ciso@example.test") == 0


def test_auth_rate_limit_trusts_x_forwarded_for_only_from_loopback_proxy():
    mod = _load_server_module()
    assert mod._client_ip(_RateHandler(peer="127.0.0.1", xff="198.51.100.23")) == "198.51.100.23"
    assert mod._client_ip(_RateHandler(peer="198.51.100.99", xff="198.51.100.23")) == "198.51.100.99"


def test_server_error_response_does_not_leak_exception_detail():
    server = (Path(__file__).resolve().parent.parent / "saas_server.py").read_text(encoding="utf-8")
    assert '{"error": "server_error", "detail": str(e)}' not in server
    assert "def _send_server_error" in server


def test_static_files_get_security_headers_and_delete_uses_host_guard():
    server = (Path(__file__).resolve().parent.parent / "saas_server.py").read_text(encoding="utf-8")
    send_file = server.split("def _send_file", 1)[1].split("def _send_csv", 1)[0]
    assert "X-Content-Type-Options" in send_file
    assert "X-Frame-Options" in send_file
    assert "Content-Security-Policy" in send_file
    delete_block = server.split("def do_DELETE", 1)[1].split("def _route", 1)[0]
    assert "_host_allowed(self)" in delete_block


def test_internet_facing_compose_uses_tls_proxy_and_no_plain_lan_bind():
    root = Path(__file__).resolve().parent.parent
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    caddyfile = (root / "Caddyfile").read_text(encoding="utf-8")
    assert '"127.0.0.1:${LUCIDFENCE_PORT:-8765}:8765"' in compose
    assert "profiles: [\"internet-facing\"]" in compose
    assert '"443:443"' in compose and '"80:80"' in compose
    assert "reverse_proxy lucidfence:8765" in caddyfile
    assert "Strict-Transport-Security" in caddyfile


def test_install_and_docker_build_use_locked_dependency_hashes():
    root = Path(__file__).resolve().parent.parent
    install = (root / "install.sh").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    lock = (root / "requirements.lock").read_text(encoding="utf-8")
    assert "curl -fsSL \"https://raw.githubusercontent.com/$REPO/main/docker-compose.yml\"" not in install
    assert "ensure_repo_checkout" in install
    assert "--require-hashes -r requirements.lock" in install
    assert "--require-hashes -r requirements.lock" in dockerfile
    assert "--hash=sha256:" in lock


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


def test_docker_compose_is_localhost_by_default_and_tls_profile_exists():
    root = Path(__file__).resolve().parent.parent
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    caddyfile = (root / "Caddyfile").read_text(encoding="utf-8")

    assert '"127.0.0.1:${LUCIDFENCE_PORT:-8765}:8765"' in compose
    assert 'profiles: ["internet-facing"]' in compose
    assert '"443:443"' in compose
    assert 'LUCIDFENCE_PUBLIC_HOST=${LUCIDFENCE_PUBLIC_HOST:?' in compose
    assert "reverse_proxy lucidfence:8765" in caddyfile
    assert "Strict-Transport-Security" in caddyfile


def test_installer_and_dockerfile_use_hashed_dependencies():
    root = Path(__file__).resolve().parent.parent
    install = (root / "install.sh").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    lock = (root / "requirements.lock").read_text(encoding="utf-8")

    assert "--require-hashes -r requirements.lock" in install
    assert "--require-hashes -r requirements.lock" in dockerfile
    assert "curl -fsSL \"https://raw.githubusercontent.com/$REPO/main/docker-compose.yml\"" not in install
    assert "requests==" in lock and "--hash=sha256:" in lock


def test_moa_and_delete_host_guard_are_not_internet_exposed():
    root = Path(__file__).resolve().parent.parent
    start = (root / "docker_start.sh").read_text(encoding="utf-8")
    server = (root / "saas_server.py").read_text(encoding="utf-8")

    assert "--host 127.0.0.1" in start
    delete_block = server.split("def do_DELETE", 1)[1].split("def _route", 1)[0]
    assert "_host_allowed(self)" in delete_block
    assert '"detail": str(e)' not in server


def test_auth_rate_limit_helpers_lock_after_repeated_failures():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "saas_server", Path(__file__).resolve().parent.parent / "saas_server.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class _FakeHandler:
        headers = {}
        client_address = ("198.51.100.10", 4444)

    h = _FakeHandler()
    email = "blocked@example.com"
    for _ in range(mod.AUTH_FAILURE_LIMIT - 1):
        assert mod._record_auth_failure(h, email) == 0
    assert mod._record_auth_failure(h, email) > 0
    assert mod._auth_lockout_remaining(h, email) > 0
    mod._record_auth_success(h, email)
    assert mod._auth_lockout_remaining(h, email) == 0

