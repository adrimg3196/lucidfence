#!/usr/bin/env python3
"""move_changelog_unreleased — renombra [Unreleased] -> [version] en un release.

Al cortar un tag, release.yml necesita que la sección [Unreleased] del
CHANGELOG pase a ser [version] - fecha, dejando una sección [Unreleased]
vacía fresca arriba para el desarrollo continuo. Sin esto, release.yml
recaía en el fallback "Release vX.Y.Z" vacío (visto en v1.5.0).

Uso:
    python3 scripts/move_changelog_unreleased.py --version 1.7.0
    python3 scripts/move_changelog_unreleased.py --version 1.7.0 --dry-run

Comportamiento:
    - Si ya existe una sección `## [<version>]`, es idempotente (no duplica).
    - Reescribe CHANGELOG.md en disco salvo --dry-run.
    - La primera sección resultante SIEMPRE es [Unreleased] (el gate de
      release_preflight check_changelog_unreleased lo exige).
"""
from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

UNRELEASED_RE = re.compile(r"^##\s+\[Unreleased\]", re.IGNORECASE)
VERSION_RE = re.compile(r"^##\s+\[([0-9]+\.[0-9]+\.[0-9]+)\]")
HEADING_RE = re.compile(r"^##\s")


def move(text: str, version: str, date: str | None = None) -> tuple[str, bool]:
    """Mueve [Unreleased] -> [version] - date. Devuelve (nuevo_texto, cambió)."""
    date = date or datetime.date.today().isoformat()
    lines = text.splitlines(keepends=True)

    # ¿Ya existe la sección de versión? -> idempotente, no tocar.
    for line in lines:
        m = VERSION_RE.match(line)
        if m and m.group(1) == version:
            return text, False

    idx = None
    for i, line in enumerate(lines):
        if UNRELEASED_RE.match(line):
            idx = i
            break
    if idx is None:
        # Sin [Unreleased]: no hay nada que mover (probablemente ya movido a
        # mano). Devolvemos sin cambios para no romper nada.
        return text, False

    # Contenido (bullets) bajo [Unreleased] hasta la siguiente cabecera '## '.
    rest = lines[idx + 1 :]
    end = len(rest)
    for j, l in enumerate(rest):
        if HEADING_RE.match(l):
            end = j
            break
    bullets = rest[:end]
    # Recortar líneas en blanco iniciales de los bullets.
    while bullets and bullets[0].strip() == "":
        bullets.pop(0)
    tail = rest[end:]

    replacement = f"## [Unreleased]\n\n## [{version}] - {date}\n"
    new_lines = lines[:idx] + [replacement] + bullets + tail
    return "".join(new_lines), True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--date", default=None)
    ap.add_argument("--file", default="CHANGELOG.md")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", args.version):
        print(f"error: versión inválida: {args.version!r}", file=sys.stderr)
        return 1

    path = Path(args.file)
    if not path.exists():
        print(f"error: {path} no existe", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    new_text, changed = move(text, args.version, date=args.date)

    if args.dry_run:
        print(new_text)
        print(f"--dry-run: cambió={changed}", file=sys.stderr)
        return 0

    path.write_text(new_text, encoding="utf-8")
    print(f"CHANGELOG.md: [Unreleased] -> [{args.version}] (cambió={changed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
