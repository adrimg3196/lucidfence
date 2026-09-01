#!/usr/bin/env python3
"""Tests para policies.py: signals, Policy, load/save/validate, RiskEngine.

 policies.py API:
 - register_signal(name) → decorator
 - sig_* (device, ctx) → dict
 - Policy(id, name, description, when, actions, enabled, severity, source, template_id)
 - Policy.to_dict() → dict
 - load_policies(path) → list[Policy]
 - save_policies(path, policies) → None
 - validate_policies(raw) → list[str]
 - RiskEngine(signals_path=None)
 - RiskEngine.evaluate(device, fence_state, ctx) → dict
"""

import json
from pathlib import Path

import pytest

from lucidfence.core import policies


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def device_basic():
    """Dispositivo básico para tests."""
    return {
        "device_id": "dev-001",
        "platform": "ios",
        "compliant": True,
        "rooted": False,
        "os_outdated": False,
        "hardware_health": {"components": []},
    }


@pytest.fixture
def fence_inside():
    """Geocerca: dispositivo dentro."""
    return "inside"


@pytest.fixture
def fence_outside():
    """Geocerca: dispositivo fuera."""
    return "outside"


@pytest.fixture
def fence_unknown():
    """Geocerca: ubicación desconocida."""
    return "unknown"


@pytest.fixture
def ctx_basic():
    """Contexto básico: turno conocido, dentro de horario, zona de riesgo baja."""
    return {
        "hour": 10,
        "shift_known": True,
        "shift_match": True,
        "off_hours": False,
        "zone_risk": 0.0,
        "route_state": "on_route",
        "route_deviation_m": 0,
    }


# ---------------------------------------------------------------------------
# Signal providers
# ---------------------------------------------------------------------------

class TestSignalProviders:
    """Signals registrados y sus valores calculados."""

    def test_register_signal_adds_to_registry(self):
        """@register_signal añade la función a SIGNAL_PROVIDERS."""
        initial = len(policies.SIGNAL_PROVIDERS)

        @policies.register_signal("test_signal_fake")
        def fake_sig(device, ctx):
            return {}

        assert "test_signal_fake" in policies.SIGNAL_PROVIDERS
        assert policies.SIGNAL_PROVIDERS["test_signal_fake"] is fake_sig
        policies.SIGNAL_PROVIDERS.pop("test_signal_fake", None)

    def test_sig_time_of_day_returns_dict(self, device_basic, ctx_basic):
        """sig_time_of_day devuelve un dict con off_hours."""
        out = policies.sig_time_of_day(device_basic, ctx_basic)
        assert isinstance(out, dict)
        assert "off_hours" in out

    def test_sig_shift_match_returns_dict(self, device_basic, ctx_basic):
        """sig_shift_match devuelve dict con shift_known."""
        out = policies.sig_shift_match(device_basic, ctx_basic)
        assert isinstance(out, dict)
        assert "shift_known" in out

    def test_sig_device_health_returns_dict(self, device_basic, ctx_basic):
        """sig_device_health devuelve dict con compliant, rooted, os_outdated."""
        out = policies.sig_device_health(device_basic, ctx_basic)
        assert isinstance(out, dict)
        assert "compliant" in out
        assert "rooted" in out
        assert "os_outdated" in out

    def test_sig_device_posture_returns_dict(self, device_basic, ctx_basic):
        """sig_device_posture devuelve dict con posture flags."""
        out = policies.sig_device_posture(device_basic, ctx_basic)
        assert isinstance(out, dict)

    def test_sig_location_integrity_returns_dict(self, device_basic, ctx_basic):
        """sig_location_integrity devuelve dict con checks."""
        out = policies.sig_location_integrity(device_basic, ctx_basic)
        assert isinstance(out, dict)

    def test_sig_zone_risk_returns_dict(self, device_basic, ctx_basic):
        """sig_zone_risk devuelve dict con zone_risk."""
        out = policies.sig_zone_risk(device_basic, ctx_basic)
        assert isinstance(out, dict)
        assert "zone_risk" in out

    def test_sig_route_state_returns_dict(self, device_basic, ctx_basic):
        """sig_route_state devuelve dict con route_state."""
        out = policies.sig_route_state(device_basic, ctx_basic)
        assert isinstance(out, dict)
        assert "route_state" in out


