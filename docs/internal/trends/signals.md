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


## 2026-08-19 (pasada GitHub — repos como el nuestro)

- **Señal:** Fleet (fleetdm/fleet, ~6.2k★, releases semanales) sigue invirtiendo
  en **GitOps/config-as-code** como diferenciador central: 4.90.0 añade
  detección de políticas duplicadas al aplicar YAML y errores más precisos y
  accionables en el apply; además soporte DDM "day one" (subir cualquier config
  DDM, canal device y user), *custom host vitals* (asset tag, caducidad de
  garantía) y renovación automática SCEP/ACME. Fuentes:
  [Fleet 4.90.0](https://fleetdm.com/releases/fleet-4-90-0) [Oficial],
  [Fleet GitOps docs](https://fleetdm.com/docs/configuration/yaml-files) [Oficial],
  [fleetdm/fleet](https://github.com/fleetdm/fleet) [Oficial].
  **Impacto para LucidFence:** valida el backlog evaluado #1 (políticas como
  código); nuestra mejora sobre el incumbente es apply sin servidor + replay
  what-if pre-aplicación (nadie lo tiene).
  **Decisión:** implementada este ciclo — `lucidfence apply` (validar → diff →
  what-if → aplicar atómico), rama `claude/missing-production-prs-hqdtv6`.

- **Señal:** consolidación minimalista en el MDM open-source Apple: MicroMDM
  (~2.6k★) entra en fin de soporte (finales de 2025) a favor de **NanoMDM**
  (~590★): servidor de protocolo mínimo, stateless, storage enchufable, que
  delega SCEP/TLS/enrolamiento en piezas externas. Fleet mismo se construye
  sobre nanoMDM+osquery. Fuentes:
  [micromdm/micromdm](https://github.com/micromdm/micromdm) [Oficial],
  [h-mdm review 2026](https://h-mdm.com/top-open-source-mdm-solutions-in-2026/) [Prensa].
  **Impacto para LucidFence:** la tendencia del ecosistema es exactamente
  nuestro posicionamiento — piezas pequeñas, componibles, sin lock-in
  (complemento sobre el UEM, stdlib, local-first). Refuerza el NO a "ser el
  UEM nº15" y el SÍ al panel multi-UEM neutral (backlog #12).
  **Decisión:** anotada como validación de posicionamiento; sin acción extra.

- **Señal:** Fleet persigue certificación **Common Criteria EAL4+ (BSI)** desde
  feb-2026 — el compliance verificable se vuelve argumento de compra en
  open-source. Fuente: [aimultiple](https://aimultiple.com/open-source-mdm-software) [Prensa].
  **Impacto para LucidFence:** refuerza la línea evidencia-no-certificación ya
  existente (`compliance_controls.py`, export con hash encadenado) y el ítem
  #13 del backlog (segunda opinión UEM vs observado, oro para auditores).
  **Decisión:** anotada; alimenta la priorización de #13.
