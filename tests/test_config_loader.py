#!/usr/bin/env python3
"""Tests para config_loader: carga desde JSON, manejo de errores, .env, MDM defaults.

La API real de config_loader.load():
- Si el archivo NO existe: devuelve {"mode": "simulation"} + lee .env si existe
- Si el archivo existe: carga JSON + mezcla .env + añade MDM defaults (intune, jamf, workspace_one)
- Nunca lanza FileNotFoundError (devuelve defaults seguros)
"""

import json
from pathlib import Path

import pytest

from lucidfence.core import config_loader


class TestConfigLoadBasics:
    """Carga básica: JSON válido, retorno correcto."""

    def test_load_existing_json_returns_dict(self, tmp_path: Path):
        """Cargar un JSON existente devuelve un dict."""
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps({"log_level": "DEBUG"}))
        cfg = config_loader.load(p)
        assert isinstance(cfg, dict)
        assert cfg["log_level"] == "DEBUG"

    def test_load_preserves_all_keys(self, tmp_path: Path):
        """Todas las claves del JSON se preservan."""
        p = tmp_path / "full.json"
        p.write_text(json.dumps({"a": 1, "b": "text", "c": True, "d": None}))
        cfg = config_loader.load(p)
        assert cfg["a"] == 1
        assert cfg["b"] == "text"
        assert cfg["c"] is True
        assert cfg["d"] is None


class TestConfigLoadMissingFile:
    """Comportamiento cuando el archivo no existe: defaults seguros, no crash."""

    def test_load_missing_file_returns_simulation_default(self, tmp_path: Path):
        """Archivo que no existe devuelve {'mode': 'simulation'}."""
        missing = tmp_path / "nope.json"
        cfg = config_loader.load(missing)
        assert cfg == {"mode": "simulation"}

    def test_load_missing_file_no_exception(self, tmp_path: Path):
        """No lanza FileNotFoundError — es design choice del módulo."""
        missing = tmp_path / "nope.json"
        # No debe lanzar
        cfg = config_loader.load(missing)
        assert cfg is not None
        assert "mode" in cfg

    def test_load_missing_file_with_env_returns_env_in_os(self, tmp_path: Path):
        """Si existe .env al lado, sus vars se setdean en os.environ."""
        env_file = tmp_path / ".env"
        env_file.write_text('TEST_VAR=hola\n')
        missing = tmp_path / "nope.json"
        import os
        os.environ.pop("TEST_VAR", None)
        cfg = config_loader.load(missing)
        assert os.environ.get("TEST_VAR") == "hola"


class TestConfigLoadEnvIntegration:
    """Integración con .env: override de valores, org_id, MDM live."""

    def test_env_org_id_merges_into_config(self, tmp_path: Path):
        """APPLIVERY_ORG_ID en .env se mergea en cfg['applivery']['org_id']."""
        env_file = tmp_path / ".env"
        env_file.write_text('APPLIVERY_ORG_ID=org-123\n')
        cfg_file = tmp_path / "cfg.json"
        cfg_file.write_text(json.dumps({"mode": "simulation"}))
        cfg = config_loader.load(cfg_file)
        assert cfg.get("applivery", {}).get("org_id") == "org-123"

    def test_env_intune_live_flag(self, tmp_path: Path):
        """INTUNE_TENANT_ID activa live mode para intune."""
        env_file = tmp_path / ".env"
        env_file.write_text('INTUNE_TENANT_ID=t-123\n')
        cfg_file = tmp_path / "cfg.json"
        cfg_file.write_text(json.dumps({"mode": "simulation"}))
        cfg = config_loader.load(cfg_file)
        mdm = cfg.get("mdm", {})
        assert mdm.get("intune", {}).get("live") is True
        assert mdm.get("intune", {}).get("tenant_id") == "t-123"

    def test_env_jamf_live_flag(self, tmp_path: Path):
        """JAMF_BASE_URL activa live mode para jamf."""
        env_file = tmp_path / ".env"
        env_file.write_text('JAMF_BASE_URL=https://jamf.example.com\n')
        cfg_file = tmp_path / "cfg.json"
        cfg_file.write_text(json.dumps({}))
        cfg = config_loader.load(cfg_file)
        mdm = cfg.get("mdm", {})
        assert mdm.get("jamf", {}).get("live") is True
        assert mdm.get("jamf", {}).get("base_url") == "https://jamf.example.com"

    def test_env_workspace_one_live_flag(self, tmp_path: Path):
        """WORKSPACE_ONE_BASE_URL activa live mode para workspace_one."""
        env_file = tmp_path / ".env"
        env_file.write_text('WORKSPACE_ONE_BASE_URL=https://wso.example.com\n')
        cfg_file = tmp_path / "cfg.json"
        cfg_file.write_text(json.dumps({}))
        cfg = config_loader.load(cfg_file)
        mdm = cfg.get("mdm", {})
        assert mdm.get("workspace_one", {}).get("live") is True

    def test_env_intune_defaults_empty_when_no_env(self, tmp_path: Path):
        """Sin INTUNE_TENANT_ID, intune live es False y tenant_id es ''."""
        env_file = tmp_path / ".env"
        env_file.write_text('# nada\n')
        cfg_file = tmp_path / "cfg.json"
        cfg_file.write_text(json.dumps({}))
        cfg = config_loader.load(cfg_file)
        intune = cfg.get("mdm", {}).get("intune", {})
        assert intune.get("live") is False
        assert intune.get("tenant_id") == ""