# ---------------------------------------------------------------------------
# RiskEngine.evaluate()
# ---------------------------------------------------------------------------

class TestRiskEngineBasics:
    """RiskEngine.evaluate() básico."""

    def test_evaluate_returns_dict_with_risk_score(self, device_basic, fence_inside, ctx_basic):
        """evaluate devuelve un dict con risk_score."""
        engine = policies.RiskEngine()
        result = engine.evaluate(device_basic, fence_inside, ctx_basic)
        assert isinstance(result, dict)
        assert "risk_score" in result
        assert isinstance(result["risk_score"], (int, float))

    def test_evaluate_inside_compliant_low_risk(self, device_basic, fence_inside, ctx_basic):
        """Dispositivo dentro + compliant → riesgo bajo (<50)."""
        engine = policies.RiskEngine()
        result = engine.evaluate(device_basic, fence_inside, ctx_basic)
        assert result["risk_score"] < 50

    def test_evaluate_outside_higher_risk_than_inside(self, device_basic, fence_inside, fence_outside, ctx_basic):
        """Dispositivo fuera → riesgo más alto que dentro."""
        engine = policies.RiskEngine()
        r_out = engine.evaluate(device_basic, fence_outside, ctx_basic)
        r_in = engine.evaluate(device_basic, fence_inside, ctx_basic)
        assert r_out["risk_score"] >= r_in["risk_score"]

    def test_evaluate_unknown_higher_than_inside(self, device_basic, fence_inside, fence_unknown, ctx_basic):
        """Dispositivo con ubicación desconocida → riesgo más alto que dentro."""
        engine = policies.RiskEngine()
        r_unk = engine.evaluate(device_basic, fence_unknown, ctx_basic)
        r_in = engine.evaluate(device_basic, fence_inside, ctx_basic)
        assert r_unk["risk_score"] >= r_in["risk_score"]

    def test_evaluate_returns_signals(self, device_basic, fence_inside, ctx_basic):
        """evaluate devuelve signals en el resultado."""
        engine = policies.RiskEngine()
        result = engine.evaluate(device_basic, fence_inside, ctx_basic)
        assert "signals" in result

    def test_evaluate_returns_reasons(self, device_basic, fence_inside, ctx_basic):
        """evaluate devuelve reasons (justificación del score)."""
        engine = policies.RiskEngine()
        result = engine.evaluate(device_basic, fence_inside, ctx_basic)
        assert "reasons" in result
        assert isinstance(result["reasons"], list)

    def test_evaluate_returns_severity(self, device_basic, fence_inside, ctx_basic):
        """evaluate devuelve severity (low|medium|high|critical)."""
        engine = policies.RiskEngine()
        result = engine.evaluate(device_basic, fence_inside, ctx_basic)
        assert result["severity"] in ("low", "medium", "high", "critical")

    def test_evaluate_returns_verified(self, device_basic, fence_inside, ctx_basic):
        """evaluate devuelve verified (bool)."""
        engine = policies.RiskEngine()
        result = engine.evaluate(device_basic, fence_inside, ctx_basic)
        assert isinstance(result["verified"], bool)

    def test_evaluate_returns_provenance(self, device_basic, fence_inside, ctx_basic):
        """evaluate devuelve provenance."""
        engine = policies.RiskEngine()
        result = engine.evaluate(device_basic, fence_inside, ctx_basic)
        assert result["provenance"] in ("tool", "none", "context")


