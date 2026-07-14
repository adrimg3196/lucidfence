"""Static frontend contract checks for controls that must reach real APIs."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_incident_operations_view_is_wired():
    # The command center SPA is dashboard.html (and saas.html), not the
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


def test_local_dashboard_requires_real_authentication_no_demo_shortcut():
    """G1: the dashboard must use the REAL multi-tenant SaaS auth
    (signup/login via /api/auth/*), never a passwordless demo shortcut.
    A demo login would let anyone into any tenant on localhost."""
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    server = (ROOT / "saas_server.py").read_text(encoding="utf-8")
    # No demo shortcut left in the client or the server.
    assert 'fetch("/api/auth/demo"' not in js
    assert 'route == "/api/auth/demo"' not in server
    # Real auth flow is wired: ensureAuth -> /api/auth/me,
    # submitAuth -> /api/auth/{login,signup}, logout -> /api/auth/logout.
    assert "async function ensureAuth" in js
    assert "async function submitAuth" in js
    assert "async function logout" in js
    assert '"/api/auth/me"' in js
    assert '"/api/auth/logout"' in js
    # login + signup are reached (tab-driven; no demo).
    assert "login" in js and "signup" in js
    # No hardcoded credentials in the client.
    assert "demo1234" not in js


def test_command_center_uses_reicon_for_ui_icons():
    # The command center SPA is served from dashboard.html (and saas.html),
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


def test_cloud_vitrina_muestra_cumplimiento_geocerca_ios():
    html = (ROOT / "static" / "cloud.html").read_text(encoding="utf-8")
    assert "Geo iOS" in html
    assert "iOS Geo OK" in html
    assert "geofence_compliance_applicable" in html
    assert "geofence_compliant" in html
    assert "geofence_compliance_label" in html


def test_cloud_vitrina_expone_chromeos_como_platform():
    html = (ROOT / "static" / "cloud.html").read_text(encoding="utf-8")
    assert "Plataforma" in html
    assert "ChromeOS" in html
    assert "chromeos" in html
    assert "platformLabel" in html
    assert "su_platform" in html


def test_cloud_vitrina_muestra_densidad_departamento_y_filtro_tenant():
    html = (ROOT / "static" / "cloud.html").read_text(encoding="utf-8")
    assert 'id="tenantFilter"' in html
    assert "function applyTenantFilter" in html
    assert "FILTERED_TENANTS" in html
    assert "Sin tenants para" in html
    assert "filterActive ? []" in html
    assert 'id="deptDensity"' in html
    assert "function departmentDensity" in html
    assert "function renderDepartmentDensity" in html
    assert "halo = densidad por departamento" in html
