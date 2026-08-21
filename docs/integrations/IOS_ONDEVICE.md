# Agente iOS de geocercas on-device — despliegue por MDM

El adapter `ios_geofence` es la opción **más privada** de LucidFence: la geocerca
se evalúa **en el dispositivo** (CoreLocation). La ubicación cruda nunca sale del
iPhone; el dispositivo solo reporta **cumplimiento** (dentro/fuera/sin señal). Tu
MDM (Intune / Jamf / Applivery) solo hace dos cosas: **entregar la config** de las
geocercas a la app gestionada y, opcionalmente, **recibir el cumplimiento**. Nunca
transporta coordenadas de dispositivos.

> Lee primero la [matriz de ubicación](LOCATION_MATRIX.md): qué da iOS de verdad
> y por qué esta es la fila más privada de la tabla.

Tiempo estimado: 15 minutos. No necesitas credenciales de ningún UEM para
**generar** la config; solo tu MDM para **empujarla**.

## 1. Cómo funciona (el porqué del mínimo privilegio)

```
  Admin (fences.json)                Dispositivo iOS (app gestionada)
        │                                    │
        │  build_geofence_appconfig()        │  evalúa geocercas con CoreLocation
        ▼                                    │  (la ubicación NO sale de aquí)
  Managed App Configuration ──MDM push──►  UserDefaults
        (definición de geocercas)            │
                                             ▼
                                    reporta SOLO cumplimiento
                                    (dentro / fuera / sin señal)
```

- La config lleva **la definición de las geocercas de política** (centros/radios de
  la organización, p. ej. la oficina), que es un dato tuyo, no la posición de nadie.
- La app decide dentro/fuera localmente y reporta un booleano de cumplimiento. Sin
  lat/lng de dispositivo, ni al MDM ni a LucidFence.

## 2. Genera la config de despliegue

El exportador es stdlib puro (`lucidfence/core/adapters/ios_geofence.py`), sin red
ni credenciales. Produce la **Managed App Configuration** que ingiere cualquier MDM:

```bash
python3 - <<'PY'
import json
from lucidfence.core.adapters.ios_geofence import (
    build_geofence_appconfig, to_appconfig_plist, build_geofence_mobileconfig,
)

fences = json.load(open("fences.json"))

# a) clave-valor (Applivery / Intune "key-value" / Jamf con pares):
print(json.dumps(build_geofence_appconfig(fences, tenant_id="acme"), indent=2))

# b) XML plist de App Configuration (Jamf / Intune "XML"):
open("ios_geofence.appconfig.plist", "w").write(
    to_appconfig_plist(build_geofence_appconfig(fences, tenant_id="acme")))

# c) perfil .mobileconfig completo (MDMs que suben un perfil):
open("ios_geofence.mobileconfig", "w").write(
    build_geofence_mobileconfig(fences, organization="Acme", tenant_id="acme"))
PY
```

La salida es **estable y determinista** por tenant (los UUID del perfil se derivan
de organización+tenant): dos ejecuciones iguales dan bytes idénticos, así puedes
versionarla en git y ver diffs limpios cuando cambian las geocercas.

Estructura de la config (esquema `lucidfence.ios_geofence/1`):

```json
{
  "schema": "lucidfence.ios_geofence/1",
  "evaluation": "on_device",
  "reporting": { "mode": "compliance_only", "include_coordinates": false },
  "fences": [
    { "id": "office-hq", "type": "circle",
      "center": {"lat": 40.42, "lng": -3.71}, "radius_m": 350,
      "notify_on": ["enter", "exit"] }
  ]
}
```

`reporting.include_coordinates` viaja en `false` **por diseño**: es el contrato que
la app respeta. No hay una variante que lo ponga en `true`.

## 3. Súbela a tu MDM (mínimo privilegio)

Todos usan el mismo mecanismo de Apple (Managed App Configuration): un diccionario
que iOS deja en `UserDefaults` bajo `com.apple.configuration.managed` y que la app
lee. El privilegio necesario es solo **asignar config a una app gestionada** — nada
de permisos de acción remota, inventario ni ubicación.

