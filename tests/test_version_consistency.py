"""Guardarrail de versiones: lo que anuncia el CLI debe ser lo que empaqueta el repo.

Origen: `lucidfence --version` decía 1.2.0 con pyproject en 1.3.1 y la última
release en v1.4.0 — tres números distintos para el mismo software. La versión
vive en pyproject.toml y el CLI debe coincidir; si divergen, la suite (y el CI)
lo bloquean.
"""
from __future__ import annotations

import os
import re
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pyproject_version() -> str:
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def test_cli_version_matches_pyproject() -> None:
    from lucidfence.cli import VERSION
    assert VERSION == _pyproject_version(), (
        f"cli.py VERSION={VERSION!r} != pyproject {_pyproject_version()!r}: "
        "alinear ambos antes de taggear una release"
    )


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", _pyproject_version())


def test_release_version_file_matches_pyproject() -> None:
    # .release-version es el botón de release (release.yml se dispara al
    # tocarlo en main); si no coincide con pyproject, el guard del workflow
    # abortaría la publicación — mejor pararlo aquí, antes del merge.
    with open(os.path.join(ROOT, ".release-version"), encoding="utf-8") as fh:
        assert fh.read().strip() == _pyproject_version()


def test_package_version_matches_pyproject() -> None:
    # lucidfence.__version__ es lo que lee `import lucidfence; lucidfence.__version__`
    # y lo que termina en el metadata del wheel. Antes decía 1.3.1 con el repo en
    # 1.6.0 (3 minors por detrás) y ningún test lo atrapaba. Este test cierra el
    # agujero: si __init__ diverge de pyproject, el CI lo bloquea.
    from lucidfence import __version__ as pkg_version
    assert pkg_version == _pyproject_version(), (
        f"lucidfence.__version__={pkg_version!r} != pyproject {_pyproject_version()!r}: "
        "alinear __init__.py antes de taggear una release"
    )
