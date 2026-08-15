# Fleet — onboarding para administradores

Fleet (fleetdm.com) encaja con LucidFence de forma natural: Fleet aporta la
telemetría osquery y el canal MDM open-source; LucidFence correlaciona esa
postura con geocercas, rutas y riesgo explicable, y devuelve las acciones.
Tiempo estimado: 15 minutos.

Referencia técnica del adapter: [docs/adapters/FLEET.md](../adapters/FLEET.md).

## 1. Token de API en Fleet

1. Crea un usuario **API-only** (recomendado, así el token no muere con la
   sesión de un humano): `fleetctl user create --api-only ...` o desde la UI.
2. Genera su token: **Settings → Users → API tokens** (o `fleetctl login`).
3. El role del usuario limita el blast radius: `observer` para el piloto
   (solo lectura), `maintainer`/`admin` solo cuando pases a enforce — los
   comandos MDM de Fleet (lock/wipe) exigen esos roles.

```bash
export FLEET_BASE_URL="https://fleet.tu-org.com"
export FLEET_API_TOKEN="<token>"
```

## 2. Configuración en LucidFence

```yaml
mode: live
enforcement:
  mode: observe
uem:
  adapter: fleet
  endpoint_template: "https://fleet.tu-org.com"
```

Verifica con `lucidfence doctor` y revisa que `/api/devices` lista los hosts.

## 3. Ubicación con Fleet: osquery, no GPS

Fleet **no da GPS**: sus hosts son sobre todo portátiles y servidores. Lo que
sí da (vía osquery) es señal de red utilizable como ubicación aproximada y,
sobre todo, **postura**:

- Integración osquery de LucidFence: [OSQUERY.md](OSQUERY.md) — SO,
  cifrado de disco, almacenamiento, integridad de la propia config.
- Geofencing "lógico": geocercas por red corporativa/país (IP/SSID) en vez
  de radio GPS. Honestidad sobre la fidelidad: [LOCATION_MATRIX.md](LOCATION_MATRIX.md).

La combinación útil en la práctica: Applivery/adapter iOS para la flota
móvil con GPS, Fleet para portátiles con postura osquery, ambos a la vez
vía multi-UEM (`providers` en config).

## 4. Acciones

El adapter mapea el contrato LucidFence a los comandos MDM de Fleet:
`lock`, `wipe`, `reboot` (restart), `message`. `locate` y `clear_passcode`
no existen en Fleet y degradan con `unsupported_action` — el resultado te lo
dice, no falla en silencio.

El rollout es el mismo runbook que el resto: [ENFORCEMENT.md](../operations/ENFORCEMENT.md)
(observe → enforce con `live_actions` → wipe con doble llave). El role del
usuario API de Fleet es la segunda línea: un `observer` no puede ejecutar
comandos aunque LucidFence los pida.

## 5. Conformidad y Conditional Access

`set_compliance` **no aplica a Fleet**: la conformidad la calculan sus
propias policies osquery y LucidFence lo degrada con guía en el mensaje.
El camino real para cortar acceso: la integración nativa de Fleet con
**Microsoft Entra conditional access** (Fleet marca el host según sus
policies y Entra bloquea el acceso). Configúrala en Fleet; usa LucidFence
para decidir *qué* policies de Fleet merecen incidente (webhook de
incidentes → automatización).

## Problemas típicos

- `401` → token caducado (los de sesión expiran; usa usuario API-only) o
  URL base sin `https://`.
- Comando aceptado y host sin cambios → el host no tiene MDM enrolado en
  Fleet (osquery solo) — lock/wipe requieren MDM activo.
- Hosts duplicados con otro UEM → usa multi-UEM (`providers`) para que cada
  dispositivo tenga un provider primario y las acciones se enruten bien.
