"""Apple DDM: generación de declarations e ingesta del status channel.

Fixtures golden contra los schemas públicos de Apple (`apple/device-management`,
`declarative/`): tipos de declaration, claves de payload y disponibilidad por
OS. Sin red.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lucidfence.core.ddm import (  # noqa: E402
    build_declarations,
    build_status_subscriptions,
    parse_status_report,
    supports_ddm,
)
from lucidfence.core.adapters.base import MDMAdapter  # noqa: E402
from lucidfence.core.adapters.jamf import JamfAdapter  # noqa: E402

POLICY = {"id": "geofence-hq", "name": "HQ", "severity": "high"}
URL = "https://mdm.example.com/profiles/geofence-hq.mobileconfig"


def test_supports_ddm_gates_by_platform_and_version():
    assert supports_ddm({"platform": "ios", "os_version": "15.0"}) is True
    assert supports_ddm({"platform": "ios", "os_version": "17.4.1"}) is True
    assert supports_ddm({"platform": "ios", "os_version": "14.8"}) is False
    assert supports_ddm({"platform": "macos", "os_version": "13.0"}) is True
    assert supports_ddm({"platform": "macos", "os_version": "12.7"}) is False
    # Sin versión conocida => no arriesgamos declarations, cae a imperativo.
    assert supports_ddm({"platform": "ios", "os_version": None}) is False
    assert supports_ddm({"platform": "android", "os_version": "14"}) is False


def test_declaration_shape_matches_apple_schema():
    out = build_declarations(POLICY, "outside", URL)
    types = [d["Type"] for d in out["configurations"]]
    assert types == [
        "com.apple.configuration.legacy",
        "com.apple.configuration.management.status-subscriptions",
    ]
    assert [d["Type"] for d in out["activations"]] == ["com.apple.activation.simple"]

    for decl in out["configurations"] + out["activations"]:
        # declarationbase.yaml: las cuatro claves son required.
        assert set(decl) == {"Type", "Identifier", "ServerToken", "Payload"}
        assert len(decl["Identifier"].encode("utf-8")) <= 64
        assert len(decl["ServerToken"].encode("utf-8")) <= 64

    legacy, subs = out["configurations"]
    assert legacy["Payload"] == {"ProfileURL": URL}
    assert subs["Payload"]["StatusItems"][0] == {"Name": "device.operating-system.version"}

    # La activación referencia ambas configurations y, sin predicado, omite la clave.
    activation = out["activations"][0]
    assert activation["Payload"]["StandardConfigurations"] == [
        legacy["Identifier"], subs["Identifier"],
    ]
    assert "Predicate" not in activation["Payload"]


def test_predicate_is_passed_through_verbatim():
    out = build_declarations(POLICY, "outside", URL, predicate="@osversion >= 17")
    assert out["activations"][0]["Payload"]["Predicate"] == "@osversion >= 17"


def test_server_token_is_deterministic_and_state_scoped():
    a = build_declarations(POLICY, "outside", URL)
    b = build_declarations(POLICY, "outside", URL)
    # Idempotencia: misma policy => mismo token => el dispositivo no reaplica.
    assert a == b
    c = build_declarations(POLICY, "inside", URL)
    assert c["configurations"][0]["Identifier"] != a["configurations"][0]["Identifier"]
    d = build_declarations(POLICY, "outside", URL + "?v=2")
    assert d["configurations"][0]["ServerToken"] != a["configurations"][0]["ServerToken"]


def test_profile_url_must_be_https():
    for bad in ("http://mdm.example.com/p.mobileconfig", "", "ftp://x"):
        try:
            build_declarations(POLICY, "outside", bad)
        except ValueError:
            continue
        raise AssertionError(f"profile_url {bad!r} should be rejected")


def test_long_policy_id_identifier_stays_within_64_octets():
    out = build_declarations({"id": "x" * 200}, "outside", URL)
    for decl in out["configurations"] + out["activations"]:
        assert len(decl["Identifier"].encode("utf-8")) <= 64


def test_status_subscriptions_accept_custom_items():
    decl = build_status_subscriptions(["passcode.is-compliant"])
    assert decl["Payload"] == {"StatusItems": [{"Name": "passcode.is-compliant"}]}


def test_parse_status_report_flat_and_nested():
    flat = parse_status_report({
        "StatusItems": {
            "device.operating-system.version": "17.4.1",
            "device.model.identifier": "iPhone15,2",
            "unknown.item": "ignored",
        },
        "Errors": [],
    })
    assert flat == {"os_version": "17.4.1", "model": "iPhone15,2"}

    nested = parse_status_report({
        "StatusItems": {"device": {"operating-system": {"version": "17.4.1"}}},
        "Errors": [{"StatusItem": "passcode.is-compliant"}],
    })
    assert nested == {"os_version": "17.4.1", "ddm_errors": ["passcode.is-compliant"]}


def test_parse_status_report_tolerates_garbage():
    assert parse_status_report(None) == {}
    assert parse_status_report({}) == {}
    assert parse_status_report({"StatusItems": "not-a-dict"}) == {}


def test_adapter_capability_flag_defaults_off():
    assert MDMAdapter.supports_ddm is False
    assert JamfAdapter.supports_ddm is True


def test_jamf_apply_ddm_builds_declarations_without_network():
    adapter = JamfAdapter()
    device = {"device_id": "dev-003", "platform": "ios",
              "os_version": "17.4.1", "fence_state": "outside"}
    res = adapter.execute(device, "apply_ddm", {"policy": POLICY, "profile_url": URL})
    assert res["ok"] is True
    assert res["declarations"]["activations"][0]["Type"] == "com.apple.activation.simple"


def test_jamf_apply_ddm_falls_back_when_device_too_old():
    adapter = JamfAdapter()
    device = {"device_id": "dev-009", "platform": "ios", "os_version": "14.8"}
    res = adapter.execute(device, "apply_ddm", {"policy": POLICY, "profile_url": URL})
    assert res["ok"] is False
    assert res["fallback"] == "imperative"


def test_jamf_apply_ddm_never_raises_on_bad_input():
    adapter = JamfAdapter()
    device = {"device_id": "dev-003", "platform": "ios", "os_version": "17.4.1"}
    assert adapter.execute(device, "apply_ddm", {})["ok"] is False
    bad = adapter.execute(device, "apply_ddm", {"policy": POLICY, "profile_url": "http://x"})
    assert bad["ok"] is False and bad["error_type"] == "invalid_profile_url"


def test_imperative_path_untouched():
    """Regresión: acciones de siempre siguen resolviéndose por el mock."""
    adapter = JamfAdapter()
    res = adapter.execute({"device_id": "dev-003"}, "lock", {})
    assert res["adapter"] == "jamf"
    assert "declarations" not in res


# --- Fase 2: canal de entrega/readback de Jamf Pro (endpoints verificados) ---

class _Resp:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body
        self.text = ""

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def _live_adapter():
    a = JamfAdapter(live=True, base_url="https://acme.jamfcloud.com",
                    client_id="c", client_secret="s")
    a._token = "stub"
    a._token_expires_at = float("inf")
    return a


DDM_DEVICE = {"device_id": "dev-003", "management_id": "mgmt-42",
              "platform": "ios", "os_version": "17.4.1"}


def _with_fake(method: str, resp, fn):
    """Sustituye requests.get/post por un doble que devuelve `resp`."""
    import requests
    captured = {}

    def fake(url, **kwargs):
        captured["url"] = url
        return resp

    original = getattr(requests, method)
    setattr(requests, method, fake)
    try:
        return fn(), captured
    finally:
        setattr(requests, method, original)


def test_ddm_status_and_sync_urls_match_verified_endpoints():
    a = _live_adapter()
    status = a.execute(DDM_DEVICE, "ddm_status", {}, dry_run=True)
    sync = a.execute(DDM_DEVICE, "ddm_sync", {}, dry_run=True)
    assert status["would_send"] == {
        "method": "GET",
        "url": "https://acme.jamfcloud.com/api/v1/ddm/mgmt-42/status-items",
    }
    assert sync["would_send"] == {
        "method": "POST",
        "url": "https://acme.jamfcloud.com/api/v1/ddm/mgmt-42/sync",
    }


def test_ddm_status_feeds_device_state_from_status_items():
    body = {"statusItems": [
        {"key": "device.operating-system.version", "value": "17.4.1"},
        {"key": "device.model.identifier", "value": "iPhone15,2"},
        # Jamf serializa los booleanos como string: no debe llegar "true" al
        # modelo de estado, que espera bool.
        {"key": "passcode.is-compliant", "value": "true"},
        {"key": "unknown.thing", "value": "ignored"},
    ]}
    res, captured = _with_fake(
        "get", _Resp(200, body),
        lambda: _live_adapter().execute(DDM_DEVICE, "ddm_status", {}),
    )
    assert res["ok"] is True and res["status_items"] == 4
    assert res["device_state"] == {"os_version": "17.4.1", "model": "iPhone15,2",
                                   "passcode_compliant": True}
    assert captured["url"].endswith("/api/v1/ddm/mgmt-42/status-items")


def test_ddm_sync_accepts_204_without_body():
    res, _ = _with_fake(
        "post", _Resp(204),
        lambda: _live_adapter().execute(DDM_DEVICE, "ddm_sync", {}),
    )
    assert res["ok"] is True and res["jamf_status"] == 204


def test_ddm_requires_management_id_and_never_raises():
    res = _live_adapter().execute({"device_id": "dev-003"}, "ddm_status", {})
    assert res["ok"] is False and res["error_type"] == "missing_management_id"


def test_ddm_unknown_client_returns_structured_error():
    res, _ = _with_fake(
        "get", _Resp(404),
        lambda: _live_adapter().execute(DDM_DEVICE, "ddm_status", {}),
    )
    assert res["ok"] is False and res["error_type"] == "device_not_found"


def test_engine_accepts_ddm_actions_from_an_operator():
    """Regresión: sin las DDM en VALID_ACTIONS el engine y la API las
    rechazaban con 'accion no valida' y la capa declarativa era inalcanzable.
    """
    from helpers import make_temp_engine  # noqa: E402
    from lucidfence.core.state_store import DeviceState  # noqa: E402

    engine = make_temp_engine()
    device = DeviceState(device_id="dev-ddm", name="iPad HQ", platform="ios",
                         os_version="17.4.1", fence_state="outside")
    res = engine.run_command(device, "apply_ddm", {"policy": POLICY, "profile_url": URL})
    assert res.get("error") != "accion no valida"


# --- Issue #70: el readback de ddm_status se persiste en el DeviceState ---

class _ReadbackStub:
    """Adapter mínimo: devuelve lo que le digas, sin red."""

    def __init__(self, result):
        self.result = result

    def execute(self, device, action, params, dry_run=False):
        return dict(self.result)


def _engine_with_prior_state():
    from helpers import make_temp_engine  # noqa: E402
    from lucidfence.core.state_store import DeviceState  # noqa: E402

    engine = make_temp_engine()
    engine.dry_run = False
    prior = DeviceState(device_id="dev-ddm", name="iPad HQ", platform="ios",
                        os_version="17.3", serial_number="C02XYZ",
                        fence_state="outside")
    engine.store.upsert(prior)
    return engine, prior


def test_run_command_persists_ddm_readback_merge_not_replace():
    engine, prior = _engine_with_prior_state()
    engine.adapter = _ReadbackStub({
        "adapter": "jamf", "ok": True, "action": "ddm_status",
        "device_id": "dev-ddm",
        "device_state": {
            "os_version": "17.4.1",
            "passcode_compliant": True,
            "filevault_enabled": None,          # null del reporte: no pisa
            "model_marketing_name": "iPad Pro",  # sin campo en DeviceState: se ignora
            "ddm_errors": ["passcode"],          # visible en el action log, no en el estado
        },
    })
    res = engine.run_command(prior, "ddm_status", {})
    assert res["ok"] is True

    saved = engine.store.get("dev-ddm")
    assert saved.os_version == "17.4.1"       # actualizado por el readback
    assert saved.passcode_compliant is True   # campo nuevo persistido
    assert saved.filevault_enabled is None    # None no pisa
    assert saved.serial_number == "C02XYZ"    # ausente en el readback: intacto
    # ddm_errors no se descarta en silencio: queda en el action log.
    assert engine.store.recent_actions()[-1]["device_state"]["ddm_errors"] == ["passcode"]


def test_run_command_failed_or_dry_run_ddm_status_leaves_state_untouched():
    engine, prior = _engine_with_prior_state()
    engine.adapter = _ReadbackStub({
        "adapter": "jamf", "ok": False, "error_type": "device_not_found",
        "action": "ddm_status", "device_id": "dev-ddm",
        "device_state": {"os_version": "99.9"},
    })
    engine.run_command(prior, "ddm_status", {})
    assert engine.store.get("dev-ddm").os_version == "17.3"

    engine.dry_run = True
    engine.adapter = _ReadbackStub({
        "adapter": "jamf", "ok": True, "action": "ddm_status",
        "device_id": "dev-ddm", "device_state": {"os_version": "99.9"},
    })
    engine.run_command(prior, "ddm_status", {})
    assert engine.store.get("dev-ddm").os_version == "17.3"
