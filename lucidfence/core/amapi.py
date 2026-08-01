"""Android Management API (AMAPI) — enforcement declarativo de geocercas.

AMAPI es declarativo por diseño: el servidor publica un documento `Policy` con
el estado deseado y Android Device Policy converge en el dispositivo. LucidFence
emite el parche de política que corresponde al estado de geocerca actual, en vez
de disparar comandos imperativos en bucle.

LÍMITE HONESTO — AMAPI no tiene primitiva de geocerca. El trigger sigue siendo
el engine/adapters de LucidFence: nosotros decidimos QUÉ parche aplicar en cada
transición. AMAPI es la capa de configuración/enforcement, no de detección.
Mismo límite que Apple DDM (`ddm.py`) y Windows DSC (`dsc.py`).

Las claves y los enums salen de la referencia REST oficial (verificada
2026-08-02, `developers.google.com/android/management/reference/rest/v1`):

- `enterprises.policies`  → campos de `Policy`, enums y `PolicyEnforcementRule`
- `enterprises.devices`   → `policyCompliant` y `NonComplianceDetail` (readback)
- `ManagementMode` / `Ownership` → alcance por modo de gestión

NO usamos campos deprecados. En concreto, la referencia marca `cameraDisabled` y
`wifiConfigsLockdownEnabled` como deprecated; sus sustitutos actuales son
`cameraAccess` y `deviceConnectivityManagement.configureWifi`.
"""
from __future__ import annotations

from typing import Any, Optional

#: Modos de gestión de AMAPI (`ManagementMode`). MANAGEMENT_MODE_UNSPECIFIED
#: está "disallowed" en la referencia, así que no es un modo operable.
DEVICE_OWNER = "DEVICE_OWNER"      # totalmente gestionado (COBO / dedicado)
PROFILE_OWNER = "PROFILE_OWNER"    # perfil de trabajo (BYOD / COPE)
MANAGEMENT_MODES = (DEVICE_OWNER, PROFILE_OWNER)

#: Propiedad del dispositivo (`Ownership`). Distingue COPE de BYOD: ambos son
#: PROFILE_OWNER, pero varias restricciones solo aplican a company-owned.
COMPANY_OWNED = "COMPANY_OWNED"
PERSONALLY_OWNED = "PERSONALLY_OWNED"

#: Vocabulario estable de LucidFence -> enum de AMAPI. Es una capa
#: anticorrupción a propósito: la geocerca habla en términos de producto y aquí
#: se traduce a la única sintaxis que Google acepta. Un valor fuera del
#: vocabulario es error de configuración, no algo que se pasa tal cual.
CAMERA_ACCESS = {
    "user_choice": "CAMERA_ACCESS_USER_CHOICE",
    "block": "CAMERA_ACCESS_DISABLED",
    "enforce": "CAMERA_ACCESS_ENFORCED",
}
LOCATION_MODE = {
    "user_choice": "LOCATION_USER_CHOICE",
    "enforced": "LOCATION_ENFORCED",
    "disabled": "LOCATION_DISABLED",
}
CONFIGURE_WIFI = {
    "allow": "ALLOW_CONFIGURING_WIFI",
    "no_new_networks": "DISALLOW_ADD_WIFI_CONFIG",
    "block": "DISALLOW_CONFIGURING_WIFI",
}

#: `InstallType` de `ApplicationPolicy`, verbatim de la referencia.
INSTALL_TYPES = frozenset({
    "INSTALL_TYPE_UNSPECIFIED",
    "PREINSTALLED",
    "FORCE_INSTALLED",
    "BLOCKED",
    "AVAILABLE",
    "REQUIRED_FOR_SETUP",
    "KIOSK",
})

#: `BlockScope` de `BlockAction`. Solo aplica a dispositivos company-owned.
BLOCK_SCOPES = frozenset({
    "BLOCK_SCOPE_UNSPECIFIED",
    "BLOCK_SCOPE_WORK_PROFILE",
    "BLOCK_SCOPE_DEVICE",
})

