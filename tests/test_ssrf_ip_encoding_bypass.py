"""Regresión SSRF: el guard `_safe_webhook_url` debe bloquear destinos internos
escritos en encodings numéricos alternativos (decimal/hex/octal/dotless), no solo
la forma canónica. Hallazgo del Centinela 2026-08-18.

Sin red: solo ejercita la función pura. Runner honesto, sin fixtures pytest.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from saas_server import _safe_webhook_url  # noqa: E402


# Destinos INTERNOS en encodings que glibc getaddrinfo resuelve; todos == loopback
# o link-local/metadata. Deben quedar BLOQUEADOS (devuelve "").
_BLOCKED = [
    "https://2130706433",         # 127.0.0.1 decimal
    "https://2130706433:9/x",     # 127.0.0.1 decimal + puerto/path
    "https://0x7f000001",         # 127.0.0.1 hex
    "https://017700000001",       # 127.0.0.1 octal
    "https://127.1",              # 127.0.0.1 dotless corto
    "https://2852039166",         # 169.254.169.254 (metadata cloud) decimal
    "https://127.0.0.1",          # canónico (ya bloqueado antes del fix)
    "https://169.254.169.254/latest/meta-data",
    "https://10.0.0.5",
    "https://mdm.internal",
]

# Hosts EXTERNOS legítimos: deben seguir PERMITIDOS (el fix no puede romperlos).
_ALLOWED = [
    "https://8.8.8.8",
    "https://api.applivery.io/v1",
    "https://hooks.example.com/incident",
]


def test_numeric_ip_encodings_to_internal_are_blocked():
    for u in _BLOCKED:
        assert _safe_webhook_url(u) == "", f"SSRF bypass no bloqueado: {u!r}"


def test_legit_external_https_hosts_still_allowed():
    for u in _ALLOWED:
        assert _safe_webhook_url(u) == u, f"host externo legítimo roto por el fix: {u!r}"


def test_non_https_and_empty_still_rejected():
    assert _safe_webhook_url("http://api.applivery.io") == ""   # solo https
    assert _safe_webhook_url("") == ""
    assert _safe_webhook_url("https://") == ""
