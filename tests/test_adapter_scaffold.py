"""Tests del scaffolding de adapters (P1.5): `lucidfence adapter new`."""
from __future__ import annotations

import ast
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.adapter_scaffold import render_adapter, scaffold_adapter, validate_name

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS_DIR = ROOT / "lucidfence" / "core" / "adapters"


def _fake_repo() -> Path:
    """Árbol mínimo de checkout con la plantilla SDK real."""
    tmp = Path(tempfile.mkdtemp(prefix="lf-scaffold-"))
    adapters = tmp / "lucidfence" / "core" / "adapters"
    adapters.mkdir(parents=True)
    shutil.copy(ADAPTERS_DIR / "_template_adapter.py", adapters / "_template_adapter.py")
    (tmp / "tests").mkdir()
    return tmp


def test_scaffold_generates_adapter_and_test() -> None:
    repo = _fake_repo()
    try:
        result = scaffold_adapter("mosyle", repo)
        assert result["ok"] is True
        adapter_src = (repo / result["adapter_path"]).read_text(encoding="utf-8")
        test_src = (repo / result["test_path"]).read_text(encoding="utf-8")
        # Naming aplicado por completo: no queda rastro de la plantilla.
        assert "class MosyleAdapter" in adapter_src
        assert 'name = "mosyle"' in adapter_src
        assert "MOSYLE_TOKEN" in adapter_src
        assert "template_mdm" not in adapter_src and "TemplateMdmAdapter" not in adapter_src
        assert "from lucidfence.core.adapters.mosyle import MosyleAdapter" in test_src
        # Ambos archivos son Python válido.
        ast.parse(adapter_src)
        ast.parse(test_src)
        assert any("ADAPTER_REGISTRY" in step for step in result["next_steps"])
    finally:
        shutil.rmtree(repo)


def test_generated_adapter_satisfies_frozen_sdk_contract() -> None:
    # El adapter recién generado debe pasar las aserciones congeladas del SDK
    # sin editar nada: ejecutamos su código renderizado en memoria.
    from tests.test_sdk_contract import assert_response_shape, assert_valid_name
    template = (ADAPTERS_DIR / "_template_adapter.py").read_text(encoding="utf-8")
    src = render_adapter(template, "kandji")
    namespace: dict = {}
    exec(compile(src, "kandji.py", "exec"), namespace)
    adapter = namespace["KandjiAdapter"](org_id="o", api_key="x" * 12)
    assert_valid_name(adapter.name)
    assert adapter.name == "kandji"
    res = adapter.execute({"device_id": "d1", "name": "D"}, "lock", {}, dry_run=True)
    assert_response_shape(res, "kandji")
    assert res["ok"] is True and res.get("mode") == "dry_run"
    bad = adapter.execute({"device_id": "d1"}, "accion-inventada", {})
    assert_response_shape(bad, "kandji")
    assert bad["ok"] is False


def test_scaffold_refuses_bad_names_and_collisions() -> None:
    repo = _fake_repo()
    try:
        assert scaffold_adapter("Mosyle", repo)["ok"] is False       # mayúscula
        assert scaffold_adapter("1abc", repo)["ok"] is False          # empieza por dígito
        assert scaffold_adapter("base", repo)["ok"] is False          # reservado
        assert scaffold_adapter("", repo)["ok"] is False
        assert scaffold_adapter("soti_mobicontrol", repo)["ok"] is True
        # Segunda vez: existe → se niega a sobreescribir.
        again = scaffold_adapter("soti_mobicontrol", repo)
        assert again["ok"] is False and "ya existe" in again["error"]
    finally:
        shutil.rmtree(repo)


def test_validate_name_reasons_are_actionable() -> None:
    assert "reservado" in validate_name("simulation", ADAPTERS_DIR)
    assert "ya existe" in validate_name("jamf", ADAPTERS_DIR)
    assert validate_name("miguel_uem", Path(tempfile.mkdtemp())) is None


def test_cli_wires_adapter_new_command() -> None:
    from lucidfence.cli import build_parser
    args = build_parser().parse_args(["adapter", "new", "mimdm"])
    assert args.name == "mimdm" and callable(args.func)
