# Fleet MDM adapter

> Guía de onboarding para administradores (token API-only, ubicación con
> osquery, rollout): [docs/integrations/FLEET.md](../integrations/FLEET.md).
> Este documento es la referencia técnica del adapter.

LucidFence soporta **Fleet** (`fleetdm.com`) como fuente de acciones UEM
remotas. Un admin de Fleet puede mandar lock/wipe/reboot/message a su flota
directamente desde el dashboard de LucidFence.

## Configuración (5 minutos)

1. Crea un **API token** en tu servidor Fleet (`Settings → Users → API tokens`,
   o usa el token de la cuenta de servicio).
2. Apunta LucidFence a tu Fleet en `config.json`:

```json
{
  "mode": "live",
  "dry_run": true,
  "uem": {
    "adapter": "fleet",
    "endpoint_template": "https://fleet.tu-org.com",
    "remediation_webhook_url": ""
  },
  "fleet": {
    "api_token": "TU_FLEET_API_TOKEN"
  },
  "server": { "host": "127.0.0.1", "port": 8765 }
}
```

> `dry_run: true` construye las peticiones pero no las envía. Pásalo a `false`
> cuando quieras ejecutar acciones reales sobre la flota.

3. Variables de entorno equivalentes (no pongas el token en el repo):

```bash
export FLEET_BASE_URL="https://fleet.tu-org.com"
export FLEET_API_TOKEN="TU_FLEET_API_TOKEN"
```

4. Arranca:

```bash
python3 saas_server.py   # dashboard en http://127.0.0.1:8765
```

## Acciones soportadas

| Acción LucidFence | Endpoint Fleet            | Notas                        |
|-------------------|--------------------------|------------------------------|
| `lock`            | `POST /device/{id}/lock` |                              |
| `wipe`            | `POST /device/{id}/wipe` |                              |
| `reboot`          | `POST /device/{id}/restart` |                          |
| `message`         | `POST /device/{id}/message` | requiere `params.message`  |
| `custom`          | (sin mapeo)              | devuelve `ok` en mock        |

Acciones que Fleet no expone vía API (`locate`, `clear_passcode`, DDM) degradan
a `unsupported_action` — el dashboard no falla.

## Sin token = mock

Si no defines `FLEET_BASE_URL`/`FLEET_API_TOKEN`, el adapter corre en **mock**:
`execute` devuelve `ok: True, mock: True`. Útil para validar el flujo sin
tocar la flota.

## Estado de la ubicación (geofencing real)

El adapter Fleet de esta versión ejecuta **acciones**. La ingesta de
**ubicación en vivo** desde Fleet (vía osquery `whereami` / GPS en dispositivos
con MDM) es un paso posterior: hoy la geovalla sobre flota Fleet se alimenta
desde el modo `simulation` o desde un `LocationSource` que tú aportes.

Para geofencing sobre tu flota real con Fleet, abre un issue etiquetado
`adapter-fleet` pidiendo el `FleetLocationSource` (osquery).

## Tests

`tests/test_adapter_fleet.py` cubre el contrato SDK, dry-run y el live path con
`requests` mockeado (sin red). Corre con `python3 tests/run_tests.py`.
