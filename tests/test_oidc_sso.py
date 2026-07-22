"""Security contract for Google/generic OIDC SSO (fake IdP only)."""
from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import stat
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from http.server import ThreadingHTTPServer
import threading
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlparse

try:
    import pytest
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    pytest_module = sys.modules.get("pytest")
    if pytest_module is not None and any("pytest" in arg for arg in sys.argv):
        pytest_module.skip("optional OIDC test dependencies unavailable", allow_module_level=True)
    raise SystemExit(0)

from core.oidc import (
    IDTokenValidator,
    OIDCClient,
    OIDCError,
    OIDCFlowStore,
    OIDCMetadataValidator,
    OIDCProvider,
    PublicEgressPolicy,
    validate_callback_params,
    validate_return_path,
)
from saas.auth import AuthStore


ISSUER = "https://idp.example.test"
REDIRECT = "https://app.example.test/api/auth/sso/fake/callback"
CLIENT_ID = "obvious-fake-client-id"
CLIENT_SECRET = "obvious-fake-secret-not-real"


def _rsa_material():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key().public_numbers()
    enc = lambda n: base64.urlsafe_b64encode(n.to_bytes((n.bit_length()+7)//8, "big")).rstrip(b"=").decode()
    jwk = {"kty": "RSA", "kid": "fake-rsa-1", "use": "sig", "alg": "RS256", "n": enc(pub.n), "e": enc(pub.e)}
    return key, jwk


def _tmp(value=None):
    return Path(value) if value is not None else Path(tempfile.mkdtemp(prefix="oidc-test-"))


class FakeTransport:
    def __init__(self, jwks=None):
        self.jwks = jwks or {"keys": []}
        self.calls = []
        self.token_response = {}
        self.userinfo_response = None

    def json_request(self, method, url, *, headers=None, form=None, max_bytes=65536, timeout=5):
        self.calls.append((method, url, headers or {}, form or {}))
        if url.endswith("/jwks"):
            return self.jwks
        if url.endswith("/token"):
            return self.token_response
        if url.endswith("/userinfo"):
            return self.userinfo_response
        raise AssertionError(f"unexpected fake endpoint: {url}")


def provider(**overrides):
    values = dict(name="fake", label="Fake IdP", issuer=ISSUER, client_id=CLIENT_ID,
                  client_secret=CLIENT_SECRET, redirect_uri=REDIRECT,
                  authorization_endpoint=ISSUER + "/authorize", token_endpoint=ISSUER + "/token",
                  jwks_uri=ISSUER + "/jwks", userinfo_endpoint=ISSUER + "/userinfo",
                  enabled=True, allowed_domains=("example.test",), provision_org_id="org-1",
                  provision_role="viewer", authorization_response_iss_parameter_supported=True)
    values.update(overrides)
    return OIDCProvider(**values)


def signed_token(key, *, nonce="n", sub="subject-1", now=None, **overrides):
    now = int(time.time()) if now is None else now
    claims = {"iss": ISSUER, "sub": sub, "aud": CLIENT_ID, "exp": now + 300,
              "iat": now, "nonce": nonce, "email": "alice@example.test", "email_verified": True}
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "fake-rsa-1"})


def test_start_persists_one_time_256_bit_state_nonce_and_pkce_s256(tmp_path=None):
    tmp_path = _tmp(tmp_path)
    store = OIDCFlowStore(tmp_path / "flows.json", ttl_seconds=600)
    client = OIDCClient({"fake": provider()}, store, FakeTransport())
    started = client.start("fake", browser_binding="browser-a", return_path="/app")
    query = parse_qs(urlparse(started.authorization_url).query)
    assert len(base64.urlsafe_b64decode(started.state + "==")) >= 32
    flow = store.peek(started.state)
    assert flow and flow["nonce"] and flow["verifier"] and flow["expires_at"] - flow["created_at"] <= 600
    expected = base64.urlsafe_b64encode(hashlib.sha256(flow["verifier"].encode()).digest()).rstrip(b"=").decode()
    assert query["code_challenge"] == [expected]
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == [REDIRECT]
    assert query["scope"] == ["openid email profile"]
    assert stat.S_IMODE((tmp_path / "flows.json").stat().st_mode) == 0o600