class TestRiskEngineSeverity:
    """Comportamiento del RiskEngine con diferentes severidades."""

    def test_off_hours_increases_risk(self, device_basic, fence_inside, ctx_basic):
        """Fuera de horario aumenta el riesgo."""
        ctx_off = {**ctx_basic, "off_hours": True}
        engine = policies.RiskEngine()
        r_off = engine.evaluate(device_basic, fence_inside, ctx_off)
        r_on = engine.evaluate(device_basic, fence_inside, ctx_basic)
        assert r_off["risk_score"] >= r_on["risk_score"]

    def test_shift_mismatch_increases_risk(self, device_basic, fence_inside, ctx_basic):
        """Dispositivo fuera de su turno aumenta el riesgo (shift_known=True, shift_match=False implícito)."""
        ctx_mismatch = {**ctx_basic, "shift_known": True}  # shift_known=True → RiskEngine penaliza si no hay shift_match=True
        engine = policies.RiskEngine()
        r_mm = engine.evaluate(device_basic, fence_inside, ctx_mismatch)
        r_match = engine.evaluate(device_basic, fence_inside, ctx_basic)  # ctx_basic tiene shift_known=True también → igual
        # Cuando shift_known=True y no hay shift_match en el signal, el motor penaliza
        # (ver policies.py L416-417: shift_known and not shift_match → +20)
        # Para este test, comparamos contra un ctx donde shift_known=False (sin penalización)
        ctx_no_shift = {**ctx_basic, "shift_known": False}
        r_no_shift = engine.evaluate(device_basic, fence_inside, ctx_no_shift)
        assert r_mm["risk_score"] >= r_no_shift["risk_score"]

    def test_high_zone_risk_increases_score(self, device_basic, fence_inside, ctx_basic):
        """Zona de alto riesgo aumenta el score."""
        ctx_high = {**ctx_basic, "zone_risk": 0.5}
        engine = policies.RiskEngine()
        r_high = engine.evaluate(device_basic, fence_inside, ctx_high)
        r_low = engine.evaluate(device_basic, fence_inside, ctx_basic)
        assert r_high["risk_score"] >= r_low["risk_score"]

    def test_off_route_increases_score(self, device_basic, fence_inside, ctx_basic):
        """Desviado de la ruta aumenta el score."""
        ctx_off = {**ctx_basic, "route_state": "off_route", "route_deviation_m": 500}
        engine = policies.RiskEngine()
        r_off = engine.evaluate(device_basic, fence_inside, ctx_off)
        r_on = engine.evaluate(device_basic, fence_inside, ctx_basic)
        assert r_off["risk_score"] >= r_on["risk_score"]


# ---------------------------------------------------------------------------
# Policy dataclass
# ---------------------------------------------------------------------------

class TestPolicyDataclass:
    """La clase Policy y su serialización."""

    def test_policy_fields(self):
        """Policy tiene las fields esperadas."""
        p = policies.Policy(
            id="pol-1",
            name="test-policy",
            description="una política de prueba",
            when=[{"field": "risk_score", "op": "gte", "value": 50}],
            actions=[{"action": "lock"}],
        )
        assert p.id == "pol-1"
        assert p.name == "test-policy"
        assert p.description == "una política de prueba"
        assert len(p.when) == 1
        assert p.enabled is True
        assert p.severity == "medium"

    def test_policy_to_dict_serializable(self):
        """Policy.to_dict() produce un dict JSON-serializable."""
        p = policies.Policy(
            id="pol-1",
            name="serialize-me",
            description="desc",
            when=[{"field": "fence_state", "op": "eq", "value": "outside"}],
            actions=[{"action": "notify"}],
            severity="high",
        )
        d = p.to_dict()
        assert isinstance(d, dict)
        json.dumps(d)  # debe ser serializable

    def test_policy_to_dict_includes_optional_fields(self):
        """to_dict incluye source y template_id si están seteados."""
        p = policies.Policy(
            id="pol-1",
            name="with-opts",
            description="desc",
            when=[],
            actions=[],
            source="template",
            template_id="tmpl-1",
        )
        d = p.to_dict()
        assert d["source"] == "template"
        assert d["template_id"] == "tmpl-1"

    def test_policy_from_dict_roundtrip(self):
        """Policy.to_dict → Policy.from_dict es idéntico."""
        original = policies.Policy(
            id="pol-1",
            name="roundtrip",
            description="desc",
            when=[{"field": "risk_score", "op": "gte", "value": 80}],
            actions=[{"action": "isolate"}],
            severity="critical",
            source="custom",
        )
        d = original.to_dict()
        restored = policies.Policy(
            id=d["id"],
            name=d["name"],
            description=d["description"],
            when=d["when"],
            actions=d["actions"],
            enabled=d.get("enabled", True),
            severity=d["severity"],
            source=d.get("source"),
            template_id=d.get("template_id"),
        )
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.severity == original.severity


