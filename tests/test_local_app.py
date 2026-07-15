from pathlib import Path
import os
import socket
import subprocess
import sys
import tempfile
import urllib.request

from core.app_paths import data_dir

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


def test_cli_version_and_managed_lifecycle():
    cli = ROOT / "bin" / "lucidfence"
    version = subprocess.run([sys.executable, str(cli), "--version"], capture_output=True, text=True)
    assert version.returncode == 0
    assert version.stdout.strip() == "lucidfence 1.2.0"

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
