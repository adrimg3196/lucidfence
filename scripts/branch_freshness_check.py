#!/usr/bin/env python3
"""branch_freshness_check.py — pre-flight branch-freshness check anti-falsos-positivos.

Self-contained, stdlib-only copy vendored into the LucidFence repo (t_13ea01ab).
It deliberately does NOT import kanban_done_audit / kanban_done_gate: those live
only in the Hermes-global scripts dir (~/.hermes/scripts/), so any repo-side copy
that imported them could never run from the repo tree — which is precisely why the
script was missing from origin/main and the PM's staleness pre-flight was unusable
(t_c5eb69ad "Gate-0 scripts missing from main"). The DB/repo resolvers are inlined
from scripts/kanban_done_gate.py so this file stands alone.

MOTIVATING INCIDENT (t_656ccdad / t_925438a3, 2026-08-23):
  Un flag de integridad CTO->CEO (#89 "engine no enruta declarativamente") resulto
  ser FALSO POSITIVO por staleness de rama. El bot evaluo `engine.py` en la rama
  `marketing-outbox-2026-08-20`, que estaba 74 commits DETRAS de origin/main, donde
  #89 YA estaba mergeado (21 refs declarative en main vs 0 en la rama). Costo un
  ciclo de coordinacion entero (hold de marketing + 3 tareas) diagnosticar que NO era
  trabajo pendiente sino arbol obsoleto.

THE RULE THIS TOOL ENFORCES (proposal to CEO, see t_656ccdad, ratificado t_00880970):
  Cualquier bot que emita un flag de "gap / ausencia / no hace X" DEBE correr este
  check en el repo afectado y embeber `commits_behind` + `merge_base` en el cuerpo
  del flag. Si la rama esta >N commits detras de origin/main, el flag se marca
  "POSIBLE STALENESS" y NO debe disparar holds de marketing/launch hasta confirmar
  contra main.

UMBRAL (N): default --threshold=10. Banda suave: 1..threshold => ADVISORY (embebe el
numero, el bot procede pero lo nota). >threshold => STALE (POSIBLE STALENESS, bloquea
escalacion). 0 => FRESH. Ajustable por el CEO en un solo lugar.

MODO EXTRA `--grep-origin <pat> [--path <f>]`: compara el conteo de <pat> en la rama
actual vs en origin/main. Es la verificacion directa contra el falso positivo #89 — si
la rama esta detras y el patron SI aparece en origin/main, el "gap" es staleness, no
brecha. Imprime ambos lados para que el bot lo pegue en el flag.

MODO `--flag-template`: emite un bloque BRANCH_FRESHNESS: listo para pegar en el
cuerpo del flag, para que el numero nunca falte.

Exit codes:
  0  OK      FRESH (0 behind) o ADVISORY (1..N behind) — procede, embebe numeros.
  2  STALE   >N commits detras — POSIBLE STALENESS, NO disparar holds/launch sin
             confirmar contra origin/main.
  1  ERROR   fallo de tool/git — no emitir flag ciego; investigar.

Uso:
  python3 scripts/branch_freshness_check.py --repo /Users/adri/lucidfence [--threshold 10]
                                           [--json] [--flag-template] [--strict]
  python3 scripts/branch_freshness_check.py --repo <repo> --grep-origin "declarative_route"
                                           [--path engine.py] [--json]
  python3 scripts/branch_freshness_check.py --task-id t_xxx [--board lucidfence]   # resuelve repo
  python3 scripts/branch_freshness_check.py --selftest
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

DEFAULT_BOARD = "lucidfence"
DEFAULT_REPO = "/Users/adri/lucidfence"
DEFAULT_THRESHOLD = 10  # N: >N commits behind => STALE / POSIBLE STALENESS

# --- inlined resolvers (mirror scripts/kanban_done_gate.py, stdlib-only) --------


def resolve_db_path(board, db_arg):
    if db_arg:
        return db_arg
    env_db = os.environ.get("HERMES_KANBAN_DB")
    if env_db:
        return env_db
    env_board = os.environ.get("HERMES_KANBAN_BOARD")
    b = board or env_board or DEFAULT_BOARD
    cand = os.path.expanduser(f"~/.hermes/kanban/boards/{b}/kanban.db")
    if os.path.exists(cand):
        return cand
    raise RuntimeError(
        f"No se encontro la base del kanban para el board '{b}' ({cand})")


def resolve_repo(repo_arg, task):
    candidates = []
    if repo_arg:
        candidates.append(repo_arg)
    wp = task.get("workspace_path") if task else None
    if wp:
        candidates.append(wp)
    candidates.append(DEFAULT_REPO)
    for cand in candidates:
        if not cand or not os.path.isdir(cand):
            continue
        rc, top = _git(cand, "rev-parse", "--show-toplevel")
        if rc != 0:
            continue
        top = top.strip()
        rc2, _ = _git(top, "rev-parse", "--verify", "origin/main")
        if rc2 == 0:
            return top
    return repo_arg or DEFAULT_REPO


# --- git / subprocess helpers --------------------------------------------------


def _run(cmd, cwd=None, timeout=600):
    try:
        p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True,
                           timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"timeout (> {timeout}s) ejecutando: {' '.join(cmd)}"
    except FileNotFoundError as e:
        return 127, f"comando no encontrado: {e}"


def _git(repo, *args, timeout=90):
    return _run(["git", "-C", repo, *args], timeout=timeout)


def dump_json(obj):
    """json.dumps that always succeeds: prefer readable UTF-8, fall back to ASCII."""
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except TypeError:
        return json.dumps(obj, indent=2)


def repo_top(repo_arg):
    """Resolve a git worktree top-level from a path/repo arg."""
    rc, top = _git(repo_arg, "rev-parse", "--show-toplevel")
    if rc != 0:
        return None
    return top.strip()  # strip trailing newline so downstream `git -C <top>` works


def _sum_grep(out):
    """Sum trailing per-file counts from `git grep -c` (one `file:N` line each)."""
    n = 0
    for ln in out.splitlines():
        m = re.search(r":(\d+)\s*$", ln)
        if m:
            n += int(m.group(1))
    return n


# --- core checks ---------------------------------------------------------------


def freshness(repo, threshold=DEFAULT_THRESHOLD, fetch=True):
    """Return dict with branch, behind, ahead, merge_base, status, detail."""
    top = repo_top(repo)
    if not top:
        return {"status": "ERROR", "detail": f"no es un repo git: {repo}",
                "branch": None, "behind": None, "ahead": None,
                "merge_base": None}
    if fetch:
        # best-effort: refresh origin/main so the verdict reflects the latest push
        _git(top, "fetch", "origin", "main", timeout=120)

    rc_b, branch = _git(top, "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch.strip() if rc_b == 0 else "(unknown)"

    rc_m, _ = _git(top, "rev-parse", "--verify", "origin/main")
    if rc_m != 0:
        return {"status": "ERROR",
                "detail": "origin/main no existe/sin fetch — no se puede medir staleness",
                "branch": branch, "behind": None, "ahead": None,
                "merge_base": None}

    rc1, behind_s = _git(top, "rev-list", "--count", "HEAD..origin/main")
    rc2, ahead_s = _git(top, "rev-list", "--count", "origin/main..HEAD")
    rc3, mb = _git(top, "merge-base", "HEAD", "origin/main")
    behind = int(behind_s.strip()) if rc1 == 0 and behind_s.strip().isdigit() else None
    ahead = int(ahead_s.strip()) if rc2 == 0 and ahead_s.strip().isdigit() else None
    merge_base = mb.strip() if rc3 == 0 else None

    if behind is None:
        status, detail = ("ERROR", "no se pudo contar commits behind")
    elif behind == 0:
        status, detail = ("FRESH", "rama al dia con origin/main (0 behind)")
    elif behind <= threshold:
        status, detail = ("ADVISORY",
                          f"rama {behind} commit(s) detras de origin/main "
                          f"(<={threshold}) — embebe el numero; confirma contra main "
                          f"si afirmas una AUSENCIA")
    else:
        status, detail = ("STALE",
                          f"rama {behind} commits DETRAS de origin/main (> {threshold}) "
                          f"— POSIBLE STALENESS: NO disparar holds/launch sin confirmar "
                          f"contra origin/main")

    return {"status": status, "detail": detail, "branch": branch,
            "behind": behind, "ahead": ahead, "merge_base": merge_base,
            "repo": top}


def grep_origin(repo, pattern, path=None, fetch=True):
    """Count `pattern` in current branch vs origin/main (the #89-class guard)."""
    top = repo_top(repo)
    if not top:
        return {"error": f"no es repo git: {repo}"}
    if fetch:
        _git(top, "fetch", "origin", "main", timeout=120)
    # local count (case-insensitive, sum per-file match counts)
    rc_l, local = _git(top, "grep", "-ci", pattern, "--", path or ".")
    # origin/main count
    rc_o, remote = _git(top, "grep", "-ci", pattern, "origin/main", "--", path or ".")
    local_n = _sum_grep(local) if rc_l == 0 else 0
    remote_n = 0
    if rc_o == 0:
        remote_n = _sum_grep(remote)
    elif rc_o == 1:  # grep exit 1 == no match
        remote_n = 0
    fr = freshness(repo, fetch=False)
    behind = fr.get("behind")
    staleness_explains = (behind and behind > 0 and remote_n > local_n)
    return {
        "pattern": pattern,
        "path": path,
        "local_count": local_n,
        "origin_main_count": remote_n,
        "branch": fr.get("branch"),
        "behind": behind,
        "staleness_explains_gap": staleness_explains,
        "verdict": (
            "GAP_IS_STALENESS" if staleness_explains else
            "GAP_CONFIRMED_ON_MAIN" if remote_n == 0 and local_n == 0 else
            "INCONCLUSIVE"),
    }


def flag_template(fr, g=None):
    lines = [
        "BRANCH_FRESHNESS:",
        f"  repo: {fr.get('repo')}",
        f"  branch: {fr.get('branch')}",
        f"  commits_behind_main: {fr.get('behind')}",
        f"  commits_ahead_main: {fr.get('ahead')}",
        f"  merge_base: {fr.get('merge_base')}",
        f"  status: {fr.get('status')}",
    ]
    if g:
        lines += [
            f"  grep[{g['pattern']}] local={g['local_count']} "
            f"origin_main={g['origin_main_count']} -> {g['verdict']}",
        ]
    return "\n".join(lines)


# --- CLI -----------------------------------------------------------------------


def main(argv):
    ap = argparse.ArgumentParser(
        description="Pre-flight branch-freshness check anti-falsos-positivos (t_13ea01ab)")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--task-id", default=None, help="resuelve repo desde workspace_path")
    ap.add_argument("--board", default=DEFAULT_BOARD)
    ap.add_argument("--db", default=None)
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    ap.add_argument("--no-fetch", action="store_true",
                    help="no correr git fetch origin main (usa refs locales)")
    ap.add_argument("--grep-origin", default=None,
                    help="patron a comparar rama actual vs origin/main (anti-#89)")
    ap.add_argument("--path", default=None,
                    help="archivo para --grep-origin")
    ap.add_argument("--flag-template", action="store_true",
                    help="emitir bloque BRANCH_FRESHNESS: para pegar en el flag")
    ap.add_argument("--strict", action="store_true",
                    help="ADVISORY tambien sale 2 (bloquea) en vez de 0")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    # resolve repo
    repo = args.repo
    if not repo and args.task_id:
        try:
            db_path = resolve_db_path(args.board, args.db)
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT workspace_path, branch_name FROM tasks WHERE id=?",
                          (args.task_id,)).fetchone()
        con.close()
        if not row:
            print(f"ERROR: task {args.task_id} no encontrado", file=sys.stderr)
            return 1
        repo = resolve_repo(None, dict(row))
    if not repo:
        repo = DEFAULT_REPO
    if not repo_top(repo):
        print(f"ERROR: --repo no es git: {repo}", file=sys.stderr)
        return 1

    fetch = not args.no_fetch
    if args.grep_origin:
        g = grep_origin(repo, args.grep_origin, args.path, fetch=fetch)
        if "error" in g:
            print(f"ERROR: {g['error']}", file=sys.stderr)
            return 1
        fr = freshness(repo, threshold=args.threshold, fetch=False)
        out = {"grep": g, "freshness": fr}
        if args.flag_template:
            print(flag_template(fr, g))
        elif args.json:
            print(dump_json(out))
        else:
            print(f"[{g['verdict']}] {args.grep_origin} "
                  f"(local={g['local_count']} origin_main={g['origin_main_count']}, "
                  f"behind={g['behind']})")
        # exit semantics: if staleness explains the gap, treat as STALE (2)
        return 2 if g["staleness_explains_gap"] else 0

    fr = freshness(repo, threshold=args.threshold, fetch=fetch)
    if args.flag_template:
        print(flag_template(fr))
    elif args.json:
        print(dump_json(fr))
    else:
        print(f"[{fr['status']}] branch={fr.get('branch')} "
              f"behind={fr.get('behind')} ahead={fr.get('ahead')} "
              f"merge_base={fr.get('merge_base')}")
        print(f"         {fr['detail']}")

    if fr["status"] == "ERROR":
        return 1
    if fr["status"] == "STALE":
        return 2
    if fr["status"] == "ADVISORY" and args.strict:
        return 2
    return 0


