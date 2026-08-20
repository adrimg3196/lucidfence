# Loop: admin-value — hacer LucidFence imprescindible para el admin IT

Patrón según [loop-engineering](https://github.com/cobusgreyling/loop-engineering)
(mismo marco que `LOOP.md`): objetivo, cadencia, estado, ciclo, verificación,
gates humanos, presupuesto y métricas. Este loop no mantiene el repo — lo
**empuja** hacia un objetivo de producto concreto.

- **Objetivo:** que un administrador de Intune/Jamf/Applivery/Fleet que prueba
  LucidFence lo adopte porque le resuelve trabajo real, con garantías
  (mínimo privilegio, rollout observe→enforce, todo validado en runtime).
- **Cadencia:** semanal (`cron 0 5 * * 1`, lunes 05:00 UTC), sesión nueva por
  ejecución. Kill switch: deshabilitar la Routine, o `LOOP_PAUSE=1`.
- **Nivel actual:** **L2 (asistido)** — ver "Verificación y niveles".
- **Riesgo:** medio (puede mergear PRs que pasen el gate; nunca toca la lista
  de gates humanos).

## Estado (memory spine)

La memoria durable vive en `docs/internal/STATE.md`, sección
**"Loop admin-value"**: backlog priorizado, en curso, watch list, ruido
descartado y overrides del propietario. Cada run la lee al empezar y la
reescribe al terminar. El historial va a `docs/internal/loop-run-log.md`
(append-only, formato existente).

## Ciclo (una ejecución)

1. **Leer estado**: `STATE.md` (sección admin-value) + run-log + issues/PRs
   abiertos + últimos fallos de CI.
2. **Triage** con la pregunta única: *"¿qué es lo siguiente que más acerca el
   producto a imprescindible para un admin real?"* Reordenar el backlog si la
   evidencia lo pide (no por gusto).
3. **Ejecutar UNA mejora** (máx. 1 PR por run): implementación + tests +
   checks de `scripts/runtime_validation.py` si añade claims ejecutables.
4. **Verificar**: suite honesta + batería runtime + gate QA del repo
   (CI verde + `mergeable` + comentario `VEREDICTO QA: APTO` con evidencia).
5. **Mergear** solo si pasa el gate Y no toca la lista de gates humanos.
   Si la toca: dejar la PR abierta y escalar al propietario.
6. **Escribir estado**: actualizar `STATE.md`, apéndice en run-log, y si el
   run descubrió trabajo nuevo, dejarlo en backlog con evidencia.
7. **Autocrítica** (2 líneas en el run-log): qué fue ruido, qué fricción hubo,
   UN ajuste para el siguiente ciclo.

## Verificación y niveles

- **L1 (report)**: triage + informe, sin PRs. Modo de arranque de cualquier
  cadencia nueva y modo degradado si el gate falla 2 runs seguidos.
- **L2 (asistido, actual)**: hasta 1 PR por run, merge solo con el gate QA
  completo. Amparado por el mandato del propietario (sesiones 2026-08-15:
  "como una empresa de software", gate + merge train WIP=1). Esto **enmienda**,
  solo para este loop, el "no auto-merge" genérico de `LOOP.md`.
- **L3 (desatendido)**: no habilitado. Requeriría decisión explícita del
  propietario escrita en `STATE.md`.

## Gates humanos (heredados de `loop-constraints.md` + producto)

Nunca se mergea sin el propietario:
- Contrato `MDMAdapter` (`lucidfence/core/adapters/base.py`), auth de
  `saas_server.py`, `lucidfence/core/notifier.py`, empaquetado Desktop,
  postura de seguridad.
- **Cambios de alcance de producto** (feature nueva no listada en el backlog
  del STATE): se abre issue con propuesta, no PR.
- Releases: el loop puede *preparar* una release (versiones + CHANGELOG +
  `.release-version`) pero el merge del PR que la publica es del propietario.

Invariantes del producto (violarlos = parar y escalar): gratis y del lado del
cliente; sin telemetría ni exfiltración de ubicación; stdlib-first; todo lo
anunciado validado en runtime.

## Modos de fallo y mitigaciones

| Fallo | Mitigación |
|---|---|
| PR sin mergear por CI rojo 2 runs seguidos | Degradar a L1, escalar con el log |
| Backlog rancio (nada mejora la adopción) | Run de solo-triage contra issues/discusiones reales de usuarios |
| Drift de claims (docs prometen lo que el código no hace) | El run añade el claim a la batería runtime o corrige el doc — es trabajo de pleno derecho |
| Runs que crecen en tokens | Cap del budget (abajo); si se toca 2 veces, partir el item |
| Reintento ciego | Regla existente: 3 fallos del verificador → nota en run-log y parar |

## Presupuesto

El de `docs/internal/loop-budget.md`: 200k tokens por run, 1 PR por run,
3 intentos máximos por fix. Un run que no puede terminar dentro del cap
termina en L1 (informe + estado actualizado), nunca a medias.

## Métricas de éxito (medibles sin telemetría)

- **Time-to-first-value**: pasos desde `brew install` hasta ver la flota
  propia en el dashboard (objetivo: bajar cada trimestre; hoy documentado
  en las guías de onboarding).
- **Claims validados**: nº de checks de `runtime_validation.py` (28 hoy) —
  debe crecer con cada feature anunciada.
- **Cobertura de onboarding**: UEMs con guía de mínimo privilegio al día
  (4/4 hoy; se rompe si un adapter nuevo llega sin guía).
- **Fricción externa**: issues/preguntas de instalación abiertas >7 días
  (objetivo: 0).
