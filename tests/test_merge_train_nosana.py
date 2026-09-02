"""Gate de producción NO-SANA del merge train (PR #290, forward-port).

MODO DRENAJE se activa por PRs NO-SANAS = ANY(STALE >7d, CONFLICTING, RED),
no por el recuento de PRs abiertas: una PR verde pero `behind` main la drena
el raíl de auto-merge y no cuenta.
"""
import datetime
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("mt", os.path.join(ROOT, "scripts", "merge_train.py"))
mt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mt)


def _pr(num, idle_days, state, failed=False):
    updated = (mt.now() - datetime.timedelta(days=idle_days)).isoformat()
    checks = [{"conclusion": "FAILURE"}] if failed else []
    return {"number": num, "title": f"PR {num}", "createdAt": updated, "updatedAt": updated,
            "mergeStateStatus": state, "statusCheckRollup": checks, "isDraft": False,
            "author": {"login": "bot"}, "labels": []}


def test_nosana_cuenta_solo_stale_conflicting_o_red():
    prs = [
        _pr(1, 1, "BEHIND"),              # verde, detrás de main -> NO nosana
        _pr(2, 1, "CLEAN"),               # lista -> NO nosana
        _pr(3, 1, "CLEAN", failed=True),  # RED -> nosana
        _pr(4, 1, "DIRTY"),               # CONFLICTING -> nosana
        _pr(5, 10, "CLEAN"),              # STALE > 7 días -> nosana
        _pr(6, 2, "CLEAN"),               # lista y fresca -> NO nosana
    ]
    q = mt.build_queue(prs)
    assert q["nosana_total"] == 3, q["nosana_total"]
    assert q["drain_mode"] is True
    primera = mt.render(q).splitlines()[0]
    assert "DRENAJE" in primera and "0 NO-SANAS" not in primera, primera


def test_sin_nosana_no_hay_drenaje_aunque_haya_muchas_abiertas():
    prs = [_pr(i, 1, "CLEAN") for i in range(1, 10)]  # 9 abiertas, todas sanas
    q = mt.build_queue(prs)
    assert q["over_limit"] is True      # informativo
    assert q["nosana_total"] == 0
    assert q["drain_mode"] is False
    assert "DRENAJE" not in mt.render(q).splitlines()[0]
