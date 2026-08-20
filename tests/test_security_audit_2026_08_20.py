"""Regression tests for the SOC security audit 2026-08-20.

Covers:
  H-1  rate-limiter bypass via rotating gf_session cookie
  H-2  CSV formula / DDE injection in export
  H-3  SSRF residual via public-DNS->internal-IP and non-allowlisted ports
  L-2  HTML escape must quote " and ' (not just & < >)

No network by default; the DNS-resolution path of H-3 is exercised with a
monkeypatched socket.getaddrinfo so it is deterministic in CI.
"""
import os
import socket
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import saas_server  # noqa: E402  (importable; see existing test_ssrf_ip_encoding_bypass)
from lucidfence.core.export import _csv_escape, _h, export_inventory_csv  # noqa: E402
from lucidfence.saas.auth import AuthStore  # noqa: E402


# ----------------------------------------------------------------- H-1 -----
class _Hdr:
    def __init__(self, cookie):
        self._cookie = cookie

    def get(self, name, default=None):
        if name == "Cookie" and self._cookie:
            return f"{saas_server.COOKIE_SESSION}={self._cookie}"
        return default

    def get_all(self, name):
        v = self.get(name)
        return [] if v is None else [v]


class _FakeHandler:
    def __init__(self, cookie=None, ip="1.2.3.4"):
        self.headers = _Hdr(cookie)
        self.client_address = (ip, 0)


def _real_auth_with_session():
    tmp = tempfile.mkdtemp()
    store = AuthStore(tmp)
    token = store.create_session("user-123")
    return store, token


def test_valid_session_still_gives_session_bucket():
    store, token = _real_auth_with_session()
    saved = saas_server._auth
    saas_server._auth = store
    try:
        key = saas_server._rate_limit_key(_FakeHandler(cookie=token))
    finally:
        saas_server._auth = saved
    assert key.startswith("sess:"), key


def test_random_cookie_falls_back_to_ip_bucket():
    # The core of H-1: an unauthenticated client rotating the cookie on every
    # request must NOT get a fresh per-request bucket. It must bucket by IP.
    store, _ = _real_auth_with_session()  # store has no random tokens
    saved = saas_server._auth
    saas_server._auth = store
    try:
        key = saas_server._rate_limit_key(_FakeHandler(cookie="deadbeef-rotating"))
    finally:
        saas_server._auth = saved
    assert key == "ip:1.2.3.4", f"rate limiter bypassed: {key!r}"


def test_no_cookie_falls_back_to_ip_bucket():
    saved = saas_server._auth
    saas_server._auth = _real_auth_with_session()[0]
    try:
        key = saas_server._rate_limit_key(_FakeHandler(cookie=None))
    finally:
        saas_server._auth = saved
    assert key == "ip:1.2.3.4", key


# ----------------------------------------------------------------- H-2 -----
def test_csv_escape_neutralizes_formula_prefixes():
    for prefix in ("=", "+", "-", "@", "\t", "\r"):
        val = prefix + "evil()"
        out = _csv_escape(val)
        # The leading apostrophe must precede the dangerous prefix so the
        # spreadsheet treats the cell as text, not a formula/DDE command.
        assert ("'" + val) in out, f"{val!r} -> {out!r} (not neutralized)"


def test_csv_escape_normal_values_unaffected():
    assert _csv_escape("normal name") == "normal name"
    assert _csv_escape("a,b") == '"a,b"'
    assert _csv_escape(None) == ""


def test_export_inventory_csv_defuses_device_controlled_field():
    devices = [{
        "device_id": "d1", "name": "=cmd|'/C calc'!A0", "platform": "ios",
        "assigned_user": "@evil", "city": "+SUM(A1:A9)", "department": "Eng",
    }]
    csv = export_inventory_csv(devices)
    # The leading apostrophe must be present in the row (Excel/LibreOffice defuse)
    assert "'=cmd|'/C calc'!A0" in csv, csv
    assert "'@evil" in csv, csv
    assert "'+SUM(A1:A9)" in csv, csv


# ----------------------------------------------------------------- H-3 -----
def test_safe_webhook_rejects_non_allowlisted_port():
    # No DNS needed; port check runs before resolution.
    assert saas_server._safe_webhook_url("https://evil.example:22/hook") == ""
    assert saas_server._safe_webhook_url("https://evil.example:8080/hook") == ""


def test_safe_webhook_blocks_public_dns_resolving_to_internal():
    orig = socket.getaddrinfo

    def fake(host, port, family=0, type=0, proto=0, flags=0):
        if host == "evil.public.example":
            # Public name that (in reality) resolves to an internal IP.
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.5", 0))]
        if host == "good.public.example":
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 0))]
        return orig(host, port, family, type, proto, flags)

    with mock.patch("socket.getaddrinfo", fake):
        # Public name -> internal IP must be blocked.
        assert saas_server._safe_webhook_url("https://evil.public.example/hook") == ""
        # Public name -> public IP is allowed (sanity: fix doesn't over-block).
        assert saas_server._safe_webhook_url("https://good.public.example/hook") == \
            "https://good.public.example/hook"


def test_safe_webhook_still_blocks_numeric_internal_after_fix():
    # Regression guard for the 2026-08-18 fix (numeric IP encodings).
    assert saas_server._safe_webhook_url("https://2852039166") == ""   # 169.254.169.254
    assert saas_server._safe_webhook_url("https://2130706433") == ""    # 127.0.0.1
    assert saas_server._safe_webhook_url("https://8.8.8.8") == "https://8.8.8.8"


# ----------------------------------------------------------------- L-2 -----
def test_html_escape_quotes_attribute_values():
    assert _h('"><script>') == "&quot;&gt;&lt;script&gt;"
    assert _h("a&b") == "a&amp;b"
    assert _h('plain') == "plain"
