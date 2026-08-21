"""Test honesto: geofence breach + CVE critico -> SOAR dispara acciones.
Valida el patron de LakshmanRekha (geofence breach -> alerta en tiempo real)
aplicado en LucidFence. No mockea: usa DEFAULT_PLAYBOOKS reales del repo.
Ejecutar: python3 tests/run_tests.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.soar import evaluate_soar, DEFAULT_PLAYBOOKS


def _device(outside: bool, cve_critical: bool, compliant: bool = True) -> dict:
    apps = []
    if cve_critical:
        apps.append({"name": "vuln-app", "max_cve_severity": "critical"})
    return {
        "id": "dev-1",
        "name": "iPad kiosco",
        "fence_state": "outside" if outside else "inside",
        "compliant": compliant,
        "risk_level": "critical" if (outside and not compliant) or cve_critical else "low",
        "apps": apps,
    }


def test_breach_no_conforme_dispara_soar():
    """Dispositivo fuera de geovalla y no conforme -> playbook de geovalla."""
    dev = _device(outside=True, cve_critical=False, compliant=False)
    res = evaluate_soar(dev, DEFAULT_PLAYBOOKS, ctx={})
    assert res, "breach de geovalla + no conforme debe disparar SOAR"
    assert any("perimetro" in p["name"].lower() or "geovalla" in p["name"].lower()
               for p in res), f"esperado playbook de geovalla, got {res}"


def test_cve_fuera_dispara_lock():
    """App CVE critico + fuera de geovalla -> lockea y notifica (LakshmanRekha: breach->alerta)."""
    dev = _device(outside=True, cve_critical=True)
    res = evaluate_soar(dev, DEFAULT_PLAYBOOKS, ctx={})
    assert res, "CVE critico + fuera debe disparar SOAR"
    actions = {a["action"] for p in res for a in p["actions"]}
    assert "lock" in actions and "locate" in actions, f"esperado lock+locate, got {actions}"


def test_cve_critico_solo_dispara_soar():
    """App con CVE critico (dentro) -> playbook de CVE se activa."""
    dev = _device(outside=False, cve_critical=True)
    res = evaluate_soar(dev, DEFAULT_PLAYBOOKS, ctx={})
    assert res, "CVE critico debe disparar SOAR"
    assert any("cve" in p["name"].lower() for p in res), f"esperado playbook CVE, got {res}"


def test_dentro_conforme_no_dispara():
    """Dentro de geovalla y conforme -> sin acciones (falso positivo evitado)."""
    dev = _device(outside=False, cve_critical=False, compliant=True)
    res = evaluate_soar(dev, DEFAULT_PLAYBOOKS, ctx={})
    assert not res, f"falso positivo dentro/conforme: {res}"


if __name__ == "__main__":
    test_breach_no_conforme_dispara_soar()
    test_cve_fuera_dispara_lock()
    test_cve_critico_solo_dispara_soar()
    test_dentro_conforme_no_dispara()
    print("OK: soar geofence breach test paso")
