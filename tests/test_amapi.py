"""Android AMAPI: generación del documento de política y readback de compliance.

Fixtures golden contra la referencia REST oficial de Android Management API
(verificada 2026-08-02): campos de `Policy`, enums, `PolicyEnforcementRule` y
`NonComplianceDetail`. Sin red, sin proyecto de Google, sin credenciales.

Los tests que fijan una invariante citan la frase de la doc que la obliga, para
que un cambio de la API se note aquí y no en producción.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lucidfence.core.amapi import (  # noqa: E402
    BLOCK_SCOPES,
    COMPANY_OWNED,
    DEVICE_OWNER,
    INSTALL_TYPES,
    PERSONALLY_OWNED,
    PROFILE_OWNER,
    build_enforcement_rules,
    build_fence_patch,
    build_policy_patch,
    management_mode_of,
    ownership_of,
    parse_device_compliance,
    supports_amapi,
)
from lucidfence.core.adapters import VALID_ACTIONS  # noqa: E402
from lucidfence.core.adapters.applivery import AppliveryAdapter  # noqa: E402
from lucidfence.core.adapters.base import MDMAdapter  # noqa: E402
from lucidfence.core.state_store import DeviceState  # noqa: E402


def _raises(fn, *args, **kwargs):
    """Devuelve el mensaje del ValueError esperado, o falla."""
    try:
        fn(*args, **kwargs)
    except ValueError as exc:
        return str(exc)
    raise AssertionError("se esperaba ValueError")


# --------------------------------------------------------------------------
# Gate de capacidad
# --------------------------------------------------------------------------
def test_supports_amapi_gates_by_platform_and_management_mode():
    assert supports_amapi({"platform": "Android 14", "management_mode": "device_owner"}) is True
    assert supports_amapi({"platform": "android", "management_mode": PROFILE_OWNER}) is True
    assert supports_amapi({"platform": "ios", "management_mode": DEVICE_OWNER}) is False
    # Sin modo no sabemos el alcance real de las restricciones (la mitad son
    # mode-scoped): preferimos caer al camino imperativo.
    assert supports_amapi({"platform": "android"}) is False


def test_unknown_management_mode_and_ownership_normalise_to_empty():
    # MANAGEMENT_MODE_UNSPECIFIED está "disallowed" en la referencia.
    assert management_mode_of({"management_mode": "MANAGEMENT_MODE_UNSPECIFIED"}) == ""
    assert ownership_of({"ownership": "nonsense"}) == ""
    assert ownership_of({"ownership": "company_owned"}) == COMPANY_OWNED


def test_camel_case_keys_from_amapi_payloads_are_accepted():
    assert management_mode_of({"managementMode": "PROFILE_OWNER"}) == PROFILE_OWNER


# --------------------------------------------------------------------------
# Forma del parche
# --------------------------------------------------------------------------
def test_modern_fields_are_emitted_not_deprecated_ones():
    # La referencia marca `cameraDisabled` y `wifiConfigsLockdownEnabled` como
    # deprecated; los sustitutos son `cameraAccess` y
    # `deviceConnectivityManagement.configureWifi`.
    out = build_policy_patch({"camera": "block", "wifi_config": "block"},
                             management_mode=DEVICE_OWNER)
    assert out["patch"]["cameraAccess"] == "CAMERA_ACCESS_DISABLED"
    assert out["patch"]["deviceConnectivityManagement"] == {
        "configureWifi": "DISALLOW_CONFIGURING_WIFI"}
    assert "cameraDisabled" not in out["patch"]
    assert "wifiConfigsLockdownEnabled" not in out["patch"]


def test_update_mask_covers_every_top_level_field():
    # "The field mask indicating the fields to update. If not set, all
    # modifiable fields will be modified." -> sin máscara, un parche parcial
    # borraría el resto de la política del tenant.
    out = build_policy_patch({"camera": "block", "location": "enforced", "kiosk": True},
                             management_mode=DEVICE_OWNER)
    assert out["update_mask"] == "cameraAccess,kioskCustomLauncherEnabled,locationMode"
    assert set(out["update_mask"].split(",")) == set(out["patch"])


def test_empty_restrictions_produce_empty_patch_and_mask():
    out = build_policy_patch({}, management_mode=DEVICE_OWNER)
    assert out["patch"] == {} and out["update_mask"] == ""


def test_patch_is_deterministic():
    # Reaplicar el mismo parche no debe incrementar `Policy.version`.
    args = {"applications": [{"package": "com.b"}, {"package": "com.a"}], "camera": "block"}
    first = build_policy_patch(args, management_mode=DEVICE_OWNER)
    second = build_policy_patch(args, management_mode=DEVICE_OWNER)
    assert first == second
    assert [a["packageName"] for a in first["patch"]["applications"]] == ["com.a", "com.b"]


def test_applications_accept_plain_package_names():
    out = build_policy_patch({"applications": ["com.example.app"]},
                             management_mode=DEVICE_OWNER)
    assert out["patch"]["applications"] == [
        {"packageName": "com.example.app", "installType": "FORCE_INSTALLED"}]


def test_enum_literals_are_accepted_verbatim():
    out = build_policy_patch({"location": "LOCATION_DISABLED"}, management_mode=DEVICE_OWNER)
    assert out["patch"]["locationMode"] == "LOCATION_DISABLED"


# --------------------------------------------------------------------------
# Validación
# --------------------------------------------------------------------------
def test_unknown_restriction_key_raises():
    # Un typo que silenciosamente no aplica una restricción de seguridad es peor
    # que un error: falla ruidoso.
    assert "camrea" in _raises(build_policy_patch, {"camrea": "block"},
                               management_mode=DEVICE_OWNER)


def test_value_outside_enum_raises():
    _raises(build_policy_patch, {"camera": "off"}, management_mode=DEVICE_OWNER)


def test_unknown_management_mode_raises():
    _raises(build_policy_patch, {"camera": "block"}, management_mode="ADMIN")


def test_invalid_install_type_raises():
    _raises(build_policy_patch,
            {"applications": [{"package": "com.x", "install_type": "MANDATORY"}]},
            management_mode=DEVICE_OWNER)


def test_application_without_package_raises():
    _raises(build_policy_patch, {"applications": [{"install_type": "BLOCKED"}]},
            management_mode=DEVICE_OWNER)


def test_declared_enums_match_the_reference():
    assert INSTALL_TYPES == {
        "INSTALL_TYPE_UNSPECIFIED", "PREINSTALLED", "FORCE_INSTALLED", "BLOCKED",
        "AVAILABLE", "REQUIRED_FOR_SETUP", "KIOSK"}
    assert BLOCK_SCOPES == {
        "BLOCK_SCOPE_UNSPECIFIED", "BLOCK_SCOPE_WORK_PROFILE", "BLOCK_SCOPE_DEVICE"}


# --------------------------------------------------------------------------
# Matriz de modos de gestión
# --------------------------------------------------------------------------
def test_kiosk_is_skipped_on_work_profile():
    # El modo kiosco es el solution set de dispositivo dedicado (totalmente
    # gestionado).
    out = build_policy_patch({"kiosk": True}, management_mode=PROFILE_OWNER)
    assert "kioskCustomLauncherEnabled" not in out["patch"]
    assert out["skipped"][0]["setting"] == "kioskCustomLauncherEnabled"


def test_wifi_lockdown_skipped_on_byod():
    # "Supported on fully managed devices and work profile on company-owned
    # devices" -> BYOD (PROFILE_OWNER + PERSONALLY_OWNED) queda fuera.
    out = build_policy_patch({"wifi_config": "block"}, management_mode=PROFILE_OWNER,
                             ownership=PERSONALLY_OWNED)
    assert out["patch"] == {}
    assert "company-owned" in out["skipped"][0]["reason"]


def test_wifi_lockdown_applies_on_cope():
    out = build_policy_patch({"wifi_config": "no_new_networks"},
                             management_mode=PROFILE_OWNER, ownership=COMPANY_OWNED)
    assert out["patch"]["deviceConnectivityManagement"] == {
        "configureWifi": "DISALLOW_ADD_WIFI_CONFIG"}
    assert out["skipped"] == []


def test_permissive_wifi_needs_no_company_ownership():
    # Permitir configurar Wi-Fi no restringe nada: no exige company-owned.
    out = build_policy_patch({"wifi_config": "allow"}, management_mode=PROFILE_OWNER,
                             ownership=PERSONALLY_OWNED)
    assert out["patch"]["deviceConnectivityManagement"] == {
        "configureWifi": "ALLOW_CONFIGURING_WIFI"}


def test_skipped_settings_are_absent_from_update_mask():
    out = build_policy_patch({"kiosk": True, "camera": "block"},
                             management_mode=PROFILE_OWNER)
    assert out["update_mask"] == "cameraAccess"


# --------------------------------------------------------------------------
# Enforcement graduado
# --------------------------------------------------------------------------
def test_block_and_wipe_must_come_as_a_pair():
    # "Note: wipeAction must also be specified" / "Note: blockAction must also
    # be specified".
    msg = _raises(build_enforcement_rules,
                  [{"setting_name": "applications", "block_after_days": 3}])
    assert "juntas" in msg


def test_block_must_precede_wipe():
    # "blockAfterDays must be less than wipeAfterDays".
    _raises(build_enforcement_rules,
            [{"setting_name": "applications", "block_after_days": 10, "wipe_after_days": 5}])
    _raises(build_enforcement_rules,
            [{"setting_name": "applications", "block_after_days": 5, "wipe_after_days": 5}])


def test_missing_setting_name_raises():
    _raises(build_enforcement_rules, [{"block_after_days": 1, "wipe_after_days": 2}])


def test_immediate_block_is_allowed():
    # "To block access immediately, set to 0."
    rules = build_enforcement_rules(
        [{"setting_name": "applications", "block_after_days": 0, "wipe_after_days": 7}])
    assert rules[0]["blockAction"]["blockAfterDays"] == 0


def test_graduated_rule_shape():
    rules = build_enforcement_rules([{
        "setting_name": "applications", "block_after_days": 2, "wipe_after_days": 9,
        "block_scope": "BLOCK_SCOPE_DEVICE", "preserve_frp": True}])
    assert rules == [{
        "settingName": "applications",
        "blockAction": {"blockAfterDays": 2, "blockScope": "BLOCK_SCOPE_DEVICE"},
        "wipeAction": {"wipeAfterDays": 9, "preserveFrp": True}}]


def test_invalid_block_scope_raises():
    _raises(build_enforcement_rules, [{
        "setting_name": "applications", "block_after_days": 1, "wipe_after_days": 2,
        "block_scope": "BLOCK_SCOPE_USER"}])


def test_enforcement_lands_in_patch_and_mask():
    out = build_policy_patch({"camera": "block"}, management_mode=DEVICE_OWNER,
                             enforcement=[{"setting_name": "cameraAccess",
                                           "block_after_days": 1, "wipe_after_days": 4}])
    assert "policyEnforcementRules" in out["patch"]
    assert out["update_mask"] == "cameraAccess,policyEnforcementRules"


# --------------------------------------------------------------------------
# Selección por estado de geocerca
# --------------------------------------------------------------------------
FENCE_POLICY = {
    "id": "pol-warehouse",
    "actions": [
        {"action": "notify", "params": {"msg": "irrelevante"}},
        {"action": "apply_amapi_policy", "when": "on_exit",
         "params": {"restrictions": {"camera": "block", "location": "enforced"}}},
    ],
}
MANAGED_DEVICE = {"device_id": "d1", "name": "tablet", "platform": "android",
                  "management_mode": DEVICE_OWNER, "ownership": COMPANY_OWNED,
                  "fence_state": "outside"}


def test_outside_selects_the_on_exit_action():
    out = build_fence_patch(FENCE_POLICY, "outside", MANAGED_DEVICE)
    assert out["patch"]["cameraAccess"] == "CAMERA_ACCESS_DISABLED"
    assert out["patch"]["locationMode"] == "LOCATION_ENFORCED"


def test_states_without_a_matching_action_are_explicit_noops():
    # La policy no declara restricciones al entrar ni en estado desconocido.
    assert build_fence_patch(FENCE_POLICY, "inside", MANAGED_DEVICE)["patch"] == {}
    assert build_fence_patch(FENCE_POLICY, "", MANAGED_DEVICE)["patch"] == {}
    assert build_fence_patch({"id": "p", "actions": []}, "outside",
                             MANAGED_DEVICE)["patch"] == {}


def test_byod_device_gets_the_mode_scoped_subset():
    policy = {"id": "p", "actions": [{
        "action": "apply_amapi_policy", "when": "on_exit",
        "params": {"restrictions": {"camera": "block", "kiosk": True}}}]}
    device = {"platform": "android", "management_mode": PROFILE_OWNER,
              "ownership": PERSONALLY_OWNED}
    out = build_fence_patch(policy, "outside", device)
    assert list(out["patch"]) == ["cameraAccess"]
    assert len(out["skipped"]) == 1


# --------------------------------------------------------------------------
# Readback de compliance
# --------------------------------------------------------------------------
def test_compliant_device_readback():
    assert parse_device_compliance({"policyCompliant": True, "nonComplianceDetails": []}) == {
        "amapi_policy_compliant": True, "amapi_non_compliance": []}


def test_non_compliance_details_are_summarised():
    out = parse_device_compliance({
        "policyCompliant": False,
        "nonComplianceDetails": [{
            "settingName": "applications",
            "nonComplianceReason": "APP_NOT_INSTALLED",
            "packageName": "com.example.app",
            "fieldPath": "applications[0].packageName",
            "currentValue": {"ignorado": True}}]})
    assert out["amapi_policy_compliant"] is False
    assert out["amapi_non_compliance"] == [{
        "settingName": "applications", "nonComplianceReason": "APP_NOT_INSTALLED",
        "packageName": "com.example.app", "fieldPath": "applications[0].packageName"}]


def test_partial_report_omits_absent_keys():
    # El merge del engine ignora ausentes: un reporte parcial no debe inventar
    # `amapi_policy_compliant` y pisar el estado previo (issue #70).
    assert parse_device_compliance({"appliedPolicyVersion": "7"}) == {
        "amapi_applied_policy_version": "7"}


def test_garbage_readback_input_is_ignored():
    assert parse_device_compliance(None) == {}
    assert parse_device_compliance("not-a-device") == {}


def test_malformed_detail_entries_are_dropped():
    out = parse_device_compliance({
        "policyCompliant": False,
        "nonComplianceDetails": ["nonsense", {}, {"settingName": "locationMode"}]})
    assert out["amapi_non_compliance"] == [{"settingName": "locationMode"}]


# --------------------------------------------------------------------------
# Cableado con el producto
#
# En la fase 1 de DDM las acciones existían pero no estaban en VALID_ACTIONS, así
# que el engine y el endpoint de comandos las rechazaban con "accion no valida":
# la capa declarativa era inalcanzable. Estos tests evitan repetir ese fallo.
# --------------------------------------------------------------------------
def _adapter():
    return AppliveryAdapter(org_id="org", endpoint_template="", api_key="unused")


def test_action_is_accepted_by_the_engine_gate():
    assert "apply_amapi_policy" in VALID_ACTIONS


def test_capability_flag_defaults_to_false_and_applivery_declares_it():
    # Gestionar Android Enterprise no implica exponer el documento de política.
    assert MDMAdapter.supports_amapi_policy is False
    assert _adapter().supports_amapi_policy is True


def test_generation_needs_no_credentials_or_network():
    res = _adapter().execute(MANAGED_DEVICE, "apply_amapi_policy", {"policy": FENCE_POLICY})
    assert res["ok"] is True
    assert res["patch"] == {"cameraAccess": "CAMERA_ACCESS_DISABLED",
                            "locationMode": "LOCATION_ENFORCED"}
    assert res["delivery"] == "offline"


def test_non_android_device_falls_back_to_imperative():
    res = _adapter().execute({"device_id": "d2", "platform": "ios"},
                             "apply_amapi_policy", {"policy": FENCE_POLICY})
    assert res["ok"] is False and res["fallback"] == "imperative"


def test_adapter_reports_errors_instead_of_raising():
    # Contrato de MDMAdapter: nunca lanza, el dashboard no debe 500ear.
    missing = _adapter().execute(MANAGED_DEVICE, "apply_amapi_policy", {})
    assert missing["ok"] is False and missing["error"] == "missing_parameter"
    bad = {"id": "p", "actions": [{"action": "apply_amapi_policy", "when": "on_exit",
                                   "params": {"restrictions": {"camera": "nope"}}}]}
    invalid = _adapter().execute(MANAGED_DEVICE, "apply_amapi_policy", {"policy": bad})
    assert invalid["ok"] is False and invalid["error"] == "invalid_restrictions"


def test_readback_rides_the_shared_device_state_channel():
    res = _adapter().execute(MANAGED_DEVICE, "apply_amapi_policy", {
        "policy": FENCE_POLICY,
        "device_resource": {"policyCompliant": False, "nonComplianceDetails": []}})
    assert res["device_state"]["amapi_policy_compliant"] is False


def test_readback_fields_exist_on_device_state():
    # El merge del engine descarta claves sin campo en DeviceState.
    state = DeviceState(device_id="d1", name="n", platform="android")
    for field in ("amapi_policy_compliant", "amapi_non_compliance",
                  "amapi_applied_policy_version"):
        assert hasattr(state, field), field


# --------------------------------------------------------------------------
# Regresiones de la revisión de código (2026-08-02). Cada una reproduce un
# fallo real que la primera versión tenía; sin ellas, la capa parecía
# funcionar en los tests y no funcionaba con un dispositivo de verdad.
# --------------------------------------------------------------------------
def test_a_real_device_state_can_pass_the_capability_gate():
    # REGRESIÓN: `supports_amapi` lee `management_mode`/`ownership`, pero
    # `DeviceState` no los tenía, así que TODO dispositivo real caía al camino
    # imperativo y la capa declarativa era inalcanzable en producción.
    state = DeviceState(device_id="d1", name="tablet", platform="android")
    assert hasattr(state, "management_mode") and hasattr(state, "ownership")
    assert supports_amapi(state) is False        # sin modo: fallback correcto
    state.management_mode = DEVICE_OWNER
    state.ownership = COMPANY_OWNED
    assert supports_amapi(state) is True


def test_adapter_accepts_the_params_shape_the_engine_emits():
    # REGRESIÓN: el engine pasa `act["params"]` tal cual, así que el adapter
    # nunca recibía `params["policy"]` y el ejemplo documentado devolvía
    # "missing_parameter".
    state = DeviceState(device_id="d1", name="tablet", platform="android")
    state.management_mode = DEVICE_OWNER
    state.ownership = COMPANY_OWNED
    state.fence_state = "outside"
    res = _adapter().execute(state, "apply_amapi_policy",
                             {"restrictions": {"camera": "block"}})
    assert res["ok"] is True
    assert res["patch"] == {"cameraAccess": "CAMERA_ACCESS_DISABLED"}


def test_fence_action_objects_are_not_silently_dropped():
    # REGRESIÓN: `Fence.from_raw` produce `ActionSpec` (dataclass), no dicts.
    # Exigir `isinstance(act, dict)` descartaba la acción y devolvía un parche
    # vacío con ok=True: una restricción de seguridad perdida sin aviso.
    from lucidfence.core.fences import Fence
    fence = Fence.from_raw({
        "id": "f1", "name": "almacen", "type": "circle",
        "center": {"lat": 40.4, "lng": -3.7}, "radius_m": 100,
        "actions": [{"action": "apply_amapi_policy", "when": "on_exit",
                     "params": {"restrictions": {"camera": "block"}}}],
    })
    out = build_fence_patch(fence, "outside", MANAGED_DEVICE)
    assert out["patch"] == {"cameraAccess": "CAMERA_ACCESS_DISABLED"}


def test_missing_when_means_on_enter_not_every_state():
    # REGRESIÓN: tratar `when` ausente como comodín desbloqueaba la cámara
    # FUERA de la geocerca en una policy que solo la permitía dentro.
    # `ActionSpec.when` y `Engine._fire_actions` usan on_enter.
    policy = {"id": "p", "actions": [{
        "action": "apply_amapi_policy",
        "params": {"restrictions": {"camera": "user_choice"}}}]}
    assert build_fence_patch(policy, "inside", MANAGED_DEVICE)["patch"] == {
        "cameraAccess": "CAMERA_ACCESS_USER_CHOICE"}
    assert build_fence_patch(policy, "outside", MANAGED_DEVICE)["patch"] == {}
    assert build_fence_patch(policy, "unknown", MANAGED_DEVICE)["patch"] == {}


def test_conflicting_install_type_for_the_same_package_raises():
    # REGRESIÓN: al fusionar una lista base con un bloqueo por geocerca se
    # emitían dos entradas del mismo paquete y el BLOCKED no se aplicaba.
    msg = _raises(build_policy_patch,
                  {"applications": [{"package": "com.whatsapp"},
                                    {"package": "com.whatsapp", "install_type": "BLOCKED"}]},
                  management_mode=DEVICE_OWNER)
    assert "conflicto" in msg
    # Repetir el MISMO installType no es conflicto: se deduplica.
    out = build_policy_patch({"applications": ["com.a", "com.a"]},
                             management_mode=DEVICE_OWNER)
    assert out["patch"]["applications"] == [
        {"packageName": "com.a", "installType": "FORCE_INSTALLED"}]


def test_enforcement_respects_the_ownership_matrix():
    # REGRESIÓN: `blockScope` ("Only applicable to devices that are
    # company-owned") y `preserveFrp` ("doesn't apply to work profiles") se
    # emitían en BYOD con `skipped` vacío, justo lo que el módulo promete no
    # hacer.
    rule = {"setting_name": "applications", "block_after_days": 1,
            "wipe_after_days": 3, "block_scope": "BLOCK_SCOPE_DEVICE",
            "preserve_frp": True}
    byod = build_policy_patch({}, management_mode=PROFILE_OWNER,
                              ownership=PERSONALLY_OWNED, enforcement=[rule])
    emitted = byod["patch"]["policyEnforcementRules"][0]
    assert "blockScope" not in emitted["blockAction"]
    assert "preserveFrp" not in emitted["wipeAction"]
    # Los plazos, que sí aplican en cualquier modo, se mantienen.
    assert emitted["blockAction"]["blockAfterDays"] == 1
    cope = build_policy_patch({}, management_mode=PROFILE_OWNER,
                              ownership=COMPANY_OWNED, enforcement=[rule])
    assert cope["patch"]["policyEnforcementRules"][0]["blockAction"]["blockScope"] == \
        "BLOCK_SCOPE_DEVICE"


def test_negative_deadlines_are_rejected():
    _raises(build_enforcement_rules,
            [{"setting_name": "applications", "block_after_days": -1,
              "wipe_after_days": 3}])


def test_preserve_frp_false_is_emitted_not_dropped():
    rules = build_enforcement_rules([{
        "setting_name": "applications", "block_after_days": 1,
        "wipe_after_days": 2, "preserve_frp": False}])
    assert rules[0]["wipeAction"]["preserveFrp"] is False


def test_empty_enforcement_list_is_an_explicit_empty_ruleset():
    # Distinto de "sin enforcement": borra las reglas anteriores a propósito.
    out = build_policy_patch({}, management_mode=DEVICE_OWNER, enforcement=[])
    assert out["patch"]["policyEnforcementRules"] == []
    assert out["update_mask"] == "policyEnforcementRules"
    assert build_policy_patch({}, management_mode=DEVICE_OWNER)["patch"] == {}
