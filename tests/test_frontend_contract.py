"""Static frontend contract checks for controls that must reach real APIs."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_incident_operations_view_is_wired():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="view-incidents"' in html
    assert 'id:"incidents"' in js
    assert "function renderIncidents" in js
    assert "/api/incidents/" in js and "/transition" in js


def test_frontend_normalizes_iso_and_unix_timestamps():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "function parseTime" in js
    assert "new Date(ts*1000)" not in js
    assert "y:undefined" not in js, "Chart.js scale config is overwritten and logs runtime errors"


def test_local_dashboard_uses_passwordless_loopback_demo_session():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    server = (ROOT / "saas_server.py").read_text(encoding="utf-8")
    assert 'fetch("/api/auth/demo", {method:"POST"})' in js
    assert 'route == "/api/auth/demo"' in server
    assert "demo login solo disponible en localhost" in server
    assert "demo1234" not in js


def test_command_center_uses_reicon_for_ui_icons():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert html.index("/static/reicon-data.js") < html.index("/static/reicon.js") < html.index("/static/app.js")
    assert "data:image/svg" not in html
    assert "<svg" not in html, "static shell still contains hand-rolled icons"
    assert "hydrateReicons" in js and 'reicon("trash")' in js
    # The only remaining inline SVGs are data visualizations (donut/ring), not icons.
    assert js.count("<svg") == 2


def test_workflow_select_uses_api_value_field():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "t.value" in js
    assert "a.value" in js


def test_route_form_sends_backend_supported_geometry():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    # Backend accepts either explicit waypoints or selected geofence IDs.
    assert "fence_ids:fs" in js or "waypoints:" in js
    assert "corridor_m" in js


def test_saas_loads_and_applies_real_reicon_library():
    html = (ROOT / "static" / "saas.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "saas.js").read_text(encoding="utf-8")
    data = (ROOT / "static" / "reicon-data.js").read_text(encoding="utf-8")
    assert html.index("/static/reicon-data.js") < html.index("/static/reicon.js") < html.index("/static/saas.js")
    assert "window.REICON_DATA" in data and '"shield-check"' in data
    for view in ("overview", "map", "devices", "routes", "workflows", "risk", "policies", "compliance", "billing", "users", "settings"):
        assert view in js, f"missing Reicon mapping for {view}"
    assert "decorateIcons" in js and "MutationObserver" in js


def test_settings_endpoints_are_tenant_local_and_token_test_is_reachable():
    server = (ROOT / "saas_server.py").read_text(encoding="utf-8")
    assert 'route == "/api/settings/test" and method == "POST"' in server
    settings_block = server.split("# settings / credentials (strictly tenant-local)", 1)[1].split("# ---- IA / MoA", 1)[0]
    assert "tdir = _tenants.data_dir(org)" in settings_block
    assert "core_secrets.save_credentials(tdir" in settings_block
    assert "core_secrets.status(tdir)" in settings_block
    assert "core_secrets.read_key(tdir)" in settings_block
    assert "core_secrets.save_credentials(ROOT" not in settings_block
