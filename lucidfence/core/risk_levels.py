"""Shared null-safe risk helpers — enforcing the repo's "no false green" invariant.

Issue #302 / t_0de7c223: a missing or crash-evaluated risk score (``None`` /
``level == 'unknown'``) MUST NOT be silently presented as ``0`` / ``low`` /
``healthy``. Every consumer of ``risk_score`` must go through these helpers
instead of the old ``x.get("risk_score") or 0`` idiom, which turned "unknown"
into a perfect-green zero.

Design:
  * ``is_unknown_risk(score, level)`` — True when there is genuinely no signal.
  * ``sortable_risk(score)`` — ordenable para ranking/agregación: ``None`` cae al
    fondo con centinela ``-1.0`` (nunca se infla a 0 ni compite con señal real).
  * ``count_high_risk(devices, threshold)`` — cuenta solo señal real >= umbral;
    los ``None`` NO se cuentan como riesgo alto ni como riesgo bajo.
"""
from __future__ import annotations

from typing import Any, Iterable

UNKNOWN_RISK = "unknown"
# Centinela ordenable: peor que cualquier riesgo real (0-100) para que
# "desconocido" caiga al final del ranking, nunca se infle ni se confunda
# con una señal buena. Refleja la convención ya usada en product.py/federated_fleet.
UNKNOWN_RISK_SORT = -1.0


def is_unknown_risk(score: Any, level: Any = None) -> bool:
    """True cuando no hay señal de riesgo utilizable (crash/desconocido)."""
    if score is None:
        return True
    if level is not None and str(level).strip().lower() == UNKNOWN_RISK:
        return True
    return False


def sortable_risk(score: Any) -> float:
    """Valor ordenable para ranking; None -> centinela, no 0."""
    if score is None:
        return UNKNOWN_RISK_SORT
    try:
        return float(score)
    except (TypeError, ValueError):
        return UNKNOWN_RISK_SORT


def count_high_risk(devices: Iterable[dict], threshold: float = 70.0) -> int:
    """Cuenta dispositivos con señal de riesgo real >= umbral.

    Los ``risk_score is None`` (desconocido) NO se cuentan: ni como alto ni
    como bajo. Es la anti-métrica del "falso verde".
    """
    n = 0
    for d in devices:
        s = d.get("risk_score") if isinstance(d, dict) else None
        if s is None:
            continue
        try:
            if float(s) >= threshold:
                n += 1
        except (TypeError, ValueError):
            continue
    return n
