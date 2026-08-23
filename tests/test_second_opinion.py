"""Segunda opinión: el UEM corrige su propio examen; esto lo verifica.

Lo que se prueba, por orden de importancia:

  1. La REGLA DE HONESTIDAD: un lado desconocido nunca produce hallazgo. Es la
     propiedad que hace creíble al informe; si desconocido pudiera "delatar",
     el panel se llenaría de ruido y el admin dejaría de mirarlo.
  2. Que la discrepancia de cifrado es DETECTABLE, que es justo lo que antes
     era imposible: la postura observada sobrescribía la afirmación del UEM y
     borraba la contradicción.
  3. Que cada hallazgo lleva evidencia de los dos lados con su antigüedad.

Ejecuta: python3 tests/run_tests.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lucidfence.core.second_opinion import second_opinion_report  # noqa: E402
from lucidfence.core.state_store import DeviceState  # noqa: E402

NOW = datetime(2026, 8, 23, 12, 0, 0, tzinfo=timezone.utc)


def _iso(delta_s: float) -> str:
    return (NOW - timedelta(seconds=delta_s)).isoformat()


def _dev(**over) -> dict:
    base = {
        "device_id": "d1", "name": "Portátil de Ana", "platform": "macos",
        "compliant": True, "last_checkin": _iso(600),
        "posture_source": "osquery", "posture_collected_at": _iso(300),
    }
    base.update(over)
    return base


def _controls(report) -> list:
    return [d["control"] for d in report["discrepancies"]]


# ---------------------------------------------------------------------------
# 1. La regla de honestidad
# ---------------------------------------------------------------------------
def test_unknown_side_never_produces_a_finding():
    """Ni el UEM callado ni la observación ausente delatan a nadie."""
    cases = [
        # El UEM no dijo nada del cifrado; osquery sí.
        _dev(uem_claimed_encryption=None, encryption_enabled=False),
        # El UEM afirmó cifrado; no hay observación independiente.
        _dev(uem_claimed_encryption=True, encryption_enabled=None),
        # Hay afirmación y observación, pero ningún canal independiente activo.
        _dev(uem_claimed_encryption=True, encryption_enabled=False,
             posture_source=None, posture_collected_at=None),
        # compliant desconocido: no hay veredicto que contrastar.
        _dev(compliant=None, hardware_health={"camera": "failed"}),
    ]
    for dev in cases:
        rep = second_opinion_report([dev], now=NOW)
        assert rep["discrepancies_total"] == 0, \
            f"un lado desconocido generó hallazgo: {rep['discrepancies']}"


def test_agreement_is_not_a_discrepancy():
    """Cuando ambos lados coinciden no hay nada que contar."""
    rep = second_opinion_report([
        _dev(uem_claimed_encryption=True, encryption_enabled=True),
        _dev(device_id="d2", uem_claimed_encryption=False, encryption_enabled=False),
    ], now=NOW)
    assert rep["discrepancies_total"] == 0


def test_zero_discrepancies_is_not_confused_with_zero_visibility():
    """`devices_verifiable` impide leer "0 discrepancias" como "todo bien":
    sin canal independiente no hay segunda opinión posible."""
    blind = {"device_id": "x", "name": "Sin señal", "compliant": True}
    rep = second_opinion_report([blind], now=NOW)
    assert rep["discrepancies_total"] == 0
    assert rep["devices_total"] == 1
    assert rep["devices_verifiable"] == 0, \
        "un dispositivo sin canal independiente no es verificable"


# ---------------------------------------------------------------------------
# 2. La discrepancia que antes era invisible
# ---------------------------------------------------------------------------
def test_uem_claims_encryption_but_endpoint_says_otherwise():
    rep = second_opinion_report([
        _dev(uem_claimed_encryption=True, encryption_enabled=False),
    ], now=NOW)
    assert _controls(rep) == ["encryption"]
    f = rep["discrepancies"][0]
    assert f["severity"] == "critical"
    # Las dos caras, cada una con procedencia y antigüedad: eso es la evidencia.
    assert f["claimed"]["value"] is True and f["claimed"]["source"] == "uem"
    assert f["observed"]["value"] is False and f["observed"]["source"] == "osquery"
    assert f["claimed"]["age_s"] == 600.0 and f["observed"]["age_s"] == 300.0


def test_uem_lagging_behind_reality_is_reported_but_mildly():
    """El endpoint cifrado y el UEM que no se ha enterado es un dato de
    inventario obsoleto, no un riesgo de seguridad: severidad baja."""
    rep = second_opinion_report([
        _dev(uem_claimed_encryption=False, encryption_enabled=True),
    ], now=NOW)
    assert _controls(rep) == ["encryption"]
    assert rep["discrepancies"][0]["severity"] == "low"


def test_the_uem_claim_survives_the_osquery_merge():
    """Guard del arreglo que habilita todo esto: DeviceState conserva la
    afirmación del UEM aparte de la postura observada. Si alguien vuelve a
    colapsar ambas en un campo, la discrepancia se vuelve indetectable."""
    assert "uem_claimed_encryption" in DeviceState.__dataclass_fields__
    state = DeviceState(device_id="d", name="n", platform="macos",
                        encryption_enabled=False, uem_claimed_encryption=True)
    d = state.to_dict()
    assert d["uem_claimed_encryption"] is True and d["encryption_enabled"] is False


# ---------------------------------------------------------------------------
# 3. El resto de controles
# ---------------------------------------------------------------------------
def test_compliant_against_degraded_hardware():
    rep = second_opinion_report([
        _dev(hardware_health={"camera": "failed", "nfc": True, "uwb": "ok"}),
    ], now=NOW)
    assert _controls(rep) == ["hardware_health"]
    assert rep["discrepancies"][0]["components"] == ["camera"]


def test_compliant_against_implausible_location():
    rep = second_opinion_report([
        _dev(location_integrity={"suspicious": True, "checks": ["velocidad imposible"]},
             last_seen=_iso(120)),
    ], now=NOW)
    assert _controls(rep) == ["location_integrity"]
    assert rep["discrepancies"][0]["checks"] == ["velocidad imposible"]


def test_compliant_against_vulnerable_apps():
    rep = second_opinion_report([
        _dev(apps=[{"name": "Google Chrome", "version": "120.0"}]),
    ], now=NOW)
    controls = _controls(rep)
    assert "vulnerable_apps" in controls, f"CVE no contrastadas: {controls}"
    f = next(d for d in rep["discrepancies"] if d["control"] == "vulnerable_apps")
    assert f["critical_cve_apps"] + f["high_cve_apps"] >= 1


def test_stale_uem_verdict_is_flagged_without_calling_it_a_contradiction():
    """El check-in del UEM es mucho más viejo que nuestra observación."""
    rep = second_opinion_report([
        _dev(last_checkin=_iso(3 * 86400), posture_collected_at=_iso(60)),
    ], now=NOW)
    assert "stale_claim" in _controls(rep)
    f = next(d for d in rep["discrepancies"] if d["control"] == "stale_claim")
    assert f["severity"] == "medium" and f["lag_s"] > 86400


def test_stale_threshold_is_honoured():
    dev = _dev(last_checkin=_iso(7200), posture_collected_at=_iso(60))
    assert "stale_claim" not in _controls(second_opinion_report([dev], now=NOW))
    relaxed = second_opinion_report([dev], now=NOW, stale_claim_after_s=3600)
    assert "stale_claim" in _controls(relaxed)


# ---------------------------------------------------------------------------
# 4. Robustez: entrada basura degrada, nunca revienta
# ---------------------------------------------------------------------------
def test_garbage_input_degrades_to_unknown_and_never_raises():
    rep = second_opinion_report([
        None, "no soy un dispositivo", 42,
        _dev(last_checkin="ayer por la tarde", posture_collected_at="???"),
        _dev(device_id="d3", hardware_health="no es un dict"),
        _dev(device_id="d4", location_integrity=["tampoco"]),
        _dev(device_id="d5", apps="ni esto"),
    ], now=NOW)
    assert isinstance(rep["discrepancies"], list)
    # Ningún timestamp ilegible se convierte en una antigüedad inventada.
    for f in rep["discrepancies"]:
        for side in ("claimed", "observed"):
            age = f[side]["age_s"]
            assert age is None or isinstance(age, float)


def test_findings_are_sorted_by_severity():
    rep = second_opinion_report([
        _dev(device_id="a", last_checkin=_iso(5 * 86400), posture_collected_at=_iso(60)),
        _dev(device_id="b", uem_claimed_encryption=True, encryption_enabled=False),
    ], now=NOW)
    assert rep["discrepancies"][0]["severity"] == "critical"
    assert rep["by_control"]["encryption"] == 1


def test_report_never_mutates_the_input():
    dev = _dev(uem_claimed_encryption=True, encryption_enabled=False,
               apps=[{"name": "Google Chrome"}])
    before = repr(dev)
    second_opinion_report([dev], now=NOW)
    assert repr(dev) == before, "el informe modificó el estado que solo debía leer"