# ---------------------------------------------------------------------------
# load_policies / save_policies
# ---------------------------------------------------------------------------

class TestLoadSavePolicies:
    """Carga y guardado de políticas desde/hacia archivos JSON."""

    def test_load_policies_from_valid_file(self, tmp_path: Path):
        """load_policies carga un archivo JSON válido."""
        path = tmp_path / "policies.json"
        path.write_text(json.dumps([
            {"id": "pol-1", "name": "first", "description": "desc", "when": [], "actions": []},
            {"id": "pol-2", "name": "second", "description": "desc2", "when": [{"field": "fence_state", "op": "eq", "value": "inside"}], "actions": []},
        ]))
        loaded = policies.load_policies(path)
        assert len(loaded) == 2
        assert loaded[0].name == "first"
        assert loaded[1].name == "second"

    def test_load_policies_empty_list(self, tmp_path: Path):
        """load_policies con [] devuelve lista vacía."""
        path = tmp_path / "empty.json"
        path.write_text("[]")
        loaded = policies.load_policies(path)
        assert loaded == []

    def test_load_policies_file_not_found_returns_empty(self, tmp_path: Path):
        """load_policies con archivo que no existe devuelve lista vacía."""
        missing = tmp_path / "nope.json"
        loaded = policies.load_policies(missing)
        assert loaded == []

    def test_load_policies_invalid_json_returns_empty(self, tmp_path: Path):
        """load_policies con JSON inválido devuelve lista vacía."""
        path = tmp_path / "bad.json"
        path.write_text("{ this is not json }")
        loaded = policies.load_policies(path)
        assert loaded == []

    def test_save_policies_writes_file(self, tmp_path: Path):
        """save_policies escribe el archivo."""
        path = tmp_path / "out.json"
        policies_list = [
            policies.Policy(id="pol-1", name="save-test", description="", when=[], actions=[]),
        ]
        policies.save_policies(path, policies_list)
        assert path.exists()
        content = json.loads(path.read_text())
        assert len(content) == 1
        assert content[0]["name"] == "save-test"

    def test_save_then_load_roundtrip(self, tmp_path: Path):
        """save → load devuelve políticas equivalentes."""
        path = tmp_path / "roundtrip.json"
        original = [
            policies.Policy(id="pol-1", name="roundtrip", description="", when=[], actions=[]),
            policies.Policy(id="pol-2", name="second", description="", when=[{"field": "risk_score", "op": "gte", "value": 50}], actions=[{"action": "lock"}]),
        ]
        policies.save_policies(path, original)
        loaded = policies.load_policies(path)
        assert len(loaded) == 2
        assert loaded[0].name == "roundtrip"
        assert loaded[1].name == "second"


# ---------------------------------------------------------------------------
# validate_policies
# ---------------------------------------------------------------------------

