"""Regresión del H-3 follow-up (tarea t_cd79333c): DNS-rebinding TOCTOU en webhooks.

La vulnerabilidad: `_safe_webhook_url` valida el hostname en CONFIG time, pero el
connect real re-resolvía el nombre en SEND time. Un atacante con control de DNS
podía devolver una IP pública en validación y una RFC1918 / link-local / metadata
(169.254.169.254) en connect, pivotando pasado el guard.

Este test simula exactamente eso: un resolver mock que devuelve 1.2.3.4 (público,
válido) en la "validación" y 169.254.169.254 (metadata) en el "connect". Con el
pinned-IP connect, la conexión DEBE ir a 1.2.3.4 (la IP validada), nunca a la
metadata — y el test lo comprueba interceptando `socket.create_connection`.

Sin red real: todo es mock/in-process.
"""
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core import notifier  # noqa: E402

# La IP que el atacante quiere alcanzar por el pivote (cloud metadata / link-local).
_MALICIOUS_IP = "169.254.169.254"
# La IP pública legítima que el guard acepta en validación.
_PUBLIC_IP = "1.2.3.4"
# IP privada RFC1918 (también debe quedar pinned a la pública validada, no rebind).
_RFC1918_IP = "10.9.8.7"

_CONNECTED_TO: list = []  # registra cada (ip, port) usado por socket.create_connection


def _make_resolver(validation_ip, connect_ip):
    """Devuelve un resolver que cambia según CUÁNDO se llama (simula rebinding)."""
    calls = {"n": 0}

    def resolver(host, port, type=socket.SOCK_STREAM):  # noqa: A002
        calls["n"] += 1
        # Primera llamada = validación (acepta la pública); el resto = connect time
        # (el atacante rebinda a la IP maliciosa).
        ip = validation_ip if calls["n"] == 1 else connect_ip
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    return resolver


def _wrap_create_connection(connect_ip):
    """Reemplaza socket.create_connection para registrar y ASSERTIR el destino."""
    real = socket.create_connection

    def fake(addr, *a, **k):
        ip, port = addr[0], addr[1]
        _CONNECTED_TO.append((ip, port))
        # El núcleo del test: con pinned-IP connect, el destino REAL debe ser la IP
        # validada (pública), NUNCA la IP maliciosa a la que rebindió el DNS.
        assert ip != connect_ip, (
            f"TOCTOU no cerrado: connect llegó a {ip} (DNS rebindeado) en vez de "
            f"la IP validada"
        )
        # No abrimos red real: devolvemos un socket fake que cierra sin errores de
        # transporte para que http.client vea una conexión "establecida".
        return _FakeSocket()

    return fake


class _FakeSocket:
    """Socket mínimo: soporta wrap_socket (https) y los métodos de http.client."""

    def __init__(self):
        self._buf = b""

    def settimeout(self, *a, **k):
        return None

    def getpeername(self):
        return ("1.2.3.4", 443)

    # Para HTTPS: ssl wrap_socket devuelve el mismo objeto (finge handshake OK).
    def __getattr__(self, name):
        return lambda *a, **k: None


def _run_post(resolver, connect_ip, url, https=True):
    real_cn = socket.create_connection
    real_getaddrinfo = socket.getaddrinfo
    try:
        socket.getaddrinfo = resolver
        socket.create_connection = _wrap_create_connection(connect_ip)
        notifier.socket.getaddrinfo = resolver
        notifier.socket.create_connection = socket.create_connection
        return notifier._default_http_post(
            url, {"event": "x"}, {"Content-Type": "application/json"}
        )
    finally:
        socket.create_connection = real_cn
        socket.getaddrinfo = real_getaddrinfo
        notifier.socket.getaddrinfo = real_getaddrinfo
        notifier.socket.create_connection = real_cn


def _base_url(https):
    return "https://hooks.example.com/incident" if https else "http://hooks.example.com/incident"


