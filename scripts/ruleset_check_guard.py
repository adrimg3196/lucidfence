#!/usr/bin/env python3
"""ruleset_check_guard.py — Pre-vuelo (fail-closed) anti-check-fantasma en
required_status_checks de GitHub rulesets.

REGLA DE ORO (CEO 2026-08-24, tarea t_26b7fac6):
  Nunca añadir un contexto a `required_status_checks` de cualquier ruleset de
  protección de rama antes de que el workflow que lo emite esté MERGEADO en
  `origin/main` Y reportando en verde en una PR real.

MOTIVO (lección verificada): el ruleset 21249696 "LucidFence Autonomy B" exigía
el check `autonomy-evidence`, cuyo workflow solo existía en el PR #264 (rojo) y
NO en main. Ningún PR podía reportar el check -> todos los PR verdes quedaban
BLOCKED por diseño (deadlock repo-wide: 10/10 PRs bloqueados). Se resolvió
quitando el check fantasma. Coste: horas de deadlock en toda la flota.

CONTRATO (fail-closed):
  exit 0 -> APTO:   todos los contextos evaluados tienen workflow en main + run
                    verde en main.
  exit 1 -> FALLO:  hay >=1 contexto fantasma (sin workflow en main) o workflow
                    en main pero sin run verde en main. Blocante.
  exit 2 -> NO EVALUABLE (sin `gh`, sin red, o ruleset no resoluble).

MODOS:
  --audit-live [--ruleset-id ID]
      Audita el ruleset vivo (default: 21249696) de adrimg3196/lucidfence.
      Para cada contexto en required_status_checks, verifica (a) y (b).
  --diff <file|-> [--repo .]
      Extrae contextos añadidos (líneas que empiezan por '+' con un 'context:')
      de un diff/unified y los evalúa. Pre-vuelo de un changeset que toca rulesets.
  --context <nombre> ...
      Evalúa contextos dados explícitamente (p.ej. desde un checklist de review).

VERIFICACIÓN POR CONTEXTO (siempre contra origin/main, NUNCA contra la rama del PR):
  (a) El workflow que emite el contexto está TRACKED en origin/main. Mapeo: busca
      en .github/workflows/*.yml un job cuya 'name:' == context (case-insensitive)
      o cuyo id == slug(context), o un workflow cuya 'name:' == context.
      Si no hay ninguno -> FALLO (check fantasma).
  (b) Ese workflow tiene >=1 run con status=success en la rama main:
      `gh run list --workflow <file> --branch main --status success --limit 1`.
      Si no -> FALLO (workflow existe pero nunca verde en main).

DISEÑO:
  - Se compara SIEMPRE contra origin/main (fetch best-effort) para no caer en el
    error de staleness de rama (t_925438a3): un check "verde en mi rama" no cuenta.
  - Sin red / sin `gh` -> exit 2 (no evaluable), nunca "pasa por defecto".
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys

DEFAULT_REPO = "/Users/adri/lucidfence"
DEFAULT_OWNER_REPO = "adrimg3196/lucidfence"
DEFAULT_RULESET_ID = "21249696"
WORKFLOWS_DIR = ".github/workflows"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _run(cmd, cwd=None, timeout=120):
    try:
        p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True,
                           timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"timeout (> {timeout}s) ejecutando: {' '.join(cmd)}"
    except FileNotFoundError as e:
        return 127, f"comando no encontrado: {e}"


def resolve_repo(repo_arg):
    for cand in (repo_arg, DEFAULT_REPO):
        if not cand or not os.path.isdir(cand):
            continue
        rc, _ = _run(["git", "-C", cand, "rev-parse", "--show-toplevel"],
                     timeout=30)
        if rc == 0:
            return cand
    return repo_arg or DEFAULT_REPO


def resolve_owner_repo(repo):
    rc, out = _run(["git", "-C", repo, "remote", "get-url", "origin"],
                   timeout=30)
    if rc == 0:
        u = out.strip()
        m = re.search(r"[:/]([^:/]+/[^:/]+?)(?:\.git)?$", u)
        if m:
            return m.group(1)
    return DEFAULT_OWNER_REPO


def _gh_available():
    return shutil.which("gh") is not None


def fetch_main(repo):
    # best-effort; no falla el script si no hay red (los chequeos lo detectan)
    _run(["git", "-C", repo, "fetch", "origin", "main"], timeout=60)


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ---------------------------------------------------------------------------
# mapeo contexto -> workflow file en origin/main
# ---------------------------------------------------------------------------
def list_workflow_files(repo):
    rc, out = _run(
        ["git", "-C", repo, "ls-tree", "-r", "--name-only", "origin/main",
         "--", WORKFLOWS_DIR], timeout=60)
    if rc != 0:
        return []
    return [ln for ln in out.splitlines() if ln.endswith((".yml", ".yaml"))]


def _read_workflow(repo, wf):
    rc, out = _run(
        ["git", "-C", repo, "show", f"origin/main:{wf}"], timeout=60)
    return out if rc == 0 else ""


def _workflow_contexts(repo, wf):
    """Devuelve (workflow_name, set(job_ids), set(job_names)) para un wf."""
    text = _read_workflow(repo, wf)
    wf_name = None
    job_ids = set()
    job_names = set()
    in_jobs = False
    for line in text.splitlines():
        if re.match(r"^jobs:\s*$", line):
            in_jobs = True
            continue
        if in_jobs:
            m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
            if m:
                job_ids.add(m.group(1))
                continue
        m = re.match(r"^name:\s*(.+?)\s*$", line)
        if m:
            val = m.group(1).strip().strip('"').strip("'")
            if not in_jobs:
                wf_name = val
            else:
                job_names.add(val)
        # también captura name: dentro de un job (indent > 2)
        m2 = re.match(r"^    name:\s*(.+?)\s*$", line)
        if m2:
            job_names.add(m2.group(1).strip().strip('"').strip("'"))
    return wf_name, job_ids, job_names


def find_workflow_for_context(repo, context):
    """Devuelve la ruta del workflow (en origin/main) que emite `context`,
    o None si ninguno lo emite."""
    target = context.strip()
    tslug = _slug(target)
    for wf in list_workflow_files(repo):
        wf_name, job_ids, job_names = _workflow_contexts(repo, wf)
        if wf_name and wf_name.lower() == target.lower():
            return wf
        if target.lower() in {n.lower() for n in job_names}:
            return wf
        if tslug in {_slug(j) for j in job_ids}:
            return wf
    return None


def workflow_has_green_run_on_main(owner_repo, wf):
    """¿El workflow tiene >=1 run success en la rama main?"""
    leaf = os.path.basename(wf)
    rc, out = _run(
        ["gh", "run", "list", "--repo", owner_repo, "--workflow", leaf,
         "--branch", "main", "--status", "success", "--limit", "1",
         "--json", "databaseId"], timeout=120)
    if rc != 0:
        return False, f"gh run list falló (rc={rc}): {out.strip()[:200]}"
    out = out.strip()
    if out and out != "[]":
        return True, f"run verde encontrado en main para {leaf}"
    return False, f"sin run verde en main para {leaf}"


# ---------------------------------------------------------------------------
# chequeo de un contexto
# ---------------------------------------------------------------------------
def check_context(repo, owner_repo, context):
    wf = find_workflow_for_context(repo, context)
    if wf is None:
        return False, (f"GHOST: ningún workflow en origin/main emite el check "
                       f"'{context}' (ni job name ni job id ni workflow name).")
    ok, detail = workflow_has_green_run_on_main(owner_repo, wf)
    if ok:
        return True, f"OK: '{context}' <- {wf} ({detail})"
    return False, (f"BLOCKED: '{context}' <- {wf} existe en main pero {detail}. "
                   f"El workflow debe haber corrido en verde en main antes de "
                   f"exigirlo como check.")


# ---------------------------------------------------------------------------
# modos
# ---------------------------------------------------------------------------
def contexts_from_diff(diff_text):
    """Extrae contextos añadidos: líneas que empiezan por '+' y contienen
    un 'context:' (formato ruleset JSON / YAML)."""
    out = []
    for line in diff_text.splitlines():
        if not line.startswith("+"):
            continue
        # Acepta "context": "X", 'context': 'X', context: X (YAML o JSON).
        m = re.search(r'context["\s:]*[:=]\s*["\']([^"\']+)["\']', line)
        if m:
            out.append(m.group(1).strip())
            continue
        # también forma sin comillas (YAML suelto): context: workflow-name
        m2 = re.search(r'context["\s:]*[:=]\s*([A-Za-z0-9_ .()/-]+)\s*$', line)
        if m2:
            out.append(m2.group(1).strip())
    return out


def audit_live(repo, owner_repo, ruleset_id):
    if not _gh_available():
        return None, "gh no disponible"
    rc, out = _run(
        ["gh", "api", f"repos/{owner_repo}/rulesets/{ruleset_id}"], timeout=120)
    if rc != 0:
        return None, f"no se pudo leer el ruleset {ruleset_id}: {out.strip()[:200]}"
    import json
    try:
        d = json.loads(out)
    except json.JSONDecodeError as e:
        return None, f"JSON inválido del ruleset: {e}"
    contexts = []
    for r in d.get("rules", []):
        if r.get("type") == "required_status_checks":
            params = r.get("parameters", {}) or {}
            # GitHub devuelve camelCase; por robustez aceptamos ambos.
            for c in params.get("requiredStatusChecks",
                                params.get("required_status_checks", [])):
                ctx = c.get("context")
                if ctx:
                    contexts.append(ctx)
    return contexts, None


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------
def selftest(repo, owner_repo):
    print("=== SELFTEST ruleset_check_guard ===")
    ok = True
    # 1) diff con check fantasma -> debe dar FALLO (exit 1 vía main)
    fake_diff = (
        "--- a/rulesets/foo.json\n"
        "+++ b/rulesets/foo.json\n"
        '+  { "context": "autonomy-evidence-fantasma" }\n'
    )
    ctxs = contexts_from_diff(fake_diff)
    assert "autonomy-evidence-fantasma" in ctxs, "extracción de diff falló"
    res = [check_context(repo, owner_repo, c) for c in ctxs]
    if any(ok_ for ok_, _ in res):
        print("  [FAIL] diff ghost debería dar FALLO")
        ok = False
    else:
        print("  [PASS] diff con check fantasma -> detectado como GHOST")
    # 2) audit-live contra el ruleset real -> todos los contextos vivos deben
    #    ser APTO (prueba que no hay falsos positivos sobre la config legítima).
    if _gh_available():
        ctxs, err = audit_live(repo, owner_repo, DEFAULT_RULESET_ID)
        if err or ctxs is None:
            print(f"  [SKIP] audit-live no evaluable: {err}")
        else:
            bad = []
            for c in ctxs:
                cok, det = check_context(repo, owner_repo, c)
                if not cok:
                    bad.append((c, det))
            if bad:
                print(f"  [WARN] audit-live: {len(bad)} contextos no APTO "
                      f"(revisar si es legítimo):")
                for c, det in bad:
                    print(f"         - {c}: {det}")
            else:
                print(f"  [PASS] audit-live: {len(ctxs)} contextos vivos "
                      f"todos APTO (sin falsos positivos)")
    else:
        print("  [SKIP] audit-live: gh no disponible")
    print("=== FIN SELFTEST ===" if ok else "=== SELFTEST CON FALLOS ===")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main(argv):
    ap = argparse.ArgumentParser(
        description="Pre-vuelo anti-check-fantasma en required_status_checks")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--owner-repo", default=None,
                    help="owner/repo (default adrimg3196/lucidfence)")
    ap.add_argument("--audit-live", action="store_true",
                    help="Audita el ruleset vivo (default 21249696)")
    ap.add_argument("--ruleset-id", default=DEFAULT_RULESET_ID)
    ap.add_argument("--diff", default=None,
                    help="archivo de diff/unified (- para stdin); evalúa "
                         "contextos añadidos")
    ap.add_argument("--context", action="append", default=[],
                    help="contexto explícito a evaluar (repeatible)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    repo = resolve_repo(args.repo)
    owner_repo = args.owner_repo or resolve_owner_repo(repo)
    fetch_main(repo)

    if args.selftest:
        return selftest(repo, owner_repo)

    def log(s):
        if not args.quiet:
            print(s)

    contexts = []
    if args.diff:
        if args.diff == "-":
            diff_text = sys.stdin.read()
        else:
            with open(args.diff) as f:
                diff_text = f.read()
        contexts = contexts_from_diff(diff_text)
        log(f"=== ruleset_check_guard --diff ({args.diff}) ===")
        log(f"contextos añadidos detectados: {len(contexts)}")
    elif args.context:
        contexts = args.context
        log("=== ruleset_check_guard --context ===")
    elif args.audit_live:
        if not _gh_available():
            log("RULESET_GUARD: NO EVALUABLE — `gh` no disponible.")
            return 2
        ctxs, err = audit_live(repo, owner_repo, args.ruleset_id)
        if err or ctxs is None:
            log(f"RULESET_GUARD: NO EVALUABLE — {err}")
            return 2
        contexts = ctxs
        log(f"=== ruleset_check_guard --audit-live (ruleset {args.ruleset_id}) ===")
        log(f"contextos en required_status_checks: {len(contexts)}")
    else:
        log("RULESET_GUARD: ningún modo seleccionado "
            "(--audit-live | --diff | --context | --selftest).")
        return 2

    if not contexts:
        log("RULESET_GUARD: APTO — no hay contextos nuevos que evaluar "
            "(nada que bloquear).")
        return 0

    log("")
    failures = []
    for c in contexts:
        cok, det = check_context(repo, owner_repo, c)
        mark = "OK  " if cok else "FAIL"
        log(f"  [{mark}] {det}")
        if not cok:
            failures.append((c, det))

    log("")
    if failures:
        log(f"RULESET_GUARD: FALLO — {len(failures)} contexto(s) violan la "
            f"Regla de Oro (check fantasma o sin run verde en main).")
        log("  Acción: mergear el workflow a origin/main y esperar un run "
            "verde en main ANTES de añadir el contexto al ruleset.")
        return 1
    log("RULESET_GUARD: APTO — todos los contextos evaluados tienen workflow "
        "en origin/main con run verde en main.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
