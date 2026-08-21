# Microsoft Intune — onboarding para administradores

Guía de conexión de un tenant Intune real, con mínimo privilegio y rollout
seguro. Tiempo estimado: 20 minutos, sin tocar ningún dispositivo (arrancas
en modo observación).

> Antes de empezar, lee la [matriz de ubicación](LOCATION_MATRIX.md): qué
> fidelidad de ubicación da Intune de verdad y qué alternativas hay. Evita
> sorpresas en la primera demo.

## 1. App registration en Microsoft Entra

1. Entra ID → **App registrations → New registration**. Nombre sugerido:
   `lucidfence-connector`. Single tenant. Sin redirect URI (client credentials).
2. **Certificates & secrets → New client secret**. Guarda el valor (solo se
   muestra una vez) y anota la caducidad para rotarlo.
3. **API permissions → Microsoft Graph → Application permissions**, según la
   fase del rollout:

| Fase | Permisos de aplicación | Qué habilita |
|---|---|---|
| Piloto (observar) | `DeviceManagementManagedDevices.Read.All` | Inventario de dispositivos; ninguna acción posible aunque se intente |
| Enforce | + `DeviceManagementManagedDevices.PrivilegedOperations.All` | `lock`, `wipe`, `clear_passcode`, `reboot`, `locate`, `message` |
| Conditional Access | + `Device.ReadWrite.All` | `set_compliance` (PATCH `isCompliant` del objeto Entra) |

4. **Grant admin consent** para el tenant.

Empieza solo con la fila de piloto: si la app no tiene el permiso, la acción
es imposible a nivel de plataforma, no solo a nivel de config.

## 2. Configuración en LucidFence

Credenciales por variables de entorno (no las metas en el YAML):

```bash
export INTUNE_TENANT_ID="<GUID del tenant>"
export INTUNE_CLIENT_ID="<client_id de la app>"
export INTUNE_CLIENT_SECRET="<secret>"
```

Config del tenant:

```yaml
mode: live
enforcement:
  mode: observe          # fase 1: todo dry-run, solo incidentes y auditoría
uem:
  adapter: intune
interval_seconds: 900    # ver "cadencia" en docs/operations/DAY2.md
```

## 3. Verificar la conexión

```bash
lucidfence validate-config   # prueba el mapeo location_source contra la API real
lucidfence doctor            # diagnóstico general de la instalación
```

Con el servidor arrancado, `GET /api/status` debe mostrar
`"enforcement": {"mode": "observe", ...}` y la flota en `/api/devices`.

## 4. Rollout: de observación a enforcement

Sigue el runbook de [ENFORCEMENT.md](../operations/ENFORCEMENT.md). Resumen:

```yaml
# fase 2 (tras >=2 semanas de observación y revisión de incidentes)
enforcement:
  mode: enforce
  live_actions: ["message", "set_compliance"]   # lo reversible primero
# fase 3 (si de verdad lo necesitas)
enforcement:
  mode: enforce
  live_actions: ["message", "set_compliance", "lock"]
# wipe: nunca por defecto; exige doble llave
enforcement:
  mode: enforce
  live_actions: ["lock", "wipe"]
  allow_wipe: true
  wipe_allowlist: ["<device_id-1>", "<device_id-2>"]
```

## 5. `set_compliance` y Conditional Access

La remediación de menor riesgo en un tenant Microsoft no es bloquear el
dispositivo: es marcarlo **no conforme** para que Conditional Access le corte
el acceso a los recursos. LucidFence lo implementa resolviendo
`managedDevice → azureADDeviceId → objeto /devices` y haciendo
`PATCH isCompliant` vía Graph.

Honestidad sobre los límites: Microsoft solo acepta escrituras de
`isCompliant` desde apps MDM aprobadas o integraciones de *compliance
partner* (en Windows de forma general; en Apple puede rechazarlo). Si Graph
rechaza el PATCH, LucidFence devuelve el error **verbatim** en el resultado
de la acción para que veas el motivo real. Pruébalo primero con
`enforcement.mode: observe` (verás el `would_send` exacto).

## Problemas típicos

- `401/403 Graph rejected` → falta admin consent o el permiso de la tabla.
- `device_not_found` → el `device_id` es el **managed device id** de Intune,
  no el objeto de Entra ni el serial.
- `no_azuread_device` en `set_compliance` → el dispositivo no tiene objeto en
  Entra; Conditional Access no le aplica.
- Rate limits de Graph → sube `interval_seconds` (guía en
  [DAY2.md](../operations/DAY2.md)).
