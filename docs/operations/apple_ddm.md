# Apple DDM — enforcement declarativo de geocercas

`lucidfence/core/ddm.py` genera declarations de Apple Declarative Device
Management a partir de una `Policy`, para que el enforcement converja en el
dispositivo en vez de en bucles de comandos del servidor.

## Límite honesto: DDM no geolocaliza

DDM **no tiene primitivas de geolocalización**. Ningún tipo de declaration
publicado por Apple evalúa posición. El trigger de geocerca se queda donde
está hoy — en el engine y los adapters de LucidFence — y DDM actúa solo como
capa de configuración/enforcement: el servidor decide **qué juego de
declarations activar** en cada transición de estado (`inside` / `outside`).

Por la misma razón, LucidFence **no sintetiza sintaxis de NSPredicate**. La
clave `Predicate` de `com.apple.activation.simple` es un passthrough: si el
integrador necesita un predicado, lo aporta como string y se copia verbatim.

## Declarations generadas

| Tipo | Origen del schema | Payload |
|------|-------------------|---------|
| `com.apple.configuration.legacy` | `declarative/declarations/configurations/legacy.yaml` | `ProfileURL` (obligatorio `https://`, alojado por el MDM) |
| `com.apple.configuration.management.status-subscriptions` | `.../management.status-subscriptions.yaml` | `StatusItems` |
| `com.apple.activation.simple` | `declarative/declarations/activations/simple.yaml` | `StandardConfigurations`, `Predicate` (opcional) |

Las cuatro claves de `declarationbase.yaml` (`Type`, `Identifier`,
`ServerToken`, `Payload`) son obligatorias y los tests las verifican, igual que
el límite de 64 octetos del `Identifier`.

**Idempotencia**: `ServerToken` es un SHA-256 del payload canónico. Regenerar
una policy sin cambios produce el mismo token, así que el dispositivo no
reaplica nada. Cambiar la `ProfileURL` o el estado de geocerca sí cambia el
token/identifier.

## Matriz de soporte

Disponibilidad de DDM (`declarationbase.yaml`) — `supports_ddm(device)` la
aplica y devuelve `False` si falta `os_version`, para no enviar declarations a
un dispositivo que no las entiende:

| Plataforma | Mínimo |
|------------|--------|
| iOS / iPadOS | 15.0 |
| macOS | 13.0 |
| tvOS | 16.0 |
| visionOS | 1.1 |
| watchOS | 10.0 |

Flag de capacidad por adapter (`MDMAdapter.supports_ddm`, `False` por defecto):

| Adapter | `supports_ddm` | Motivo |
|---------|----------------|--------|
| `jamf` | ✅ | Jamf Pro expone DDM; acción `apply_ddm`. |
| `applivery` | ❌ | Su documentación pública no describe superficie DDM (verificado 2026-07-29). Se activará cuando la documenten. |
| `ios_geofence` | ❌ | Módulo de vitrina, no habla con ningún MDM real. |
| resto | ❌ | Sin DDM: camino imperativo intacto. |

## Uso

```python
adapter.execute(device, "apply_ddm", {
    "policy": policy,
    "profile_url": "https://mdm.example.com/profiles/geofence-hq.mobileconfig",
})
```

Devuelve `{"ok": True, "declarations": {"configurations": [...], "activations": [...]}}`.
La acción es **offline**: construye los documentos, no los sube — la entrega
por el canal de declarations la hace el MDM.

Si el dispositivo no llega al mínimo de OS, devuelve
`{"ok": False, "error": "ddm_unsupported", "fallback": "imperative"}` para que
el llamante siga por el camino de comandos de siempre. Capacidad aditiva: nada
del camino imperativo cambia.

## Status channel

`parse_status_report(report)` traduce un `StatusReport` a campos del modelo de
estado de dispositivo (`os_version`, `model`, `serial_number`,
`passcode_compliant`, `filevault_enabled`). Acepta `StatusItems` con claves
planas y anidadas, ignora items desconocidos y expone los fallos del reporte en
`ddm_errors`.

Los nombres de status item suscritos por defecto salen de
`declarative/status/` del repo de Apple; no se inventan.

### Lockdown Mode como postura (OS 27)

WWDC 2026 anunció que DDM se vuelve **obligatorio** en la generación OS 27 y
añade nuevos *status items*, entre ellos **Lockdown Mode** (ver
`docs/internal/trends/signals.md`). LucidFence lo ingiere como **postura
correlacionable**, no como una nueva fuente de ubicación:

- El modelo de dispositivo lleva un campo booleano de readback `lockdown_mode`
  (`LocationReport` → `DeviceState`). Igual que `passcode_compliant` y
  `filevault_enabled`, **solo se rellena cuando la UEM lo reporta**.
- `sig_device_posture` deriva `lockdown_mode_off`, que es `True` **únicamente**
  cuando `lockdown_mode is False` (reportado OFF de forma explícita). Un valor
  `None`/ausente —el caso común hoy, porque Apple aún no publica la clave del
  status item— **no penaliza**: nunca se inventa riesgo a partir de un dato
  desconocido.
- Cuando contribuye, el motor suma riesgo con la razón textual
  `"Lockdown Mode desactivado"`, junto al resto de flags de postura.

Así, un dispositivo **fuera de su geocerca con Lockdown Mode OFF** puntúa más
alto que uno con Lockdown Mode ON o desconocido, y el admin puede escribir una
política sobre ese estado:

```json
{
  "id": "lockdown-off-outside",
  "name": "Fuera de geocerca sin Lockdown Mode",
  "when": [
    {"field": "fence_state", "op": "eq", "value": "outside"},
    {"field": "lockdown_mode", "op": "eq", "value": false}
  ],
  "actions": [{"action": "notify", "params": {}}]
}
```

