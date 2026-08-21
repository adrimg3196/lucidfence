# Jamf Pro — onboarding para administradores

Conexión de un Jamf Pro real con un API client de mínimo privilegio y rollout
en observación. Tiempo estimado: 15 minutos.

> Jamf no expone ubicación continua por API — lee primero la
> [matriz de ubicación](LOCATION_MATRIX.md) para decidir tu fuente de
> ubicación (osquery, adapter iOS, o solo postura/conformidad).

## 1. API client en Jamf Pro

1. **Settings → System → API roles and clients → New API role.** Dale solo
   los privilegios de la fase actual:

| Fase | Privilegios del API role | Qué habilita |
|---|---|---|
| Piloto (observar) | `Read Mobile Devices` / `Read Computers` | Inventario; ninguna acción |
| Enforce | + `Send Mobile Device Remote Lock Command`, `Send Mobile Device Remote Command to Wipe a Device`, `Create Mobile Device Remote Commands` (elige solo los que vayas a usar) | `lock`, `wipe`, `reboot`, `clear_passcode`, `message` |

2. **New API client**, asígnale el role, habilítalo y guarda `client_id` +
   `client_secret` (el secret se muestra una vez).

## 2. Configuración en LucidFence

```bash
export JAMF_BASE_URL="https://tu-org.jamfcloud.com"
export JAMF_CLIENT_ID="<client_id>"
export JAMF_CLIENT_SECRET="<client_secret>"
```

```yaml
mode: live
enforcement:
  mode: observe
uem:
  adapter: jamf
```

Verifica con `lucidfence validate-config` y `lucidfence doctor`; después,
`GET /api/devices` debe listar la flota.

## 3. Rollout

El runbook completo está en [ENFORCEMENT.md](../operations/ENFORCEMENT.md):
observe → enforce con `live_actions` acotadas → `wipe` solo con
`allow_wipe` + `wipe_allowlist`. El API role es tu segunda línea de defensa:
si no incluye el privilegio del comando, Jamf lo rechaza aunque LucidFence
lo pida.

## 4. DDM (declarativo)

Para dispositivos Apple con DDM, el adapter soporta `apply_ddm`,
`ddm_status` y `ddm_sync`: LucidFence construye las declarations y Jamf las
entrega por su canal declarativo. Si el dispositivo no soporta DDM, la
acción degrada al camino imperativo de siempre (`fallback: imperative`).

## 5. Conformidad y Conditional Access

`set_compliance` **no existe en Jamf** como comando de API y LucidFence lo
degrada con ese mensaje en vez de simular que funciona. El mecanismo real en
el ecosistema Jamf:

- **Smart groups**: la pertenencia se recalcula con el inventario; usa los
  atributos que LucidFence escribe vía webhook/exports si quieres reflejar
  incidentes.
- **Jamf ↔ Microsoft compliance partner** (Jamf Pro + Intune partner
  compliance): Jamf reporta la conformidad del Mac a Entra y Conditional
  Access actúa. Configúralo en Jamf, no en LucidFence.

## Problemas típicos

- `auth_error` al primer uso → el API client está deshabilitado (se crean
  deshabilitados por defecto) o el role no tiene el privilegio.
- Comandos aceptados pero sin efecto → el dispositivo no tiene supervisión o
  el tipo de comando no aplica a esa plataforma; revisa el historial de
  comandos del dispositivo en Jamf.
- Rate limits → sube `interval_seconds` (guía en [DAY2.md](../operations/DAY2.md)).