def test_flow_consume_is_atomic_browser_bound_expiring_and_single_use(tmp_path=None):
    tmp_path = _tmp(tmp_path)
    store = OIDCFlowStore(tmp_path / "flows.json", ttl_seconds=1, clock=lambda: 100.0)
    state = store.create(provider(), "browser-a", "/app", "login")[0]
    with pytest.raises(OIDCError, match="browser_binding"):
        store.consume(state, "browser-b", "fake")
    assert store.peek(state) is not None  # theft must not burn victim's state
    flow = store.consume(state, "browser-a", "fake")
    assert flow["provider"] == "fake"
    with pytest.raises(OIDCError, match="invalid_state"):
        store.consume(state, "browser-a", "fake")
    expired = store.create(provider(), "browser-a", "/app", "login")[0]
    store._clock = lambda: 102.0
    with pytest.raises(OIDCError, match="invalid_state"):
        store.consume(expired, "browser-a", "fake")


def test_concurrent_callbacks_only_one_consumes_state(tmp_path=None):
    tmp_path = _tmp(tmp_path)
    store = OIDCFlowStore(tmp_path / "flows.json")
    state = store.create(provider(), "browser-a", "/app", "login")[0]
    def consume(_):
        try:
            store.consume(state, "browser-a", "fake"); return True
        except OIDCError:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(consume, range(8))).count(True) == 1


def test_return_path_is_enum_allowlisted():
    for value in ["https://evil.test", "//evil.test", "/%2f%2fevil.test", "/%252f%252fevil.test", "/\\evil", "/unknown"]:
        with pytest.raises(OIDCError, match="invalid_return_path"):
            validate_return_path(value)
    assert validate_return_path("/app") == "/app"


def test_callback_parameter_pollution_and_code_error_are_rejected():
    for query in ("state=a&state=b&code=c", "state=a&code=c&code=d", "state=a&code=c&error=x", "state=a&error=x&error_description=secret"):
        with pytest.raises(OIDCError, match="invalid_callback"):
            validate_callback_params(query)


def test_metadata_url_rejects_ambiguous_or_non_public_destinations():
    policy = PublicEgressPolicy(resolver=lambda host, port: ["93.184.216.34"])
    urls = ["http://idp.example.test/x", "https://user@idp.example.test/x", "https://idp.example.test/x?q=1",
            "https://idp.example.test/x#f", "https://idp.example.test:444/x", "https://127.0.0.1/x",
            "https://10.0.0.1/x", "https://169.254.169.254/x", "https://[::1]/x", "https://[fc00::1]/x",
            "https://[::ffff:127.0.0.1]/x", "https://2130706433/x", "https://0x7f000001/x"]
    for url in urls:
        with pytest.raises(OIDCError, match="unsafe_endpoint"):
            OIDCMetadataValidator(policy).validate_endpoint(url)


def test_mixed_and_rebinding_dns_fail_before_request():
    mixed = PublicEgressPolicy(resolver=lambda h, p: ["93.184.216.34", "10.0.0.1"])
    with pytest.raises(OIDCError, match="unsafe_endpoint"):
        OIDCMetadataValidator(mixed).validate_endpoint(ISSUER + "/token")
    snapshots = iter([["93.184.216.34"], ["127.0.0.1"]])
    policy = PublicEgressPolicy(resolver=lambda h, p: next(snapshots))
    assert policy.resolve_public("idp.example.test", 443) == ("93.184.216.34",)
    with pytest.raises(OIDCError, match="unsafe_endpoint"):
        policy.resolve_public("idp.example.test", 443)


def test_discovery_requires_exact_issuer_and_validates_every_endpoint():
    validator = OIDCMetadataValidator(PublicEgressPolicy(resolver=lambda h, p: ["93.184.216.34"]))
    metadata = {"issuer": ISSUER, "authorization_endpoint": ISSUER+"/authorize", "token_endpoint": ISSUER+"/token",
                "jwks_uri": ISSUER+"/jwks", "userinfo_endpoint": ISSUER+"/userinfo"}
    assert validator.validate_metadata(ISSUER, metadata)["issuer"] == ISSUER
    with pytest.raises(OIDCError, match="issuer_mismatch"):
        validator.validate_metadata(ISSUER, {**metadata, "issuer": "https://other.example.test"})


