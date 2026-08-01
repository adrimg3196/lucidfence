---
name: mdm-adapter-guide
description: Cómo escribir un adaptador MDM nuevo para LucidFence implementando la interfaz MDMAdapter, dónde ubicarlo (lucidfence/core/adapters/), cómo testearlo contra mock y el flujo de Pull Request. Usa cuando el usuario quiere añadir soporte para un nuevo UEM (Intune, Jamf, Fleet, etc.), crear un adapter, o entender la interfaz MDMAdapter.
---

# Guía de adaptadores MDM para LucidFence

LucidFence es multi-MDM mediante **adaptadores** que implementan una interfaz
común. El motor de geofencing y el dashboard hablan con cualquier UEM a través
de `MDMAdapter`, sin conocer el proveedor.

## Dónde vive el código

- Interfaz base: **`lucidfence/core/adapters/base.py`** → clase `MDMAdapter` (abstracta).
- Adaptadores concretos: **`lucidfence/core/adapters/<mdm>.py`** (p. ej. `applivery.py`).
- Tests: **`tests/test_adapter_<mdm>.py`**.

## Pasos para crear un adaptador

1. **Copia la referencia**:
   ```bash
   cp lucidfence/core/adapters/applivery.py lucidfence/core/adapters/<mdm>.py
   ```
   `<mdm>` en minúsculas (intune, jamf, fleet…).

2. **Implementa `MDMAdapter`** de `lucidfence/core/adapters/base.py`. Debes cubrir todos los
   métodos abstractos con la misma firma y semántica que Applivery:
   - `authenticate()` — gestiona credenciales/tokens del UEM.
   - `get_devices()` — lista la flota de dispositivos.
   - `get_device_location(device_id)` — devuelve la ubicación actual.
   - `lock(device_id)`, `wipe(device_id)`, `message(device_id, text)`,
     `locate(device_id)`, `reboot(device_id)` — acciones UEM.

3. **Registra el adaptador** en el discovery del core para que aparezca en el
   dashboard (mismo punto donde se cargan los adaptadores disponibles).

4. **Tests contra mock** (obligatorio, sin red real):
   - Instancia el adaptador con credenciales simuladas.
   - Usa `unittest.mock` para simular las respuestas HTTP del UEM.
   - Verifica cada método (happy path + al menos un caso de error).
   - No uses datos de tenants reales.

   ```bash
   poetry run python3 tests/run_tests.py
   ```

5. **Abre el PR** usando `.github/PULL_REQUEST_TEMPLATE.md`. El CI ejecuta
   `poetry run python3 tests/run_tests.py` (Python 3.11+) y `node --check static/app.js`.

## Contrato de la interfaz (resumen)

| Método | Responsabilidad |
|--------|-----------------|
| `authenticate` | Obtener/refrescar token o sesión del UEM. |
| `get_devices` | Listar dispositivos con su identificador. |
| `get_device_location` | Ubicación (lat/lon + timestamp) del dispositivo. |
| `lock` / `wipe` | Acciones de contención remota. |
| `message` | Enviar mensaje al dispositivo. |
| `locate` | Forzar/localizar posición. |
| `reboot` | Reinicio remoto. |

Devuelve estructuras consistentes con Applivery (dicts con los mismos campos)
para no romper el motor ni el contrato del frontend.

## Convenciones

- Sin credenciales hardcodeadas; usa el módulo `lucidfence/core/secrets.py` o variables de
  entorno.
- Nunca imprimas secretos; usa `logging`.
- Mantén el adaptador aislado: el core no debe importar lógica específica del UEM
  fuera de `lucidfence/core/adapters/`.

## Flujo de PR

1. Fork → rama `feature/adapter-<mdm>`.
2. Implementa + tests contra mock.
3. `poetry run python3 tests/run_tests.py` en verde localmente (con Python >=3.11).
4. PR con la plantilla: tipo de cambio, tests pasando, y para adapters el
   **nombre del MDM** + checklist de `MDMAdapter`.

> El módulo Enterprise (Risk Engine / CVE / SOAR) es cerrado: no se aceptan PRs
> contra él en este repo.