# --- self-test -----------------------------------------------------------------


def _selftest():
    tmp = tempfile.mkdtemp(prefix="lf-fresh-test-")
    origin = os.path.join(tmp, "origin.git")
    repo = os.path.join(tmp, "repo")
    try:
        _run(["git", "init", "--bare", "-q", origin])
        os.makedirs(repo)
        _run(["git", "init", "-q", repo])
        _run(["git", "-C", repo, "config", "user.email", "t@t"])
        _run(["git", "-C", repo, "config", "user.name", "t"])
        _run(["git", "-C", repo, "remote", "add", "origin", origin])
        # main with the "feature" already present
        with open(os.path.join(repo, "engine.py"), "w") as f:
            f.write("def _declarative_route(): pass\n")
        _run(["git", "-C", repo, "add", "engine.py"])
        _run(["git", "-C", repo, "commit", "-qm", "main has declarative"])
        _run(["git", "-C", repo, "branch", "-M", "main"])
        _run(["git", "-C", repo, "push", "-q", "origin", "main"])

        # STALE branch: branch off an OLD main point, then main advances 12 commits
        _run(["git", "-C", repo, "checkout", "-qb", "stale-branch", "HEAD~0"])
        with open(os.path.join(repo, "engine.py"), "w") as f:
            f.write("# no declarative here\n")
        _run(["git", "-C", repo, "add", "engine.py"])
        _run(["git", "-C", repo, "commit", "-qm", "stale removes declarative"])
        _run(["git", "-C", repo, "checkout", "-q", "main"])
        for i in range(12):
            with open(os.path.join(repo, f"f{i}.txt"), "w") as f:
                f.write(str(i))
            _run(["git", "-C", repo, "add", f"f{i}.txt"])
            _run(["git", "-C", repo, "commit", "-qm", f"main advance {i}"])
        _run(["git", "-C", repo, "push", "-q", "origin", "main"])
        _run(["git", "-C", repo, "checkout", "-q", "stale-branch"])

        # FRESH branch: off current main, 0 behind
        _run(["git", "-C", repo, "checkout", "-qb", "fresh-branch", "main"])
        with open(os.path.join(repo, "x.txt"), "w") as f:
            f.write("x")
        _run(["git", "-C", repo, "add", "x.txt"])
        _run(["git", "-C", repo, "commit", "-qm", "fresh add"])

        failures = []

        # 1) STALE branch -> exit 2 and grep-origin shows GAP_IS_STALENESS.
        _run(["git", "-C", repo, "checkout", "-q", "stale-branch"])
        code = main(["--repo", repo, "--no-fetch", "--threshold", "10"])
        ok = code == 2
        print(f"[{'PASS' if ok else 'FAIL'}] stale-branch exit={code} want=2 (STALE)")
        if not ok:
            failures.append("stale-exit")

        gcode = main(["--repo", repo, "--no-fetch", "--grep-origin",
                      "_declarative_route", "--path", "engine.py"])
        ok = gcode == 2
        print(f"[{'PASS' if ok else 'FAIL'}] stale grep-origin exit={gcode} "
              f"want=2 (GAP_IS_STALENESS)")
        if not ok:
            failures.append("stale-grep")

        # 2) FRESH branch -> exit 0
        _run(["git", "-C", repo, "checkout", "-q", "fresh-branch"])
        code = main(["--repo", repo, "--no-fetch", "--threshold", "10"])
        ok = code == 0
        print(f"[{'PASS' if ok else 'FAIL'}] fresh-branch exit={code} want=0 (FRESH)")
        if not ok:
            failures.append("fresh-exit")

        # 3) flag-template emits the BRANCH_FRESHNESS block
        _run(["git", "-C", repo, "checkout", "-q", "stale-branch"])
        old = sys.stdout
        sys.stdout = __import__("io").StringIO()
        try:
            main(["--repo", repo, "--no-fetch", "--flag-template"])
        finally:
            captured = sys.stdout.getvalue()
            sys.stdout = old
        ok = captured.startswith("BRANCH_FRESHNESS:") and "commits_behind_main:" in captured
        print(f"[{'PASS' if ok else 'FAIL'}] flag-template produces embeddable block")
        if not ok:
            failures.append("flag-template")

        if failures:
            print(f"\nSELFTEST FAILED: {failures}")
            return 1
        print("\nSELFTEST OK: 4/4 (STALE-exit, STALE-grep, FRESH-exit, flag-template)")
        return 0
    finally:
        _run(["git", "-C", repo, "worktree", "prune"], timeout=30)
        for w in glob.glob(os.path.join(tempfile.gettempdir(), "lf-fresh-*")):
            shutil.rmtree(w, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