#: Alcance por modo de cada restricción que emitimos. La clave es el campo
#: top-level de `Policy`. Todas las filas salen de una frase literal de la
#: referencia salvo `kioskCustomLauncherEnabled`, que va marcada como inferida.
#:
#: - `cameraAccess`: soportado en ambos modos. En perfil de trabajo solo afecta
#:   a las apps del perfil ("applies device-wide on fully managed devices and
#:   only within the work profile on devices with a work profile").
#: - `locationMode`: "on work profile and fully managed devices" -> ambos.
#: - `applications`: ambos modos.
#: - `kioskCustomLauncherEnabled`: INFERIDO, no citado. La referencia describe el
#:   campo sin acotar el modo; lo restringimos a fully managed porque el modo
#:   kiosco es el solution set de dispositivo dedicado, que se aprovisiona como
#:   totalmente gestionado. Si Google lo documenta en perfil de trabajo, se
#:   amplía aquí y cae `test_kiosk_is_skipped_on_work_profile`.
#: - `deviceConnectivityManagement`: los valores restrictivos de `configureWifi`
#:   están soportados "on fully managed devices and work profile on
#:   company-owned devices" -> excluye BYOD (PROFILE_OWNER + PERSONALLY_OWNED).
_SETTING_SCOPE = {
    "cameraAccess": (DEVICE_OWNER, PROFILE_OWNER),
    "locationMode": (DEVICE_OWNER, PROFILE_OWNER),
    "applications": (DEVICE_OWNER, PROFILE_OWNER),
    "kioskCustomLauncherEnabled": (DEVICE_OWNER,),
    "deviceConnectivityManagement": (DEVICE_OWNER, PROFILE_OWNER),
}

#: Restricciones que además exigen dispositivo company-owned cuando el modo es
#: PROFILE_OWNER (es decir: COPE sí, BYOD no).
_COMPANY_OWNED_ONLY = frozenset({"deviceConnectivityManagement"})

#: `configureWifi` en su valor permisivo no restringe nada, así que no exige
#: company-owned. Solo los valores de bloqueo lo hacen.
_WIFI_PERMISSIVE = "ALLOW_CONFIGURING_WIFI"


