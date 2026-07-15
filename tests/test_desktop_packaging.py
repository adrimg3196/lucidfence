from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_is_native_webkit_not_shell_wrapper():
    swift = (ROOT / "macos" / "LucidFenceApp.swift").read_text()
    plist = (ROOT / "macos" / "Info.plist").read_text()
    assert "WKWebView" in swift
    assert "Process()" in swift
    assert 'CFBundleExecutable</key>\n    <string>LucidFence</string>' in plist
    assert "NSAllowsLocalNetworking" in plist
    assert not (ROOT / "macos" / "LucidFence.app" / "Contents" / "MacOS" / "lucidfence-launcher").exists()


def test_desktop_launcher_owns_only_its_embedded_backend():
    swift = (ROOT / "macos" / "LucidFenceApp.swift").read_text()
    assert 'appendingPathComponent("backend/LucidFenceBackend")' in swift
    assert "startedBackend = true" in swift
    assert "/api/health" in swift
    assert 'health.service == "lucidfence"' in swift
    assert 'health.status == "ok"' in swift
    assert 'environment["LUCIDFENCE_QA_SNAPSHOT"] != nil' in swift
    assert "developerExtrasEnabled" in swift
    assert "navigationType == .linkActivated" in swift
    assert "decisionHandler(.cancel)" in swift
    assert "if startedBackend" in swift
    assert "process.terminate()" in swift
    assert "SIGKILL" in swift
    assert "LUCIDFENCE_DESKTOP_NONCE" in swift
    assert "health.desktopNonce == expectedNonce" in swift
    assert "WKUIDelegate" in swift
    assert "targetFrame == nil" in swift
    assert "pkill" not in swift
    assert "killall" not in swift


def test_desktop_build_includes_only_safe_seed_files():
    build = (ROOT / "macos" / "build_desktop.py").read_text()
    for name in ("fleet_seed.json", "fences.json", "routes.json", "policies.json"):
        assert name in build
    for forbidden in ("_users.json", "_sessions.json", "cloud_state.json", "device_states.json", "trails.jsonl"):
        assert forbidden not in build
    assert "PyInstaller" in build
    assert "vendor_shared" in build
    assert "core.atomicmail.session" in build
    assert "config.desktop.json" in build
    assert "ROOT / 'config.json'" not in build
    assert "hdiutil" in build
    assert "codesign" in build


def test_tenant_seed_loader_uses_packaged_data_directory():
    import tempfile
    import saas_server

    with tempfile.TemporaryDirectory() as source_tmp, tempfile.TemporaryDirectory() as target_tmp:
        source = Path(source_tmp)
        target = Path(target_tmp)
        for name in ("fleet_seed.json", "fences.json", "routes.json", "policies.json"):
            (source / name).write_text('{"seed":"' + name + '"}')
        old = saas_server.TEMPLATE_DATA
        try:
            saas_server.TEMPLATE_DATA = source
            getattr(saas_server, "_seed_tenant_defaults")(target)
        finally:
            saas_server.TEMPLATE_DATA = old
        assert (target / "fences.json").is_file()
        assert "fences.json" in (target / "fences.json").read_text()


def test_desktop_gateway_help_uses_current_origin():
    assert "http://127.0.0.1:8765/v1/chat/completions" not in (ROOT / "static" / "app.js").read_text()


def test_desktop_release_has_drag_to_applications_contract():
    build = (ROOT / "macos" / "build_desktop.py").read_text()
    assert 'os.symlink("/Applications"' in build
    assert "LucidFence-{version}-{arch}.dmg" in build
    assert 'MINIMUM_MACOS = "14.0"' in build
    assert 'apple-macosx{MINIMUM_MACOS}' in build
    assert "spctl" in build
    assert '"app": app.name' in build
    assert '"dmg": dmg.name if dmg else None' in build
    assert '"app": str(app)' not in build