def test_id_token_validates_signature_claims_nonce_and_bounded_jwks_refresh():
    rsa_material = _rsa_material()
    key, jwk = rsa_material
    transport = FakeTransport({"keys": [jwk]})
    validator = IDTokenValidator(provider(), transport)
    claims = validator.validate(signed_token(key, nonce="nonce-a"), "nonce-a")
    assert claims["sub"] == "subject-1"
    assert len([c for c in transport.calls if c[1].endswith("/jwks")]) == 1
    validator.validate(signed_token(key, nonce="nonce-b"), "nonce-b")
    assert len([c for c in transport.calls if c[1].endswith("/jwks")]) == 1


def test_id_token_rejects_invalid_claims():
    rsa_material = _rsa_material()
    key, jwk = rsa_material
    mutations_list = [{"iss": "https://evil.example.test"}, {"aud": "wrong-client"}, {"exp": 1},
                      {"iat": int(time.time()) + 600}, {"nonce": "wrong"},
                      {"aud": [CLIENT_ID, "other"], "azp": "wrong"}]
    for mutations in mutations_list:
        validator = IDTokenValidator(provider(), FakeTransport({"keys": [jwk]}))
        token_args = {"nonce": "expected", **mutations}
        with pytest.raises(OIDCError, match="invalid_id_token"):
            validator.validate(signed_token(key, **token_args), "expected")


def test_id_token_rejects_alg_none_unknown_kid_and_bad_signature():
    rsa_material = _rsa_material()
    key, jwk = rsa_material
    validator = IDTokenValidator(provider(), FakeTransport({"keys": [jwk]}))
    unsigned = jwt.encode({"iss": ISSUER}, key="", algorithm="none", headers={"kid": "fake-rsa-1"})
    with pytest.raises(OIDCError, match="invalid_id_token"):
        validator.validate(unsigned, "n")
    unknown = jwt.encode({"iss": ISSUER}, key, algorithm="RS256", headers={"kid": "unknown"})
    with pytest.raises(OIDCError, match="invalid_id_token"):
        validator.validate(unknown, "n")
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(OIDCError, match="invalid_id_token"):
        validator.validate(signed_token(other), "n")
    assert len([c for c in validator.transport.calls if c[1].endswith("/jwks")]) <= 2


def test_jwks_rejects_encryption_and_sign_only_keys():
    key, jwk = _rsa_material()
    for marker in ({"use": "enc"}, {"key_ops": ["sign"]}, {"use": "sig", "key_ops": ["sign"]}):
        candidate = {**jwk, **marker}
        validator = IDTokenValidator(provider(), FakeTransport({"keys": [candidate]}))
        with pytest.raises(OIDCError, match="invalid_id_token"):
            validator.validate(signed_token(key), "n")

    for marker in ({"use": "sig"}, {"key_ops": ["verify"]}, {}):
        candidate = {key: value for key, value in jwk.items() if key != "use"}
        candidate.update(marker)
        assert IDTokenValidator(provider(), FakeTransport({"keys": [candidate]})).validate(
            signed_token(key), "n"
        )["sub"] == "subject-1"


def test_callback_rejects_mixup_before_token_endpoint(tmp_path=None):
    tmp_path = _tmp(tmp_path)
    transport = FakeTransport()
    p_a = provider(name="a")
    p_b = provider(name="b", issuer="https://b.example.test", token_endpoint="https://b.example.test/token")
    client = OIDCClient({"a": p_a, "b": p_b}, OIDCFlowStore(tmp_path / "flows.json"), transport)
    started = client.start("a", "browser-a", "/app")
    with pytest.raises(OIDCError, match="provider_mixup"):
        client.callback("b", f"state={started.state}&code=obvious-fake-code&iss={ISSUER}", "browser-a")
    assert transport.calls == []


