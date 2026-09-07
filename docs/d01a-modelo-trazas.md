# D01a — modelo de postura y trazas (parte de T01)

Base: `d96e74578b8a92e54d2048d14d9191c5d10f49a9`. Esta entrega no cierra T01.

- `Device.Posture`: `rooted`, `os_outdated` y `osquery_config_valid` son
  `*bool`: nil es desconocido; false y true son observaciones explícitas.
  JSON ausente/null se lee como nil en un dispositivo nuevo. La salida omite
  desconocidos y conserva false. Se decodifica cada observación en un valor
  nuevo, no encima de una observación anterior (semántica de `encoding/json`).
- `hardware_health` solo contiene métricas informadas; nil/mapa vacío no aporta
  evidencia y se omite al serializar. `country`/`site` vacíos son no informados.
  Un dispositivo sin postura emite `posture:{}`; OpenAPI la deja opcional para
  aceptar también respuestas M1. No se modifica ningún campo obligatorio M1.
- `action.Result` añade `route_id`, `policy_id`, `playbook_id`, `severity`,
  `blocked` y `error_type`, todos omitidos a valor cero. Los resultados M1
  conservan su forma y `at`; no se renombra a `timestamp`. La ausencia de
  `blocked` no acredita autorización ni ejecución: son trazas, no guardarraíles.
- Pruebas: round-trip real `encoding/json` (false/true/desconocido y campos M1),
  reapertura del store JSON/JSONL y check de postura desconocida contra binario
  demo. No se afirma ingesta ni ejecución live UEM con estos casos locales.
- Pendientes: D01b (modelo/evaluación de integridad), D01c (reloj y dwell),
  `Signals` con D02, integración en motor, guardarraíles, productores de trazas
  y postura real. No se crean campos de integridad falsamente evaluados.
- Gate: `make verify` y job security de CI; revisión CTO independiente ligada
  al SHA y aprobación de propietario para cambios en `internal/battery/`.
  Sin merge, automerge, release ni declaración de producción en esta entrega.
