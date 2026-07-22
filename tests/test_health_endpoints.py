#!/usr/bin/env python3
"""Smoke tests for public health endpoints used by monitoring-expert."""
from __future__ import annotations

import http.client
import sys
import time

HOST = "127.0.0.1"
PORT = 8765


def _get(path: str) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection(HOST, PORT, timeout=3)
    conn.request("GET", path)
    r = conn.getresponse()
    body = r.read()
    conn.close()
    return r.status, body


def wait_server() -> bool:
    for _ in range(20):
        try:
            _get("/api/health")
            return True
        except Exception:
            time.sleep(0.5)
    return False


def test_public_health_endpoints() -> None:
    if not wait_server():
        print("server_not_ready")
        raise AssertionError("server_not_ready")

    checks = ["/api/health", "/api/healthz", "/api/readyz"]
    ok = True
    for path in checks:
        try:
            status, body = _get(path)
            if status != 200:
                ok = False
                print(f"fail {path}: {status} {body.decode('utf-8', 'ignore')[:200]}")
            else:
                print(f"ok {path}: {body.decode('utf-8', 'ignore')[:200]}")
        except Exception as exc:
            ok = False
            print(f"error {path}: {type(exc).__name__}: {exc}")

    assert ok, "one or more public health endpoints failed"


def main() -> int:
    try:
        test_public_health_endpoints()
    except AssertionError as exc:
        print(exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
