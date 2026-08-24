"""Installer health gate: never report success before the app is ready."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


def _run_installer(*, succeed_after: int, timeout: int = 2,
                   docker_available: bool = False,
                   public_host: str = "",
                   server_stays_alive: bool = True,
                   curl_available: bool = True):
    with tempfile.TemporaryDirectory(prefix="lucidfence-install-health-") as raw:
        checkout = Path(raw)
        shutil.copy2(ROOT / "install.sh", checkout / "install.sh")
        (checkout / "saas_server.py").write_text("# controlled installer fixture\n")
        (checkout / "docker-compose.yml").write_text("services: {}\n")
        (checkout / "requirements.lock").write_text(
            "fixture==1 --hash=sha256:0123456789abcdef\n")

        fake_bin = checkout / "fake-bin"
        fake_bin.mkdir()
        if not curl_available:
            for command in (
                "bash", "cat", "chmod", "cp", "date", "dirname", "grep",
                "mkdir", "nohup", "rm", "sleep",
            ):
                executable = shutil.which(command)
                assert executable is not None
                (fake_bin / command).symlink_to(executable)
        docker_exit = 0 if docker_available else 1
        _executable(
            fake_bin / "docker",
            f"#!/usr/bin/env bash\nexit {docker_exit}\n",
        )
        _executable(
            fake_bin / "python3",
            "#!/usr/bin/env bash\n"
            "if [[ \"${1:-}\" == \"-m\" && \"${2:-}\" == \"venv\" ]]; then\n"
            "  mkdir -p \"$3/bin\"\n"
            "  cp \"$0\" \"$3/bin/python\"\n"
            "  chmod +x \"$3/bin/python\"\n"
            "  exit 0\n"
            "fi\n"
            "if [[ \"${1:-}\" == \"-m\" && \"${2:-}\" == \"pip\" ]]; then exit 0; fi\n"
            "if [[ \"${1:-}\" == \"-\" ]]; then\n"
            "  count=0\n"
            "  if [[ -f \"$FAKE_CURL_STATE\" ]]; then count=$(<\"$FAKE_CURL_STATE\"); fi\n"
            "  count=$((count + 1))\n"
            "  printf '%s' \"$count\" > \"$FAKE_CURL_STATE\"\n"
            "  if (( count < FAKE_CURL_SUCCEED_AFTER )); then exit 1; fi\n"
            "  printf '{\"status\":\"ok\"}\\n'\n"
            "  exit 0\n"
            "fi\n"
            "if [[ \"${1:-}\" == \"saas_server.py\" && \"$FAKE_SERVER_STAYS_ALIVE\" == \"1\" ]]; then\n"
            "  exec sleep 30\n"
            "fi\n"
            "exit 0\n",
        )
        if curl_available:
            _executable(
                fake_bin / "curl",
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "count=0\n"
                "if [[ -f \"$FAKE_CURL_STATE\" ]]; then count=$(<\"$FAKE_CURL_STATE\"); fi\n"
                "count=$((count + 1))\n"
                "printf '%s' \"$count\" > \"$FAKE_CURL_STATE\"\n"
                "if (( count < FAKE_CURL_SUCCEED_AFTER )); then exit 22; fi\n"
                "printf '{\"status\":\"ok\"}\\n'\n",
            )

        state = checkout / "curl-count"
        env = dict(os.environ)
        env.update({
            "PATH": (
                f"{fake_bin}:{env['PATH']}" if curl_available
                else str(fake_bin)
            ),
            "FAKE_CURL_STATE": str(state),
            "FAKE_CURL_SUCCEED_AFTER": str(succeed_after),
            "FAKE_SERVER_STAYS_ALIVE": "1" if server_stays_alive else "0",
            "LUCIDFENCE_HEALTH_TIMEOUT": str(timeout),
        })
        if public_host:
            env["LUCIDFENCE_PUBLIC_HOST"] = public_host
        result = subprocess.run(
            ["bash", "install.sh"], cwd=checkout, env=env,
            text=True, capture_output=True, timeout=10, check=False,
        )
        attempts = int(state.read_text()) if state.exists() else 0
        pid_file = checkout / "lucidfence.pid"
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text()), 15)
            except (OSError, ValueError):
                pass
        return result, attempts


def test_python_fallback_waits_until_health_is_ready():
    result, attempts = _run_installer(succeed_after=2)
    assert result.returncode == 0, result.stderr
    assert attempts >= 2
    assert "Health confirmado" in result.stdout


def test_python_fallback_creates_an_isolated_virtualenv():
    result, _attempts = _run_installer(succeed_after=1)
    assert result.returncode == 0, result.stderr
    assert "Creando entorno Python aislado" in result.stdout
    assert "Dependencias instaladas en .venv" in result.stdout


def test_python_fallback_fails_closed_when_health_times_out():
    result, attempts = _run_installer(succeed_after=999, timeout=1)
    assert result.returncode != 0
    assert attempts >= 1
    assert "no respondió" in result.stderr


def test_docker_install_fails_closed_when_health_times_out():
    result, attempts = _run_installer(
        succeed_after=999, timeout=1, docker_available=True)
    assert result.returncode != 0
    assert attempts >= 1
    assert "no respondió" in result.stderr


def test_public_docker_does_not_claim_success_before_health():
    result, _attempts = _run_installer(
        succeed_after=999, timeout=1, docker_available=True,
        public_host="fence.example.test",
    )
    assert result.returncode != 0
    assert "arrancado en https://fence.example.test" not in result.stdout


def test_python_fallback_rejects_health_from_an_unrelated_process():
    result, attempts = _run_installer(
        succeed_after=2, server_stays_alive=False)
    assert attempts >= 2
    assert result.returncode != 0
    assert "proceso Python terminó" in result.stderr


def test_installer_rejects_an_invalid_health_timeout():
    result, attempts = _run_installer(succeed_after=1, timeout=0)
    assert result.returncode == 2
    assert attempts == 0
    assert "debe ser mayor que cero" in result.stderr


def test_installer_has_a_health_client_without_requiring_curl():
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "command -v curl" in installer
    assert "urllib.request" in installer
    assert "docker compose exec -T lucidfence" in installer


def test_python_health_fallback_works_when_curl_is_missing():
    result, attempts = _run_installer(
        succeed_after=2,
        curl_available=False,
    )
    assert result.returncode == 0, result.stderr
    assert attempts >= 2
    assert "Health confirmado" in result.stdout
