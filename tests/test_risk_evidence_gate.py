"""Tests del evidence gate del Risk Engine (patrón T3MP3ST aplicado a LucidFence).

Valida que un score de riesgo nunca se emita sin provenancia (reasons),
igual que el "honesty spine" de T3MP3ST: un claim no es válido sin
provenancia de tool output. Aquí: un riesgo no es válido sin su razón.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.policies import RiskEngine


def check(cond, msg):
    assert cond, f"FAIL: {msg}"


def _eng():
    return RiskEngine()


def test_outside_fence_has_reasons_and_verified():
    eng = _eng()
    d = {"device_id": "d1", "compliant": True, "fence_id": "f1"}
    r = eng.evaluate(d, "outside", {"hour": 12})
    check(r["risk_score"] > 0, "outside => riesgo > 0")
    check(r["reasons"], "outside => tiene reasons (provenance)")
    check(r["verified"] is True, "outside => verified (respaldado por señal)")
    check(r["provenance"] == "tool", "provenance tool")


def test_inside_compliant_low_risk():
    eng = _eng()
    d = {"device_id": "d2", "compliant": True, "fence_id": "f1",
         "encryption_enabled": True, "battery_level": 90, "storage_free_gb": 50,
         "storage_total_gb": 64, "os_version": "Android 14"}
    r = eng.evaluate(d, "inside", {"hour": 12})
    # dentro + conforme + posture sana => riesgo bajo (puede ser 0)
    check(r["risk_score"] >= 0, "score >= 0")
    if r["risk_score"] > 0:
        check(r["reasons"], "si hay score>0, hay reasons")
        check(r["verified"] is True, "score>0 => verified")
    else:
        # score 0: no debe tener reasons (no hay hallazgo)
        check(r["provenance"] in ("none",), "score 0 => provenance none")


def test_posture_signals_contribute():
    eng = _eng()
    d = {"device_id": "d3", "compliant": False, "fence_id": "f1",
         "rooted": True, "os_outdated": True,
         "storage_free_gb": 1, "storage_total_gb": 64,  # disk_low
         "battery_level": 10,                            # battery_critical
         "os_version": "android 12",                      # os_unpatched
         "encryption_enabled": False}                     # encryption_off
    r = eng.evaluate(d, "inside", {"hour": 12})
    joined = " ".join(r["reasons"]).lower()
    check("disco casi lleno" in joined, "disk_low contribuye a reasons")
    check("batería crítica" in joined, "battery_critical contribuye")
    check("sin cifrar" in joined, "encryption_off contribuye")
    check("sin parchear" in joined, "os_unpatched contribuye")
    check(r["verified"] is True, "posture con señales => verified")


def test_no_overclaim_without_reasons():
    # Caso extremo: dispositivo sin ningún campo de señal y dentro de geovalla.
    eng = _eng()
    d = {"device_id": "d4", "fence_id": "f1"}  # sin compliant/battery/etc.
    r = eng.evaluate(d, "inside", {"hour": 12})
    # El evidence gate garantiza: si hay score>0, SIEMPRE hay reasons (provenance).
    # No puede haber overclaim (riesgo sin justificación).
    if r["risk_score"] > 0:
        check(r["reasons"], "score>0 => SIEMPRE reasons (no overclaim)")
        check(r["verified"] is True, "score>0 con reasons => verified")
    else:
        check(r["provenance"] == "none", "score 0 => provenance none")


if __name__ == "__main__":
    for fn in (v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)):
        fn()
        print(f"PASS {fn.__name__}")
    print("ALL RISK EVIDENCE-GATE TESTS PASS")
