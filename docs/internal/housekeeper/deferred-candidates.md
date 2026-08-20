# Candidatos diferidos (se listan, nunca se borran)

Candidatos de limpieza detectados pero SIN prueba suficiente de bajo riesgo.
Un candidato sale de aquí solo cuando un ciclo consigue la evidencia (y
entonces se limpia vía PR) o cuando el propietario decide. Nunca se borra
la entrada: se anota la resolución.

## Abiertos

- **2026-08-19 · `lucidfence/core/storage.py` (módulo entero, 148 líneas)** —
  etiqueta ponytail `delete`: cero importadores en todo el repo (código,
  tests, scripts); incluye un cliente SigV4 de Cloudflare R2 hecho a mano que
  nada invoca. NO se borra en este ciclo porque `docs/operations/DEPLOY_FREE.md`
  lo referencia dos veces como parte de la historia de deploy gratis
  ("Storage de reportes … R2 free"): retirar el módulo obliga a decidir si esa
  capacidad documentada se elimina del relato de producto → decisión de
  producto/docs, no de limpieza mecánica. Evidencia: `grep -rn "core.storage\|core/storage"`
  solo devuelve el propio fichero y ese doc.
- **2026-08-19 · `lucidfence/core/secrets.py` imports muertos (`json`, `stat`)
  y variable `e` sin uso (L185)** — etiqueta ponytail `shrink`: pyflakes los
  marca, pero el fichero es superficie de credenciales/seguridad y la carta
  del ciclo prohíbe tocar guards de seguridad ("ni una línea") → diferido
  para un ciclo con revisión de seguridad explícita.
- **2026-08-19 · `lucidfence/core/adapter_marketplace.py` (`verify_index`,
  30 líneas)** — etiqueta ponytail `yagni`: su único caller es
  `tests/test_annual_roadmap.py`; ningún código de producto verifica el
  índice del marketplace. Borrarlo exigiría borrar/debilitar un test
  existente, cosa vetada por la carta → diferido hasta que el propietario
  decida si el marketplace local sigue en el roadmap.
- **2026-08-19 · `lucidfence/core/oidc.py`** — fuera de alcance deliberado
  del ciclo (auth/SSO, 6 fallos baseline conocidos en su suite); cualquier
  shrink ahí debe ir con el arreglo de esos tests, no con housekeeping.

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

- **2026-08-16 · Unificar `docs/roadmap/ROADMAP_Q3.md` y `ROADMAP_Q3_2026.md`** —
  era decisión de producto, no de limpieza. **Resuelto por el loop Roadmap**
  (ciclo 0): `docs/roadmap/PRODUCT_ROADMAP.md` es el canónico vivo; ambos Q3
  quedan archivados como snapshots históricos con banner y puntero. No se
  borran (los referencia el CEO review de julio).

- **[plankton 2026-08-20] adapters/base.py:96 — llamada requests sin timeout (bandit B113).** Un UEM colgado bloquearía el ciclo del engine para siempre. Diferido: base.py es contrato congelado (denylist: sin bump MAJOR + mock offline no se toca). Decisión para fleet-architect/iot-fleet-engineer: añadir timeout interno NO cambia la interfaz MDMAdapter — candidato a fix quirúrgico con test en el próximo ciclo que abra base.py legítimamente.
