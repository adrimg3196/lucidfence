"""Tenant-local credential isolation tests."""
import os
import tempfile
from pathlib import Path

from core import secrets as core_secrets
from core.actions import LiveAdapter
from core.location_source import LiveLocationSource


def test_credentials_are_isolated_by_root():
    with tempfile.TemporaryDirectory() as td:
        a = Path(td) / "org-a"
        b = Path(td) / "org-b"
        a.mkdir(); b.mkdir()
        core_secrets.save_credentials(a, "token-org-a-123", "workspace-a")
        assert core_secrets.read_key(a) == "token-org-a-123"
        assert core_secrets.read_org_id(a) == "workspace-a"
        assert core_secrets.read_key(b) == ""
        assert core_secrets.read_org_id(b) == ""
        assert (a / ".env").stat().st_mode & 0o777 == 0o600


def test_live_clients_prefer_explicit_tenant_key_over_process_env():
    old = os.environ.get("APPLIVERY_API_KEY")
    os.environ["APPLIVERY_API_KEY"] = "wrong-global-key"
    try:
        src = LiveLocationSource("workspace-a", api_key="tenant-key")
        adapter = LiveAdapter("workspace-a", "/x", api_key="tenant-key")
        assert src._headers()["Authorization"] == "Bearer tenant-key"
        assert adapter._headers()["Authorization"] == "Bearer tenant-key"
    finally:
        if old is None:
            os.environ.pop("APPLIVERY_API_KEY", None)
        else:
            os.environ["APPLIVERY_API_KEY"] = old