La política casa solo cuando el status llega como `false`: un dispositivo con
`lockdown_mode` desconocido (`None`) **no** dispara la regla (desconocido ≠ OFF).

Cuando Apple publique la clave del status item de Lockdown Mode, el único cambio
es mapearla a `lockdown_mode` en `_STATUS_FIELD_MAP` (`ddm.py`); no se hardcodea
una clave inventada mientras OS 27 no esté publicado. Dependencia de readback
honesta: sin UEM que lo reporte, el campo se queda en `None` y la plumbing
engine/política sigue funcionando sin penalizar.

### Tipo de enrolamiento (supervisión) como postura (OS 27)

El mismo anuncio de WWDC 2026 añade el status item de **tipo de enrolamiento**.
LucidFence ingiere su faceta booleana de mayor valor —**supervisión**— como
postura correlacionable, con idéntica disciplina de readback honesto que
Lockdown Mode:

- El modelo lleva el campo booleano de readback `supervised`
  (`LocationReport` → `DeviceState`), junto a `lockdown_mode`. **Solo se rellena
  cuando la UEM lo reporta.**
- `sig_device_posture` deriva `unsupervised`, que es `True` **únicamente** cuando
  `supervised is False` (no supervisado de forma explícita). `None`/ausente —el
  caso común hoy— **no penaliza**: nunca se inventa riesgo desde un desconocido.
- Cuando contribuye, el motor suma riesgo con la razón textual
  `"dispositivo sin supervisión (enrolamiento personal)"` (+10), junto al resto
  de flags de postura.

Un dispositivo **fuera de geocerca y no supervisado** (enrolamiento personal/BYOD,
donde la mayoría del enforcement declarativo no aplica) puntúa más alto que uno
supervisado o desconocido. Política de ejemplo:

```json
{
  "id": "unsupervised-outside",
  "name": "Fuera de geocerca sin supervisión",
  "when": [
    {"field": "fence_state", "op": "eq", "value": "outside"},
    {"field": "supervised", "op": "eq", "value": false}
  ],
  "actions": [{"action": "notify", "params": {}}]
}
```

`supervised` desconocido (`None`) **no** dispara la regla (desconocido ≠ no
supervisado). Cuando Apple publique la clave del status item de enrolamiento, el
único cambio es mapearla a `supervised` en `_STATUS_FIELD_MAP` (`ddm.py`); no se
hardcodea una clave inventada mientras OS 27 no esté publicado.

## Fase 2 — canal de Jamf Pro (endpoints verificados)

Verificado contra el OpenAPI oficial de la Jamf Pro API **v11.30**
(`developer.jamf.com/jamf-pro/reference/jamf-pro-api`). La superficie DDM
publicada es de lectura y refresco:

| Acción LucidFence | Endpoint Jamf | Respuesta |
|-------------------|---------------|-----------|
| `ddm_status` | `GET /api/v1/ddm/{clientManagementId}/status-items` | `{"statusItems":[{"key","value","lastUpdateTime"}]}` |
| `ddm_sync` | `POST /api/v1/ddm/{clientManagementId}/sync` | `204` sin cuerpo (encola un `DeclarativeManagementCommand`) |

`ddm_status` pasa los `statusItems` por `parse_status_report` y devuelve
`device_state` con los campos del modelo; `ddm_sync` fuerza al dispositivo a
reconciliar tras cambiar el juego de declarations. Ambas respetan `dry_run`
(devuelven `would_send` sin llamar) y requieren `live=True`.

Desde el issue #70, `Engine.run_command` persiste ese `device_state` en el
store con semántica de **merge, no reemplazo**: un status report parcial
(Apple solo manda los items suscritos que cambiaron) nunca pisa campos que no
trae, un `ddm_status` fallido no toca el estado y `dry_run` nunca muta.
`ddm_errors` no se persiste como campo pero queda en el action log.

`clientManagementId` **no es** el id de mobile-device: sale de
`device.management_id`. Sin él, la acción devuelve `missing_management_id` en
vez de mandar un id que Jamf no reconoce.

### Hueco declarado: subir declarations propias

Jamf Pro **no publica** endpoint para crear/actualizar declarations propias.
Lo único que existe es `GET /api/v1/dss-declarations/{declarationId}`, que lee
las que genera el propio servidor; las declarations personalizadas se
despliegan por la UI (Blueprints), no por API. Por eso `apply_ddm` sigue
offline: preferimos un hueco declarado a una llamada inventada. Cuando Jamf
publique el endpoint de entrega, el cambio es local a `_apply_ddm`.

### Selección del juego por estado de geocerca

No hay hook nuevo en el engine, a propósito: `apply_ddm` lee `fence_state` del
`DeviceState` que ya recibe, así que el camino genérico
(`Engine.run_command(dev, "apply_ddm", {...})`) selecciona el juego correcto en
cada transición. El trigger sigue siendo del engine — DDM no geolocaliza.

## Tests

`tests/test_ddm.py` — 19 checks con fixtures golden, sin red: forma de las
declarations contra el schema, gating por versión de OS, idempotencia del
`ServerToken`, rechazo de `ProfileURL` no https, truncado del `Identifier`,
parseo de status (plano/anidado/basura), URLs de los dos endpoints DDM
verificados, readback de `statusItems` a `device_state`, `204` sin cuerpo,
ausencia de `management_id`, `404` del cliente y regresión de que el camino
imperativo sigue intacto.

## Referencias

- Schemas: <https://github.com/apple/device-management> (`declarative/`)
- Jamf Pro API v11.30: `GET /v1/ddm/{id}/status-items`, `POST /v1/ddm/{id}/sync`,
  `GET /v1/dss-declarations/{id}`
- Issues: #40 (fase 1), #52 (fase 2)