def _get(obj: Any, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _norm(value: Any) -> str:
    return str(value or "").strip()


def supports_amapi(device: Any) -> bool:
    """True si el dispositivo es Android con un modo de gestión AMAPI conocido.

    Sin `management_mode` devuelve False: preferimos caer al camino imperativo
    antes que emitir un parche cuyo alcance real no podemos determinar (la mitad
    de las restricciones son mode-scoped).
    """
    platform = _norm(_get(device, "platform")).lower()
    if "android" not in platform:
        return False
    return management_mode_of(device) in MANAGEMENT_MODES


def management_mode_of(device: Any) -> str:
    """Modo de gestión normalizado del dispositivo, o "" si no se conoce."""
    mode = _norm(
        _get(device, "management_mode") or _get(device, "managementMode")
    ).upper()
    return mode if mode in MANAGEMENT_MODES else ""


def ownership_of(device: Any) -> str:
    """Propiedad normalizada del dispositivo, o "" si no se conoce."""
    own = _norm(_get(device, "ownership")).upper()
    return own if own in (COMPANY_OWNED, PERSONALLY_OWNED) else ""


def _enum(table: dict, value: Any, field: str) -> str:
    """Traduce vocabulario LucidFence -> enum AMAPI, o acepta el enum literal."""
    raw = _norm(value)
    if not raw:
        raise ValueError(f"{field}: valor vacío")
    if raw in table:
        return table[raw]
    upper = raw.upper()
    if upper in table.values():
        return upper
    raise ValueError(
        f"{field}: '{raw}' no es válido; usa uno de "
        f"{sorted(table)} o el enum AMAPI {sorted(set(table.values()))}"
    )


def _applications(apps: Any) -> list:
    """Normaliza la lista de apps a `ApplicationPolicy` mínima y válida.

    OJO: `applications` es un reemplazo de lista entera en AMAPI. La política
    resultante contiene exactamente estas apps; las que no aparezcan dejan de
    estar gestionadas. `update_mask` protege los campos hermanos, no el
    contenido de la lista.
    """
    if not isinstance(apps, (list, tuple)):
        raise ValueError("applications: se esperaba una lista")
    by_package: dict = {}
    for index, app in enumerate(apps):
        if isinstance(app, str):
            package, install_type = app, "FORCE_INSTALLED"
        elif isinstance(app, dict):
            package = _norm(app.get("package") or app.get("packageName"))
            install_type = _norm(
                app.get("install_type") or app.get("installType") or "FORCE_INSTALLED"
            ).upper()
        else:
            raise ValueError(f"applications[{index}]: se esperaba str o dict")
        if not package:
            raise ValueError(f"applications[{index}]: falta packageName")
        if install_type not in INSTALL_TYPES:
            raise ValueError(
                f"applications[{index}].installType: '{install_type}' no es un "
                f"InstallType de AMAPI ({sorted(INSTALL_TYPES)})"
            )
        # Un paquete repetido con installType distinto es un conflicto real: al
        # fusionar una lista base con una regla de bloqueo por geocerca, dejar
        # las dos entradas haría que el bloqueo no se aplicara. Falla ruidoso.
        previous = by_package.get(package)
        if previous is not None and previous != install_type:
            raise ValueError(
                f"applications: '{package}' aparece con installType en conflicto "
                f"('{previous}' y '{install_type}')"
            )
        by_package[package] = install_type
    # Orden estable: el parche debe ser determinista para que reaplicarlo sin
    # cambios no incremente `Policy.version` en el servidor.
    return [{"packageName": pkg, "installType": by_package[pkg]}
            for pkg in sorted(by_package)]


def build_enforcement_rules(rules: Any, *, company_owned: bool = True) -> list:
    """Construye `policyEnforcementRules` con las invariantes que Google exige.

    La referencia es explícita en dos puntos que un parche mal formado incumple
    y AMAPI rechaza:

    1. `blockAction` y `wipeAction` van SIEMPRE en pareja ("Note: wipeAction
       must also be specified" / "Note: blockAction must also be specified").
    2. `blockAfterDays` debe ser menor que `wipeAfterDays`.

    Se validan aquí, no en el adapter: es la única puerta por la que pasan
    todas las reglas.

    Args:
        rules: lista de reglas en vocabulario LucidFence.
        company_owned: False si el dispositivo es personal. `blockScope` "Only
            applicable to devices that are company-owned" y `preserveFrp`
            "doesn't apply to work profiles", así que en ese caso se omiten en
            vez de emitir un campo que el dispositivo no puede honrar.

    Raises:
        ValueError: si falta una de las dos acciones, si los plazos no son
            crecientes, si el scope no es un `BlockScope`, o si el disparador
            `settingName` está vacío.
    """
    if not isinstance(rules, (list, tuple)):
        raise ValueError("enforcement: se esperaba una lista de reglas")
    out = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"enforcement[{index}]: se esperaba un dict")
        setting = _norm(rule.get("setting_name") or rule.get("settingName"))
        if not setting:
            raise ValueError(
                f"enforcement[{index}].settingName es obligatorio: es el campo "
                "top-level de Policy que dispara la regla"
            )
        block_days = rule.get("block_after_days", rule.get("blockAfterDays"))
        wipe_days = rule.get("wipe_after_days", rule.get("wipeAfterDays"))
        if block_days is None or wipe_days is None:
            raise ValueError(
                f"enforcement[{index}]: blockAction y wipeAction deben ir juntas "
                "(AMAPI rechaza la regla si falta una de las dos)"
            )
        try:
            block_days = int(block_days)
            wipe_days = int(wipe_days)
        except (TypeError, ValueError):
            raise ValueError(f"enforcement[{index}]: los plazos deben ser enteros de días")
        if block_days < 0 or wipe_days < 0:
            raise ValueError(f"enforcement[{index}]: los plazos no pueden ser negativos")
        if block_days >= wipe_days:
            raise ValueError(
                f"enforcement[{index}]: blockAfterDays ({block_days}) debe ser menor "
                f"que wipeAfterDays ({wipe_days})"
            )

        block: dict = {"blockAfterDays": block_days}
        scope = _norm(rule.get("block_scope") or rule.get("blockScope"))
        if scope:
            scope = scope.upper()
            if scope not in BLOCK_SCOPES:
                raise ValueError(
                    f"enforcement[{index}].blockScope: '{scope}' no es un BlockScope "
                    f"({sorted(BLOCK_SCOPES)})"
                )
            # "Only applicable to devices that are company-owned."
            if company_owned:
                block["blockScope"] = scope

        wipe: dict = {"wipeAfterDays": wipe_days}
        preserve = rule.get("preserve_frp", rule.get("preserveFrp"))
        # "This setting doesn't apply to work profiles."
        if preserve is not None and company_owned:
            wipe["preserveFrp"] = bool(preserve)

        out.append({"settingName": setting, "blockAction": block, "wipeAction": wipe})
    return out