def test_callback_binds_mutable_provider_configuration_before_exchange(tmp_path=None):
    tmp_path = _tmp(tmp_path)
    mutations = {
        "issuer": "https://changed.example.test",
        "client_id": "changed-client",
        "redirect_uri": "https://app.example.test/api/auth/sso/fake/changed",
        "token_endpoint": "https://changed.example.test/token",
        "authorization_endpoint": "https://changed.example.test/authorize",
    }
    for field, changed in mutations.items():
        transport = FakeTransport()
        original = provider()
        store = OIDCFlowStore(tmp_path / f"flows-{field}.json")
        client = OIDCClient({"fake": original}, store, transport)
        started = client.start("fake", "browser-a", "/app")
        setattr(original, field, changed)
        with pytest.raises(OIDCError, match="provider_mixup"):
            client.callback(
                "fake", f"state={started.state}&code=obvious-fake-code&iss={ISSUER}", "browser-a"
            )
        assert transport.calls == []
        assert store.peek(started.state) is None


def test_distinct_callback_allows_missing_iss_only_when_provider_declares_unsupported(tmp_path=None):
    tmp_path = _tmp(tmp_path); key, jwk = _rsa_material()
    p = provider(authorization_response_iss_parameter_supported=False)
    transport = FakeTransport({"keys": [jwk]})
    store = OIDCFlowStore(tmp_path / "flows.json")
    client = OIDCClient({"fake": p}, store, transport)
    started = client.start("fake", "browser-a", "/app")
    transport.token_response = {"id_token": signed_token(key, nonce=store.peek(started.state)["nonce"])}
    result = client.callback("fake", f"state={started.state}&code=c", "browser-a")
    assert result.claims["sub"] == "subject-1"


def test_successful_fake_crypto_callback_uses_basic_auth_and_checks_userinfo_sub(tmp_path=None):
    tmp_path = _tmp(tmp_path); rsa_material = _rsa_material()
    key, jwk = rsa_material
    transport = FakeTransport({"keys": [jwk]})
    store = OIDCFlowStore(tmp_path / "flows.json")
    client = OIDCClient({"fake": provider()}, store, transport)
    started = client.start("fake", "browser-a", "/app")
    nonce = store.peek(started.state)["nonce"]
    transport.token_response = {"id_token": signed_token(key, nonce=nonce), "access_token": "obvious-fake-access-token", "token_type": "Bearer"}
    transport.userinfo_response = {"sub": "subject-1", "email": "alice@example.test", "email_verified": True}
    result = client.callback("fake", f"state={started.state}&code=obvious-fake-code&iss={ISSUER}", "browser-a")
    assert result.claims["sub"] == "subject-1" and result.return_path == "/app"
    token_call = next(c for c in transport.calls if c[1].endswith("/token"))
    assert token_call[2]["Authorization"].startswith("Basic ")
    assert token_call[3]["redirect_uri"] == REDIRECT and "client_secret" not in token_call[3]
    assert "obvious-fake-access-token" not in repr(result)


def test_userinfo_subject_mismatch_is_rejected(tmp_path=None):
    tmp_path = _tmp(tmp_path); rsa_material = _rsa_material()
    key, jwk = rsa_material
    transport = FakeTransport({"keys": [jwk]})
    store = OIDCFlowStore(tmp_path / "flows.json")
    client = OIDCClient({"fake": provider()}, store, transport)
    started = client.start("fake", "browser-a", "/app")
    transport.token_response = {"id_token": signed_token(key, nonce=store.peek(started.state)["nonce"]), "access_token": "obvious-fake-access-token"}
    transport.userinfo_response = {"sub": "attacker"}
    with pytest.raises(OIDCError, match="userinfo_mismatch"):
        client.callback("fake", f"state={started.state}&code=c&iss={ISSUER}", "browser-a")


