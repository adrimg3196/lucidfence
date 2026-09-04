#!/usr/bin/env python3
"""verify — la definición de "hecho" de LucidFence en UN comando.

Inspirado en el `pnpm verify` de agentic-ship (github.com/moasq/agentic-ship):
un único punto de entrada ejecutable que ES el gate de calidad, en vez de una
lista de pasos que cada loop/agente re-escribe (y del que se olvida uno).

Corre, en orden, las comprobaciones que forman el gate QA del repo:

  1. Licencia Apache-2.0 verbatim
  2. Coherencia de versión   cli.VERSION == pyproject == .release-version
  3. Enlaces de docs          links relativos de *.md resuelven (docs/ + raíz)
  4. Batería runtime          scripts/runtime_validation.py debe dar N/N
  5. Suite honesta            tests/run_tests.py; 0 failed obligatorio. Los
                              tests que no pueden correr aquí (cryptography
                              fijada ausente) SALTAN con motivo, no fallan.
  6. Provenance release       verifica el fixture de supply-chain offline
                              (artifact + sbom + dsse) con scripts/verify_provenance.py

Uso:
    python3 scripts/verify.py             # todo; exit 0 solo si todo pasa
    python3 scripts/verify.py --fast      # omite la batería runtime (checks 1,2,3,5,6)
    python3 scripts/verify.py --docs-only # solo versión + enlaces + provenance (instantáneo, CI)
    python3 scripts/verify.py --quiet     # solo el resumen final

Stdlib-only (convención del repo). Exit 0 = APTO; !=0 = algo falló.
"""
from __future__ import annotations

import os
import re
import json
import subprocess
import sys

# #51: el repo exige Python >= 3.11 (tomllib, match statements, etc.). El
# sistema trae 3.9 y `import tomllib` rompe verify.py al arrancar. Fallamos
# temprano con un mensaje claro en vez de un traceback de ImportError.
_MIN_PY = (3, 11)
if sys.version_info < _MIN_PY:
    sys.stderr.write(
        "ERROR: LucidFence `verify` necesita Python >= "
        f"{'%d.%d' % _MIN_PY}, pero usa {sys.version.split()[0]}.\n"
        "Usa un venv: python3.11 -m venv .venv && . .venv/bin/activate\n"
        "  luego: python3.11 scripts/verify.py\n"
    )
    sys.exit(2)

import tomllib  # noqa: E402  (después del guard de versión)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Versión del proyecto (pyproject.toml), usada por check_provenance_release
# para construir el nombre del artifact del fixture. Se lee de pyproject.toml
# en vez de importar lucidfence.cli para evitar efectos laterales al importar
# el módulo completo durante verify --docs-only.
def _read_project_version() -> str:
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
        return tomllib.load(fh)["project"]["version"]

PROJECT_VERSION = _read_project_version()


def _run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def check_license_apache2() -> tuple[bool, str]:
    """LICENSE must be verbatim Apache-2.0 (SPDX) except the appendix block.

    GitHub's license detector and OSS aggregators (LibHunt, alternativeto,
    "open-source alternatives to Intune" lists) rely on a clean Apache-2.0
    match; a paraphrased/modified LICENSE makes them report "Other" and omit
    us. The terms-and-conditions body must be byte-identical to the ASF
    canonical (vendored at scripts/license-ref/APACHE-2.0.txt); only the
    APPENDIX boilerplate (copyright holder) is allowed to differ.
    """
    license_path = os.path.join(ROOT, "LICENSE")
    ref_path = os.path.join(ROOT, "scripts", "license-ref", "APACHE-2.0.txt")
    if not os.path.exists(license_path):
        return False, "LICENSE ausente"
    if not os.path.exists(ref_path):
        return False, "referencia scripts/license-ref/APACHE-2.0.txt ausente"
    with open(license_path, encoding="utf-8") as fh:
        actual = fh.read()
    with open(ref_path, encoding="utf-8") as fh:
        ref = fh.read()

    marker = "END OF TERMS AND CONDITIONS"

    def terms(text: str) -> str:
        idx = text.find(marker)
        if idx == -1:
            return text
        end = text.find("\n", idx)
        return text[:end] if end != -1 else text

    actual_terms, ref_terms = terms(actual), terms(ref)
    if actual_terms != ref_terms:
        a, r = actual_terms.splitlines(), ref_terms.splitlines()
        for i, (la, lr) in enumerate(zip(a, r)):
            if la != lr:
                return False, (f"términos Apache-2.0 difieren en línea {i + 1}: "
                               f"LICENSE={la!r} vs canonical={lr!r}")
        return False, "estructura de términos Apache-2.0 difiere (longitud)"
    if "Licensed under the Apache License, Version 2.0" not in actual:
        return False, "el apéndice no conserva el aviso Apache-2.0"
    if "Copyright" not in actual:
        return False, "el apéndice no conserva el copyright"
    return True, "LICENSE == Apache-2.0 (términos verbatim; apéndice rellenado)"


