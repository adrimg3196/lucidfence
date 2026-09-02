"""El panel del SOC no puede mostrar un "MTTR 0s" que no midió nada.

Los incidentes derivados nacen en ``merge()`` con timeline vacío; antes, el
MTTR solo se calculaba desde una entrada ``to == "open"`` que nunca existía
salvo tras una reapertura, así que la métrica salía 0 (falso verde: parece
resolución instantánea). Ahora la apertura cae a ``first_seen`` y, sin datos,
la respuesta es None (el front ya pinta "–" con null).
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

T0 = "2026-07-10T10:00:00+00:00"
T0_EPOCH = 1783677600.0  # datetime(2026, 7, 10, 10, tzinfo=utc).timestamp()


def _store():
    from lucidfence.core.incidents import IncidentStore
    return IncidentStore(Path(tempfile.mkdtemp()))


def test_without_incidents_metrics_are_none_not_zero():
    stats = _store().analytics(now=lambda: T0_EPOCH)
    assert stats["mttr_seconds"] is None, stats
    assert stats["mttr_median_seconds"] is None, stats
    assert stats["oldest_open_seconds"] is None, stats
    assert stats["open"] == 0 and stats["resolved"] == 0


def test_mttr_falls_back_to_first_seen_when_timeline_has_no_open_entry():
    store = _store()
    store.merge([{"id": "inc-1", "status": "open", "title": "Fuera",
                  "severity": "high", "first_seen": T0}])
    store.transition("inc-1", "resolved", actor="soc")
    row = store.get("inc-1")
    assert all(ev.get("to") != "open" for ev in row["timeline"]), row["timeline"]
    stats = store.analytics(now=lambda: T0_EPOCH + 3600)
    # resolved "ahora" (reloj real) frente a first_seen en 2026-07-10: > 0 seguro
    assert stats["mttr_seconds"] is not None and stats["mttr_seconds"] > 0, stats
    assert stats["mttr_median_seconds"] == stats["mttr_seconds"], stats


def test_reopen_entry_wins_over_first_seen():
    from lucidfence.core import incidents as mod
    store = _store()
    store.merge([{"id": "inc-1", "status": "open", "title": "x", "first_seen": T0}])
    store.transition("inc-1", "resolved", actor="soc")
    row = store.get("inc-1")
    # reapertura registrada en la timeline (más tarde que first_seen)
    row["timeline"].append({"ts": "2026-07-10T12:00:00+00:00", "from": "resolved",
                            "to": "open", "actor": "soc"})
    assert mod._opened_ts(row) == T0_EPOCH + 7200
    assert mod._opened_ts({"first_seen": T0}) == T0_EPOCH
    assert mod._opened_ts({"timeline": [], "first_seen": None}) is None
    assert mod._opened_ts({}) is None


def test_oldest_open_uses_first_seen_and_stays_none_when_unknown():
    store = _store()
    store.merge([{"id": "known", "status": "open", "title": "a", "first_seen": T0},
                 {"id": "unknown", "status": "open", "title": "b"}])
    stats = store.analytics(now=lambda: T0_EPOCH + 120)
    assert stats["oldest_open_seconds"] == 120, stats
    only_unknown = _store()
    only_unknown.merge([{"id": "unknown", "status": "open", "title": "b"}])
    stats = only_unknown.analytics(now=lambda: T0_EPOCH)
    assert stats["open"] == 1 and stats["oldest_open_seconds"] is None, stats
