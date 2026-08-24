"""`lucidfence quickstart`: guía autoverificada del install a ver la flota.

Reduce el time-to-first-value del admin IT. Tests sin arrancar el server real
(doctor y health mockeados). Captura stdout con redirect_stdout para funcionar
tanto bajo pytest como bajo el runner honesto (sin fixtures).
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout
import unittest.mock as mock

from lucidfence import cli


def _run_quickstart():
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.cmd_quickstart(
            cli.SimpleNamespace(host=None, port=None, open_browser=False))
    return rc, buf.getvalue()


def test_quickstart_subcommand_registered():
    parser = cli.build_parser()
    args = parser.parse_args(["quickstart"])
    assert args.func is cli.cmd_quickstart
    assert args.open_browser is False


def test_quickstart_stops_when_environment_fails():
    bad = {"ok": False, "errors": 1, "warnings": 0,
           "checks": [{"name": "python", "ok": False, "severity": "error",
                       "detail": "Python 3.11+ requerido"}]}
    with mock.patch("lucidfence.core.doctor.run_doctor", return_value=bad), \
         mock.patch("shutil.which", return_value=None), \
         mock.patch("lucidfence.cli.cmd_start") as start:
        rc, out = _run_quickstart()
    assert rc == 1
    start.assert_not_called()  # no arranca la app si el entorno falla
    assert "FAIL" in out and "python" in out
    assert "`python3 -m lucidfence.cli quickstart`" in out
    assert "`lucidfence quickstart`" not in out


def test_quickstart_happy_path_when_app_already_up():
    good = {"ok": True, "errors": 0, "warnings": 0, "checks": []}
    with mock.patch("lucidfence.core.doctor.run_doctor", return_value=good), \
         mock.patch("shutil.which", return_value=None), \
         mock.patch("lucidfence.cli._healthy", return_value=True), \
         mock.patch("lucidfence.cli.Path.is_file", return_value=False), \
         mock.patch("lucidfence.cli.cmd_start") as start:
        rc, out = _run_quickstart()
    assert rc == 0
    start.assert_not_called()  # ya activa → no re-arranca
    assert "[1/4] OK" in out and "[2/4] OK" in out
    assert "Abre tu flota" in out
    assert "`python3 -m lucidfence.cli validate-config`" in out
    assert "`lucidfence validate-config`" not in out


def test_quickstart_starts_app_when_down():
    good = {"ok": True, "errors": 0, "warnings": 0, "checks": []}
    # primera comprobación: caída; tras arrancar: sana
    healthy = iter([False, True])
    with mock.patch("lucidfence.core.doctor.run_doctor", return_value=good), \
         mock.patch("lucidfence.cli._healthy", side_effect=lambda *a, **k: next(healthy)), \
         mock.patch("lucidfence.cli.cmd_start", return_value=0) as start:
        rc, out = _run_quickstart()
    assert rc == 0
    start.assert_called_once()


def test_quickstart_module_mode_reports_a_runnable_status_command():
    good = {"ok": True, "errors": 0, "warnings": 0, "checks": []}
    with mock.patch("lucidfence.core.doctor.run_doctor", return_value=good), \
         mock.patch("shutil.which", return_value=None), \
         mock.patch("lucidfence.cli._healthy", return_value=False), \
         mock.patch("lucidfence.cli.cmd_start", return_value=1):
        rc, out = _run_quickstart()
    assert rc == 1
    assert "`python3 -m lucidfence.cli status`" in out
    assert "`lucidfence status`" not in out


def test_quickstart_keeps_global_commands_when_cli_is_installed():
    good = {"ok": True, "errors": 0, "warnings": 0, "checks": []}
    with mock.patch("lucidfence.core.doctor.run_doctor", return_value=good), \
         mock.patch("shutil.which", return_value="/opt/homebrew/bin/lucidfence"), \
         mock.patch("lucidfence.cli._healthy", return_value=True), \
         mock.patch("lucidfence.cli.Path.is_file", return_value=False):
        rc, out = _run_quickstart()
    assert rc == 0
    assert "`lucidfence validate-config`" in out
    assert "`python3 -m lucidfence.cli validate-config`" not in out