class TestConfigLoadMdmDefaults:
    """Verificar que los defaults de MDM se añaden automáticamente."""

    def test_mdm_section_added_to_existing_config(self, tmp_path: Path):
        """Cualquier config existe, se añade cfg['mdm'] con intune/jamf/workspace_one."""
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps({"custom": "value"}))
        cfg = config_loader.load(p)
        assert "mdm" in cfg
        mdm = cfg["mdm"]
        assert "intune" in mdm
        assert "jamf" in mdm
        assert "workspace_one" in mdm

    def test_mdm_intune_has_expected_keys(self, tmp_path: Path):
        """intune cfg tiene las claves esperadas."""
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps({}))
        cfg = config_loader.load(p)
        intune = cfg["mdm"]["intune"]
        assert "live" in intune
        assert "tenant_id" in intune
        assert "client_id" in intune
        assert "client_secret" in intune
        assert "endpoint_template" in intune

    def test_mdm_jamf_has_expected_keys(self, tmp_path: Path):
        """jamf cfg tiene las claves esperadas."""
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps({}))
        cfg = config_loader.load(p)
        jamf = cfg["mdm"]["jamf"]
        assert "live" in jamf
        assert "base_url" in jamf
        assert "client_id" in jamf
        assert "client_secret" in jamf

    def test_mdm_workspace_one_has_expected_keys(self, tmp_path: Path):
        """workspace_one cfg tiene las claves esperadas."""
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps({}))
        cfg = config_loader.load(p)
        wso = cfg["mdm"]["workspace_one"]
        assert "live" in wso
        assert "base_url" in wso
        assert "tenant_code" in wso
        assert "username" in wso
        assert "password" in wso


class TestConfigLoadEnvParsing:
    """Parseo de .env: comentarios, blanks, quoting."""

    def test_env_comments_ignored(self, tmp_path: Path):
        """Lneas que empiezan con # son ignoradas."""
        env_file = tmp_path / ".env"
        env_file.write_text('# esto es un comentario\nREAL_VAR=valor\n')
        missing = tmp_path / "nope.json"
        import os
        os.environ.pop("REAL_VAR", None)
        cfg = config_loader.load(missing)
        assert os.environ.get("REAL_VAR") == "valor"

    def test_env_blank_lines_ignored(self, tmp_path: Path):
        """Lneas en blanco son ignoradas."""
        env_file = tmp_path / ".env"
        env_file.write_text('\n\nKEY=val\n\n')
        missing = tmp_path / "nope.json"
        import os
        os.environ.pop("KEY", None)
        cfg = config_loader.load(missing)
        assert os.environ.get("KEY") == "val"

    def test_env_quoted_values_stripped(self, tmp_path: Path):
        """Valores entre comillas se desquetan."""
        env_file = tmp_path / ".env"
        env_file.write_text('KEY="valor entre comillas"\n')
        missing = tmp_path / "nope.json"
        import os
        os.environ.pop("KEY", None)
        cfg = config_loader.load(missing)
        assert os.environ.get("KEY") == "valor entre comillas"

    def test_env_single_quotes_stripped(self, tmp_path: Path):
        """Valores entre comillas simples se desquetan."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY='valor simple'\n")
        missing = tmp_path / "nope.json"
        import os
        os.environ.pop("KEY", None)
        cfg = config_loader.load(missing)
        assert os.environ.get("KEY") == "valor simple"
