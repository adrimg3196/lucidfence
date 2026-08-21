"""Scaffolding de adapters comunitarios: `lucidfence adapter new <nombre>`.

La tesis del ecosistema: cada UEM regional lo añade un contribuidor, no el
core team. Para eso la fricción de empezar tiene que ser ~1 minuto:

    lucidfence adapter new mosyle

genera `lucidfence/core/adapters/mosyle.py` (desde la plantilla SDK con el
naming ya aplicado) y `tests/test_adapter_mosyle.py` (contra las aserciones
congeladas de tests/test_sdk_contract.py), e imprime los dos pasos restantes:
registrar en ADAPTER_REGISTRY y regenerar el índice verificado por hash.

Todo con stdlib; nunca sobreescribe archivos existentes.
"""
from __future__ import annotations

import re
from pathlib import Path

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
# Nombres que chocarían con módulos existentes o palabras del SDK.
_RESERVED = {"base", "simulation", "template_mdm", "adapter", "core", "test"}

TEMPLATE_FILE = "_template_adapter.py"


def _camel(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def validate_name(name: str, adapters_dir: Path) -> str | None:
    """Devuelve el motivo de rechazo, o None si el nombre es válido."""
    if not _NAME_RE.match(name or ""):
        return ("nombre inválido: minúsculas ASCII, dígitos y '_', 2-32 chars, "
                "empezando por letra (p.ej. 'mosyle', 'soti_mobicontrol')")
    if name in _RESERVED:
        return f"'{name}' es un nombre reservado del SDK"
    if (adapters_dir / f"{name}.py").exists():
        return f"ya existe lucidfence/core/adapters/{name}.py"
    return None


def render_adapter(template: str, name: str) -> str:
    """Aplica el naming del nuevo adapter sobre la plantilla SDK."""
    cls = f"{_camel(name)}Adapter"
    out = template.replace("TemplateMdmAdapter", cls)
    out = out.replace('name = "template_mdm"', f'name = "{name}"')
    out = out.replace("TEMPLATE_MDM_TOKEN", f"{name.upper()}_TOKEN")
    out = out.replace("_VALID_ACTIONS_FOR_TEMPLATE", f"_VALID_ACTIONS_{name.upper()}")
    header = (
        f'"""Adapter MDM `{name}` — generado por `lucidfence adapter new {name}`.\n'
        "\n"
        "Rellena _build_request() y la rama live de execute() con la API real de\n"
        "tu MDM. Reglas duras del contrato (ver ADAPTER.md):\n"
        "  1. execute() NUNCA hace raise: ante fallo, {'ok': False, 'error': ...}.\n"
        "  2. name es estable y único (auditoría y routing multi-UEM).\n"
        "  3. dry_run=True construye la petición pero no la envía.\n"
        '"""\n'
    )
    # Sustituye el docstring de la plantilla por el del adapter generado.
    end = out.find('"""', out.find('"""') + 3) + 3
    return header + out[end:]


def render_test(name: str) -> str:
    cls = f"{_camel(name)}Adapter"
    return f'''"""Contract test del adapter `{name}` (generado por el scaffolding).

Reutiliza las aserciones congeladas del SDK (tests/test_sdk_contract.py):
un adapter que pasa esto puede registrarse en ADAPTER_REGISTRY sin tocar core/.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.adapters.{name} import {cls}
from tests.test_sdk_contract import assert_response_shape, assert_valid_name

DEVICE = {{"device_id": "dev-1", "name": "Dispositivo de prueba"}}


def _adapter() -> {cls}:
    return {cls}(org_id="org-test", api_key="x" * 12)


def test_{name}_name_is_contract_valid() -> None:
    assert_valid_name(_adapter().name)
    assert _adapter().name == "{name}"


def test_{name}_dry_run_builds_without_sending() -> None:
    res = _adapter().execute(DEVICE, "lock", {{}}, dry_run=True)
    assert_response_shape(res, "{name}")
    assert res["ok"] is True and res.get("mode") == "dry_run"
    assert res.get("would_send"), "dry_run debe describir la petición que enviaría"


def test_{name}_unsupported_action_fails_closed_without_raising() -> None:
    res = _adapter().execute(DEVICE, "accion-inventada", {{}})
    assert_response_shape(res, "{name}")
    assert res["ok"] is False and res.get("error_type")


def test_{name}_never_raises_on_bad_device() -> None:
    res = _adapter().execute({{}}, "lock", {{}}, dry_run=True)
    assert isinstance(res, dict) and "ok" in res
'''


def scaffold_adapter(name: str, root: str | Path) -> dict:
    """Genera adapter + test. Devuelve {"ok": bool, ...} sin lanzar."""
    root = Path(root)
    adapters_dir = root / "lucidfence" / "core" / "adapters"
    tests_dir = root / "tests"
    reason = validate_name(name, adapters_dir)
    if reason:
        return {"ok": False, "error": reason}
    template_path = adapters_dir / TEMPLATE_FILE
    if not template_path.is_file():
        return {"ok": False, "error": f"plantilla SDK no encontrada: {template_path}"}
    test_path = tests_dir / f"test_adapter_{name}.py"
    if test_path.exists():
        return {"ok": False, "error": f"ya existe {test_path.name}"}

    adapter_path = adapters_dir / f"{name}.py"
    adapter_path.write_text(render_adapter(template_path.read_text(encoding="utf-8"), name),
                            encoding="utf-8")
    test_path.write_text(render_test(name), encoding="utf-8")
    cls = f"{_camel(name)}Adapter"
    return {
        "ok": True,
        "adapter_path": str(adapter_path.relative_to(root)),
        "test_path": str(test_path.relative_to(root)),
        "class_name": cls,
        "next_steps": [
            f"1. Implementa la API real en {adapter_path.relative_to(root)} "
            "(_build_request + rama live de execute).",
            "2. Regístralo en lucidfence/core/adapters/__init__.py: "
            f"ADAPTER_REGISTRY[\"{name}\"] = {cls}",
            f"3. Corre los tests: python3 -m pytest tests/test_adapter_{name}.py",
            "4. Regenera el índice verificado: python3 scripts/build_adapter_index.py",
            "5. Guía completa y reglas del contrato: lucidfence/core/adapters/ADAPTER.md",
        ],
    }
