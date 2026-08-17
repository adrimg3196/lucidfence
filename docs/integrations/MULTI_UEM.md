# Multi-UEM — registrar una flota mixta desde el dashboard

La mayoría de las flotas no son de un solo UEM. Lo habitual es **móviles en un
sitio y portátiles en otro**: p.ej. Applivery gestiona los iPhone/Android y
Fleet (osquery) gestiona los MacBook y portátiles Windows/Linux. LucidFence no
te obliga a elegir: registras cada UEM como un *provider* del tenant, le pones
una etiqueta de segmento (`móviles`, `portátiles`, …) y el orquestrador
multi-UEM correlaciona todo en el mismo mapa de riesgo.

Esta guía cubre el flujo de registro con **mínimo privilegio por UEM**. Para lo
que de verdad entrega cada plataforma en ubicación, mira la
[matriz de ubicación](LOCATION_MATRIX.md) antes de dimensionar el piloto.

Tiempo estimado: 10 minutos por UEM.

## 0. Quién puede hacerlo

El registro es una mutación de configuración: exige rol con la capability
`engine:config` (owner/admin de la org). Un rol operador o una API key de solo
lectura reciben `403`. Cada alta y baja deja un evento hash-chained en el audit
log (`provider.registered` / `provider.removed`) — sin el secreto, solo el
nombre del UEM y el segmento.

## 1. El caso real: Applivery (móviles) + Fleet (portátiles)

### 1a. Applivery para los móviles

Fuente **live** de ubicación GPS para iOS/Android gestionados. Onboarding con
mínimo privilegio en [APPLIVERY.md](APPLIVERY.md). Necesitas solo:

- Un **API token** de Applivery con permiso de lectura de dispositivos (y de
  acción solo cuando pases a enforce).

En el dashboard: **Integraciones UEM → + Conectar UEM → Applivery**, pega el
token, elige segmento **`móviles`**, pulsa **Probar conexión** y **Guardar**.

### 1b. Fleet para los portátiles

Telemetría osquery + MDM open-source para macOS/Windows/Linux. Onboarding con
mínimo privilegio en [FLEET.md](FLEET.md). Necesitas solo:

- Un usuario **API-only** con rol `observer` (solo lectura) para el piloto.
- El `endpoint` (URL base de tu Fleet) y su token.

En el dashboard: **+ Conectar UEM → FleetDM**, rellena endpoint + token, elige
segmento **`portátiles`**, **Probar** y **Guardar**.

Resultado: dos conectores en la lista, cada uno con su pill de segmento. El
engine enruta cada acción de remediación al UEM correcto según el
`provider_ref` del dispositivo — un wipe de un iPhone va por Applivery, un lock
de un MacBook va por Fleet. Nunca se cruzan.

## 2. Mínimo privilegio, UEM por UEM

| UEM | Credencial que pides | Alcance mínimo para el piloto |
|---|---|---|
| Applivery | API token | Lectura de dispositivos; acción solo en enforce |
| Fleet | Usuario API-only + token | Rol `observer` (lectura); `maintainer` solo en enforce |
| Intune | `tenant_id` + `client_id` + `client_secret` | App registration con `DeviceManagementManagedDevices.Read.All` |
| Jamf | `client_id` + `client_secret` | API role de solo lectura de inventario |

Detalle por plataforma: [INTUNE.md](INTUNE.md), [JAMF.md](JAMF.md).

Regla de oro: **empieza en `observe`**. El registro del provider no cambia la
fase de enforcement; los comandos siguen en dry-run hasta que subes a enforce a
propósito (y el wipe siempre exige la doble llave).

## 3. Dónde viven las credenciales

- El secreto de cada provider se guarda **aislado por tenant** en
  `integration.json` con permisos `0600`, en la misma frontera de confianza que
  el `.env` de credenciales del core.
- **Nunca** se re-emite al cliente: `GET /api/providers` devuelve el provider
  enmascarado (sin `secret`, `api_key`, `client_secret`, `refresh_token`…),
  solo con el flag `configured` y el `segment`.
- **Nunca** se escribe en `cloud_state.json` ni en logs ni en el audit trail.
- El dato geoespacial no sale de la máquina: el multi-UEM correlaciona en local.

## 4. La API por debajo (para automatizar)

El wizard del dashboard llama a estos endpoints; puedes usarlos igual desde un
script con una sesión válida y `engine:config`:

- `GET  /api/providers/catalog` — UEM disponibles y sus campos.
- `POST /api/providers/test` — prueba las credenciales **antes** de guardar
  (sin persistir nada).
- `POST /api/providers` — registra/actualiza un provider. Body:
  `{"name": "fleet", "endpoint": "...", "api_key": "...", "segment": "portátiles"}`.
- `GET  /api/providers` — lista los providers registrados (enmascarados) y su
  salud.
- `DELETE /api/providers/<name>` — quita un provider (exige `engine:config`).

## 5. Verificación

- Los dos conectores aparecen en **Integraciones UEM**, cada uno con su pill de
  segmento y `· conectado`.
- `GET /api/providers` los lista sin filtrar ningún secreto.
- El audit log (`GET /api/audit`) tiene un `provider.registered` por cada alta,
  con la cadena de integridad intacta.

Más contexto: [índice de integraciones](../README.md) ·
[matriz de ubicación](LOCATION_MATRIX.md).