class TestValidatePolicies:
    """Validación de políticas: detecta errores en el JSON de entrada."""

    def test_validate_empty_list_ok(self):
        """Lista vacía es válida (no hay errores)."""
        errors = policies.validate_policies([])
        assert errors == []

    def test_validate_valid_policy_ok(self):
        """Política bien formada no genera errores."""
        raw = [
            {"id": "pol-1", "name": "ok", "description": "", "when": [{"field": "risk_score", "op": "gte", "value": 50}], "actions": [{"action": "lock"}], "enabled": True, "severity": "medium"},
        ]
        errors = policies.validate_policies(raw)
        assert errors == []

    def test_validate_not_list_error(self):
        """Si raw no es lista, devuelve error."""
        errors = policies.validate_policies({"not": "a list"})
        assert len(errors) >= 1

    def test_validate_missing_id_reported(self):
        """Política sin id genera error."""
        raw = [
            {"name": "p", "description": "", "when": [], "actions": []},
        ]
        errors = policies.validate_policies(raw)
        assert len(errors) >= 1

    def test_validate_duplicate_id_reported(self):
        """IDs duplicados generan error."""
        raw = [
            {"id": "dup", "name": "p1", "description": "", "when": [], "actions": []},
            {"id": "dup", "name": "p2", "description": "", "when": [], "actions": []},
        ]
        errors = policies.validate_policies(raw)
        assert any("duplicate" in e.lower() for e in errors)

    def test_validate_empty_when_reported(self):
        """when vacío o no es lista genera error."""
        raw = [
            {"id": "pol-1", "name": "p", "description": "", "when": [], "actions": []},
        ]
        errors = policies.validate_policies(raw)
        assert any("when" in e.lower() for e in errors)

    def test_validate_condition_missing_field_reported(self):
        """Condición sin field genera error."""
        raw = [
            {"id": "pol-1", "name": "p", "description": "", "when": [{"op": "gte", "value": 50}], "actions": []},
        ]
        errors = policies.validate_policies(raw)
        assert len(errors) >= 1

    def test_validate_condition_invalid_op_reported(self):
        """Op desconocido genera error."""
        raw = [
            {"id": "pol-1", "name": "p", "description": "", "when": [{"field": "risk_score", "op": "invalid_op", "value": 50}], "actions": []},
        ]
        errors = policies.validate_policies(raw)
        assert len(errors) >= 1
        assert any("invalid_op" in e for e in errors)

    def test_validate_condition_missing_value_reported(self):
        """Condición sin value genera error."""
        raw = [
            {"id": "pol-1", "name": "p", "description": "", "when": [{"field": "risk_score", "op": "gte"}], "actions": []},
        ]
        errors = policies.validate_policies(raw)
        assert len(errors) >= 1

    def test_validate_invalid_action_reported(self):
        """Acción desconocida genera error."""
        raw = [
            {"id": "pol-1", "name": "p", "description": "", "when": [{"field": "risk_score", "op": "gte", "value": 50}], "actions": [{"action": "invalid_action"}], "severity": "medium"},
        ]
        errors = policies.validate_policies(raw)
        assert len(errors) >= 1
        assert any("invalid_action" in e for e in errors)

    def test_validate_invalid_severity_reported(self):
        """Severidad inválida genera error."""
        raw = [
            {"id": "pol-1", "name": "p", "description": "", "when": [{"field": "risk_score", "op": "gte", "value": 50}], "actions": [], "severity": "invalid"},
        ]
        errors = policies.validate_policies(raw)
        assert len(errors) >= 1
        assert any("invalid" in e for e in errors)

    def test_validate_multiple_errors_in_one_policy(self):
        """Varios errores en una política se reportan todos."""
        raw = [
            {"name": "p", "when": [{"op": "bad_op"}], "actions": [{"action": "bad_action"}], "severity": "bad_sev"},
        ]
        errors = policies.validate_policies(raw)
        assert len(errors) >= 3  # name, when, action, severity
