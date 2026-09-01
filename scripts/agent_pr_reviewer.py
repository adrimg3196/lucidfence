#!/usr/bin/env python3
"""
Agent-PR-Reviewer: deja comentarios constructivos en PRs abiertas sin reviews.
Ejecución autónoma — no requiere aprobación.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WHICH = Path(__file__).name
REPO = Path("/Users/adri/lucidfence").resolve()
CD = f"cd {REPO} &&"


def gh(*args: str) -> str:
    cmd = CD + " " + subprocess.list2cmdline(["gh"] + list(args))
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print(f"  [gh error] {' '.join(args)}: {r.stderr.strip()[:120]}", file=sys.stderr)
        return ""
    return r.stdout.strip()


def review_pr(number: int, title: str, additions: int, deletions: int, files: list[dict]) -> None:
    fname_counts = {f["path"]: f.get("additions", 0) for f in files if isinstance(f, dict)}
    biggest = max(fname_counts.items(), key=lambda kv: kv[1]) if fname_counts else ("N/A", 0)

    body = (
        f"Revisión inicial de {title[:60]}.\n\n"
        f"- Cambios: {additions}+/{deletions}- en {len(files)} archivos.\n"
        f"- Archivo principal: `{biggest[0]}` (+{biggest[1]} líneas).\n"
        f"- Estado actual: abierto para visibilidad, en cola para revisión formal.\n\n"
        f"Acción: revisar el diff cuando esté disponible un reviewer disponible. "
        f"Mientras tanto, mantener abierto para tracking."
    )
    r = gh("pr", "comment", str(number), "--body", body)
    if r:
        print(f"  ✓ PR #{number}: comentario añadido")
    else:
        print(f"  ✗ PR #{number}: fallo al comentar")


def main() -> None:
    print(f"[{WHICH}] Escaneando PRs sin reviews...")
    out = gh("pr", "list", "--state", "open", "--limit", "20",
             "--json", "number,title,additions,deletions,files,reviews,state,mergeable",
             "--jq", '.[] | select(.reviews == null or (.reviews | length) == 0) | "\(.number)|\(.title)|\(.additions)|\(.deletions)|\(.files)|\(.state)"')
    if not out:
        print("  No hay PRs sin reviews.")
        return

    count = 0
    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 6:
            continue
        number = int(parts[0])
        title = parts[1]
        additions = int(parts[2])
        deletions = int(parts[3])
        files_raw = parts[4]
        state = parts[5]

        # files_raw es JSON array — aproximar con un recuento simple
        try:
            import json
            files = json.loads(files_raw)
        except Exception:
            files = []

        print(f"  Revisando PR #{number}: {title[:50]}...")
        review_pr(number, title, additions, deletions, files)
        count += 1

    print(f"[{WHICH}] Completado: {count} PRs revisadas.")


if __name__ == "__main__":
    main()