def test_external_identity_is_unique_never_email_auto_linked_and_sessions_rotate(tmp_path=None):
    tmp_path = _tmp(tmp_path)
    auth = AuthStore(tmp_path, session_ttl=60, session_idle_timeout=30)
    password_user = auth.create_user("alice@example.test", "Password Alice", "password123", "org-1", "viewer")
    sso_user, token = auth.complete_oidc_login(ISSUER, "subject-1", "alice@example.test", "SSO Alice",
                                               "org-1", "viewer", old_session="attacker-fixed")
    assert sso_user.id != password_user.id
    assert auth.get_by_external_identity(ISSUER, "subject-1").id == sso_user.id
    assert token != "attacker-fixed" and auth.get_session(token)
    with pytest.raises(ValueError, match="external_identity_conflict"):
        auth.link_external_identity(password_user.id, ISSUER, "subject-1")
    persisted = (tmp_path / "_users.json").read_text()
    assert "access_token" not in persisted and "id_token" not in persisted and CLIENT_SECRET not in persisted
    auth.destroy_session(token)
    assert auth.get_session(token) is None


def test_disabled_sso_user_cannot_login_or_rotate_existing_session(tmp_path=None):
    tmp_path = _tmp(tmp_path)
    auth = AuthStore(tmp_path, session_ttl=60, session_idle_timeout=30)
    user, old_session = auth.complete_oidc_login(
        ISSUER, "disabled-subject", "disabled@example.test", "Disabled",
        "org-1", "viewer",
    )
    user.active = False
    auth._save_users()
    sessions_before = json.loads((tmp_path / "_sessions.json").read_text())

    with pytest.raises(ValueError, match="account_inactive"):
        auth.complete_oidc_login(
            ISSUER, "disabled-subject", "disabled@example.test", "Disabled",
            "org-1", "viewer", old_session=old_session,
        )

    assert json.loads((tmp_path / "_sessions.json").read_text()) == sessions_before
    assert auth.get_session(old_session) is not None


def test_existing_password_user_json_loads_compatibly(tmp_path=None):
    tmp_path = _tmp(tmp_path)
    auth = AuthStore(tmp_path)
    user = auth.create_user("legacy@example.test", "Legacy", "password123", "org-1")
    raw = json.loads((tmp_path / "_users.json").read_text())
    raw[0].pop("external_identities", None)
    (tmp_path / "_users.json").write_text(json.dumps(raw))
    loaded = AuthStore(tmp_path)
    assert loaded.authenticate("legacy@example.test", "password123").id == user.id
    assert loaded.get(user.id).external_identities == []


def test_google_preset_and_disabled_provider_list_are_non_secret():
    google = OIDCProvider.google(client_id="", client_secret="", redirect_uri="")
    assert google.issuer == "https://accounts.google.com" and not google.enabled
    assert google.authorization_endpoint.startswith("https://accounts.google.com/")
    assert google.token_endpoint == "https://oauth2.googleapis.com/token" and google.jwks_uri.startswith("https://")
    row = google.public_dict()
    assert set(row) == {"name", "label", "enabled"}
    assert CLIENT_SECRET not in json.dumps(row)


def test_loopback_redirect_is_exact_ip_literal_public_client_only():
    local = provider(client_secret="", redirect_uri="http://127.0.0.1:8765/api/auth/sso/fake/callback",
                     token_auth_method="none", local_public_client=True)
    assert local.local_public_client
    for bad in (
        "http://localhost:8765/api/auth/sso/fake/callback",
        "http://0.0.0.0:8765/api/auth/sso/fake/callback",
        "http://192.168.1.2:8765/api/auth/sso/fake/callback",
        "http://127.0.0.1:8765/wrong/callback",
        "http://127.0.0.1:8765/api/auth/sso/fake/callback/extra",
    ):
        with pytest.raises(OIDCError, match="invalid_redirect_uri"):
            provider(client_secret="", redirect_uri=bad, token_auth_method="none", local_public_client=True)


def test_local_public_client_must_match_actual_listener_exactly():
    import saas_server as server
    local_v4 = provider(
        client_secret="", redirect_uri="http://127.0.0.1:8765/api/auth/sso/fake/callback",
        token_auth_method="none", local_public_client=True,
    )
    server._validate_oidc_startup({"fake": local_v4}, "127.0.0.1", 8765)
    for host, port in (("127.0.0.1", 8766), ("::1", 8765), ("0.0.0.0", 8765), ("localhost", 8765)):
        with pytest.raises(RuntimeError, match="OIDC local redirect must match server listener"):
            server._validate_oidc_startup({"fake": local_v4}, host, port)

    local_v6 = provider(
        client_secret="", redirect_uri="http://[::1]:8765/api/auth/sso/fake/callback",
        token_auth_method="none", local_public_client=True,
    )
    server._validate_oidc_startup({"fake": local_v6}, "::1", 8765)