def build_policy_patch(
    restrictions: Any,
    *,
    management_mode: str,
    ownership: str = "",
    enforcement: Any = None,
) -> dict:
    """Construye el parche AMAPI para un estado de geocerca.

    Args:
        restrictions: vocabulario de LucidFence. Claves admitidas: `camera`,
            `location`, `wifi_config`, `kiosk`, `applications`. Una clave
            desconocida es un error, no se ignora en silencio: un typo que no
            aplica una restricción de seguridad debe fallar ruidoso.
        management_mode: `DEVICE_OWNER` o `PROFILE_OWNER`.
        ownership: `COMPANY_OWNED` o `PERSONALLY_OWNED`. Distingue COPE de BYOD;
            sin él, las restricciones que exigen company-owned se omiten.
        enforcement: reglas para `build_enforcement_rules` (opcional).

    Returns:
        dict con:
          - `patch`: cuerpo para `enterprises.policies.patch`.
          - `update_mask`: valor de `updateMask`, campos top-level separados por
            coma. NO es opcional en la práctica: la referencia dice que sin
            `updateMask` "all modifiable fields will be modified", así que
            enviar un parche parcial sin máscara borraría el resto de la
            política del tenant.
          - `skipped`: restricciones omitidas por no aplicar al modo/propiedad,
            con su motivo. La matriz de modos se declara, no se silencia.

    Raises:
        ValueError: modo desconocido, clave desconocida o valor fuera de enum.
    """
    mode = _norm(management_mode).upper()
    if mode not in MANAGEMENT_MODES:
        raise ValueError(
            f"management_mode '{management_mode}' desconocido; usa {list(MANAGEMENT_MODES)}"
        )
    own = _norm(ownership).upper()
    if own and own not in (COMPANY_OWNED, PERSONALLY_OWNED):
        raise ValueError(f"ownership '{ownership}' desconocido")

    if restrictions is None:
        restrictions = {}
    if not isinstance(restrictions, dict):
        raise ValueError("restrictions: se esperaba un dict")

    known = {"camera", "location", "wifi_config", "kiosk", "applications"}
    unknown = sorted(set(restrictions) - known)
    if unknown:
        raise ValueError(
            f"restrictions: clave(s) desconocida(s) {unknown}; admitidas {sorted(known)}"
        )

    # Vocabulario LucidFence -> campo top-level + valor AMAPI.
    candidates: list[tuple[str, Any]] = []
    if "camera" in restrictions:
        candidates.append(("cameraAccess", _enum(CAMERA_ACCESS, restrictions["camera"], "camera")))
    if "location" in restrictions:
        candidates.append(("locationMode", _enum(LOCATION_MODE, restrictions["location"], "location")))
    if "wifi_config" in restrictions:
        wifi = _enum(CONFIGURE_WIFI, restrictions["wifi_config"], "wifi_config")
        candidates.append(("deviceConnectivityManagement", {"configureWifi": wifi}))
    if "kiosk" in restrictions:
        candidates.append(("kioskCustomLauncherEnabled", bool(restrictions["kiosk"])))
    if "applications" in restrictions:
        candidates.append(("applications", _applications(restrictions["applications"])))

    patch: dict = {}
    skipped: list[dict] = []
    for field, value in candidates:
        if mode not in _SETTING_SCOPE[field]:
            skipped.append({
                "setting": field,
                "reason": f"no soportado en {mode}",
            })
            continue
        # El bloqueo de Wi-Fi exige company-owned; permitirlo sí es universal.
        needs_company = field in _COMPANY_OWNED_ONLY and not (
            field == "deviceConnectivityManagement"
            and value.get("configureWifi") == _WIFI_PERMISSIVE
        )
        if needs_company and mode == PROFILE_OWNER and own != COMPANY_OWNED:
            skipped.append({
                "setting": field,
                "reason": (
                    "requiere dispositivo company-owned en PROFILE_OWNER "
                    f"(ownership={own or 'desconocida'})"
                ),
            })
            continue
        patch[field] = value

    if enforcement is not None:
        # Un dispositivo personal solo es "no company-owned" cuando lo sabemos:
        # con `ownership` desconocida no inventamos que lo sea.
        patch["policyEnforcementRules"] = build_enforcement_rules(
            enforcement, company_owned=(own != PERSONALLY_OWNED)
        )

    return {
        "patch": patch,
        "update_mask": ",".join(sorted(patch)),
        "skipped": skipped,
    }


