# ZERO-BACKLOG

Backlog operativo de los turnos nocturnos de Zero. Los docs del repo
(AGENTS.md, LOOP.md, KANBAN.md) son contexto; esto es el registro de turnos.

## Roles log

| Fecha | Rol | Resumen |
|-------|-----|---------|
| 2026-07-27 | BARRENDERO | Completada la migración a "gratis + donaciones": fuera Pro/Enterprise, `/api/plan*`, capability `org:billing` y 4 ficheros `static/saas_views*.js` muertos (530 líneas). Fix de causa raíz en `log_message` (POST a ruta desconocida devolvía 500 en vez de 404). Docs de pricing reescritos. Suite 267 PASS (= baseline main). |

## Hecho (2026-07-27)

- Migración free-only terminada (venía a medias sin commitear de un turno anterior).
- Bug preexistente arreglado: sanitizador de logs rompía `send_error(404)` en POST/DELETE (format `%d` con str) → 500s falsos.
- SBOM regenerado tras borrar los JS muertos.
- `.github/FUNDING.yml` (github: adrimg3196) — **pendiente: Adri debe activar GitHub Sponsors** para que el botón funcione.

## Ideas

- Purga de menciones a planes de pago en docs legacy de marketing (`docs/launch-copy/`, `docs/marketing-copy.md`, `KANBAN.md`, `docs/PILOT_RUNBOOK.md`).
- Capabilities `org:delete` y `user:role` están en la matriz RBAC pero ningún endpoint las comprueba — decidir: implementar endpoints o borrarlas.
- Botón "Apoya el proyecto" (donaciones) discreto en el dashboard, alimentado por `FREE_PLAN.donations`.
- Migrar los 2 tests multiuem que fallan por `TypeGuard` (Python 3.9 del sistema) a `typing_extensions` o guardas de versión — único rojo de la suite.
- Rehacer `tests/coverage_analysis_cloud.md` tras la limpieza de billing.

## Notas para el siguiente turno

- Rama de trabajo: `zero-nightly`. La rama local `gt/migrar-a-gratis-donaciones` quedó obsoleta (sin commits propios) — borrar cuando el PR se mergee.
- La suite se ejecuta con `python3 tests/run_tests.py` (hermética: exige el puerto 8765 libre; mata cualquier `saas_server.py` colgado antes).

## API-SDK-MCP

Directriz de producto de Adri (2026-07-28, vigente siempre): LucidFence se diseña
API-first con tecnología 100% actual, contemplando TODOS los escenarios de consumo.
Progreso de cada frente se registra aquí.

- [ ] **API pública**: spec OpenAPI versionada en el repo como contrato único; el
      dashboard consume la misma API (sin rutas privadas duplicadas).
- [ ] **SDKs oficiales**: Python y/o JS, ligeros, generados sobre la spec,
      publicables gratis (PyPI/npm).
- [ ] **Servidor MCP oficial**: agentes IA gestionan geocercas/eventos/alertas vía
      Model Context Protocol. Candidato ideal a prototipo de una noche.
- [ ] **Webhooks/eventos** para integraciones de terceros.

Restricción transversal: coste 0 (free tiers), sin dependencias obsoletas.
