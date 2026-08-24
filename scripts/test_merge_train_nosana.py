import datetime
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("mt", "scripts/merge_train.py")
mt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mt)

now = mt.now()
def pr(num, idle_days, state, failed=False):
    updated = (now - datetime.timedelta(days=idle_days)).isoformat()
    checks = [{"conclusion": "FAILURE"}] if failed else []
    return {"number": num, "title": f"PR {num}", "createdAt": updated, "updatedAt": updated, "mergeStateStatus": state, "statusCheckRollup": checks, "isDraft": False}

PRs = [
    pr(1, 1, "BEHIND"),                 # green, behind main -> NOT nosana
    pr(2, 1, "CLEAN"),                  # ready -> NOT nosana
    pr(3, 1, "CLEAN", failed=True),     # RED -> nosana
    pr(4, 1, "DIRTY"),                  # CONFLICTING -> nosana
    pr(5, 10, "CLEAN"),                 # STALE >7d -> nosana
    pr(6, 2, "CLEAN"),                  # ready, fresh -> NOT nosana
]
q = mt.build_queue(PRs)
print("open_total:", q["open_total"])
print("nosana_total:", q["nosana_total"])
print("drain_mode:", q["drain_mode"])
body = mt.render(q)
print("---RENDER---")
print(body.splitlines()[0])
assert q["nosana_total"] == 3, q["nosana_total"]
assert q["drain_mode"] is True
assert "0 NO-SANAS" not in body.splitlines()[0]
print("PASS: drain_mode on with 1-5 open incl NO-SANA")

q2 = mt.build_queue([pr(1,1,"BEHIND"), pr(2,1,"CLEAN"), pr(6,2,"CLEAN")])
print("nosana_total healthy:", q2["nosana_total"], "drain:", q2["drain_mode"])
assert q2["drain_mode"] is False
print("PASS: no NO-SANA -> not drain")
print("ALL TESTS PASSED")