| MDM | Dónde | Qué subes |
|---|---|---|
| **Intune** | Apps → App configuration policies → **Managed devices** → target = la app | El JSON como pares clave-valor, o el XML plist (opción "Enter XML data") |
| **Jamf Pro** | La app gestionada → pestaña **App Configuration** | El XML plist (`ios_geofence.appconfig.plist`) |
| **Applivery** | App gestionada → **Managed configuration** | El JSON clave-valor de `build_geofence_appconfig` |
| Otros (perfil) | Sube un perfil de configuración | `ios_geofence.mobileconfig` (payload `com.apple.app.managed`) |

En Intune/Jamf/Applivery esto **no** requiere los permisos de acción de sus guías
respectivas ([Intune](INTUNE.md) · [Jamf](JAMF.md) · [Applivery](APPLIVERY.md)):
la app config es una capacidad de "gestión de apps", independiente del rol que
ejecuta `lock`/`wipe`. Si solo despliegas geocercas on-device, no des más.

## 4. Permisos de localización que pide iOS

La app pide autorización de ubicación al usuario/dispositivo. Para geocercas por
entrada/salida en segundo plano, iOS exige **"Siempre" (Always)** más
**region monitoring** (CoreLocation `CLCircularRegion`), no acceso continuo a
posición. Recomendado gestionarlo por MDM con el perfil de la app para que no
dependa de que cada usuario acepte:

- Concede la autorización de localización **a la app**, no a un servicio de
  tracking. La app usa CoreLocation para **evaluar la geocerca**, no para emitir
  coordenadas.
- No necesitas "Precisa" (Precise) para regiones circulares grandes; radios muy
  pequeños (< ~100 m) sí la piden y iOS puede degradar la exactitud.

## 5. Cómo reporta cumplimiento (sin coordenadas)

El dispositivo emite un estado de cumplimiento por geocerca — `inside` / `outside`
/ `unknown` — que el resto del producto normaliza vía `ios_geofence_compliance`
(campos `geofence_compliant`, `geofence_compliance_label`). Ese booleano es lo
único que cruza la red. En la vitrina/engine se agrega como
`ios_geofence_summary` (total / compliant / %), nunca como un mapa de posiciones.

Si quieres cortar acceso ante no-cumplimiento, encadena ese estado con el
Conditional Access de tu tenant (misma idea que el resto: LucidFence decide, el
UEM/IdP actúa). Ver [ENFORCEMENT.md](../operations/ENFORCEMENT.md).

## 6. Limitaciones honestas (qué da iOS de verdad)

- **Region monitoring, no tiempo real.** iOS despierta la app en cruces de región y
  limita el número de regiones monitorizadas simultáneamente (histórico: ~20 por
  app). Para muchas geocercas, prioriza las más cercanas; no esperes cientos activas
  a la vez.
- **El usuario puede revocar localización.** Si baja el permiso a "Al usar la app" o
  lo quita, el estado pasa a `unknown` — nunca se inventa una posición (regla del
  producto, ver [LOCATION_MATRIX.md](LOCATION_MATRIX.md)).
- **Requiere la app gestionada instalada** vía tu MDM; sin app gestionada no hay app
  config que empujar. Complementa —no sustituye— a Applivery para GPS de flota o a
  Fleet/osquery para portátiles. La combinación práctica está en
  [FLEET.md](FLEET.md) y [MULTI_UEM.md](MULTI_UEM.md).
- **DDM/Apple declarativo** cuando aplique: contexto en
  [apple_ddm.md](../operations/apple_ddm.md).

## Referencias

- Adapter y exportador: `lucidfence/core/adapters/ios_geofence.py`.
- Test del exportador (payload estable, sin fugas, caso 0 geocercas):
  `tests/test_ios_geofence_appconfig.py`.
- Índice de documentación: [docs/README.md](../README.md).
