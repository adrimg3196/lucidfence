"""Guardarrail issue #108: pyproject.toml y requirements.lock no pueden divergir.

El job `Dependency audit` del CI solo audita `requirements.lock`, así que un pin
vulnerable en `pyproject.toml` (la vía de `pip install -e .` / `pip install
lucidfence`) pasaba en verde. Estos tests hacen que cualquier divergencia entre
los pins exactos declarados y la lock rompa la suite.
"""
from __future__ import annotations

import os
import re
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _declared_exact_pins() -> dict[str, str]:
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
        pyproject = tomllib.load(fh)
    pins: dict[str, str] = {}
    for dep in pyproject["project"]["dependencies"]:
        m = re.fullmatch(r"([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?==([0-9][A-Za-z0-9_.]*)", dep.strip())
        if m:
            pins[m.group(1).lower().replace("_", "-")] = m.group(2)
    return pins


def _locked_versions() -> dict[str, str]:
    locked: dict[str, str] = {}
    with open(os.path.join(ROOT, "requirements.lock"), encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"^([A-Za-z0-9_.-]+)==([0-9][A-Za-z0-9_.]*)", line.strip())
            if m:
                locked[m.group(1).lower().replace("_", "-")] = m.group(2)
    return locked


def test_exact_pins_in_pyproject_match_requirements_lock() -> None:
    pins = _declared_exact_pins()
    locked = _locked_versions()
    assert pins, "pyproject.toml sin pins exactos: revisa el parser de este test"
    divergent = {
        name: (version, locked.get(name))
        for name, version in pins.items()
        if locked.get(name) != version
    }
    assert not divergent, (
        "pyproject.toml y requirements.lock divergen (issue #108): "
        + ", ".join(
            f"{name} declara {decl} pero la lock trae {lock}"
            for name, (decl, lock) in sorted(divergent.items())
        )
    )


def test_cryptography_pin_is_not_vulnerable_49() -> None:
    # Regresión directa de PYSEC-2026-3552: cryptography 49.0.0 en el camino
    # de auth OIDC (validación de firma JWKS del id_token).
    pins = _declared_exact_pins()
    assert "cryptography" in pins, "cryptography debe seguir pineada en pyproject.toml"
    assert pins["cryptography"] != "49.0.0", (
        "cryptography==49.0.0 es vulnerable (PYSEC-2026-3552); alinear con requirements.lock"
    )
