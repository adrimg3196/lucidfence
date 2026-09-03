# Matriz de ubicación por UEM — lo que de verdad obtienes

LucidFence hace geofencing, pero la ubicación sale de las APIs del UEM, y
cada una da una cosa distinta. Esta tabla existe para que dimensiones el
piloto con expectativas reales, no las de una demo.

| Fuente | Fidelidad real | Cadencia | Plataformas | Notas honestas |
|---|---|---|---|---|
| **Applivery** | GPS por dispositivo (lat/lng/accuracy) vía API MDM | La del check-in MDM (típico 15-60 min), no tiempo real | iOS/Android gestionados | La única fuente live verificada contra API real hoy. El dispositivo puede revocar el permiso de localización: esos entran como `unknown` |
| **Intune** | Muy limitada: `locateDevice` es puntual, pensado para dispositivos perdidos (supervisados/corporativos) | Bajo demanda, no continua | iOS supervisado, Windows | Graph **no** expone un stream de ubicación de flota. No planifiques geofencing continuo solo con Intune |
| **Jamf** | Sin ubicación continua por API | — | macOS/iOS | Jamf da inventario y postura excelentes, ubicación no. Combínalo con el adapter iOS o geofencing lógico |
| **Fleet (osquery)** | Aproximada por señal de red (IP pública, SSID/BSSID) — "geofencing lógico" ([NETWORK_LOCATION.md](NETWORK_LOCATION.md)) | La del intervalo osquery (configurable, minutos) | macOS/Windows/Linux | Sin GPS. Ideal para "¿está en la red de la oficina / en qué país sale a internet?", no para radios de 200 m |
| **Adapter iOS geofence** (`ios_geofence`) | Geocercas evaluadas **en el dispositivo** (CoreLocation), el server solo recibe cumplimiento | Eventos de entrada/salida | iOS | La opción más privada: la ubicación cruda no sale del dispositivo. Despliegue por MDM en [IOS_ONDEVICE.md](IOS_ONDEVICE.md) |
| **Webhook genérico** (`generic_http_source`) | La que tenga tu sistema (CAD, telemática vehicular, EDR…) | La de tu sistema | Cualquiera | Si ya tienes una fuente de ubicación mejor, inyéctala y usa el UEM solo para actuar |

## Cómo decidir

- **Flota móvil corporativa (iOS/Android)** → Applivery como fuente, o el
  adapter iOS si la privacidad manda.
- **Portátiles** → Fleet/osquery con [geofencing lógico por red](NETWORK_LOCATION.md)
  (mapeo IP/SSID/BSSID → sitio) + postura. Un portátil sin GPS nunca dará radios
  finos: no lo prometas en tu piloto.
- **Tenant Microsoft puro** → asume que la señal de Intune es de inventario
  y conformidad; para ubicación real añade otra fuente (webhook, agente, o el
  [geofencing lógico por red](NETWORK_LOCATION.md) si conoces la topología de tus
  sedes) y usa Intune para **actuar** (`set_compliance` → Conditional Access).
- **Mixto** → multi-UEM (`providers`): cada dispositivo con su provider;
  el engine correlaciona todo en el mismo mapa de riesgo.

## Reglas del producto que protegen al admin

- Un dispositivo sin ubicación es `unknown`, nunca se inventa una posición.
- El anti-spoofing (`location_integrity`) usa **nuestro** reloj de
  observación, no el `last_seen` que declara el dispositivo.
- Precisión ≠ verdad: `accuracy_m` viaja con cada report. Con
  `location_max_accuracy_m` en la config (metros; `0` = desactivado, el valor
  por defecto) el engine trata como **desconocido** cualquier fix más impreciso
  que ese umbral: no dispara `on_exit`, no cuenta como "fuera" y deja un
  evento `location_rejected` (`reason: inaccurate`) en el timeline, y el
  contador `location_rejected_inaccurate` en las estadísticas del ciclo. Una
  precisión desconocida (`accuracy_m` ausente) nunca descarta el fix. Ojo con
  la ubicación por red: declara `accuracy_m` = radio del sitio a propósito, así
  que el umbral debe ser mayor que el radio de tus sitios.
- Todo lo anterior corre local: la ubicación de tu flota no sale de tu
  máquina (garantía de diseño del producto, no una promesa de marketing).
- La ubicación se **correlaciona** con postura de readback (cifrado, y ahora
  el status **Lockdown Mode** de Apple DDM OS 27) **solo cuando la UEM la
  reporta**: un dato ausente es `None` y nunca suma riesgo — ver
  [apple_ddm.md](../operations/apple_ddm.md).
