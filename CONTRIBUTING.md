# Contribuyendo a Geofence UEM

¡Gracias por tu interés en contribuir! Geofence UEM es un **dashboard local de
geofencing para flotas UEM** (multi-tenant) que hoy funciona con Applivery y se
está abriendo a **múltiples MDM** (Intune, Jamf, Fleet…) mediante adaptadores.

## Modelo open-core

El repositorio es **open-core** con dos capas claras:

| Capa | Licencia | Qué incluye |
|------|----------|-------------|
| **Core (open source)** | Apache-2.0 | Glue, motor de geofencing, dashboard, almacenamiento de estado, y la **interfaz `MDMAdapter`** + adaptadores comunitarios. |
| **Enterprise on-prem (cerrado)** | Propietaria | *Risk Engine* explicable, correlación **CVE** y orquestación **SOAR**. Se distribuye por separado; no se aceptan PRs contra este código aquí. |

Todo lo que contribuyas al core (incluidos nuevos adaptadores MDM) se publica
bajo **Apache-2.0**. No incluyas código, secretos ni lógica del módulo Enterprise.

## Cómo crear un adaptador MDM

Los adaptadores viven en `core/adapters/` y siguen una interfaz común
(`MDMAdapter`, definida en `core/adapters/base.py`). Esto permite que el motor de
geofencing y el dashboard funcionen con cualquier UEM sin cambios.

1. **Copia el adaptador de referencia**:
   ```bash
   cp core/adapters/applivery.py core/adapters/<mdm>.py
   ```
   donde `<mdm>` es el nombre del proveedor en minúsculas (p. ej. `intune`,
   `jamf`, `fleet`).

2. **Implementa la interfaz `MDMAdapter`** de `core/adapters/base.py`. Debes
   cubrir todos los métodos abstractos (autenticación, obtención de dispositivos
   y ubicación, y ejecución de acciones como `lock`, `wipe`, `message`,
   `locate`, `reboot`). Mantén la misma firma y semántica que Applivery para no
   romper el motor.

3. **Añade tests contra mock**. No se aceptan adaptadores sin pruebas. Crea
   `tests/test_adapter_<mdm>.py` que:
   - instancie el adaptador con credenciales/credenciales simuladas,
   - simule las respuestas HTTP del UEM con `unittest.mock`,
   - verifique cada método de la interfaz (happy path + al menos un error).

4. **Registra el adaptador** en el discovery del core (donde se cargan los
   adaptadores disponibles) para que aparezca en el dashboard.

5. **Abre un Pull Request** siguiendo la plantilla `.github/PULL_REQUEST_TEMPLATE.md`.
   El CI (`python3 tests/run_tests.py`) debe pasar en local antes de pedir revisión.

## Adapter Bounty Sprint 🏁

Periódicamente lanzamos un **Adapter Bounty Sprint**: recompensamos con
reconocimiento y menciones a quienes entreguen adaptadores completos y testeados
para MDM populares. Los objetivos del sprint se anuncian en el tablero de issues
(con la etiqueta `bounty`). Reglas:

- El adaptador debe pasar CI y seguir la interfaz `MDMAdapter` al pie de la letra.
- Documenta en el PR el mapeo de acciones del UEM (qué endpoints usas).
- El primero en fusionar un MDM nuevo se lleva el "first adapter" del sprint.

## Hall of Fame 🏆

Adaptadores que ya forman parte del core gracias a la comunidad:

| MDM | Autor | Fecha |
|-----|-------|-------|
| (tu nombre aquí) | (tu usuario) | — |

Cada adaptador fusionado añade una fila a esta tabla. ¡Sé el primero!

## Buenas prácticas

- Usa `python3 -m venv` y `pip install -r requirements.txt` antes de probar.
- Corre `python3 tests/run_tests.py` localmente (no ejecutes datos de tenants reales).
- Mantén los mensajes de commit en español o inglés, claros y atómicos.
- Sigue la guía de estilo del repo: sin credenciales hardcodeadas, sin prints de
  secretos, logging vía el módulo `logging`.
