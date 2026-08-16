# docs/internal/LOOP.md — Improvement loop for LucidFence

LucidFence is a local-first, free, open-source geofencing / UEM product. This
file documents the improvement loop used to maintain it, adapting the
[loop-engineering](https://github.com/cobusgreyling/loop-engineering) patterns.
Reporting style follows [i-have-adhd](https://github.com/ayghri/i-have-adhd)
(regla 8); Growth's SEO menu follows [open-seo](https://github.com/every-app/open-seo);
Centinela's offensive method follows [Strix](https://github.com/usestrix/strix).

## Active loops

### Admin-value (L2 — asistido, cadencia semanal)
- **Patrón completo:** `docs/internal/loop-admin-value.md`.
- **Objetivo:** empujar el producto a "imprescindible para el admin IT"
  (onboarding sin fricción, rollout seguro, claims siempre validados).
- **Trigger:** Routine semanal (sábados 00:07 UTC ≈ 02:07 Madrid) que lanza
  una sesión nueva; también ejecutable a mano pidiendo "ejecuta un ciclo del
  loop admin-value".
- **Rama:** `claude/admin-value-loop` (propiedad exclusiva; ver Coordinación).
- **Gate:** hasta 1 PR por run, auto-merge en verde con el gate QA (CI +
  runtime battery + `VEREDICTO QA: APTO`); si la mejora publica una release
  (`.release-version`), esa PR la mergea el propietario (§Autonomía).
- **Estado/memoria:** sección "Loop admin-value" de `STATE.md` + run-log.

### Housekeeper (L2 — limpieza diaria, auto-merge de bajo riesgo)
- **Especificación completa:** `docs/internal/housekeeper/README.md`.
- **Objetivo:** un cleanup de housekeeping probado por día (código muerto,
  ficheros/comentarios rancios, duplicación…), con lo incierto diferido y
  listado, nunca borrado.
- **Trigger:** Routine diaria (23:13 UTC ≈ 01:13 Madrid; NO corre la noche
  del viernes — ver Coordinación); también ejecutable a mano.
- **Rama:** `claude/housekeeper` (propiedad exclusiva).
- **Gate:** máx. 1 PR nueva/día, con la evidencia de bajo riesgo en el
  cuerpo. **Auto-merge con el gate QA** (Tier A de la §Autonomía): la
  limpieza probada y CI-verde no espera a un humano — el propietario
  cambió el objetivo a "autónomo sin intervención humana" (2026-08-16),
  lo que sustituye el "merge del propietario" anterior. WIP=1 por título
  `housekeeping:`: con una abierta, el run del día es solo-refresco.
- **Estado/memoria:** `docs/internal/housekeeper/` (cards, deferred,
  metrics) + dashboard + línea en el run-log común.

### Guardián (L2 — salud de main, backlog, watchdog de la flota; diario)
- **Objetivo:** que `main` nunca amanezca rojo, que el backlog de PRs no se
  pudra, y que ningún loop se quede muerto sin que nadie lo note. Patrones
  ci-sweeper + pr-babysitter + post-merge-cleanup + backlog-drain + watchdog.
- **Trigger:** Routine diaria (04:23 UTC ≈ 06:23 Madrid).
- **Rama:** `claude/ci-sweeper` (propiedad exclusiva).
- **Responsabilidades:**
  1. *Salud de main*: si CI está rojo, diagnostica y arregla (Tier A) o
     escala; nunca deja main roto de un día para otro sin acción.
  2. *Drenaje de backlog*: es el DUEÑO de las PRs sin loop asignado (las 14
     heredadas de Jules/sesiones viejas incluidas). Cada PR abierta con >7
     días sin avanzar: rebasea y mergea las verdes con el gate QA (auth,
     seguridad y demás incluidos — auto-merge total), cierra con evidencia
     las superadas/muertas/duplicadas, y deja en "Te espera" solo lo que
     publica hacia fuera (release/outreach). Objetivo permanente: 0 zombis.
  3. *Triage de terceros* (L1): comenta y etiqueta según "Contributor PR
     triage"; a autores externos JAMÁS les mergea.
  4. *Watchdog de la flota*: lee la última línea de cada loop en el run-log;
     si un loop lleva >1 ciclo sin correr cuando debía (comparado con el
     Calendario), lo anota como INCIDENTE en el run-log para que Dirección
     lo suba al digest. (No puede re-disparar Routines desde su sesión: su
     arma es hacerlo visible, no silenciarlo.)
  5. *Limpieza post-merge*: borra ramas `claude/*` cuya PR está MERGED.
- **Gate:** todo con el gate QA completo; auto-merge (releases/outreach
  ajenos, esos no son suyos).
- **Estado/memoria:** línea por run en el run-log común.

### Deps-sweeper (L1.5 — dependencias al día; semanal)
- **Objetivo:** que los pins de `requirements.lock` no se pudran (la
  historia del pin de cryptography, issue #108, es el porqué).
- **Trigger:** Routine semanal (miércoles 21:37 UTC ≈ 23:37 Madrid).
- **Rama:** `claude/deps-sweeper` (propiedad exclusiva).
- **Gate:** PR con suite + batería runtime verdes y el diff de versiones
  razonado; **auto-merge en verde** (incl. bumps MAJOR) — el gate QA es la
  red: si un bump rompe algo, no pasa. WIP=1 por título `deps:`.
- **Estado/memoria:** línea por run en el run-log común.

### Dirección (L2 — resumen ejecutivo semanal; el ÚNICO que notifica)
- **Especificación completa:** `docs/internal/exec/README.md`.
- **Objetivo:** un informe ejecutivo semanal al propietario: lo nuevo, lo
  corregido, la tracción (con deltas), lo que espera su decisión y la salud
  de la flota de loops. El propietario no lee logs: lee esto.
- **Trigger:** Routine semanal (lunes 05:33 UTC ≈ 07:33 Madrid).
- **Rama:** `claude/exec-digest` (propiedad exclusiva).
- **Gate:** su PR es solo `docs/internal/exec/` (informe + serie de
  tracción); mergeable con gate QA (docs internos).
- **Estado/memoria:** `docs/internal/exec/` (informes + `traction.jsonl`).

### Growth (L2 — vigilar la adopción y empujarla; semanal)
- **Especificación completa:** `docs/internal/growth/README.md`.
- **Objetivo:** que la gente encuentre y use el producto. Vigila inbound
  (issues sin respuesta), menciones y superficie pública; ejecuta UN
  experimento de crecimiento por ciclo (discoverability, casos de uso,
  borradores de outreach) y lee su resultado en la serie de tracción.
- **Trigger:** Routine semanal (martes 06:17 UTC ≈ 08:17 Madrid).
- **Rama:** `claude/growth-loop` (propiedad exclusiva).
- **Gate:** cambios de superficie pública (README/Pages/topics) mergeables
  con el gate QA. **Outreach con aprobación previa del propietario**:
  lo ejecutable con la cuenta de GitHub (PR a una lista awesome-*,
  discussion, respuesta útil en un repo relacionado) se propone en una PR
  `outreach:` con el contenido exacto y el destino — **el merge del
  propietario ES la aprobación** y el siguiente run lo publica y registra
  el enlace. Fuera de GitHub (HN/Reddit/LinkedIn: el agente no tiene esas
  cuentas) queda en `docs/gtm/outbox/` para copy/paste del propietario.
  Sin spam, sin social proof inventado, sin telemetría.
- **Estado/memoria:** `docs/internal/growth/` (experiments, mentions) +
  línea en el run-log común.

### Centinela (L2 — seguridad ofensiva de aplicación; semanal)
- **Especificación completa:** `docs/internal/security/README.md`.
- **Objetivo:** atacar el propio LucidFence en localhost (metodología Strix:
  validar por PoC, no estáticamente) para cazar IDOR/aislamiento de tenant,
  authz, fuga de secretos, SSRF y XSS antes de que lleguen a producción.
  Complementa gitleaks + pip-audit del CI.
- **Trigger:** Routine semanal (jueves 22:07 UTC ≈ 00:07 Madrid).
- **Rama:** `claude/security-loop` (propiedad exclusiva).
- **Alcance autorizado:** SOLO el localhost efímero del agente; jamás infra
  de tenant ni terceros. Los fixes (incl. auth/notifier/sesión) auto-mergean
  en verde SIEMPRE con su test de regresión (falla antes / pasa después) —
  un fix de seguridad sin regresión NO se mergea. Crítico → notifica al
  momento igual, aunque el fix ya esté aplicado.
- **Estado/memoria:** `docs/internal/security/findings.md` + run-log común.

## Coordinación entre loops (contrato de la casa)

Reglas que TODO loop lee antes de actuar. Existen para que dos agentes
autónomos no se pisen como no se pisarían dos ingenieros seniors.

1. **Propiedad de ramas.** Cada loop trabaja SOLO en su rama dedicada:
   | Loop | Rama |
   |---|---|
   | Admin-value | `claude/admin-value-loop` |
   | Housekeeper | `claude/housekeeper` |
   | Guardián | `claude/ci-sweeper` |
   | Deps-sweeper | `claude/deps-sweeper` |
   | Dirección | `claude/exec-digest` |
   | Growth | `claude/growth-loop` |
   | Centinela | `claude/security-loop` |
   Prohibido recrear o force-pushear la rama de otro loop o la de una
   sesión interactiva: un force-push ajeno muta la PR abierta de su dueño.
2. **Calendario sin solape** (todo en UTC; cambiar una cadencia obliga a
   revisar esta tabla):
   | Loop | Cadencia |
   |---|---|
   | Housekeeper | diario 23:13, excepto noche del viernes |
   | Admin-value | sábado 00:07 |
   | Guardián | diario 04:23 |
   | Dirección | lunes 05:33 |
   | Deps-sweeper | miércoles 21:37 |
   | Growth | martes 06:17 |
   | Centinela | jueves 22:07 |
3. **Derivación cruzada, no invasión.** Si el Housekeeper encuentra algo que
   es mejora de producto (no limpieza), lo anota como candidato en la
   sección "Loop admin-value" de `STATE.md` y NO lo implementa. Si el
   Admin-value encuentra deuda de limpieza pura, la añade a
   `docs/internal/housekeeper/deferred-candidates.md` con su evidencia y NO
   la limpia en su PR. Cada hallazgo viaja a la cola del loop dueño.
4. **Prioridad en conflicto.** Si ambos loops quieren tocar el mismo fichero
   la misma semana, el Admin-value (producto) tiene prioridad; el
   Housekeeper difiere su candidato con una nota. Un rebase trivial no es
   conflicto.
5. **Registro común.** Ambos loops añaden una línea por run a
   `docs/internal/loop-run-log.md` (formato existente), además de su memoria
   propia. El run-log es la cronología única de lo que las máquinas hicieron
   al repo.
6. **Auto-merge total en verde (propietario, 2026-08-16: "ponlo todo en
   automerge, todo salvo publicar release").** El humano deja de ser el
   merger. CUALQUIER cambio a `main` — código de producto incluido: auth de
   `saas_server.py`, `notifier.py`, contrato de adapters (`base.py` con bump
   mayor + mock offline), modelo de sesión, empaquetado Desktop, bumps MAJOR
   de deps, postura de seguridad — lo auto-mergea su loop dueño EN CUANTO
   pasa el **gate QA de máquina**: CI verde + batería runtime N/N + tests de
   regresión relevantes + `VEREDICTO QA: APTO`. Un fix de seguridad exige
   además su test de regresión (falla antes / pasa después). El gate QA es
   innegociable: "auto-merge" = "sin humano", jamás "sin comprobar". La
   denylist absoluta de `loop-constraints.md` no entra ni en verde.
   - **Único gate humano restante: publicar hacia fuera.** (a) Releases —
     el commit que toca `.release-version` (dispara `release.yml` →
     Homebrew/descargas): el loop lo deja listo, lo mergea el propietario.
     (b) Outreach — las PR `outreach:` de Growth (publican con su identidad).
     Ambas son PR abiertas NO bloqueantes: el loop sigue con otro trabajo y
     Dirección las lista en "Te espera". Nada más espera a un humano.
7. **Reporting: un solo canal.** El propietario recibe UNA notificación:
   el resumen ejecutivo semanal del loop Dirección (lo nuevo, lo corregido,
   tracción, decisiones pendientes, salud de la flota). Los demás loops
   corren en silencio; sus resultados llegan al propietario vía el digest y
   quedan auditables en el run-log común y las PRs. Un loop solo rompe el
   silencio si detecta algo que no puede esperar al lunes (main roto que no
   sabe arreglar, secreto filtrado, vulnerabilidad crítica explotable, PR
   maliciosa) — y Growth, además, puede notificar cuando deja una PR
   `outreach:` esperando aprobación.
8. **Estilo de reporting** (adaptado de la skill
   [i-have-adhd](https://github.com/ayghri/i-have-adhd): la respuesta no
   entierra la acción). Aplica a resúmenes finales, digest, cuerpos de PR
   y run-log de TODOS los loops:
   - **La acción primero.** Si el propietario tiene que hacer algo, es la
     primera línea, imperativa y con enlace ("Mergea #138: …"). Nunca
     enterrada tras contexto.
   - **Decisiones numeradas.** Varias cosas que decidir = lista numerada,
     máx. 5 items; el resto se agrega ("y 3 menores en el run-log").
   - **Estado visible.** Cada informe reafirma el estado en una línea
     (versión en producción, main verde/rojo, PRs abiertas N).
   - **Victorias visibles, errores sin drama.** Lo aterrizado se dice
     ("aterrizó X"); lo fallado se dice igual de plano, con el siguiente
     paso, sin disculpas ni relleno.
   - **Sin preámbulo, sin recapitulación, sin despedidas.** Nada de "esta
     semana ha sido…"; el TL;DR ES la primera línea. Números concretos,
     jamás "varios" o "algunos" si el dato existe.
   - **Cierre con UN siguiente paso concreto** (el del propietario si lo
     hay; el del loop si no).

### Contributor PR triage (L1 — human-gated)
- **Trigger:** new PR or issue on `adrimg3196/lucidfence`.
- **Maker:** contributor (or maintainer) proposes the change.
- **Verifier (checker / maker-split):** the change is verified by the honest test
  runner `python3 tests/run_tests.py`, a `gitleaks` secret scan, and a
  frozen-contract check (`lucidfence/core/adapters/base.py` must not change). All three MUST
  pass before human merge. This file itself is the verifier contract.
- **Checks (verifier):** secrets scan (`gitleaks`), frozen `MDMAdapter` contract
  (`lucidfence/core/adapters/base.py` must NOT change), offline mode preserved, tests green
  without real credentials, `.env.example` only placeholders.
- **Gate:** NO auto-merge. Maintainer reviews and merges.
- **Duplicate/spam policy:** close duplicate PRs; reject PRs that embed wallet
  addresses, credentials, or off-topic changes.

### Daily quality dogfood (L1 — report-only)
- **Trigger:** on push / PR via `.github/workflows/loop-audit.yml`.
- **Action:** run `loop-audit` and post the readiness score as a PR check.
- **Human review:** weekly review of drift below L1.

## Safety & gates

- **Auto-merge total en verde** (propietario, 2026-08-16). El gate humano
  previo desaparece; lo sustituye el **gate QA de máquina** (CI + batería
  runtime + regresión + `VEREDICTO QA: APTO`), que es innegociable. Detalle
  y el único gate humano restante (publicar release/outreach) en
  `docs/internal/loop-constraints.md` y en la regla 6 de Coordinación.
- **Denylist absoluta** (ni con gate verde): secretos en
  `config.json`/`data/`/`.env`; `base.py` sin bump mayor + mock; publicar
  `data/cloud_state.json` con datos reales de tenant; wallets/spam.
- **Least privilege:** CI uses read-only `GITHUB_TOKEN`; no deploy secrets in
  loop workflows.
- **MCP usage:** not required for this loop. If a connector is added later, it
  MUST be read-only (issue/PR discovery) and scoped in `docs/internal/LOOP.md` before use.
- **Worktree isolation:** every unattended code-change experiment runs in an
  isolated git worktree; one worktree per fix, discarded after a failed verifier.
- **No-progress / circuit breaker:** after 3 failed verifier attempts on the
  same fix, stop; write a note to `docs/internal/loop-run-log.md` (lo recoge
  el watchdog del Guardián). Never repeat the same failing action.
- **Red de seguridad reactiva:** el Guardián revisa main a diario; un merge
  que ponga main rojo se revierte/arregla en el siguiente ciclo (el gate QA
  hace improbable que llegue roto, pero la red existe).

## Budget & observability

- Token caps and kill switch: `docs/internal/loop-budget.md`.
- Run history: `docs/internal/loop-run-log.md` (append-only).
- `loop-audit` is the readiness signal; score regressions are reviewed, not
  auto-reverted.

## How to run locally

```bash
npx @cobusgreyling/loop-audit . --suggest
npx @cobusgreyling/loop-audit . --badge
```
