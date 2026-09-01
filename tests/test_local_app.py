from pathlib import Path
import os
import socket
import subprocess
import sys
import tempfile
import urllib.request
from types import SimpleNamespace
from unittest import mock

from lucidfence.core.app_paths import data_dir

ROOT = Path(__file__).resolve().parents[1]


def test_data_dir_override_wins():
    got = data_dir({"LUCIDFENCE_DATA_DIR": "/tmp/lf-custom"}, platform="darwin", home=Path("/Users/test"))
    assert got == Path("/tmp/lf-custom").resolve()


def test_data_dir_macos_native_location():
    got = data_dir({}, platform="darwin", home=Path("/Users/test"))
    assert got == Path("/Users/test/Library/Application Support/LucidFence")


def test_data_dir_linux_xdg_location():
    got = data_dir({"XDG_STATE_HOME": "/srv/state"}, platform="linux", home=Path("/home/test"))
    assert got == Path("/srv/state/lucidfence")


def test_server_uses_portable_data_root_and_dashboard_home():
    source = (ROOT / "saas_server.py").read_text()
    assert "DATA_ROOT = ensure_data_dir()" in source
    assert "TenantStore(DATA_ROOT)" in source
    assert 'if route in ("/", "/app", "/app/", "/dashboard", "/dashboard.html")' in source
    assert 'if route in ("/about", "/index.html", "/landing", "/landing.html")' in source


def test_http_server_bind_does_not_depend_on_reverse_dns():
    import socket as socket_module
    import saas_server

    with mock.patch.object(socket_module, "getfqdn", side_effect=RuntimeError("DNS bloqueado")):
        server = saas_server.LucidFenceHTTPServer(("127.0.0.1", 0), saas_server.Handler)
    try:
        assert server.server_name == "127.0.0.1"
        assert server.server_port > 0
    finally:
        server.server_close()


def test_start_deadline_includes_slow_health_probes():
    import lucidfence.cli as cli_module

    class FakeClock:
        def __init__(self):
            self.now = 0.0

        def monotonic(self):
            return self.now

        def sleep(self, seconds):
            self.now += seconds

    class FakeProcess:
        pid = 4242

        def poll(self):
            return None

    clock = FakeClock()

    def slow_unhealthy(_host, _port, timeout=0.8):
        clock.now += timeout
        return False

    with tempfile.TemporaryDirectory(prefix="lucidfence-deadline-") as tmp:
        log_path = Path(tmp) / "lucidfence.log"
        with (
            mock.patch.object(cli_module.time, "monotonic", side_effect=clock.monotonic),
            mock.patch.object(cli_module.time, "sleep", side_effect=clock.sleep),
            mock.patch.object(cli_module, "_healthy", side_effect=slow_unhealthy),
            mock.patch.object(cli_module, "_runtime_dir", return_value=Path(tmp)),
            mock.patch.object(cli_module, "_log_file", return_value=log_path),
            mock.patch.object(cli_module, "_write_pid_record"),
            mock.patch.object(cli_module, "_rollback_start"),
            mock.patch.object(cli_module.subprocess, "Popen", return_value=FakeProcess()),
        ):
            rc = cli_module.cmd_start(
                SimpleNamespace(host="127.0.0.1", port=54321, open_browser=False)
            )

    assert rc == 1
    assert clock.now <= 16.0, f"startup tardó {clock.now:.2f}s simulados"


def test_cli_version_and_managed_lifecycle():
    cli = ROOT / "lucidfence" / "cli.py"
    version = subprocess.run([sys.executable, str(cli), "--version"], capture_output=True, text=True)
    assert version.returncode == 0
    # La versión canónica vive en pyproject.toml (ver
    # test_version_consistency.py): el test no debe hardcodearla o se queda
    # rancio en cada release, que es exactamente cómo llegó a decir 1.2.0.
    import tomllib
    with open(ROOT / "pyproject.toml", "rb") as fh:
        expected = tomllib.load(fh)["project"]["version"]
    assert version.stdout.strip() == f"lucidfence {expected}"

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    with tempfile.TemporaryDirectory(prefix="lucidfence-test-") as tmp:
        env = dict(os.environ)
        env.update({"LUCIDFENCE_DATA_DIR": tmp, "LUCIDFENCE_PORT": str(port)})
        start = subprocess.run(
            [sys.executable, str(cli), "start", "--no-open"],
            env=env, capture_output=True, text=True, timeout=30,
        )
        try:
            assert start.returncode == 0, start.stderr
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
                html = response.read().decode()
            assert response.status == 200
            assert "Command Center" in html
            status = subprocess.run(
                [sys.executable, str(cli), "status"], env=env,
                capture_output=True, text=True, timeout=10,
            )
            assert status.returncode == 0
            assert "activo" in status.stdout
        finally:
            subprocess.run(
                [sys.executable, str(cli), "stop"], env=env,
                capture_output=True, text=True, timeout=10,
            )
