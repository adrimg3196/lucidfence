# Loop Roadmap — el rumbo de producto, vivo y sin dueño humano

Noveno loop de la flota (propietario, 2026-08-16: *"¿hay un agente que cree
roadmap?"* → sí, este). Mantiene un **roadmap de producto vivo** a varios ciclos
vista, para que la empresa autónoma no solo mejore el producto ciclo a ciclo
(eso ya lo hace Admin-value) sino que **sepa hacia dónde va**.

## Por qué existe

Antes de este loop había maquinaria de roadmap (`lucidfence/core/roadmap_tooling.py`,
`roadmap.json`) pero estaba **congelada**: `roadmap.json` es el roadmap del
*tooling de auto-mejora* (`/loop` MoA), 18/18 features `complete`, `updated`
2026-08-01 — un artefacto histórico, no un plan vivo. Y ningún agente lo
mantenía. `product-manager` prioriza la mejora del ciclo actual, pero nadie
curaba el horizonte a trimestres. Este loop cierra ese hueco.

## Fuente de verdad

- **`docs/roadmap/PRODUCT_ROADMAP.md`** — el roadmap de producto VIVO, horizonte
  deslizante **Ahora / Próximo / Después**. Canónico.
- **`roadmap.json`** — histórico del tooling de auto-mejora, **archivado**. No se
  reabre (su schema y capabilities son de la máquina interna, no del producto).
- Snapshots `docs/roadmap/ROADMAP_Q3*.md`, `ROADMAP_2026-2027.md` — históricos,
  con banner de archivado y puntero al vivo.

## Especialista dueño

Delega en **`product-roadmap-strategist`** (`.claude/agents/`). El loop es el
departamento; el especialista decide prioridades. El humano no está en la cadena.

## Ciclo (qué hace cada run)

1. **Reconciliar.** Lo que los loops entregaron desde el último run baja de
   "Ahora" (verifica contra el run-log común y las PRs mergeadas).
2. **Recoger señal** (SOLO real, cada ítem cita origen):
   - gaps abiertos del README ("No está terminado");
   - candidatos diferidos del Housekeeper (`deferred-candidates.md`);
   - findings de Centinela (`security/findings.md`);
   - issues de terceros sin resolver (vía Growth/triage);
   - `STATE.md` y `docs/internal/plan.md`.
3. **Repriorizar** el horizonte (impacto × esfuerzo × principios: local-first,
   $0, runtime-first).
4. **Reabrir** el "Próximo/Después" y empujar el "Próximo" a la cola de
   Admin-value (derivación cruzada; no implementa).
5. **PR** a `docs/roadmap/PRODUCT_ROADMAP.md` + línea en el run-log.

## Trigger, rama y gate

- **Trigger:** Routine semanal, **viernes 21:17 UTC** (≈23:17 Madrid). Hueco
  libre del calendario: el Housekeeper NO corre la noche del viernes. Trabajo
  ligero si no hay señal nueva desde el último run (solo-refresco + nota).
- **Rama:** `claude/roadmap-loop` (propiedad exclusiva).
- **Gate:** su PR es docs (roadmap + snapshots); mergeable con el gate QA
  (`python3 scripts/verify.py` → `VEREDICTO QA: APTO`). Auto-merge en verde.
- **Reporting:** silencioso; su resultado llega al propietario vía el digest de
  Dirección. Nunca notifica salvo algo que no espera al lunes.

## Relación con los demás loops

- **Admin-value** consume el "Próximo" del roadmap para elegir la mejora del
  ciclo. El roadmap prioriza; Admin-value ejecuta.
- **Dirección** cita el estado del roadmap (qué avanzó, qué entra) en el digest.
- **Housekeeper** difiere a este loop las decisiones de producto que encuentra
  (p. ej. qué roadmap histórico es canónico) en vez de resolverlas él.
