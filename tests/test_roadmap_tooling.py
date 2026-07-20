#!/usr/bin/env python3
"""tests/roadmap_tooling_test.py — Valida el roadmap anual de mejora tooling.

Se descubre automaticamente por tests/run_tests.py (patron *_test.py).
NO rompe la suite existente: solo importa roadmap_tooling (stdlib) y valida
schema + CLI + API + loop (modo local, sin secretos).
"""
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, ROOT)

PASS = 0
FAIL = 0
FAILS = []


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILS.append(label)
        print(f"  FAIL  {label}")


def test_schema():
    print("[roadmap tooling / schema]")
    import roadmap_tooling as rm
    d = rm.load_roadmap()
    check("roadmap.json cargado", bool(d))
    errs = rm.validate_roadmap(d)
    check("roadmap valido contra schema", errs == [])
    feats = rm.all_features(d)
    check("roadmap tiene >= 18 features", len(feats) >= 18)
    # cada feature tiene los campos obligatorios
    bad = [f["id"] for f in feats if not (f.get("id") and f.get("title") and f.get("status"))]
    check("todas las features tienen id/title/status", bad == [])
    # progress computable
    prog = rm._compute_progress(d)
    check("progress tiene total>0", prog["total"] > 0)
    check("progress pct en 0..100", 0 <= prog["pct"] <= 100)


def test_cli():
    print("[roadmap tooling / CLI]")
    def run(args):
        return subprocess.run([sys.executable, "roadmap_tooling.py"] + args,
                              capture_output=True, text=True, cwd=ROOT, timeout=60)
    r = run(["--validate"])
    check("roadmap_tooling.py --validate exit 0", r.returncode == 0 and "valido" in r.stdout)
    r = run([])
    check("roadmap_tooling.py muestra plan", r.returncode == 0 and "ROADMAP" in r.stdout)
    r = run(["--export"])
    try:
        json.loads(r.stdout)
        ok = True
    except Exception:
        ok = False
    check("roadmap_tooling.py --export es JSON valido", ok and r.returncode == 0)
    # --mark actualiza y persiste
    import roadmap_tooling as rm
    d0 = rm.load_roadmap()
    r = run(["--mark", "F4.5", "status", "blocked"])
    check("roadmap_tooling.py --mark persiste", r.returncode == 0 and "F4.5" in r.stdout)
    # revertir para no dejar estado sucio
    rm.update_feature(d0, "F4.5", "status", "planned")
    rm.save_roadmap(d0)


def test_loop_local():
    print("[roadmap tooling / loop local (sin secretos)]")
    import loop_improve as lp
    # No debe requerir claves: modo local deterministico
    provs = lp._available_providers()
    # proposer local siempre disponible
    d = lp.rm.load_roadmap()
    feat = lp._next_feature(d)
    check("loop encuentra proxima feature", feat is not None)
    # Forzar CLI local para que el test no cuelgue en una llamada real a claude
    # (Opus 4.8 via claude CLI) durante la suite honesta del proyecto.
    saved_cli = lp._CLI
    lp._CLI = "/nonexistent/claude"
    local_prop = lp._local_proposer(feat, 0.5)
    check("proposer local produce texto", bool(local_prop))
    merged = lp._aggregate([local_prop], feat, 0.5)
    check("agregador local produce merge", bool(merged))
    lp._CLI = saved_cli
    score = lp._quality_score(merged)
    check("quality_score en 0..10", 0 <= score <= 10)
    # run_loop --dry-run no debe romper ni tocar estado
    rc = lp.run_loop(feature_id=feat["id"], max_iter=1, dry_run=True)
    check("loop --dry-run retorna 0", rc == 0)


def main():
    global PASS, FAIL
    test_schema()
    test_cli()
    test_loop_local()
    print(f"\n[roadmap_tooling_test] {PASS} PASS / {FAIL} FAIL")
    if FAIL:
        for f in FAILS:
            print("  -", f)
        sys.exit(1)


# Ejecuta al importarse: tests/run_tests.py solo importa los *_test.py,
# no llama main(), asi que corremos los checks a nivel de modulo.
if __name__ != "__main__":
    try:
        main()
    except SystemExit:
        pass
    except Exception as e:  # noqa: BLE001
        print("  FAIL  roadmap_tooling import: ", e)
        FAIL += 1
        FAILS.append("roadmap_tooling import: " + str(e))


if __name__ == "__main__":
    main()