def test_http_routes_complete_crypto_fake_login_with_clean_303(tmp_path=None):
    tmp_path = _tmp(tmp_path); rsa_material = _rsa_material()
    import saas_server as server
    key, jwk = rsa_material
    transport = FakeTransport({"keys": [jwk]})
    flows = OIDCFlowStore(tmp_path / "flows.json", lock=threading.RLock())
    client = OIDCClient({"fake": provider()}, flows, transport)
    old_client, old_providers, old_auth = server._oidc_client, server._oidc_providers, server._auth
    server._oidc_client, server._oidc_providers = client, {"fake": provider()}
    server._auth = AuthStore(tmp_path / "auth")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True); thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port)
        conn.request("GET", "/api/auth/sso/providers", headers={"Host": f"127.0.0.1:{httpd.server_port}"})
        response = conn.getresponse(); providers = json.loads(response.read())
        assert response.status == 200 and providers == {"providers": [{"name": "fake", "label": "Fake IdP", "enabled": True}]}

        conn.request("GET", "/api/auth/sso/fake/start?return_path=%2Fapp", headers={"Host": f"127.0.0.1:{httpd.server_port}"})
        response = conn.getresponse(); response.read()
        assert response.status == 302
        preauth_cookie = response.getheader("Set-Cookie")
        assert "gf_oidc_pre=" in preauth_cookie and "HttpOnly" in preauth_cookie and "SameSite=Lax" in preauth_cookie and "Domain=" not in preauth_cookie
        auth_query = parse_qs(urlparse(response.getheader("Location")).query)
        state = auth_query["state"][0]
        nonce = flows.peek(state)["nonce"]
        transport.token_response = {"id_token": signed_token(key, nonce=nonce), "access_token": "obvious-fake-access-token"}
        transport.userinfo_response = {"sub": "subject-1", "email": "alice@example.test", "email_verified": True}
        cookie_header = preauth_cookie.split(";", 1)[0]
        callback = f"/api/auth/sso/fake/callback?state={state}&code=obvious-fake-code&iss={ISSUER}"
        conn.request("GET", callback, headers={"Host": f"127.0.0.1:{httpd.server_port}", "Cookie": cookie_header})
        response = conn.getresponse(); response.read()
        cookies = response.getheaders()
        assert response.status == 303 and response.getheader("Location") == "/app"
        assert response.getheader("Cache-Control") == "no-store"
        assert response.getheader("Referrer-Policy") == "no-referrer"
        session_cookie = next(value for name, value in cookies if name == "Set-Cookie" and value.startswith("gf_session="))
        attributes = {part.strip().split("=", 1)[0].lower(): part.strip().split("=", 1)[1]
                      for part in session_cookie.split(";") if "=" in part}
        assert int(attributes["max-age"]) == server._auth.session_ttl
        expires_in = parsedate_to_datetime(attributes["expires"]).timestamp() - time.time()
        assert server._auth.session_ttl - 2 <= expires_in <= server._auth.session_ttl + 2
    finally:
        httpd.shutdown(); httpd.server_close(); thread.join(timeout=2)
        server._oidc_client, server._oidc_providers, server._auth = old_client, old_providers, old_auth


