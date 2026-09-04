"""Regression tests for the "no false green" invariant (issue #302 / t_0de7c223).

INVARIANTE: lo desconocido (risk_score=None / level='unknown') NUNCA se presenta
como señal buena (0 / 'low' / 'healthy'). Los consumidores deben propagar el
desconocido como desconocido, o ignorarlo en el ranking, pero jamás inflarlo a
verde.

Cada test inyecta un dispositivo con risk_score=None en un consumidor real y
asserta que no aparece como riesgo 0/low/healthy en el output agregado.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lucidfence.core import ai as ai_mod
from lucidfence.core import alerts as alerts_mod
from lucidfence.core import soar as soar_mod
from lucidfence.core.risk_levels import (
    is_unknown_risk,
    sortable_risk,
    count_high_risk,
    UNKNOWN_RISK_SORT,
)
from saas_server import _summary as saas_summary  # noqa: E402


def _device(risk_score, **over):
    d = {"device_id": "dev-x", "name": "Test", "fence_state": "inside",
         "compliant": True, "risk_score": risk_score}
    d.update(over)
    return d


def test_is_unknown_risk():
    assert is_unknown_risk(None) is True
    assert is_unknown_risk(None, "unknown") is True
    assert is_unknown_risk(0.0) is False
    assert is_unknown_risk(50.0, "medium") is False
    assert is_unknown_risk(0.0, "low") is False  # 0 real es señal válida, no desconocido


def test_sortable_risk_none_falls_to_bottom():
    assert sortable_risk(None) == UNKNOWN_RISK_SORT
    # centinela es peor que cualquier riesgo real 0-100
    assert sortable_risk(None) < sortable_risk(0.0)
    assert sortable_risk(42.0) == 42.0


def test_count_high_risk_ignores_unknown():
    devs = [
        _device(None),            # desconocido -> NO cuenta
        _device(0.0),             # 0 real -> NO es alto
        _device(85.0),            # alto -> cuenta
    ]
    assert count_high_risk(devs, 70) == 1
    # y el desconocido NO se cuenta como "bajo/verde" tampoco:
    # (no hay assert positivo necesario, el conteo de alto ya lo demuestra)


def test_ai_digest_summary_unknown_not_high():
    saved = ai_mod.available
    ai_mod.available = lambda: False  # force plain branch
    try:
        devs = [_device(None)] + [_device(10.0 + i) for i in range(5)]
        out = ai_mod.digest_summary({}, devs, dry=True)
        # "Riesgo alto" debe ser 0: el None no se infla a >=70 (anti falso-verde)
        assert "0 en riesgo alto" in out
        # el None jamas se presenta como riesgo 0 verde en el texto plano
        assert "riesgo 0, inside" not in out
    finally:
        ai_mod.available = saved


def test_ai_incident_narrative_unknown():
    saved = ai_mod.available
    ai_mod.available = lambda: False  # force plain branch
    try:
        dev = _device(None, fence_state="outside")
        out = ai_mod.incident_narrative(dev, dry=True)
        assert "desconocido" in out
        assert "riesgo 0/100" not in out  # NO se presenta como 0 (falso verde)
    finally:
        ai_mod.available = saved


def test_alerts_risk_above_does_not_fire_on_unknown():
    alert = alerts_mod.AlertEngine.__new__(alerts_mod.AlertEngine)
    alert._rules = {}
    alert._firings = []
    alert.lock = __import__("threading").RLock()
    # Regla risk_above con umbral 50 (sin scope = all)
    rule = alerts_mod.AlertRule(id="r1", type="risk_above", threshold=50.0)
    rule.scope = ""
    rule.scope_value = ""
    alert._rules = {"r1": rule}
    fired = alert.evaluate([_device(None)], now=1_000_000)
    # None no dispara risk_above (no se trata como 0 < 50, ni como >=50)
    assert fired == []


def test_soar_max_severity_unknown_not_low():
    # dispositivo sin apps y sin nivel -> 'unknown', jamás 'low'
    assert soar_mod._max_severity({"device_id": "x"}) == "unknown"
    # dispositivo con CVE critical y nivel desconocido -> critical manda
    dev = {"device_id": "y", "apps": [{"max_cve_severity": "critical"}],
           "risk_level": "unknown"}
    assert soar_mod._max_severity(dev) == "critical"
    # nivel 'unknown' explícito no vence a 'low' de CVE
    dev2 = {"device_id": "z", "apps": [{"max_cve_severity": "low"}],
            "risk_level": "unknown"}
    assert soar_mod._max_severity(dev2) == "low"


def test_engine_summary_unknown_counted_separately():
    devs = [_device(None)] + [_device(80.0) for _ in range(2)] + [_device(5.0) for _ in range(3)]
    out = saas_summary(devs)
    # high_risk = 2 (los 80), unknown_risk = 1 (el None), nunca 3 o 0 mal contado
    assert out["high_risk"] == 2
    assert out["unknown_risk"] == 1
    assert out["total"] == 6


def test_saas_summary_none_not_high():
    devs = [_device(None)] + [_device(0.0) for _ in range(4)]
    out = saas_summary(devs)
    assert out["high_risk"] == 0
    assert out["unknown_risk"] == 1
