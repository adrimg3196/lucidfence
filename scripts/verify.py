#!/usr/bin/env python3
"""verify — la definición de "hecho" de LucidFence en UN comando.

Inspirado en el `pnpm verify` de agentic-ship (github.com/moasq/agentic-ship):
un único punto de entrada ejecutable que ES el gate de calidad, en vez de una
lista de pasos que cada loop/agente re-escribe (y del que se olvida uno).

Corre, en orden, las cuatro comprobaciones que forman el gate QA del repo:

  1. Coherencia de versión   cli.VERSION == pyproject == .release-version
  2. Enlaces de docs          links relativos de *.md resuelven (docs/ + raíz)
  3. Batería runtime          scripts/runtime_validation.py debe dar N/N
  4. Suite honesta            tests/run_tests.py; tolera SOLO la baseline
                              conocida de test_oidc_sso.py (cryptography del
                              sistema roto en algunos contenedores; verde en CI)

Uso:
    python3 scripts/verify.py             # todo; exit 0 solo si todo pasa
    python3 scripts/verify.py --fast      # omite la batería runtime (checks 1,2,4)
    python3 scripts/verify.py --docs-only # solo versión + enlaces (instantáneo, CI)
    python3 scripts/verify.py --quiet     # solo el resumen final

Stdlib-only (convención del repo). Exit 0 = APTO; !=0 = algo falló.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

# Compatible con Python 3.9 (macOS system) y 3.11+ (venv del proyecto).
# tomllib llegó en 3.11; en 3.9 usamos tomli (fallback) si está disponible.
try:
    import tomllib
    # Stdlib tomllib: load desde archivo binario
    def _load_toml(path: str) -> dict:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
except ImportError:
    try:
        import tomli as _toml_lib
        # tomli: loads desde string
        def _load_toml(path: str) -> dict:
            with open(path, encoding="utf-8") as fh:
                return _toml_lib.loads(fh.read())
    except ImportError:
        import toml as _toml_lib  # type: ignore[no-redef]
        # toml: loads desde string
        def _load_toml(path: str) -> dict:
            with open(path, encoding="utf-8") as fh:
                return _toml_lib.loads(fh.read())

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# La única baseline de fallos tolerada: OIDC necesita un `cryptography` sano y
# algunos contenedores lo traen roto. En CI (cryptography bueno) estos pasan.
OIDC_BASELINE = "test_oidc_sso.py"


def _run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def check_version_consistency() -> tuple[bool, str]:
    pyproject = _load_toml(os.path.join(ROOT, "pyproject.toml"))["project"]["version"]
    sys.path.insert(0, ROOT)
    from lucidfence.cli import VERSION as cli_version  # noqa: E402
    rv_path = os.path.join(ROOT, ".release-version")
    release_version = ""
    if os.path.exists(rv_path):
        with open(rv_path, encoding="utf-8") as fh:
            release_version = fh.read().strip()
    parts = {"cli.py": cli_version, "pyproject.toml": pyproject}
    if release_version:
        parts[".release-version"] = release_version
    distinct = set(parts.values())
    if len(distinct) == 1:
        return True, f"todas en {cli_version}"
    return False, "divergen: " + ", ".join(f"{k}={v}" for k, v in parts.items())


def check_doc_links() -> tuple[bool, str]:
    md_files: list[str] = []
    for base in ("README.md", "AGENTS.md", "CHANGELOG.md"):
        p = os.path.join(ROOT, base)
        if os.path.exists(p):
            md_files.append(p)
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, "docs")):
        for f in files:
            if f.endswith(".md"):
                md_files.append(os.path.join(dirpath, f))
    broken: list[str] = []
    link_re = re.compile(r"\]\(([^)#]+?)(#[^)]*)?\)")
    for md in md_files:
        base = os.path.dirname(md)
        with open(md, encoding="utf-8") as fh:
            text = fh.read()
        for m in link_re.finditer(text):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "tel:")):
                continue
            resolved = os.path.normpath(os.path.join(base, target))
            if not os.path.exists(resolved):
                broken.append(f"{os.path.relpath(md, ROOT)} → {target}")
    if not broken:
        return True, f"{len(md_files)} ficheros .md, 0 enlaces rotos"
    return False, f"{len(broken)} rotos: " + "; ".join(broken[:6])


def check_runtime_battery() -> tuple[bool, str]:
    rc, out = _run([sys.executable, "scripts/runtime_validation.py"])
    m = re.search(r"RUNTIME:\s*(\d+)/(\d+)\s*claims", out)
    if not m:
        tail = out.strip().splitlines()[-1] if out.strip() else "sin salida"
        return False, f"no se pudo leer el resultado ({tail})"
    passed, total = int(m.group(1)), int(m.group(2))
    if passed == total and rc == 0:
        return True, f"{passed}/{total} claims validados en vivo"
    fails = [l.strip() for l in out.splitlines() if l.strip().startswith("FALLO")]
    return False, f"{passed}/{total}; " + "; ".join(fails[:5])


def check_test_suite() -> tuple[bool, str]:
    rc, out = _run([sys.executable, "tests/run_tests.py"])
    m = re.search(r"===\s*(\d+)\s*passed,\s*(\d+)\s*failed\s*===", out)
    if not m:
        tail = out.strip().splitlines()[-1] if out.strip() else "sin salida"
        return False, f"no se pudo leer el tally ({tail})"
    passed, failed = int(m.group(1)), int(m.group(2))
    if failed == 0:
        return True, f"{passed} passed, 0 failed"
    # Falla — ¿son todos la baseline conocida de OIDC?
    fail_lines = re.findall(r"^\s*-\s+(\S+::\S+)", out, re.MULTILINE)
    non_baseline = [f for f in fail_lines if not f.startswith(OIDC_BASELINE)]
    if fail_lines and not non_baseline:
        return True, (f"{passed} passed, {failed} failed "
                      f"(todos {OIDC_BASELINE} — baseline conocida del contenedor; "
                      f"verde en CI)")
    shown = non_baseline or [f"{failed} fallos no parseables"]
    return False, f"{passed} passed, {failed} failed — reales: " + "; ".join(shown[:5])


# (nombre, función, is_runtime, is_deterministic-doc-check)
CHECKS = [
    ("Coherencia de versión", check_version_consistency, False, True),
    ("Enlaces de docs", check_doc_links, False, True),
    ("Batería runtime (en vivo)", check_runtime_battery, True, False),
    ("Suite honesta", check_test_suite, False, False),
]


def main(argv: list[str]) -> int:
    fast = "--fast" in argv
    quiet = "--quiet" in argv
    docs_only = "--docs-only" in argv
    results: list[tuple[str, bool, str]] = []
    for name, fn, is_runtime, is_doc in CHECKS:
        if docs_only and not is_doc:
            continue
        if fast and is_runtime:
            if not quiet:
                print(f"  …  {name}: omitido (--fast)")
            continue
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, f"excepción: {type(exc).__name__}: {exc}"
        results.append((name, ok, detail))
        if not quiet:
            mark = "OK  " if ok else "FALLO"
            print(f"  {mark} {name}: {detail}")
    hard_fails = [n for n, ok, _ in results if not ok]
    print()
    if hard_fails:
        print(f"=== VERIFY: FALLO ({len(hard_fails)}/{len(results)}): "
              + ", ".join(hard_fails) + " ===")
        return 1
    print(f"=== VERIFY: APTO ({len(results)}/{len(results)} checks) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
