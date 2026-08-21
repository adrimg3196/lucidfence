# LucidFence: enforcement declarativo vs imperativo — lo que el UEM modela, y lo que no

> Borrador técnico para LinkedIn / X (audiencia: CISO, ingeniería de fleet, MSP).
> Co-firmado por CTO (empresa-cto, t_5e8c5bfe, 2026-08-21) + PM (t_aa308b79 §1).
> Wording alineado a `pm_decision_declarative_enforcement.md` §1; respeta
> reglas #110 (asimetría DDM build-only vs DSC end-to-end, lock=postura geocerca,
> cero declarativo en Android hasta #42).
> NO publicable por el agente: owner gate antes de publicar.

> ## ⛔ HOLD — NO PUBLICAR (Marketing, 2026-08-21 18:00 CEST)
> Esta pieza queda **retenida** aunque figure co-firmada, porque contiene un claim
> que Marketing ha verificado como **no sostenible** contra `origin/main` de hoy:
> - Líneas 44-46 ("Windows DSC = end-to-end real … lo reporta en vivo vía Graph"):
>   `windows_conformidad._apply_dsc` **solo genera** `dsc_v3` / `dsc_classic_ps1` /
>   `dsc_classic_mof` y devuelve `applied: True` — **no hace POST**. El único POST del
>   adapter (`windows_conformidad.py:91`) es la petición de **token OAuth**, y
>   `_report_live` es un **GET** de `deviceManagement/managedDevices` para la acción
>   `report`. Es read-back de conformidad, no entrega del manifest.
> - Líneas 20/23 (`core/declarative.py`) fueron marcadas como error por el CTO, pero
>   **son correctas hoy**: `engine.py:32` importa `declarative_path_for` de
>   `lucidfence.core.declarative`. Existe además una **segunda definición** en
>   `ddm.py:123` (y `declarative.py:65` importa la de ddm como `_ddm_path`) — duplicidad
>   real que conviene resolver en código, no en el copy.
> Ruta de desbloqueo: card de kanban Marketing→CTO "disputa fáctica DSC" (2026-08-21).
> Mientras esté en HOLD, el ángulo declarativo **no** se usa en ninguna pieza nueva.

## La matriz real (verificada en runtime, main, 2026-08-21)

No inferimos. Esto es lo que el código decide hoy, por UEM:

| UEM | Canal declarativo | Estado |
|-----|------------------|--------|
| Jamf | Apple DDM (`supports_ddm = True`) | SÍ |
| Windows (conformidad) | Windows DSC (`supports_dsc = True`) | SÍ |
| Intune | — | NO |
| Fleet | — | NO |
| Android AMAPI | el flag de capacidad existe, el builder no (#42/#90) | NO todavía |

Fuente: `lucidfence/core/adapters/{jamf,windows_conformidad,fleet,intune}.py` y la
puerta `lucidfence/core/declarative.py` (`declarative_path_for`).

## El matiz que respetamos en el copy

Solo la acción `lock` tiene un equivalente declarativo modelado
(`DECLARATIVE_EQUIVALENTS = {"lock": "apply_ddm"}` en `core/ddm.py`).
`wipe`, `reboot`, `clear_passcode`, `locate` y `message` son comandos MDMv1 en
Apple y lo seguirán siendo — Apple no publica declaration para ellos.

Por eso la frase canónica que usamos (co-firmada por CTO y PM, alineada a
`pm_decision_declarative_enforcement.md` §1):

> "LucidFence aplica **enforcement declarativo donde el UEM lo modela de forma
> nativa**: configuración de dispositivo vía **Windows DSC** (entrega end-to-end
> por Microsoft Graph) y postura de geocerca vía **Apple DDM** (generamos la
> declaration DDM; el MDM la entrega por su canal declarativo — Jamf hoy no
> expone upload por API). El resto de acciones (wipe, reboot, locate, lock de
> comando, message) viajan por **comando imperativo auditado**, porque Apple no
> modela esas acciones como declarativas y no las vamos a inventar."

**Asimetría que el copy debe respetar (riesgo de integridad #110):**
- **Windows DSC (`apply_dsc`) = end-to-end real**: genera el manifest DSC v3 y
  lo reporta en vivo vía Microsoft Graph (`_report_live` en
  `core/adapters/windows_conformidad.py`).
- **Apple DDM (`apply_ddm`) = build-only / offline**: generamos la declaration,
  pero Jamf no publica endpoint de upload (hueco declarado en
  `docs/operations/apple_ddm.md` §"Hueco declarado"); el MDM la empuja por su
  canal declarativo. **No** es "enforcement declarativo end-to-end en Apple".
- El `lock` equivalente declarativo = **aplica la postura restrictiva del estado
  de geocerca** (declaration DDM, build-only), **NO** envía un comando de
  bloqueo de dispositivo. `wipe`, `reboot`, `locate`, `message` son imperativos
  y lo seguirán siendo.
- **Android AMAPI**: cero "declarativo" en material público hasta el builder #42
  + tests verdes (el flag `supports_amapi_policy` existe, `apply_amapi` no).

Si una pieza dice o insinúa "todo el enforcement es declarativo", es falso:
solo donde el UEM lo modela (Windows DSC, Apple DDM geofence-posture).

## La historia de ingeniería de hoy (#205 / PR #206)

Antes, el mismo iPad podía recibir un comando distinto según el camino interno
de código: la ruta multi-UEM enrutaba declarativamente y la ruta single-provider
(la que usan los tenants desde el dashboard) llamaba siempre `adapter.execute()`
de forma imperativa, sin consultar nunca la capacidad declarativa.

Inconsistencia de correctness, no feature pendiente — y Apple hizo DDM
obligatorio en OS 27.

Está arreglado en main (`origin/main`, commit `5cd5a1a`):
`ddm.declarative_path_for(device, action, adapter, params)` se evalúa UNA vez y
DESPUÉS de todo el gating (doble llave del wipe, dry_run/observe, allow-list de
live_actions, cooldown destructivo, audit y human-gate SOAR), y su resultado
alimenta las dos rutas de dispatch. La consistencia entre caminos es por
construcción, no por dos criterios que puedan divergir. El transporte cambia; el
permiso no.

Detalle que evitó un fallo grave: Apple NO modela DeviceLock declarativamente.
Enrutar un `lock` sin perfil habría acabado en `missing_parameter` — un móvil
robado se quedaba sin bloquear. Por eso la cuarta condición del path (el llamante
debe aportar el perfil que la declaration transporta).

14 tests nuevos en verde; batería runtime 51/51 en el merge.

## Red lines que respetamos (por si alguien adapta el copy)

- Multi-UEM: Applivery live por defecto; Intune/Jamf **no son live
  incondicionalmente** — se activan en modo live al conectar tu token
  (simulación sin token). Nunca "Intune/Jamf live" sin anclar al estado de token.
- Webhook SOAR: firmado HMAC-SHA256 por tenant (`X-LucidFence-Signature`),
  dirigido al SIEM que ya uses. No "SSRF-hardened / egress RFC1918" — eso vive
  solo en `oidc.py` (fetch de IdP OIDC), no en el webhook de salida.
