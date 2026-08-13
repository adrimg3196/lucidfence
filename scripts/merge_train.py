#!/usr/bin/env python3
"""Merge train — cola compartida de PRs para el equipo de agentes.

Ver `docs/references/agent-team-charter.md`. Existe porque el cuello de botella
del repo no es producir PRs sino mergearlos: el 2026-08-13 había 21 PRs abiertos,
11 verdes sin mergear, el más antiguo de 16 días, y 0 merges en 6 días.

Usage:
    python3 scripts/merge_train.py              # informe por consola
    python3 scripts/merge_train.py --publish    # upsert de la issue de la cola
    python3 scripts/merge_train.py --enforce    # etiqueta stale-rebase / wip-over-limit
    python3 scripts/merge_train.py --json       # salida cruda para otros agentes

Solo stdlib + `gh` CLI (convención del repo: nada de dependencias nuevas).
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys

REPO = "adrimg3196/lucidfence"
QUEUE_LABEL = "merge-train"
STALE_LABEL = "stale-rebase"
STALE_DAYS = 3
GLOBAL_WIP_LIMIT = 6

# Estados de mergeabilidad que GitHub devuelve y qué significan para la cola.
READY = {"CLEAN", "HAS_HOOKS", "UNSTABLE"}
BLOCKED_BY_CONFLICT = {"DIRTY"}
BLOCKED_BY_BASE = {"BEHIND"}


def gh_json(args: list[str]) -> object:
    """Llama a `gh` y parsea JSON. Falla ruidosamente: la cola en silencio miente."""
    try:
        out = subprocess.check_output(["gh", *args], text=True, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise SystemExit("gh CLI no encontrado — requerido para hablar con la API")
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"gh {' '.join(args)} falló: {exc.stderr.strip()}")
    return json.loads(out) if out.strip() else []


def now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def age_days(iso: str) -> int:
    stamp = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (now() - stamp).days


def ci_state(pr: dict) -> tuple[int, int]:
    """(checks en verde, checks totales). Un PR sin checks no cuenta como verde."""
    checks = pr.get("statusCheckRollup") or []
    failed = sum(
        1 for c in checks
        if c.get("conclusion") in ("FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED")
    )
    return len(checks) - failed, len(checks)


def classify(pr: dict) -> str:
    """Estado del PR de cara a la cola. Un solo sitio decide, para que agentes
    distintos no discrepen sobre quién va primero."""
    green, total = ci_state(pr)
    state = pr.get("mergeStateStatus") or "UNKNOWN"
    if state in BLOCKED_BY_CONFLICT:
        return "conflict"
    if total == 0:
        return "no-ci"
    if green < total:
        return "ci-red"
    if state in BLOCKED_BY_BASE:
        return "needs-update"
    if state in READY:
        return "ready"
    return "unknown"


def fetch_prs() -> list[dict]:
    fields = "number,title,createdAt,updatedAt,author,labels,mergeStateStatus,statusCheckRollup,isDraft"
    prs = gh_json(["pr", "list", "--repo", REPO, "--state", "open", "--limit", "100",
                   "--json", fields])
    return [p for p in prs if not p.get("isDraft")]


def build_queue(prs: list[dict]) -> dict:
    rows = []
    for pr in prs:
        green, total = ci_state(pr)
        rows.append({
            "number": pr["number"],
            "title": pr["title"],
            "author": (pr.get("author") or {}).get("login", "?"),
            "age": age_days(pr["createdAt"]),
            "idle": age_days(pr["updatedAt"]),
            "ci": f"{green}/{total}",
            "status": classify(pr),
            "labels": [lb["name"] for lb in pr.get("labels") or []],
        })
    # El train es FIFO estricto entre los listos: el que lleva más tiempo esperando
    # entra primero. Lo no-listo se ordena detrás, también por antigüedad.
    rows.sort(key=lambda r: (r["status"] != "ready", -r["age"]))
    ready = [r for r in rows if r["status"] == "ready"]
    return {
        "generated_at": now().isoformat(timespec="seconds"),
        "open_total": len(rows),
        "wip_limit": GLOBAL_WIP_LIMIT,
        "over_limit": len(rows) > GLOBAL_WIP_LIMIT,
        "next_up": ready[0]["number"] if ready else None,
        "rows": rows,
    }


def render(queue: dict) -> str:
    lines = []
    drain = queue["over_limit"]
    if drain:
        lines.append(
            f"> **MODO DRENAJE** — {queue['open_total']} PRs abiertos "
            f"(límite {queue['wip_limit']}). Nadie empieza trabajo nuevo: "
            "solo rebasar, mergear o cerrar. Regla 1 del charter."
        )
    else:
        lines.append(
            f"> {queue['open_total']}/{queue['wip_limit']} PRs abiertos — "
            "dentro de límite, se puede coger trabajo nuevo."
        )
    lines.append("")
    nxt = queue["next_up"]
    lines.append(f"**Siguiente en entrar:** {'#%d' % nxt if nxt else '— ninguno listo —'}")
    lines.append("")
    lines.append("| # | edad | CI | estado | autor | título |")
    lines.append("|---|---|---|---|---|---|")
    for r in queue["rows"]:
        mark = {
            "ready": "listo",
            "conflict": "CONFLICTO — lo rebasa su autor",
            "needs-update": "detrás de main",
            "ci-red": "CI en rojo",
            "no-ci": "sin CI",
            "unknown": "?",
        }[r["status"]]
        stale = " ⏳" if r["idle"] >= STALE_DAYS and r["status"] != "ready" else ""
        lines.append(
            f"| #{r['number']} | {r['age']}d | {r['ci']} | {mark}{stale} | "
            f"{r['author']} | {r['title'][:60]} |"
        )
    lines.append("")
    lines.append(
        "_Generado por `scripts/merge_train.py`. No editar a mano: se regenera._  \n"
        "_Reglas: `docs/references/agent-team-charter.md`._"
    )
    return "\n".join(lines)


def find_queue_issue() -> int | None:
    issues = gh_json(["issue", "list", "--repo", REPO, "--state", "open",
                      "--label", QUEUE_LABEL, "--limit", "5", "--json", "number"])
    return issues[0]["number"] if issues else None


def publish(body: str) -> None:
    title = "Merge train — cola compartida del equipo de agentes"
    existing = find_queue_issue()
    if existing:
        subprocess.check_call(["gh", "issue", "edit", str(existing), "--repo", REPO,
                               "--body", body])
        print(f"cola actualizada en issue #{existing}")
        return
    subprocess.check_call(["gh", "issue", "create", "--repo", REPO, "--title", title,
                           "--label", QUEUE_LABEL, "--body", body])
    print("issue de cola creada")


def enforce(queue: dict) -> None:
    """Etiqueta lo que está podrido. No cierra ni mergea nada: hacer visible lo
    roto es el trabajo, decidir es del coordinador."""
    for r in queue["rows"]:
        needs_stale = r["idle"] >= STALE_DAYS and r["status"] in ("conflict", "needs-update")
        has_stale = STALE_LABEL in r["labels"]
        if needs_stale and not has_stale:
            subprocess.check_call(["gh", "pr", "edit", str(r["number"]), "--repo", REPO,
                                   "--add-label", STALE_LABEL])
            print(f"#{r['number']} -> +{STALE_LABEL}")
        elif not needs_stale and has_stale:
            subprocess.check_call(["gh", "pr", "edit", str(r["number"]), "--repo", REPO,
                                   "--remove-label", STALE_LABEL])
            print(f"#{r['number']} -> -{STALE_LABEL}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--publish", action="store_true", help="upsert de la issue de cola")
    ap.add_argument("--enforce", action="store_true", help="etiqueta PRs podridos")
    ap.add_argument("--json", action="store_true", help="salida cruda")
    args = ap.parse_args()

    queue = build_queue(fetch_prs())

    if args.json:
        print(json.dumps(queue, indent=2))
        return 0

    body = render(queue)
    print(body)
    if args.publish:
        publish(body)
    if args.enforce:
        enforce(queue)
    return 0


if __name__ == "__main__":
    sys.exit(main())
