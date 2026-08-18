# Señales de tendencia → producto (append-only)

Memoria del loop Tendencias (`docs/internal/trends/README.md`). Cada entrada:
fecha, señal, fuente (URL), etiqueta de confianza ([Oficial]/[Prensa]/[Rumor]),
y decisión (implementada con nº de PR, o derivada al backlog de Admin-value, o
descartada con motivo). Nunca se borra; el estado se actualiza en su sitio.

<!-- Formato de entrada:
## AAAA-MM-DD
- **Señal:** <qué cambió en el ecosistema>. Fuente: <URL> [Oficial|Prensa|Rumor].
  **Impacto para LucidFence:** <por qué importa al admin>.
  **Decisión:** implementada (#PR) | backlog Admin-value | descartada (<motivo>).
-->

## 2026-08-18 (primera pasada)

- **Señal:** WWDC 2026 — Apple hace **DDM obligatorio** en la generación OS 27
  (iOS/iPadOS/macOS 27) y añade nuevos *status items*: Lockdown Mode, salud de
  hardware (baseband, cámara, Face/Touch ID, NFC, UWB), tipo de enrolamiento,
  Shared iPad; además, 7 configs DDM nuevas para el stack de red y migración de
  perfiles legacy a declarativo. Fuentes:
  [Jamf](https://www.jamf.com/blog/wwdc26-key-takeaways-for-apple-admins/) [Oficial-vendor],
  [42Gears](https://www.42gears.com/blog/wwdc-2026-whats-new-apple-device-management/) [Prensa],
  [ManageEngine](https://www.manageengine.com/mobile-device-management/articles/wwdc-2026-apple-admins-mdm-changes.html) [Prensa].
  **Impacto para LucidFence:** los nuevos status (Lockdown Mode, salud de hardware)
  son postura correlacionable por el motor de riesgo; ya soportamos DDM
  (`apply_ddm`, `supports_ddm`) y tenemos canal `device_state` para readback.
  **Decisión:** demasiado grande para un ciclo → item citado en el backlog de
  Admin-value (`STATE.md` #7), empezando por el status booleano de Lockdown Mode.

- **Señal:** osquery **5.23.1** (2026-06-24) — release de fixes de seguridad:
  heap buffer overflow en las tablas `processes`/`authenticode` de Windows y un
  use-after-free en `process_file_events` de Linux. Fuente:
  [osquery releases](https://github.com/osquery/osquery/releases) [Oficial].
  **Impacto para LucidFence:** bajo/indirecto — **no empaquetamos osquery**, solo
  leemos su results-log/`osqueryi` (`osquery_posture.py`); la superficie afectada
  (tablas Windows) no está en nuestra allow-list de queries. **Decisión:** anotado;
  sin acción de producto. Recomendar en docs que el operador corra osquery ≥5.23.1.

