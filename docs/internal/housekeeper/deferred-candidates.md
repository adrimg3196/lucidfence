# Candidatos diferidos (se listan, nunca se borran)

Candidatos de limpieza detectados pero SIN prueba suficiente de bajo riesgo.
Un candidato sale de aquí solo cuando un ciclo consigue la evidencia (y
entonces se limpia vía PR) o cuando el propietario decide. Nunca se borra
la entrada: se anota la resolución.

## Abiertos

- **2026-08-16 · Unificar `docs/roadmap/ROADMAP_Q3.md` y `ROADMAP_Q3_2026.md`** —
  dos roadmaps de Q3 con solapamiento aparente pero contenido distinto
  (boards `uem-ops` vs `lucidfence`, principios distintos; 63 vs 112 líneas;
  ambos tocados en agosto). `ROADMAP_Q3.md` está referenciado por
  `docs/internal/CEO_PRODUCT_REVIEW_2026-07-27.md`. Decidir cuál es canónico
  es decisión de producto, no de limpieza → diferido al propietario.
- **2026-08-16 · `loop_improve.py` (raíz)** — parece legacy (excluido del
  tarball en `build.sh`) pero está referenciado por `saas_server.py`,
  `lucidfence/core/roadmap_tooling.py`, `tests/test_audit_regressions.py`,
  `roadmap.json` y docs. NO es código muerto demostrable; requiere análisis
  de si las referencias son ejecutables o históricas.
- **2026-08-16 · `ZERO-BACKLOG.md` (raíz)** — solo referenciado por el
  exclude de `build.sh`; probablemente rancio, pero borrar un doc de la raíz
  del repo del propietario sin su OK no cumple el listón de certeza.
- **2026-08-16 · Sección "Stabilization QA (2026-07-20)" de
  `docs/internal/STATE.md`** — declara "Base v1.2.0. Próximo hito v1.3.0"
  (hoy: v1.5.0 publicada). Es memoria del loop de mantenimiento del
  propietario; actualizarla debería hacerlo un run de ese loop, no el
  Housekeeper → diferido con aviso.

## Resueltos

(ninguno aún)
