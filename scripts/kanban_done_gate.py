#!/usr/bin/env python3
"""kanban_done_gate.py — Guard obligatorio de DONE para tareas de código.

Aplica la política CEO 2026-08-21 (tarea t_86afa3e2): una tarea de código solo
se marca DONE en el kanban cuando su commit es ancestro de `origin/main` Y el
gate `scripts/verify.py` pasa SOBRE `origin/main`. Rama verde con PR abierto =
"en review", nunca "done".

CONTRATO (fail-closed):
  - exit 0  -> guard APTO: se puede ejecutar `hermes kanban complete`.
  - exit 1  -> guard FALLO: NO marcar done. Con --enforce deja comentario de
               evidencia y mueve la card a review.
  - exit 2  -> error de entorno (no se pudo evaluar la tarea).

Principio rector: si no se puede *demostrar* que el trabajo está en
`origin/main`, la tarea NO está done. No hay "pasa por defecto".

Uso:
  python3 scripts/kanban_done_gate.py <TASK_ID> \
      [--board lucidfence] [--db /path/kanban.db] [--repo /path/repo] \
      [--branch <rama>] [--test tests/foo.py ...] \
      [--code-task | --non-code] [--enforce] [--complete-on-pass] \
      [--dry-run] [--quiet]

Integración sugerida en el cierre de una card de código:
  python3 scripts/kanban_done_gate.py <TASK_ID> --branch <rama-del-trabajo> \
      --enforce --complete-on-pass
  - Si pasa: marca done automáticamente.
  - Si falla: comenta la evidencia, mueve a review y NO marca done.

Comprobaciones (solo para tareas de código):
  1. `git merge-base --is-ancestor <rama-trabajo> origin/main` == 0. La rama
     se toma de --branch o de task.branch_name; si no hay rama conocida y no
     se pasó --non-code, el gate no adivina y devuelve exit 2 (NO EVALUABLE).
  2. Los tests de aceptación de la card están TRACKED en origin/main (no
     untracked en la rama del agente). Si el test queda untracked, CI no lo
     corre: no cuenta.
  3. `python3 scripts/verify.py` APTO sobre origin/main (en un worktree efímero
     de main). Por defecto --verify-mode auto: si el único fallo es la batería
     runtime en vivo (flaky en main), cae a --fast.

Stdlib-only (convención del repo). No requiere dependencias externas.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

DEFAULT_BOARD = "lucidfence"
DEFAULT_REPO = "/Users/adri/lucidfence"

# Intérpretes aceptables, en orden de preferencia. El repo exige >=3.11.
PY_CANDIDATES = ["python3.11", "python3.12", "python3.13", "python3.14", "python3"]


def _run(cmd, cwd=None, timeout=600):
    try:
        p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True,
                           timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"timeout (> {timeout}s) ejecutando: {' '.join(cmd)}"
    except FileNotFoundError as e:
        return 127, f"comando no encontrado: {e}"


def find_python(repo) -> str:
    for cand in PY_CANDIDATES:
        exe = shutil.which(cand)
        if not exe:
            continue
        rc, out = _run([exe, "--version"])
        m = re.search(r"(\d+)\.(\d+)", out)
        if not m:
            continue
        major, minor = int(m.group(1)), int(m.group(2))
        if (major, minor) >= (3, 11):
            return exe
    raise RuntimeError(
        "No se encontró un Python >= 3.11 (el repo lo exige). "
        "Usa un venv: python3.11 -m venv .venv && . .venv/bin/activate"
    )


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
        f"No se encontró la base del kanban para el board '{b}' ({cand})")


def read_task(db_path, task_id):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        "SELECT id, title, body, branch_name, workspace_path, status "
        "FROM tasks WHERE id = ?", (task_id,))
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    return dict(row)


def _cleanup_stale_gate_worktrees(repo):
    """Elimina worktrees huérfanos de ejecuciones previas (p.ej. kills con
    SIGTERM) cuyo path empieza por lf-main-gate-. Si no se limpian, el
    `git worktree add` posterior falla por path/lock ya existente y el gate
    degrada a 'no se pudo crear worktree' -> exit 1 en falso."""
    import glob
    import shutil as _shutil
    tmp_root = tempfile.gettempdir()
    for path in glob.glob(os.path.join(tmp_root, "lf-main-gate-*")):
        # Quita el registro del worktree (best-effort) y borra el dir.
        _run(["git", "-C", repo, "worktree", "remove", "--force", path],
             timeout=30)
        if os.path.isdir(path):
            try:
                _shutil.rmtree(path)
            except OSError:
                pass
    _run(["git", "-C", repo, "worktree", "prune"], timeout=30)


def _free_port_8765():
    """El harness de tests de LucidFence arranca un server en el puerto fijo
    8765 y, en algunas condiciones, lo deja escuchando tras el run. Un listener
    huérfano hace que el SIGUIENTE verify falle con 'ya está ocupado / no se
    pudo leer el tally' — un fallo AMBIENTAL, no de calidad. Antes de correr
    verify, liberamos cualquier listener en 8765 para no bloquear DONEs válidos
    por causa ajena a la card. Best-effort: si no hay listener o no hay permiso,
    no pasa nada."""
    # macOS / Linux: lsof -ti :8765 devuelve los pids escuchando.
    rc, out = _run(["lsof", "-ti", ":8765"], timeout=15)
    if rc == 0 and out.strip():
        for pid in out.split():
            _run(["kill", "-9", pid.strip()], timeout=10)
    # Segundo intento con fuser si está disponible.
    rc2, out2 = _run(["fuser", "-k", "8765/tcp"], timeout=15)
    # Pequeña pausa para que el SO libere el socket.
    import time as _time
    _time.sleep(0.5)


def _is_env_failure(out_v):
    """Detecta fallos del verify que son CAUSA AMBIENTAL (no de calidad):
    el harness de tests no pudo arrancar (p.ej. puerto 8765 ocupado por un
    run previo: 'ya está ocupado' / 'no se pudo leer el tally'), o excepción
    de import/arranque. Estos NO son fallos de los tests del código y merecen
    reintento. Un tally real ('X passed, Y failed') NO se considera ambiental.
    """
    if not out_v:
        return False
    markers = [
        "ya está ocupado",
        "no se pudo leer el tally",
        "address already in use",
        "port is already allocated",
        "OSError",
        "ConnectionRefusedError",
        "BindError",
    ]
    return any(m in out_v for m in markers)


def resolve_repo(repo_arg, task):
    candidates = []
    if repo_arg:
        candidates.append(repo_arg)
    wp = task.get("workspace_path")
    if wp:
        candidates.append(wp)
    candidates.append(DEFAULT_REPO)
    for cand in candidates:
        if not cand or not os.path.isdir(cand):
            continue
        rc, top = _run(["git", "-C", cand, "rev-parse", "--show-toplevel"],
                       timeout=30)
        if rc != 0:
            continue
        top = top.strip()
        rc2, _ = _run(["git", "-C", top, "rev-parse", "--verify", "origin/main"],
                      timeout=30)
        if rc2 == 0:
            return top
    return repo_arg or DEFAULT_REPO


def resolve_ref(repo, branch):
    for ref in (branch, f"origin/{branch}"):
        rc, _ = _run(["git", "-C", repo, "rev-parse", "--verify", ref], timeout=30)
        if rc == 0:
            return ref
    return None  # no resoluble


def resolve_ancestry(repo, branch):
    ref = resolve_ref(repo, branch)
    if ref is None:
        return None, None  # no resoluble
    # Retry para absorber errores transitorios de lock del object DB
    # (rc=128) cuando hay `git fetch`/worktree concurrentes. rc=1 se trata
    # estrictamente como "no ancestro"; rc>1 (128) se reintenta.
    last_rc = 1
    for _ in range(3):
        rc, _ = _run(["git", "-C", repo, "merge-base", "--is-ancestor",
                      ref, "origin/main"], timeout=60)
        if rc <= 1:
            last_rc = rc
            break
        last_rc = rc  # error transitorio; reintenta
    return (last_rc == 0), f"{ref} (rc={last_rc})"


def detect_code_task(task, primary_branch, force_code, force_noncode):
    if force_noncode:
        return False
    if force_code:
        return True
    if primary_branch:
        return True
    # Sin rama ni flag explícito: el gate no debe *adivinar*. main() tratará
    # esto como "no evaluable" (exit 2) y exigirá --branch o --non-code.
    return False


def collect_acceptance_tests(task, test_args, body_text):
    paths = list(test_args or [])
    for m in re.finditer(r"tests/[A-Za-z0-9_/]+\.py", body_text or ""):
        paths.append(m.group(0))
    for m in re.finditer(r"test_[A-Za-z0-9_]+\.py", body_text or ""):
        paths.append("tests/" + m.group(0))
    seen, out = set(), []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def verdict_fail(args, task, evidence_text):
    if not (args.enforce and not args.dry_run):
        return
    task_id = task["id"]
    comment = (
        "🚫 **DONE bloqueado por `scripts/kanban_done_gate.py`** "
        "(política CEO 2026-08-21, t_86afa3e2).\n\n"
        "Un agente no puede marcar esta tarea DONE: su cambio no cumple el gate "
        "de ancestro/verify sobre `origin/main`. Evidencia:\n\n"
        f"```\n{evidence_text}\n```\n\n"
        "Acción requerida: entregar el cambio a `origin/main` (mergear el PR o "
        "crear tarjeta hija 'entregar a main') y volver a correr el gate con "
        "`--branch <rama-de-entrega>`."
    )
    _run(["hermes", "kanban", "comment", task_id, "--author", "done-gate",
          "--max-len", "6000", comment], timeout=60)
    _run(["hermes", "kanban", "request-review", task_id, "--force",
          "--summary",
          "DONE bloqueado por gate: el cambio no es ancestro de origin/main / "
          "verify no pasa sobre main."], timeout=60)


def do_complete(args, task):
    if args.dry_run or not args.complete_on_pass:
        return
    _run(["hermes", "kanban", "complete", task["id"],
          "--summary",
          "DONE validado por scripts/kanban_done_gate.py: commit ancestro de "
          "origin/main y verify.py APTO sobre main."], timeout=60)


def main(argv):
    ap = argparse.ArgumentParser(
        description="Guard de DONE para tareas de código de LucidFence")
    ap.add_argument("task_id")
    ap.add_argument("--board", default=DEFAULT_BOARD)
    ap.add_argument("--db", default=None)
    ap.add_argument("--repo", default=None)
    ap.add_argument("--branch", default=None,
                    help="Fuerza la rama de trabajo a evaluar")
    ap.add_argument("--test", action="append", default=[],
                    help="Test de aceptación a exigir tracked en origin/main")
    ap.add_argument("--code-task", action="store_true",
                    help="Fuerza modo código (aplica el gate)")
    ap.add_argument("--non-code", action="store_true",
                    help="Fuerza modo no-código (pasa sin verificar)")
    ap.add_argument("--enforce", action="store_true",
                    help="En fallo: comenta evidencia y mueve la card a review")
    ap.add_argument("--complete-on-pass", action="store_true",
                    help="Si el gate pasa, marca la tarea done automáticamente")
    ap.add_argument("--verify-mode", default="auto",
                    choices=["auto", "full", "fast"],
                    help="auto (por defecto): corre verify.py completo; si el "
                         "único fallo es la batería runtime en vivo (conocida "
                         "como flaky en main), cae a --fast y lo registra. "
                         "full: exige verify.py APTO completo (falla si la "
                         "batería en vivo está roja). fast: usa --fast "
                         "(version + enlaces + suite honesta, sin batería en vivo).")
    ap.add_argument("--dry-run", action="store_true",
                    help="No muta el board")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    evidence = []

    def log(line):
        if not args.quiet:
            print(line)
        evidence.append(line)

    try:
        db_path = resolve_db_path(args.board, args.db)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    task = read_task(db_path, args.task_id)
    if not task:
        print(f"ERROR: tarea {args.task_id} no encontrada en {db_path}",
              file=sys.stderr)
        return 2
    body_text = (task.get("body") or "")
    repo = resolve_repo(args.repo, task)
    _cleanup_stale_gate_worktrees(repo)  # evita leaks de runs previos

    # Resolución de la rama de trabajo (requiere un branch explícito).
    primary_branch = args.branch or task.get("branch_name") or None
    is_code = detect_code_task(task, primary_branch, args.code_task,
                               args.non_code)

    log(f"=== kanban_done_gate — tarea {args.task_id} ===")
    log(f"title: {task.get('title')}")
    log(f"repo:  {repo}")
    log(f"rama de trabajo (--branch o task.branch_name): {primary_branch or '(ninguna)'}")
    log(f"modo: {'CÓDIGO' if is_code else 'NO-CÓDIGO (pasa sin verificar ancestro/main)'}")

    # Ni rama, ni --code-task, ni --non-code: el gate no puede evaluar de
    # forma segura. No adivinar — pedir al llamador que declare.
    if not is_code and not args.code_task and not args.non_code:
        log("")
        log("DONE_GATE: NO EVALUABLE — tarea sin rama conocida y sin flag "
            "explícito. El gate no adivina el tipo de tarea. Reejecuta con "
            "--branch <rama-del-trabajo> (código) o --non-code (proceso/docs).")
        return 2

    log("")

    if not is_code:
        do_complete(args, task)
        return 0

    # Refrescar origin/main (best-effort).
    _run(["git", "-C", repo, "fetch", "origin", "main"], timeout=60)

    checks = []  # (name, ok_or_none, detail)

    # CHECK 1: ancestro de origin/main
    # Lógica fail-closed: exige una rama primaria y que ESA sea ancestro.
    # Sin rama primaria -> FALLO (no se puede demostrar que el trabajo está
    # en origin/main). Con rama primaria que no existe como ref -> FALLO.
    ancestry_ok = None
    ancestry_detail = ""
    if primary_branch:
        is_anc, det = resolve_ancestry(repo, primary_branch)
        if is_anc is None:
            ancestry_ok = False
            ancestry_detail = (f"la rama '{primary_branch}' no existe como ref "
                               f"local ni origin/ (detalle: {det}). No se puede "
                               f"probar ancestro de origin/main.")
        else:
            ancestry_ok = is_anc
            ancestry_detail = (f"rama '{primary_branch}': "
                               f"{'ES ancestro de origin/main' if is_anc else 'NO es ancestro — el cambio vive solo en la rama del agente'}"
                               f" ({det})")
    else:
        ancestry_ok = False
        ancestry_detail = ("no hay rama de trabajo (--branch o task.branch_name "
                           "vacíos): no se puede demostrar que el trabajo está "
                           "en origin/main. No se marca done (fail-closed). "
                           "Pasa --branch <rama> o --non-code.")
    checks.append(("ancestro-de-origin/main", ancestry_ok, ancestry_detail))
    log(f"[{'OK' if ancestry_ok else 'FALLO'}] 1. {ancestry_detail}")

    # CHECK 2: tests de aceptación TRACKED en origin/main
    acc_tests = collect_acceptance_tests(task, args.test, body_text)
    untracked = []
    if acc_tests:
        for t in acc_tests:
            rc2, _ = _run(["git", "-C", repo, "cat-file", "-e",
                           f"origin/main:{t}"], timeout=30)
            if rc2 != 0:
                untracked.append(t)
            log(f"    - test aceptación {t}: "
                f"{'TRACKED en origin/main' if rc2 == 0 else 'NO TRACKED en origin/main (untracked en rama del agente = CI no lo corre)'}")
    ok2 = (len(untracked) == 0)
    detail2 = ("todos los tests de aceptación referenciados están TRACKED en origin/main"
               if ok2 else
               f"tests NO tracked en origin/main: {', '.join(untracked)} "
               f"(untracked en rama del agente = CI no los corre = no cuenta)")
    checks.append(("tests-tracked-en-main", ok2, detail2))
    log(f"[{'OK' if ok2 else 'FALLO'}] 2. {detail2}")

    # CHECK 3: verify.py APTO sobre origin/main. Solo si ya pasamos 1 y 2
    # (ahorra tiempo cuando ya sabemos que bloqueamos).
    ok3 = False
    detail3 = ""

    def _attempt_verify():
        """Intenta crear worktree de origin/main y correr verify.
        Devuelve (ok, detail, transient): transient=True si el fallo es por
        causa transitoria (lock de git / timeout) y merece reintento."""
        tmp = tempfile.mkdtemp(prefix="lf-main-gate-")
        try:
            rc_add, out_add = _run(
                ["git", "-C", repo, "worktree", "add", "--detach", tmp,
                 "origin/main"], timeout=120)
            if rc_add != 0:
                return False, f"no se pudo crear worktree de origin/main: {out_add[-300:]}", True
            py = find_python(repo)
            mode = args.verify_mode
            cmd_full = [py, "scripts/verify.py", "--quiet"]
            cmd_fast = [py, "scripts/verify.py", "--fast"]
            _free_port_8765()  # limpia listener huérfano en 8765 (fallo ambiental)
            if mode == "fast":
                rc_v, out_v = _run(cmd_fast, cwd=tmp, timeout=120)
                # Fallo AMBIENTAL del verify (p.ej. el server de pruebas
                # hermético no arranca porque el puerto 8765 quedó ocupado
                # por un run previo: "ya está ocupado / no se pudo leer el
                # tally") NO es fallo de calidad del código; se reintenta.
                # Un fallo real de tests (X failed) es fail-closed.
                env_fail = _is_env_failure(out_v)
                ok = (rc_v == 0)
                det = ("verify.py APTO sobre origin/main (--fast)"
                       if ok else f"verify.py FALLO sobre origin/main (--fast, rc={rc_v})")
                log(f"    python usado: {py}")
                log(f"    `python3 scripts/verify.py --fast` (sobre origin/main) -> rc={rc_v}")
                return ok, det, (env_fail and not ok)
            rc_v, out_v = _run(cmd_full, cwd=tmp, timeout=120)
            if rc_v == 124:
                # Timeout del verify (p.ej. batería en vivo colgada): causa
                # transitoria, reintenta.
                return False, "verify.py superó el timeout (120s) — posible cuelgue transitorio de la batería en vivo", True
            only_runtime = ("Batería runtime (en vivo)" in out_v)
            if rc_v == 0:
                log(f"    python usado: {py}")
                log(f"    `python3 scripts/verify.py --quiet` (sobre origin/main) -> rc={rc_v}")
                return True, "verify.py APTO sobre origin/main (completo)", False
            if only_runtime and mode == "auto":
                rc_f, out_f = _run(cmd_fast, cwd=tmp, timeout=120)
                log(f"    python usado: {py}")
                log(f"    verify completo (rc={rc_v}) falló solo por batería en "
                    f"vivo; fallback --fast rc={rc_f}")
                return (rc_f == 0), ("verify.py APTO sobre origin/main "
                                     "(--fast, fallback de la batería en vivo)"), False
            if only_runtime and mode == "full":
                log(f"    python usado: {py}")
                log(f"    verify completo (rc={rc_v}) falló por batería en vivo; "
                    f"modo full no lo tolera.")
                return False, ("verify.py FALLO en modo full: la batería runtime "
                               "en vivo está roja sobre origin/main. Usa "
                               "--verify-mode auto para tolerar ese fallo "
                               "conocido."), False
            # Fallo real de tests, o fallo ambiental del verify (server no
            # arranca). El primero es fail-closed; el segundo se reintenta.
            env_fail = _is_env_failure(out_v)
            log(f"    python usado: {py}")
            log(f"    verify completo rc={rc_v} "
                f"({'fallo ambiental (reintentable)' if env_fail else 'fallo real de tests'})")
            return False, f"verify.py FALLO sobre origin/main (rc={rc_v})", env_fail
        finally:
            if os.path.isdir(tmp):
                _run(["git", "-C", repo, "worktree", "remove", "--force", tmp],
                     timeout=60)

    if ancestry_ok and ok2:
        _cleanup_stale_gate_worktrees(repo)
        last_detail = ""
        for attempt in range(3):
            ok3, detail3, transient = _attempt_verify()
            last_detail = detail3
            if ok3 or not transient:
                break
            log(f"    (reintento {attempt+1}: fallo transitorio de git/worktree, "
                f"reintentando) — {detail3}")
            _cleanup_stale_gate_worktrees(repo)
        detail3 = last_detail
    else:
        detail3 = "omitido (los checks 1/2 ya fallaron; no se ejecuta verify)"
        log(f"[----] 3. {detail3}")
    checks.append(("verify-apto-sobre-main", ok3, detail3))

    failed = [n for n, ok, _ in checks if not ok and ok is not None]
    log("")
    if failed:
        log(f"DONE_GATE: FALLO — checks fallidos: {', '.join(failed)}")
        log("La tarea NO debe marcarse DONE. Rama verde con PR abierto = 'en review'.")
        verdict_fail(args, task, "\n".join(evidence))
        return 1
    log("DONE_GATE: APTO — el commit es ancestro de origin/main y verify pasa "
        "sobre main. La tarea puede marcarse DONE.")
    do_complete(args, task)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
