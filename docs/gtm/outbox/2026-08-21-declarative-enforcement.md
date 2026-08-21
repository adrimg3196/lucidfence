# LucidFence: enforcement declarativo vs imperativo — lo que el UEM modela, y lo que no

> Borrador técnico para LinkedIn / X (audiencia: CISO, ingeniería de fleet, MSP).
> Co-firmado por CTO (empresa-cto, t_1a407df5, 2026-08-21) + PM (t_aa308b79 §1).
> Wording alineado a `pm_decision_declarative_enforcement.md` §1; respeta
> reglas #110 (lock = postura geocerca declarativa; cero declarativo en Android
> hasta #42; ni DDM ni DSC son "end-to-end por Graph" — ambos son build-only).

> ## ✅ HOLD LEVANTADO — CTO co-firma (t_1a407df5, 2026-08-21)
> El claim "Windows DSC end-to-end por Graph" (disputa t_2c00a8f2, decisión A) era
> **falso** y se ha eliminado del copy. Verificado contra `origin/main`:
> `windows_conformidad._apply_dsc` solo genera los manifest y devuelve `applied: True`
> (sin POST del manifest); `_report_live` es un GET de read-back de conformidad. El copy
> ahora dice la verdad: **Windows DSC = build-only, NO end-to-end por Graph** (igual que
> Apple DDM).
> - `core/declarative.py` **existe** en `origin/main` (feat #89) y `engine.py:32` lo
>   importa — el aviso previo de "módulo inexistente" era falso positivo sobre el ref
>   obsoleto `5cd5a1a`. La duplicidad `declarative_path_for` (ddm.py:123 vs
>   declarative.py) quedó consolidada en `origin/main` (merge #88 / `86730bb`).
> - Matriz jamf/windows_conformidad SÍ declarativo, intune/fleet NO, Android AMAPI
>   pendiente (#42/#90) — exacta. Matiz lock-only — exacto.
> CTO co-firma la pieza corregida. Pende de Marketing levantar el HOLD de publicación.

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
`pm_decision_declarative_enforcement.md` §1, y verificada contra `origin/main`):

> "Enforcement declarativo donde el UEM lo modela — **Apple DDM vía Jamf** y
> **Windows DSC** — con el resto de acciones por comando imperativo auditado, y
> el mismo veredicto de transporte en las dos rutas de dispatch."

**Asimetría que el copy debe respetar (riesgo de integridad #110):**
- **Windows DSC (`apply_dsc`) = build-only (NO end-to-end por Graph)**: genera
  los manifest DSC v3 / classic PS1 / classic MOF y devuelve `applied: True`
  (`core/adapters/windows_conformidad.py:134`). El adapter **no hace POST del
  manifest**; su único POST es la petición de token OAuth. La acción `report`
  (`_report_live`, línea 176) es un **GET** de
  `deviceManagement/managedDevices` — read-back de conformidad, no entrega del
  manifest.
- **Apple DDM (`apply_ddm`) = build-only / offline**: generamos la declaration,
  pero Jamf no publica endpoint de upload (hueco declarado en
  `docs/operations/apple_ddm.md` §"Hueco declarado"); el MDM la empuja por su
  canal declarativo. **No** es "enforcement declarativo end-to-end en Apple".
- El `lock` equivalente declarativo = **aplica la postura restrictiva del estado
  de geocerca** (declaration DDM, build-only), **NO** envía un comando de
  bloqueo de dispositivo. `wipe`, `reboot`, `locate`, `message` son imperativos
  y lo seguirán siendo.
- **Android AMAPI**: cero "declarativo" en material público hasta el builder #42
  + tests verdes (el gate `declarative.py` acepta el flag `supports_amapi_policy`,
  pero ningún adapter lo declara y `_apply_amapi` no existe).

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