def check_version_consistency() -> tuple[bool, str]:
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
        pyproject = tomllib.load(fh)["project"]["version"]
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
    # ¿El fallo era de ENTORNO (p.ej. puerto ocupado por proceso ajeno) y no de
    # producto? Lo decimos explícitamente para que el fallo no se lea como
    # "main está roto" (coste: decenas de horas de DoD rojo para cualquier
    # agente). El texto lo emite runtime_validation.py (check CLI lifecycle).
    env_lines = [l.strip() for l in out.splitlines()
                 if l.strip().startswith("FALLO")
                 and "ENTORNO (no es regresión de producto)" in l]
    if env_lines:
        # El claim ya viene como "FALLO <nombre>: ENTORNO (no es regresión de
        # producto): <razón>". Extraemos solo la <razón> para que el resumen
        # sea legible y no repita prefijos.
        reasons = []
        for line in env_lines[:2]:
            idx = line.find("): ")
            reasons.append(line[idx + 3:] if idx != -1 else line)
        return False, (f"{passed}/{total}; ENTORNO (no producto): "
                       + " | ".join(reasons)
                       + " — libera el puerto y reejecuta; main NO está roto")
    fails = [l.strip() for l in out.splitlines() if l.strip().startswith("FALLO")]
    return False, f"{passed}/{total}; " + "; ".join(fails[:5])


def check_test_suite() -> tuple[bool, str]:
    rc, out = _run([sys.executable, "tests/run_tests.py"])
    m = re.search(r"===\s*(\d+)\s*passed,\s*(\d+)\s*skipped,\s*(\d+)\s*failed\s*===", out)
    if not m:
        tail = out.strip().splitlines()[-1] if out.strip() else "sin salida"
        return False, f"no se pudo leer el tally ({tail})"
    passed, skipped, failed = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if failed == 0:
        return True, f"{passed} passed, {skipped} skipped, 0 failed"
    # El runner honesto ahora SALTA (no falla) la baseline OIDC del contenedor,
    # con motivo declarado. Cualquier `failed` aquí es un fallo real y bloquea.
    fail_lines = re.findall(r"^\s*-\s+(\S+::\S+)", out, re.MULTILINE)
    shown = fail_lines or [f"{failed} fallos no parseables"]
    return False, f"{passed} passed, {skipped} skipped, {failed} failed — reales: " + "; ".join(shown[:5])


# ---------------------------------------------------------------------------
# Provenance release check (t_f455bc58 / #233)
# Verifies the committed supply-chain fixture OFFLINE using
# scripts/verify_provenance.py. This is the "único punto de hecho" hook for the
# verifiable-provenance claim: it proves the shipped fixture (artifact + sbom +
# dsse) is internally consistent and links to a git ancestor — with no network.
# It is deterministic-doc (is_doc=True) so --docs-only / --fast behave sanely.
# ---------------------------------------------------------------------------
FIXTURE_DIR = os.path.join(ROOT, "docs", "supply-chain", "fixture")


def check_provenance_release() -> tuple[bool, str]:
    artifact = os.path.join(FIXTURE_DIR, f"lucidfence-{PROJECT_VERSION}.tar.gz")
    sbom = os.path.join(FIXTURE_DIR, "sbom.cdx.json")
    dsse = os.path.join(FIXTURE_DIR, "provenance.dsse.json")
    key = os.path.join(FIXTURE_DIR, "release_signing_demo.pub")
    missing = [p for p in (artifact, sbom, dsse, key) if not os.path.exists(p)]
    if missing:
        return False, "fixture ausente: " + ", ".join(os.path.relpath(p, ROOT) for p in missing)
    # Invoke the standalone verifier; it returns JSON on stdout.
    rc, out = _run([sys.executable, "scripts/verify_provenance.py",
                    "--artifact", artifact, "--sbom", sbom, "--dsse", dsse,
                    "--repo", ROOT, "--key", key, "--json"])
    # The verifier prints the per-check JSON then a final JSON verdict line.
    # Parse the last JSON object on stdout (the verdict dict).
    verdict = None
    for line in reversed(out.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                verdict = json.loads(line)
            except json.JSONDecodeError:
                verdict = None
            break
    if rc != 0 or not verdict:
        return False, f"verify_provenance rc={rc}: " + (out.strip().splitlines()[-1] if out.strip() else "sin salida")
    if verdict.get("verdict") != "APTO":
        return False, "fixture no APTO: " + json.dumps(verdict.get("checks", {}), ensure_ascii=False)[:200]
    predicate_ver = verdict.get("checks", {}).get("version_consistent", {}).get("versions", {}).get("predicate", "?")
    return True, f"fixture APTO (v{predicate_ver})"


# (nombre, función, is_runtime, is_deterministic-doc-check)
CHECKS = [
    ("Licencia Apache-2.0 verbatim", check_license_apache2, False, False),
    ("Coherencia de versión", check_version_consistency, False, True),
    ("Enlaces de docs", check_doc_links, False, True),
    ("Batería runtime (en vivo)", check_runtime_battery, True, False),
    ("Suite honesta", check_test_suite, False, False),
    ("Provenance release", check_provenance_release, False, True),
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