def test_toctou_public_to_metadata_is_pinned():
    """Rebind público->169.254.169.254: connect DEBE ir a la IP pública validada."""
    _CONNECTED_TO.clear()
    resolver = _make_resolver(_PUBLIC_IP, _MALICIOUS_IP)
    res = _run_post(resolver, _MALICIOUS_IP, _base_url(True))
    assert _CONNECTED_TO, "no se abrió ninguna conexión"
    assert all(ip != _MALICIOUS_IP for ip, _ in _CONNECTED_TO), (
        f"connect tocó IP de metadata {_MALICIOUS_IP}: {_CONNECTED_TO}"
    )
    # La IP fijada (validada) es la pública.
    assert _CONNECTED_TO[0][0] == _PUBLIC_IP, (
        f"se esperaba connect a {_PUBLIC_IP} (validada), fue a {_CONNECTED_TO[0][0]}"
    )


def test_toctou_public_to_rfc1918_is_pinned():
    """Rebind público->10.x: también debe quedar pinned a la IP pública validada."""
    _CONNECTED_TO.clear()
    resolver = _make_resolver(_PUBLIC_IP, _RFC1918_IP)
    res = _run_post(resolver, _RFC1918_IP, _base_url(True))
    assert _CONNECTED_TO[0][0] == _PUBLIC_IP, (
        f"se esperaba connect a {_PUBLIC_IP}, fue a {_CONNECTED_TO[0][0]}"
    )


def test_toctou_http_scheme_also_pinned():
    """El esquema http (SIEM on-prem) también debe fijar la IP validada."""
    _CONNECTED_TO.clear()
    resolver = _make_resolver(_PUBLIC_IP, _MALICIOUS_IP)
    res = _run_post(resolver, _MALICIOUS_IP, _base_url(False))
    assert _CONNECTED_TO[0][0] == _PUBLIC_IP, (
        f"http: se esperaba connect a {_PUBLIC_IP}, fue a {_CONNECTED_TO[0][0]}"
    )


def test_literal_ip_bypasses_dns_no_rebind():
    """Una IP literal no habla DNS: connect va directo a la IP (comportamiento legacy)."""
    _CONNECTED_TO.clear()
    # Una IP literal jamás llama a getaddrinfo; no hay superficie de rebinding.
    res = notifier._default_http_post(
        "http://127.0.0.1:9099/hook", "ping", {"Content-Type": "text/plain"}
    )
    # No chequeamos éxito de red (el harness local puede o no escuchar); solo que
    # el path no rompa y que _webhook_resolve devuelva la IP literal tal cual.
    assert notifier._webhook_resolve("127.0.0.1", 9099) == ["127.0.0.1"]


def test_webhook_resolve_blocks_pivot_address():
    """_webhook_resolve debe rechazar (ValueError) si CUALQUIER IP es link-local."""
    # Simulamos un resolver que devuelve SOLO la metadata IP.
    def pivot_resolver(host, port, type=socket.SOCK_STREAM):  # noqa: A002
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_MALICIOUS_IP, port))]

    saved = notifier.socket.getaddrinfo
    try:
        notifier.socket.getaddrinfo = pivot_resolver
        raised = False
        try:
            notifier._webhook_resolve("hooks.evil.test", 443)
        except ValueError:
            raised = True
        assert raised, "se esperaba ValueError: el resolver devolvió IP de metadata"
    finally:
        notifier.socket.getaddrinfo = saved


def test_webhook_resolve_allows_rfc1918():
    """_webhook_resolve permite RFC1918 (trade-off local-first, no un bug)."""
    def priv_resolver(host, port, type=socket.SOCK_STREAM):  # noqa: A002
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_RFC1918_IP, port))]

    saved = notifier.socket.getaddrinfo
    try:
        notifier.socket.getaddrinfo = priv_resolver
        out = notifier._webhook_resolve("siem.corp.local", 8443)
        assert out == [_RFC1918_IP], f"RFC1918 debe permitirse, got {out}"
    finally:
        notifier.socket.getaddrinfo = saved


if __name__ == "__main__":
    test_toctou_public_to_metadata_is_pinned()
    test_toctou_public_to_rfc1918_is_pinned()
    test_toctou_http_scheme_also_pinned()
    test_literal_ip_bypasses_dns_no_rebind()
    test_webhook_resolve_blocks_pivot_address()
    test_webhook_resolve_allows_rfc1918()
    print("ALL test_webhook_toctou_pinning PASSED")