def test_http_callback_error_consumes_state_and_redirects_to_generic_clean_url(tmp_path=None):
    tmp_path = _tmp(tmp_path)
    import saas_server as server
    flows = OIDCFlowStore(tmp_path / "flows.json", lock=threading.RLock())
    client = OIDCClient({"fake": provider()}, flows, FakeTransport())
    started = client.start("fake", "browser-a", "/settings")
    old_client, old_providers = server._oidc_client, server._oidc_providers
    server._oidc_client, server._oidc_providers = client, {"fake": provider()}
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True); thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port)
        callback = f"/api/auth/sso/fake/callback?state={started.state}&error=access_denied&iss={ISSUER}"
        conn.request("GET", callback, headers={
            "Host": f"127.0.0.1:{httpd.server_port}",
            "Cookie": "gf_oidc_pre=browser-a",
        })
        response = conn.getresponse(); body = response.read()
        assert response.status == 303
        assert response.getheader("Location") == "/settings?auth_error=sso_failed"
        assert response.getheader("Cache-Control") == "no-store"
        assert response.getheader("Referrer-Policy") == "no-referrer"
        assert body == b""
        assert flows.peek(started.state) is None
        assert "Max-Age=0" in response.getheader("Set-Cookie")
    finally:
        httpd.shutdown(); httpd.server_close(); thread.join(timeout=2)
        server._oidc_client, server._oidc_providers = old_client, old_providers


def test_http_disabled_sso_user_gets_generic_redirect_and_old_session_survives(tmp_path=None):
    tmp_path = _tmp(tmp_path); key, jwk = _rsa_material()
    import saas_server as server
    transport = FakeTransport({"keys": [jwk]})
    flows = OIDCFlowStore(tmp_path / "flows.json", lock=threading.RLock())
    client = OIDCClient({"fake": provider()}, flows, transport)
    auth = AuthStore(tmp_path / "auth")
    user, old_session = auth.complete_oidc_login(
        ISSUER, "disabled-http", "disabled@example.test", "Disabled", "org-1", "viewer"
    )
    user.active = False; auth._save_users()
    started = client.start("fake", "browser-a", "/app")
    nonce = flows.peek(started.state)["nonce"]
    transport.token_response = {"id_token": signed_token(key, nonce=nonce, sub="disabled-http")}
    transport.userinfo_response = None
    old_globals = server._oidc_client, server._oidc_providers, server._auth
    server._oidc_client, server._oidc_providers, server._auth = client, {"fake": provider()}, auth
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True); thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port)
        callback = f"/api/auth/sso/fake/callback?state={started.state}&code=c&iss={ISSUER}"
        conn.request("GET", callback, headers={
            "Host": f"127.0.0.1:{httpd.server_port}",
            "Cookie": f"gf_oidc_pre=browser-a; gf_session={old_session}",
        })
        response = conn.getresponse(); response.read()
        assert response.status == 303 and response.getheader("Location") == "/app?auth_error=sso_failed"
        assert response.getheader("Cache-Control") == "no-store"
        assert response.getheader("Referrer-Policy") == "no-referrer"
        assert not any(value.startswith("gf_session=") for name, value in response.getheaders()
                       if name == "Set-Cookie")
        sessions = json.loads((tmp_path / "auth" / "_sessions.json").read_text())
        assert old_session in sessions and len(sessions) == 1
        assert flows.peek(started.state) is None
    finally:
        httpd.shutdown(); httpd.server_close(); thread.join(timeout=2)
        server._oidc_client, server._oidc_providers, server._auth = old_globals


def test_oidc_dependency_is_optional_until_a_provider_is_enabled():
    import core.oidc as oidc
    import saas_server as server
    old_jwt = oidc.jwt
    old_check = server.oidc_dependencies_available
    try:
        oidc.jwt = None
        server.oidc_dependencies_available = oidc.oidc_dependencies_available
        disabled = provider(enabled=False)
        server._validate_oidc_startup({"fake": disabled}, "127.0.0.1", 8765)
        with pytest.raises(RuntimeError, match="OIDC dependencies unavailable"):
            server._validate_oidc_startup({"fake": provider()}, "127.0.0.1", 8765)
    finally:
        oidc.jwt = old_jwt
        server.oidc_dependencies_available = old_check


def test_http_callback_access_log_redacts_entire_query():
    import saas_server as server
    assert server._redact_access_path("/api/auth/sso/google/callback?code=secret&state=secret") == "/api/auth/sso/google/callback?[REDACTED]"
    assert server._redact_access_path("/api/health?verbose=1") == "/api/health?verbose=1"
