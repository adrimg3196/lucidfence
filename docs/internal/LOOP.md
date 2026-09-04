# docs/internal/LOOP.md — Improvement loop for LucidFence

LucidFence is a local-first, free, open-source geofencing / UEM product. This
file documents the improvement loop used to maintain it, adapting the
[loop-engineering](https://github.com/cobusgreyling/loop-engineering) patterns.
Reporting style follows [i-have-adhd](https://github.com/ayghri/i-have-adhd)
(regla 8); Growth's SEO menu follows [open-seo](https://github.com/every-app/open-seo);
Centinela's offensive method follows [Strix](https://github.com/usestrix/strix).
Cada loop delega decisiones de dominio en un bench de especialistas
([agency-agents](https://github.com/msitarzewski/agency-agents), adaptado en
`~/lucidfence-agents-tooling/.claude/agents/`); el organigrama loop→especialistas→derechos de decisión está
en `docs/internal/agency/ORG.md`.

## Norte de la flota (goal, propietario 2026-08-16)

### Qué es autónomo y qué NO (frontera inviolable, propietario 2026-08-18)

Lo **autónomo es el DESARROLLO del producto**: la flota de loops es la *empresa*
que idea, implementa, prueba, versiona y publica LucidFence sin intervención
humana. Eso es lo que no tiene gate humano.

Lo que **NUNCA es autónomo es el PRODUCTO en runtime**: el geofencing y el
enforcement sobre **dispositivos reales** los decide **siempre el administrador**.
El producto mantiene al admin en control por diseño y ningún loop puede debilitarlo:
- `dry_run` por defecto `True`; fase `observe` = todo dry-run (nada sale al UEM).
- `enforce` (acciones en vivo) **solo** si el admin lo activa explícitamente por
  tenant; `live_actions` es una allow-list por acción.
- `wipe` exige **doble llave** (`allow_wipe: true` **y** `wipe_allowlist`); jamás
  se amplía desde la UI ni desde un loop.
- LucidFence nunca actúa sobre un dispositivo real por su cuenta: ejecuta la
  política que el admin escribió, con esos frenos.

**Invariante para todo loop:** está prohibido entregar un cambio que quite al
admin del control de acciones sobre dispositivos reales o que haga que el producto
actúe solo (cambiar el default a `enforce`, autoejecutar `wipe`, saltarse la doble
llave, o disparar acciones en vivo sin config explícita del tenant). El gate QA y
la revisión del Centinela tratan cualquier regresión de esto como bloqueante,
aunque el resto esté verde. La autonomía es de la *empresa*, no del *geofencing*.

### Todo loop existe para mejorar el producto

**TODO loop y cron existe para mejorar el producto** — un LucidFence que un
administrador IT real elige y usa. Ningún loop es un fin en sí mismo. Regla que
prevalece sobre la función concreta de cada loop:

1. **El producto es la vara de medir.** Antes de actuar, cada loop se pregunta:
   *¿esto mejora el producto para el admin, o habilita/protege una mejora?* Si
   la respuesta es no, no se hace.
2. **Todo hallazgo de producto viaja a Admin-value.** Cualquier loop (Housekeeper,
   Guardián, Deps, Dirección, Centinela, Growth, Lanzamiento, Roadmap) que al
   hacer su trabajo vea una oportunidad de mejora de producto la anota en el
   backlog de la sección "Loop admin-value" de `STATE.md` — no la implementa
   fuera de su carril, pero **jamás la deja pasar sin registrarla**.
3. **Admin-value es el loop de producto por excelencia** y tiene prioridad de
   recursos; los loops de plataforma (Housekeeper/Guardián/Deps) existen para
   que Admin-value pueda entregar rápido y seguro. Centinela protege el producto,
   Roadmap le da rumbo, Lanzamiento lo entrega, Growth consigue que se use,
   Dirección informa del avance del producto.
4. **Reporting en clave de producto.** Cada resumen dice qué mejoró (o habilitó)
   para el admin IT, no solo qué tarea corrió.

## Active loops

### Admin-value (L2 — asistido, cadencia semanal)
- **Patrón completo:** `docs/internal/loop-admin-value.md`.
- **Objetivo:** empujar el producto a "imprescindible para el admin IT"
  (onboarding sin fricción, rollout seguro, claims siempre validados).
- **Trigger:** Routine semanal (sábados 00:00 UTC ≈ 02:00 Madrid) que lanza
  una sesión nueva; también ejecutable a mano pidiendo "ejecuta un ciclo del
  loop admin-value".
- **Rama:** `claude/admin-value-loop` (propiedad exclusiva; ver Coordinación).
- **Gate:** hasta 1 PR por run, auto-merge en verde con el gate QA (CI +
  runtime battery + `VEREDICTO QA: APTO`); incluidas las que publican release
  (`.release-version`) — el smoke de `release.yml` es el gate automático, no un
  humano (§Autonomía).
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
     seguridad y demás incluidos — auto-merge total, release/outreach también),
     y cierra con evidencia las superadas/muertas/duplicadas. Nada se deja para
     un humano. Objetivo permanente: 0 zombis.
  3. *Triage de terceros* (L1): comenta y etiqueta según "Contributor PR
     triage"; a autores externos JAMÁS les mergea.
  4. *Watchdog de la flota*: lee la última línea de cada loop en el run-log;
     si un loop lleva >1 ciclo sin correr cuando debía (comparado con el
     Calendario), lo anota como INCIDENTE en el run-log para que Dirección
     lo suba al digest. (No puede re-disparar Routines desde su sesión: su
     arma es hacerlo visible, no silenciarlo.)
  5. *Limpieza post-merge*: borra ramas `claude/*` cuya PR está MERGED.
- **Gate:** todo con el gate QA completo; auto-merge total (a autores externos
  jamás; su código no es de confianza aunque pase CI).
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
- **Gate:** todo con el gate QA (autonomía total 2026-08-18: sin aprobación
  humana). Lo ejecutable con la cuenta de GitHub (PR a una lista awesome-*,
  discussion, respuesta útil en un repo relacionado) va en una PR `outreach:`
  con el contenido exacto y el destino; **el raíl la auto-mergea en verde** y
  el siguiente run la publica y registra el enlace. Fuera de GitHub
  (HN/Reddit/LinkedIn: el agente no tiene esas cuentas) queda en
  `docs/gtm/outbox/`. Guardarraíles anti-daño que NO son aprobación humana y
  siguen vigentes: **sin spam** (máx. 1 publicación externa por ciclo, valor
  genuino, sin repetir destino en 30 días), **sin social proof inventado**,
  sin suplantar identidad, sin telemetría.
- **Estado/memoria:** `docs/internal/growth/` (experiments, mentions) +
  línea en el run-log común.

### Lanzamiento (L2 — publica releases nuevas de forma autónoma; semanal)
- **Especificación completa:** `docs/internal/release/README.md`.
- **Objetivo:** que las versiones nuevas se publiquen solas (propietario,
  2026-08-16). Dueño del runbook de release de punta a punta: decide si toca
  lanzar, bumpea versión coherente (cli.py + pyproject + `.release-version` +
  CHANGELOG), dispara `release.yml` y actualiza las fórmulas Homebrew con el
  sha del asset publicado.
- **Trigger:** Routine semanal (domingo 20:43 UTC ≈ 22:43 Madrid; tras el
  ciclo de producto del sábado).
- **Rama:** `claude/release-loop` (propiedad exclusiva).
- **Gate:** solo lanza si hay cambios de usuario desde la última tag (nunca
  releases vacías); **auto-publica** con el gate QA + el smoke de
  `release.yml` (construye, instala y arranca el artefacto antes de publicar)
  como red. Nunca bump MAJOR autónomo (contrato de adapters/API → propietario).
- **Estado/memoria:** `docs/internal/release/` (history, pending-tap) +
  run-log común.

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

### Roadmap (L2 — el rumbo de producto vivo; semanal)
- **Especificación completa:** `docs/internal/roadmap/README.md`.
- **Objetivo:** mantener un roadmap de producto VIVO a varios ciclos vista
  (`docs/roadmap/PRODUCT_ROADMAP.md`, horizonte deslizante Ahora/Próximo/
  Después) para que la empresa no solo mejore ciclo a ciclo sino que sepa hacia
  dónde va. Reconcilia lo entregado, repriorije con señal real y empuja el
  "Próximo" a la cola de Admin-value. `roadmap.json` (tooling de auto-mejora)
  queda archivado; no se reabre.
- **Trigger:** Routine semanal (viernes 21:17 UTC ≈ 23:17 Madrid).
- **Rama:** `claude/roadmap-loop` (propiedad exclusiva).
- **Gate:** su PR es docs (roadmap + snapshots archivados); auto-merge en verde
  con el gate QA. Solo señal real (cada ítem cita origen); no implementa —
  prioriza y deriva. Resuelve las decisiones de producto que otros loops
  difieren (p. ej. qué roadmap histórico es canónico).
- **Estado/memoria:** `docs/roadmap/PRODUCT_ROADMAP.md` + línea en el run-log.

### Tendencias → Producto (L2 — I+D aplicada; semanal)
- **Especificación completa:** `docs/internal/trends/README.md`.
- **Objetivo:** vigilar el ecosistema (Apple DDM, Android AMAPI, Windows CSP/DSC,
  osquery/Fleet, CVEs de la stack, regulación NIS2/GDPR/CRA, gaps de competencia)
  como un ingeniero senior y **convertir la señal real en producto**: implementa
  la mejora si cabe en un diff pequeño, o la deriva al backlog de Admin-value con
  la fuente citada. No es el Radar de preventa (ese informa a una persona fuera
  del repo); este entrega producto.
- **Trigger:** Routine semanal (miércoles 12:00 UTC ≈ 14:00 Madrid), sesión fresca.
- **Rama:** `claude/trends-loop` (propiedad exclusiva).
- **Gate:** auto-merge en verde con el gate QA vía el raíl. Solo señal citada;
  nada inventado; invariantes intactos. Sin autorización humana.
- **Estado/memoria:** `docs/internal/trends/signals.md` (append-only) + run-log.

### Product Manager → Nuevas funciones (L2 — features autónomas; semanal)
- **Especificación completa:** `docs/internal/product/README.md`.
- **Objetivo:** un product manager autónomo que **suma capacidades nuevas** al
  producto cada ciclo (mientras Admin-value hace *imprescindible* lo que ya
  existe, este **añade lo que aún no existe**). Ideas de fuentes reales: roadmap
  vivo, señales de Tendencias, gaps declarados y dogfooding del dashboard. Una
  función usable por ciclo (o su primer incremento funcional), nunca humo.
- **Trigger:** Routine semanal (lunes 12:00 UTC ≈ 14:00 Madrid), sesión fresca.
- **Rama:** `claude/pm-features` (propiedad exclusiva).
- **Gate:** auto-merge en verde con el gate QA vía el raíl; sin autorización
  humana. Todo claim nuevo se prueba en la batería runtime.
- **Estado/memoria:** `STATE.md` (función registrada) + run-log.

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
   | Lanzamiento | `claude/release-loop` |
   | Roadmap | `claude/roadmap-loop` |
   | Tendencias | `claude/trends-loop` |
   | Product Manager | `claude/pm-features` |
   Prohibido recrear o force-pushear la rama de otro loop o la de una
   sesión interactiva: un force-push ajeno muta la PR abierta de su dueño.
2. **Calendario sin solape** (todo en UTC; cambiar una cadencia obliga a
   revisar esta tabla):
   | Loop | Cadencia |
   |---|---|
   Todos corren de **noche** (propietario 2026-08-18: ventana 22:00–05:00 UTC =
   00:00–07:00 Madrid) para no interrumpir el día del propietario.
   | Housekeeper | diario 23:13, excepto noche del viernes |
   | Admin-value | sábado 00:00 |
   | Guardián | diario 03:00 |
   | Dirección | lunes 04:30 |
   | Deps-sweeper | miércoles 22:40 |
   | Growth | martes 23:15 |
   | Centinela | jueves 22:07 |
   | Lanzamiento | domingo 23:20 |
   | Roadmap | viernes 23:40 |
   | Tendencias | miércoles 23:30 |
   | Product Manager | lunes 23:00 |
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
   pasa el **gate QA de máquina**. Ese gate es UN comando, la definición de
   "hecho" del repo (estilo `pnpm verify` de agentic-ship): **`python3
   scripts/verify.py`** — coherencia de versión + enlaces de docs + batería
   runtime N/N + suite honesta (tolera solo la baseline OIDC del contenedor).
   Verde local + CI verde + `VEREDICTO QA: APTO` = mergeable. Un fix de
   seguridad exige además su test de regresión (falla antes / pasa después).
   El gate es innegociable: "auto-merge" = "sin humano", jamás "sin
   comprobar". La denylist absoluta de `loop-constraints.md` no entra ni en
   verde.
   - **Releases: autónomas** (propietario, 2026-08-16: "publica releases
     nuevas también"). Las publica el loop Lanzamiento: bumpea versión,
     mergea `.release-version` → `release.yml` construye, instala y arranca
     el artefacto ANTES de publicar (ese smoke es la red de máquina), y
     actualiza las fórmulas Homebrew. Sin humano.
   - **Outreach: también autónomo** (propietario, 2026-08-18: "todo lo decide
     la IA, nada los humanos"). Las PR `outreach:` de Growth las auto-mergea el
     raíl en verde como cualquier otra; el siguiente run de Growth ejecuta la
     publicación. **Ya no queda ningún gate humano.** Los guardarraíles
     anti-daño siguen (sin spam, sin social proof inventado, sin suplantación,
     jamás auto-merge de forks/terceros).
7. **Reporting: un solo canal.** El propietario recibe UNA notificación:
   el resumen ejecutivo semanal del loop Dirección (lo nuevo, lo corregido,
   tracción, decisiones pendientes, salud de la flota). Los demás loops
   corren en silencio; sus resultados llegan al propietario vía el digest y
   quedan auditables en el run-log común y las PRs. Un loop solo rompe el
   silencio si detecta algo que no puede esperar al lunes (main roto que no
   sabe arreglar, secreto filtrado, vulnerabilidad crítica explotable, PR
   maliciosa).
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
9. **Delegación al bench (agency-agents).** Cada loop es un departamento y
   delega las decisiones de dominio en los especialistas de `~/lucidfence-agents-tooling/.claude/agents/`
   (invocables por su slug como `subagent_type`). El loop es el gerente; el
   especialista decide y devuelve el entregable. El humano no está en esta
   cadena. Mapa loop→especialistas→derechos de decisión:
   | Loop | Especialistas |
   |---|---|
   | Admin-value | `product-manager`, `engineering-senior-developer`, `engineering-backend-architect`, `engineering-iot-fleet-engineer` |
   | Housekeeper | `engineering-minimal-change-engineer` |
   | Guardián | `engineering-code-reviewer`, `engineering-git-workflow-master`, `engineering-devops-automator` |
   | Deps-sweeper | `engineering-devops-automator`, `testing-reality-checker` |
   | Dirección | `specialized-chief-of-staff` |
   | Growth | `marketing-seo-specialist`, `marketing-community-builder`, `support-issue-triage` |
   | Centinela | `security-penetration-tester`, `security-architect` |
   | Lanzamiento | `engineering-devops-automator`, `testing-reality-checker` |
   | Roadmap | `product-roadmap-strategist` |
   | Transversal | `project-shepherd`, `finance-fpa-analyst`, `specialized-fleet-architect`, `testing-reality-checker`, `engineering-privacy-engineer` |
   Detalle completo y derechos de decisión: `docs/internal/agency/ORG.md`.

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

- **Autonomía total: todo lo decide la IA, nada los humanos** (propietario,
  2026-08-18). NO queda ningún gate humano — ni release ni outreach. El único
  juez es el **gate QA de máquina** (CI + batería runtime + regresión +
  `VEREDICTO QA: APTO`), innegociable. Detalle en
  `docs/internal/loop-constraints.md` y en la regla 6 de Coordinación.
- **Denylist absoluta** (ni con gate verde): secretos en
  `config.json`/`data/`/`.env`; `base.py` sin bump mayor + mock; publicar
  `data/cloud_state.json` con datos reales de tenant; wallets/spam.
- **Least privilege:** CI uses read-only `GITHUB_TOKEN`; no deploy secrets in
  loop workflows.
- **MCP usage:** not required for this loop. If a connector is added later, it
  MUST be read-only (issue/PR discovery) and scoped in `docs/internal/LOOP.md` before use.
- **Requisito de las Routines (connectors GitHub):** cada loop auto-mergea vía
  las tools `mcp__github__*` (abrir PR, `get_check_runs`, `merge_pull_request`).
  Una Routine creada sin esos connectors dispara sesiones que solo pueden hacer
  `git push` por Bash, pero NO abrir/mergear PRs → el loop dejaría PRs colgadas.
  Al crear/editar una Routine de loop hay que garantizar que la sesión fresca
  hereda los connectors de GitHub (crearla desde una sesión que los tenga, o
  desde la UI de Routines de claude.ai). Verificar en el primer run real de cada
  loop que pudo mergear; si no, el Guardián lo verá como PR colgada y lo anota.
  **Fix reproducible (2026-08-16):** `.mcp.json` en la raíz declara el GitHub
  MCP oficial para TODAS las sesiones (incl. cron); requiere
  `GITHUB_PERSONAL_ACCESS_TOKEN` en el environment. Detalle:
  `docs/internal/mcp-github.md`.
  **Raíl de entrega por Actions (VERIFICADO EN VIVO 2026-08-18) — la forma
  canónica de entregar.** Toda sesión cron entrega su trabajo con un solo gesto:
  **`git push` a su rama `claude/<loop>`**. A partir de ahí el raíl actúa solo:
  `agent-pr.yml` abre la PR contra `main` y `agent-automerge.yml` la squash-mergea
  en cuanto la CI (el gate QA) está verde, aplicando este contrato (jamás
  forks/drafts; auto-mergea TODO lo demás en verde, outreach y release incluidos;
  ignora solo el helper `train`). Probado extremo a extremo (PR #166: abierta y
  mergeada por el raíl, sin intervención humana).

  Regla operativa para las sesiones cron: **haz push y para.** NO necesitas las
  tools `mcp__github__*` (abrir PR, `get_check_runs`, `merge_pull_request`); si tu
  prompt de loop aún menciona esos pasos, quedan **superados por el raíl** —
  ignóralos, el push es la entrega. Una PR por ciclo (WIP=1 por título). No queda
  ningún gate humano. Requiere el Actions Secret `AGENTS_GITHUB_PAT` con permisos
  Pull requests + Contents (RW), ya configurado. Detalle: `docs/internal/mcp-github.md`.
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
