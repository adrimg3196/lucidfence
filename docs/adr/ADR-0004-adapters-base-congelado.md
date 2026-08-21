# ADR-0004 — `adapters/base.py` como contrato congelado

**Estado:** Accepted — ~2026-07 (contrato `MDMAdapter/v1`; regla en Constitución §Restricciones).

## Contexto

Cada UEM (Applivery, Intune, Jamf, Fleet, Workspace ONE, ChromeOS, iOS…) se
integra con un adapter. Si la interfaz que el engine consume cambia sin control,
cada adapter se rompe en silencio y el engine tiene que defenderse de
excepciones arbitrarias. El engine necesita un contrato estable y predecible: un
adapter nunca debe tumbar el ciclo de geofencing, y los tests deben correr sin
credenciales reales.

## Decisión

`lucidfence/core/adapters/base.py` define la interfaz `MDMAdapter`
**congelada**: expone `name` y `execute(device, action, params, dry_run) ->
dict`, y **jamás lanza excepción** (devuelve `{"ok": False, "error": ...}` ante
fallo). API actual: `MDMAdapter/v1`. Cambiar la forma del contrato exige **bump
de versión MAYOR y preservar el camino mock offline**. Toda implementación
conserva su mock offline para que los tests corran sin red ni credenciales.

## Consecuencias

- **A favor:** el engine trata a todos los UEM por igual; añadir un UEM nuevo es
  implementar la interfaz, no tocar el engine; los tests son herméticos;
  paridad de primera clase entre adapters (incluido Fleet).
- **En contra:** el contrato es rígido a propósito — evolucionarlo es caro
  (MAJOR); toda mejora transversal debe caber en `execute(...)->dict`.
- **Denylist absoluta** (ni con CI verde): tocar `base.py` sin bump MAJOR + mock
  offline preservado.

## Dónde vive hoy

`lucidfence/core/adapters/base.py`; implementaciones y mocks en
`core/adapters/*`; contrato en [SPEC.md §4](../architecture/SPEC.md); regla en
[CONSTITUTION.md §Restricciones](../architecture/CONSTITUTION.md); guía en
`docs/contributing/new-adapter-guide.md`.