def build_fence_patch(policy: Any, fence_state: str, device: Any, **kwargs) -> dict:
    """Atajo: parche para la geocerca de una `Policy` en el estado dado.

    Lee las restricciones del action `apply_amapi_policy` de la policy cuyo
    `when` coincide con el estado (`inside` -> `on_enter`, `outside` ->
    `on_exit`, `unknown` -> `on_unknown`). Si la policy no declara ninguna,
    devuelve un parche vacío: es un no-op explícito, no un error.

    Acepta acciones como dict o como objeto (`ActionSpec` de `fences.py`): una
    `Fence` construida con `Fence.from_raw` trae dataclasses, y descartarlas
    silenciosamente dejaría la restricción sin aplicar sin avisar.

    El `when` ausente significa `on_enter`, igual que `ActionSpec.when` y que
    `Engine._fire_actions`. Un comodín aquí haría que "cámara permitida dentro
    de la geocerca" también desbloqueara la cámara fuera.
    """
    state = _norm(fence_state).lower() or "unknown"
    when = {"inside": "on_enter", "outside": "on_exit"}.get(state, "on_unknown")
    restrictions: dict = {}
    enforcement = kwargs.pop("enforcement", None)
    for act in (_get(policy, "actions", None) or []):
        if _get(act, "action") != "apply_amapi_policy":
            continue
        if (_get(act, "when") or "on_enter") != when:
            continue
        params = _get(act, "params") or {}
        restrictions = _get(params, "restrictions") or {}
        if enforcement is None:
            enforcement = _get(params, "enforcement")
        break
    return build_policy_patch(
        restrictions,
        management_mode=management_mode_of(device),
        ownership=ownership_of(device),
        enforcement=enforcement,
        **kwargs,
    )


def parse_device_compliance(device_resource: Any) -> dict:
    """Traduce un recurso `Device` de AMAPI a campos del modelo de estado.

    Consume `policyCompliant` y `nonComplianceDetails[]`. Los detalles se
    resumen a lo accionable (`settingName`, `nonComplianceReason`,
    `packageName`, `fieldPath`): el recurso completo es enorme y el resto no
    cabe en el estado de dispositivo.

    Un recurso sin `policyCompliant` no produce la clave: el merge del engine
    ignora ausentes, así que un reporte parcial nunca pisa el estado previo.
    """
    if not isinstance(device_resource, dict):
        return {}
    out: dict = {}

    compliant = device_resource.get("policyCompliant")
    if isinstance(compliant, bool):
        out["amapi_policy_compliant"] = compliant

    details = device_resource.get("nonComplianceDetails")
    if isinstance(details, list):
        summary = []
        for item in details:
            if not isinstance(item, dict):
                continue
            entry = {k: item[k] for k in ("settingName", "nonComplianceReason",
                                          "packageName", "fieldPath") if item.get(k)}
            if entry:
                summary.append(entry)
        out["amapi_non_compliance"] = summary

    applied = device_resource.get("appliedPolicyVersion")
    if applied is not None:
        out["amapi_applied_policy_version"] = str(applied)
    return out


__all__ = [
    "DEVICE_OWNER",
    "PROFILE_OWNER",
    "MANAGEMENT_MODES",
    "COMPANY_OWNED",
    "PERSONALLY_OWNED",
    "CAMERA_ACCESS",
    "LOCATION_MODE",
    "CONFIGURE_WIFI",
    "INSTALL_TYPES",
    "BLOCK_SCOPES",
    "supports_amapi",
    "management_mode_of",
    "ownership_of",
    "build_policy_patch",
    "build_enforcement_rules",
    "build_fence_patch",
    "parse_device_compliance",
]
