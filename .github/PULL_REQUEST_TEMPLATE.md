<!--
Plantilla de Pull Request para Geofence UEM.
Todos los apartados son OBLIGATORIOS salvo los marcados como opcionales.
-->

## Descripción
<!-- Explica qué cambiaste y por qué. Referencia issues con #número si aplica. -->

## Tipo de cambio
- [ ] Bugfix (corrección de un comportamiento incorrecto)
- [ ] Nueva funcionalidad del core (Apache-2.0)
- [ ] Nuevo adaptador MDM (`core/adapters/<mdm>.py`)
- [ ] Documentación
- [ ] Refactor / mantenimiento (sin cambio de comportamiento)

## Tests contra mock (CI)
- [ ] `python3 tests/run_tests.py` pasa en local (sin datos de tenants reales)
- [ ] Añadí/actualicé tests contra `unittest.mock` para mi cambio
- [ ] `node --check static/app.js` no reporta errores (si toqué el frontend)

## Para adaptadores MDM (obligatorio si aplica)
**Nombre del MDM:** <!-- p. ej. Intune, Jamf, Fleet -->

Checklist de la interfaz `MDMAdapter` (`core/adapters/base.py`) — marca todo lo
que implementaste y probaste contra mock:
- [ ] `authenticate()` / gestión de credenciales
- [ ] `get_devices()` (listado de dispositivos de la flota)
- [ ] `get_device_location(device_id)` (ubicación actual)
- [ ] `lock(device_id)`
- [ ] `wipe(device_id)`
- [ ] `message(device_id, text)`
- [ ] `locate(device_id)`
- [ ] `reboot(device_id)`
- [ ] El adaptador se registra en el discovery del core y aparece en el dashboard
- [ ] `tests/test_adapter_<mdm>.py` cubre happy path + al menos un caso de error

## Notas adicionales
<!-- Mapeo de endpoints del UEM, decisiones de diseño, riesgos. -->
