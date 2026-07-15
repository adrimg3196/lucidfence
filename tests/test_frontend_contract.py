"""Static frontend contract checks for controls that must reach real APIs."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_incident_operations_view_is_wired():
    # The command center SPA is dashboard.html, not the
    # marketing landing index.html. Assert against the real SPA shell.
    html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")
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


def test_risk_engine_explicable_is_wired_in_ui():
    """G2: the Risk Engine's explicable output (reasons + verified)
    must be rendered in the UI. The client normalizes BOTH the
    spec'd shape {reasons[], verified} and the real product-layer
    /api/risk -> risk:[{factors:[{label}], level}]."""
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "function normalizeRisk" in js
    assert "function verifiedBadge" in js
    assert "function reasonsList" in js or "function reasonsSummary" in js
    # handles the real backend shape (factors[].label) when reasons absent
    assert "factors" in js
    # verified badge text reflects real signal vs no-signal
    assert "Verificado" in js
    assert "no verificado" in js or "Sin señal" in js


def test_local_dashboard_has_one_click_demo_without_client_side_credentials():
    """G1: local-first onboarding must be one click without exposing a
    hardcoded password in the browser bundle. Real login/signup remains wired
    for users created on the customer's own machine."""
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    server = (ROOT / "saas_server.py").read_text(encoding="utf-8")
    assert '"/api/auth/demo"' in js
    assert 'route == "/api/auth/demo"' in server
    assert '"/api/auth/me"' in js
    assert '"/api/auth/logout"' in js
    assert '"/api/auth/login"' in js
    assert '"/api/auth/signup"' in js
    # No hardcoded credentials in the client.
    assert "demo1234" not in js
    assert "[REDACTED]" not in js


def test_command_center_uses_reicon_for_ui_icons():
    # The command center SPA is served from dashboard.html,
    # not the marketing landing index.html. Assert against the real SPA shell.
    html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert html.index("static/reicon-data.js") < html.index("static/reicon.js") < html.index("static/app.js")
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


def test_dashboard_loads_and_applies_real_reicon_library():
    html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    data = (ROOT / "static" / "reicon-data.js").read_text(encoding="utf-8")
    assert html.index("static/reicon-data.js") < html.index("static/reicon.js") < html.index("static/app.js")
    assert "window.REICON_DATA" in data and '"shield-check"' in data
    for view in ("overview", "map", "devices", "routes", "workflows", "risk", "settings"):
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
