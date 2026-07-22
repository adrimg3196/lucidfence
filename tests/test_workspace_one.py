from __future__ import annotations

from core.adapters import ADAPTER_REGISTRY
from core.adapters.workspace_one import WorkspaceONEAdapter, build_workspace_one_adapter_from_config


def test_workspace_one_is_registered_and_mock_ready():
    assert ADAPTER_REGISTRY["workspace_one"] is WorkspaceONEAdapter
    adapter = WorkspaceONEAdapter()
    result = adapter.execute({"device_id": "ws1-1", "name": "Rugged"}, "lock", {}, False)
    assert result["ok"] is True and result["mock"] is True
    assert result["adapter"] == "workspace_one"


def test_workspace_one_live_missing_credentials_never_raises():
    result = WorkspaceONEAdapter(live=True).execute({"device_id": "ws1-1"}, "lock", {}, False)
    assert result["ok"] is False
    assert result["error_type"] == "auth_error"


def test_workspace_one_dry_run_and_geofence_export():
    adapter = WorkspaceONEAdapter(live=True, base_url="https://uem.example.test", tenant_code="tenant", username="user", password="secret")
    dry = adapter.execute({"device_id": "ws1/1"}, "lock", {}, True)
    assert dry["ok"] is True
    assert "ws1%2F1" in dry["would_send"]["url"]
    exported = adapter.execute({"device_id": "ws1-1"}, "sync_geofences", {"fences": [{"id": "hq"}]}, False)
    assert exported["ok"] is True and exported["mode"] == "export"
    assert exported["count"] == 1


def test_workspace_one_config_builder():
    adapter = build_workspace_one_adapter_from_config({"mdm": {"workspace_one": {"base_url": "https://uem.example.test", "live": True}}})
    assert adapter.live is True
    assert adapter.base_url == "https://uem.example.test"
