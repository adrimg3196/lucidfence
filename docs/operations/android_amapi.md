# Android AMAPI — enforcement declarativo de geocercas

Cierra el frente declarativo junto a [Apple DDM](apple_ddm.md) y
[Windows DSC](windows_dsc.md). Android Management API (AMAPI) es declarativo por
diseño: el servidor publica un documento `Policy` con el estado deseado y
Android Device Policy converge en el dispositivo, sin bucles de comandos.

Módulo: `lucidfence/core/amapi.py` · Tests: `tests/test_amapi.py` (51, sin red).

## Límite honesto

**AMAPI no tiene primitiva de geocerca.** El trigger de ubicación sigue siendo
el engine/adapters de LucidFence: nosotros decidimos QUÉ parche corresponde a
cada transición de estado. AMAPI es la capa de configuración/enforcement, no de
detección. Es el mismo límite que DDM (#40) y DSC (#41).

## Fuentes

Todas las claves y enums salen de la referencia REST oficial, verificada el
2026-08-02:

| Qué | Dónde |
|---|---|
| Campos de `Policy`, enums, `PolicyEnforcementRule` | `developers.google.com/android/management/reference/rest/v1/enterprises.policies` |
| `policyCompliant`, `NonComplianceDetail` | `.../rest/v1/enterprises.devices` |
| `ManagementMode`, `Ownership` | `.../rest/v1/ManagementMode`, `.../rest/v1/Ownership` |
| Semántica de `updateMask` | `.../rest/v1/enterprises.policies/patch` |

## Dos decisiones que evitan un parche inválido

**1. Nada de campos deprecados.** La referencia marca `cameraDisabled` y
`wifiConfigsLockdownEnabled` como *deprecated*. Emitimos sus sustitutos
actuales:

| Deprecado | Lo que emitimos |
|---|---|
| `cameraDisabled` (boolean) | `cameraAccess` (enum `CameraAccess`) |
| `wifiConfigsLockdownEnabled` (boolean) | `deviceConnectivityManagement.configureWifi` (enum `ConfigureWifi`) |

**2. `updateMask` siempre.** La doc de `enterprises.policies.patch` dice: *"The
field mask indicating the fields to update. If not set, all modifiable fields
will be modified."* Enviar un parche parcial **sin** máscara borraría el resto
de la política del tenant. `build_policy_patch` devuelve `update_mask` con los
campos top-level que realmente lleva el parche.

## Vocabulario

La geocerca habla en términos de producto; el módulo traduce al único enum que
Google acepta. Un valor fuera del vocabulario es un error de configuración, no
algo que se pasa tal cual (una restricción de seguridad que no se aplica por un
typo es peor que un fallo ruidoso).

| Restricción LucidFence | Valores | Campo AMAPI |
|---|---|---|
| `camera` | `user_choice` · `block` · `enforce` | `cameraAccess` |
| `location` | `user_choice` · `enforced` · `disabled` | `locationMode` |
| `wifi_config` | `allow` · `no_new_networks` · `block` | `deviceConnectivityManagement.configureWifi` |
| `kiosk` | `true` / `false` | `kioskCustomLauncherEnabled` |
| `applications` | lista de paquetes o `{package, install_type}` | `applications[]` |

También se acepta el enum de AMAPI literal (`LOCATION_DISABLED`, …).

## Matriz de modos de gestión

Muchas restricciones son *mode-scoped*. `build_policy_patch` **omite** las que
no aplican y las declara en `skipped` con su motivo — no las envía en silencio
ni finge que se aplicaron.

| Restricción | Fully managed (`DEVICE_OWNER`) | Work profile company-owned (COPE) | Work profile personal (BYOD) |
|---|---|---|---|
| `cameraAccess` | sí, todo el dispositivo | sí, solo dentro del perfil de trabajo | sí, solo dentro del perfil de trabajo |
| `locationMode` | sí | sí | sí |
| `applications` | sí | sí | sí |
| `kioskCustomLauncherEnabled` | sí | no | no |
| `configureWifi` (valores restrictivos) | sí | sí | **no** |

Notas de la referencia que sostienen la tabla:

- `CameraAccess`: *"applies device-wide on fully managed devices and only within
  the work profile on devices with a work profile"*.
- `LocationMode`: *"The degree of location detection enabled on work profile and
  fully managed devices"*.
- `DISALLOW_ADD_WIFI_CONFIG` / `DISALLOW_CONFIGURING_WIFI`: *"Supported on fully
  managed devices and work profile on company-owned devices"* → excluye BYOD.
  `ALLOW_CONFIGURING_WIFI` no restringe nada, así que no exige company-owned.
- `kioskCustomLauncherEnabled`: **inferido**, no citado. La referencia describe
  el campo sin acotar el modo; lo restringimos a fully managed porque el modo
  kiosco es el solution set de *dedicated device*, que se aprovisiona como
  dispositivo totalmente gestionado. Es la única fila de la tabla que no sale de
  una frase literal — si Google documenta kiosco en perfil de trabajo, se
  amplía `_SETTING_SCOPE` y cae el test que lo fija.

COPE y BYOD son ambos `PROFILE_OWNER`: se distinguen por `Ownership`
(`COMPANY_OWNED` / `PERSONALLY_OWNED`). Sin `ownership` conocida, las
restricciones que la exigen se omiten.

## Enforcement graduado

`policyEnforcementRules` sustituye al bucle imperativo: warn → block → wipe lo
aplica el dispositivo. La referencia impone dos invariantes que
`build_enforcement_rules` valida antes de emitir nada:

1. `blockAction` y `wipeAction` van **siempre en pareja** (*"Note: wipeAction
   must also be specified"* / *"Note: blockAction must also be specified"*).
2. `blockAfterDays` debe ser **menor** que `wipeAfterDays`.

```python
build_enforcement_rules([{
    "setting_name": "applications",   # campo top-level de Policy que dispara
    "block_after_days": 2,            # 0 = bloquear de inmediato
    "wipe_after_days": 9,
    "block_scope": "BLOCK_SCOPE_DEVICE",   # solo company-owned
    "preserve_frp": True,
}])
```

## Uso desde una policy

```json
{
  "id": "pol-fuera-almacen",
  "actions": [
    {
      "action": "apply_amapi_policy",
      "when": "on_exit",
      "params": {
        "restrictions": {"camera": "block", "location": "enforced"},
        "enforcement": [
          {"setting_name": "applications", "block_after_days": 1, "wipe_after_days": 5}
        ]
      }
    }
  ]
}
```

El engine mapea `inside → on_enter`, `outside → on_exit`,
`unknown → on_unknown`, y pasa `params` al adapter tal cual. Un `when` ausente
significa `on_enter`, igual que en el resto del modelo de acciones — no es un
comodín. Una policy sin acción `apply_amapi_policy` produce un parche vacío:
no-op explícito, no error.

Llamando a mano se puede pasar la policy entera y dejar que el módulo elija el
juego según el estado: `execute(device, "apply_amapi_policy", {"policy": pol})`.

### Requisito en el estado del dispositivo

El gate `supports_amapi` necesita `management_mode` (y `ownership` para
distinguir COPE de BYOD) en el `DeviceState`. Sin ellos el adapter devuelve
`fallback: "imperative"` y no genera nada: la mitad de las restricciones son
mode-scoped, así que emitir un parche sin saber el modo sería adivinar el
alcance. Es el equivalente de `os_version` en el gate de DDM.

⚠️ **Hueco de documentación (Applivery):** El API pública de Applivery (`/v1/organizations/{org}/mdm/devices`) no publica ni describe los campos del modo de gestión de Android (`management_mode`) ni la propiedad del dispositivo (`ownership`) en su respuesta oficial. Por lo tanto, los dispositivos sincronizados de manera real a través de este UEM llegarán con `None` en estos atributos y el gate de AMAPI de LucidFence caerá correctamente al camino imperativo como fallback de seguridad, evitando adivinar o emitir parches de alcance desconocido.

## Soporte por adapter

| Adapter | `supports_amapi_policy` | Motivo |
|---|---|---|
| `applivery` | **True** | Publica el passthrough: `PUT /v1/organizations/{org}/mdm/android/enterprise/policies/{emmPolicyId}`, cuyo campo `config` es el *"Google Android Enterprise policy configuration object"* (verificado 2026-08-02 contra su doc oficial). |
| `intune` | False | Gestiona Android Enterprise, pero no documenta un endpoint que acepte el documento de política de AMAPI: su superficie es Graph, con su propio modelo. |
| `workspace_one` | False | Mismo caso. |

Gestionar Android Enterprise **no** implica exponer el documento de política por
API. Solo marcamos la capacidad donde el proveedor la documenta — el mismo
criterio que dejó `supports_ddm` solo en `jamf`.

## Entrega

`apply_amapi_policy` **genera** el documento; no lo publica. Publicar exigiría el
`emmPolicyId` del tenant y mutaría la política de un cliente real, así que esa
decisión es de quien integra. La respuesta trae `patch`, `update_mask`,
`skipped` y `delivery: "offline"`. Mismo criterio que `apply_ddm` en Jamf.

### ⚠️ Cómo entregar el parche sin borrar la política del tenant

`build_policy_patch` devuelve un parche **parcial**: solo los campos que la
geocerca cambia. Cómo se entrega depende del canal, y equivocarse aquí borra
configuración del cliente:

| Canal | Verbo | Qué enviar |
|---|---|---|
| AMAPI directo (`androidmanagement.googleapis.com`) | `PATCH` | el parche tal cual + `updateMask` = `update_mask` |
| Passthrough de Applivery | `PUT` | **`config` actual del tenant con el parche fusionado encima** |

El PUT de Applivery reemplaza `config` entero y **no acepta `updateMask`**.
Enviar ahí el parche a secas dejaría la política con solo esos campos y tiraría
el resto. Hay que hacer `GET` de la política, fusionar las claves del parche
sobre el `config` existente y hacer `PUT` del objeto completo.

El módulo **no** trae helper de fusión a propósito: requiere leer el estado
remoto, y esa llamada es del integrador (aquí no hacemos red). Un `dict.update`
de primer nivel basta, porque todas las claves del parche son campos top-level
de `Policy`.

Ojo también con `applications`: en AMAPI es un **reemplazo de lista entera**. La
política resultante contiene exactamente las apps del parche; las que no
aparezcan dejan de estar gestionadas. `update_mask` protege los campos hermanos,
no el contenido de la lista.

## Readback

`parse_device_compliance` traduce un recurso `Device` de AMAPI al estado
persistido:

| AMAPI | `DeviceState` |
|---|---|
| `policyCompliant` | `amapi_policy_compliant` |
| `nonComplianceDetails[]` | `amapi_non_compliance` (resumen accionable) |
| `appliedPolicyVersion` | `amapi_applied_policy_version` |

Viaja por el canal `device_state` que ya existe, así que el engine hace **merge,
no reemplazo**: un reporte parcial nunca pisa campos ausentes (issue #70).
