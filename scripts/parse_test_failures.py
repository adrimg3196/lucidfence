#!/usr/bin/env python3
"""parse_test_failures — clasifica fallos de tests/run_tests.py vs QUARANTINE.txt.

monitor-hourly corre el runner honesto (tests/run_tests.py). Algunos módulos
son conocidos-flaky (no accionables); otros son dips de salud reales que deben
auto-archivarse. Este script lee la salida del runner y separa los fallos:

  - real:        fallos en módulos NO listados en QUARANTINE.txt  -> incidente
  - quarantined: fallos en módulos SÍ listados en QUARANTINE.txt  -> se ignoran

Exit 0 si TODOS los fallos están en quarantine (monitor no debe ponerse rojo).
Exit 1 si hay ALGÚN fallo real (el monitor debe auto-archivar un incidente).

Imprime JSON {"real": [...], "quarantined": [...]} a stdout.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FAIL_RE = re.compile(r"^\s*FAIL\s+(\S+\.py)(?:::\S+)?")


def load_quarantine(path: str) -> set[str]:
    q: set[str] = set()
    p = Path(path)
    if not p.exists():
        return q
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Permitir comentarios en línea: "test_x.py   # por qué está en cuarentena"
        line = line.split("#", 1)[0].strip()
        if line:
            q.add(line)
    return q


def classify(text: str, quarantine: set[str]) -> dict:
    real: set[str] = set()
    quarantined: set[str] = set()
    for line in text.splitlines():
        m = FAIL_RE.match(line)
        if not m:
            continue
        f = m.group(1)
        base = Path(f).name
        if base in quarantine or f in quarantine:
            quarantined.add(base)
        else:
            real.add(base)
    return {"real": sorted(real), "quarantined": sorted(quarantined)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarantine", default="tests/QUARANTINE.txt")
    ap.add_argument("--input", default=None, help="fichero con la salida de run_tests.py (def: stdin)")
    args = ap.parse_args()

    text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
    quarantine = load_quarantine(args.quarantine)
    result = classify(text, quarantine)
    print(json.dumps(result))
    return 1 if result["real"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
