import importlib.machinery
import os
import signal
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    name = "lucidfence_cli_regression_%s" % os.getpid()
    return importlib.machinery.SourceFileLoader(name, str(ROOT / "bin" / "lucidfence")).load_module()


def test_stop_refuses_unrelated_reused_pid():
    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("LUCIDFENCE_DATA_DIR")
        os.environ["LUCIDFENCE_DATA_DIR"] = tmp
        sleeper = subprocess.Popen(["sleep", "30"])
        try:
            (Path(tmp) / "lucidfence.pid").write_text(str(sleeper.pid))
            cli = _load_cli()
            result = cli.cmd_stop(SimpleNamespace(host="127.0.0.1", port=65530))
            assert result == 1
            assert sleeper.poll() is None
            assert not (Path(tmp) / "lucidfence.pid").exists()
        finally:
            if sleeper.poll() is None:
                sleeper.terminate()
                sleeper.wait(timeout=5)
            if old is None:
                os.environ.pop("LUCIDFENCE_DATA_DIR", None)
            else:
                os.environ["LUCIDFENCE_DATA_DIR"] = old


def test_failed_start_rolls_back_pid_and_child():
    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("LUCIDFENCE_DATA_DIR")
        os.environ["LUCIDFENCE_DATA_DIR"] = tmp
        try:
            cli = _load_cli()
            result = cli.cmd_start(SimpleNamespace(host="203.0.113.1", port=65529, open=False))
            assert result == 1
            assert not (Path(tmp) / "lucidfence.pid").exists()
        finally:
            if old is None:
                os.environ.pop("LUCIDFENCE_DATA_DIR", None)
            else:
                os.environ["LUCIDFENCE_DATA_DIR"] = old


def test_restart_does_not_start_when_stop_fails():
    cli = _load_cli()
    calls = []
    setattr(cli, "cmd_stop", lambda _args: 1)
    setattr(cli, "cmd_start", lambda _args: calls.append("start") or 0)
    result = cli.cmd_restart(SimpleNamespace())
    assert result == 1
    assert calls == []


def test_all_app_assets_are_root_absolute():
    html = (ROOT / "static" / "dashboard.html").read_text()
    js = (ROOT / "static" / "app.js").read_text()
    assert 'href="/static/' in html
    assert 'src="/static/' in html
    assert '"/static/vendor/offline-map.svg"' in js
    assert '"static/' not in html
    assert '"static/' not in js


def test_map_and_device_table_have_independent_filters():
    js = (ROOT / "static" / "app.js").read_text()
    assert "mapFilter" in js
    map_block = js[js.index("function initMap"):js.index("function renderDevices")]
    assert "App.devFilter" not in map_block


def test_offline_map_declares_real_web_mercator_projection():
    js = (ROOT / "static" / "app.js").read_text()
    svg = (ROOT / "static" / "vendor" / "offline-map.svg").read_text()
    assert "offline-iberia" not in js
    assert 'data-projection="EPSG:3857"' in svg


def test_map_views_use_unique_dom_ids():
    js = (ROOT / "static" / "app.js").read_text()
    assert 'id="map"' not in js
    assert 'id="overviewMap"' in js
    assert 'id="fleetMap"' in js
    assert 'initMap(devs, "overviewMap")' in js
    assert 'initMap(App.status.devices||[], "fleetMap")' in js


def test_demo_and_gateway_use_actual_bound_socket():
    import saas_server
    loopback = SimpleNamespace(server=SimpleNamespace(server_address=("127.0.0.1", 8765)), client_address=("127.0.0.1", 1234), headers={})
    exposed = SimpleNamespace(server=SimpleNamespace(server_address=("0.0.0.0", 8765)), client_address=("127.0.0.1", 1234), headers={})
    assert saas_server._bound_host(loopback) == "127.0.0.1"
    assert saas_server._gateway_allowed(loopback) is True
    assert saas_server._gateway_allowed(exposed) is False
    server = (ROOT / "saas_server.py").read_text()
    assert "bound_host = _bound_host(self)" in server
