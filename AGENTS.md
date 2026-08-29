# AGENTS.md — LucidFence project rules (context-engineering)

Apply these rules on every task in this repo. They describe the REAL conventions,
not the wiki.

## Multi-agent collaboration
At least three AI agents work this repo concurrently, different LLMs, same human
owner (Adri). There may be a 4th: commits as `Adrian Martinez <adri@lucidfence.local>`
doing brand/video/skill-tooling work (OpenMontage, FLUX, "agent-upgrade", daily brief
generation) at high frequency (multiple commits/hour) — not yet confirmed whether
that's Adri himself or another automation using his identity. Verify with Adri before
assuming either way; don't dedupe against it as if it were a known agent.
- **Zero** (Claude/Anthropic, via OpenClaw) — coordinator role: dedupes competing PRs,
  runs an independent review gate before merge, drives the nightly/scheduled crons
  (`jules-scheduler`, `jules-lucidfence-loop`, `lucidfence-nightly-dev*`). Commits as
  `zero@lucidfence.local` — **verify `git config --local user.email` at the start of
  every session in this repo**: on 2026-08-02 Zero's local checkout was misconfigured
  to Hermes' identity (`geofence-uem@local`) and every Zero commit that session was
  mis-attributed as Hermes, silently breaking the dedup check below.
- **Jules** (Google) — autonomous sessions per GitHub issue, opens PRs for review.
  Commits as `google-labs-jules[bot]`.
- **Hermes** (Nous Research, per Adri 2026-08-01) — commits seen under both `Geofence
  UEM <geofence-uem@local>` and `Hermes Agent <hermes@local>` (inconsistent, not yet
  resolved). Task split with the other two still informal: Adri/Zero assign work via
  `hermes kanban` (board `lucidfence`), no shared queue with Jules.

**The shared queue now exists — read it before claiming anything.** The open
issue labelled `merge-train` holds the authoritative order of entry, regenerated
by `scripts/merge_train.py` (workflow `merge-train.yml`, twice daily). Rules of
engagement — WIP limits, claim protocol, rebase discipline, merge order, what
escalates to Adri — live in `docs/references/agent-team-charter.md`. Read it
before opening a PR: on 2026-08-13 this repo had 19 open PRs and **zero**
mergeable, because everyone kept producing and nobody drained.

Before starting work that could overlap, check `git log --all --format='%an %s' -20`
for recent activity from the other identities — same dedup practice already used
for the #46/#47 duplicate-PR precedent (see `memory/lucidfence-jules-log.md` in the
OpenClaw workspace for the full history Zero keeps on this).

**Shared local checkout (`/Users/adri/geofence-uem`) gets hard-reset without
warning, aggressively enough to discard uncommitted edits AND switch away from a
branch you just created.** Confirmed 2026-08-02: Zero lost the same uncommitted edit
twice in a row, the second time already on a dedicated branch. Not a `main`-push
conflict — `engine-cron` (the 15-min cloud-state publisher) runs entirely on GitHub's
own runners and never touches this machine, so GitHub branch protection would not
have prevented this and would break `engine-cron`'s direct push unless explicitly
exempted (not done, needs Adri's input if pursued). Most likely cause: a local agent
task-runner (Hermes' kanban dispatcher is the leading suspect, given the timing)
resets this checkout to a clean `origin/main` before claiming/running a task, with no
awareness another agent is editing it interactively. **Rule: use `git worktree add
../geofence-uem-<name> -b <branch>` for any interactive/manual work in this repo —
don't edit the shared checkout directly, even briefly.** Commit fast is not enough;
the reset can land mid-edit.

## Verify — la definición de "hecho" en UN comando
`python3 scripts/verify.py` es el gate de calidad del repo (estilo el
`pnpm verify` de agentic-ship): coherencia de versión + enlaces de docs +
batería runtime en vivo (N/N) + suite honesta (tolera solo la baseline OIDC
del contenedor, verde en CI). **Verde en `verify.py` = mergeable.** No
re-listes los pasos sueltos: corre `verify.py`. `--fast` omite la batería
runtime; `--quiet` solo el resumen. El CI (`.github/workflows/ci.yml`)
re-corre las mismas comprobaciones como autoridad final.

## Stack & commands
- Python 3.11, stdlib-first. No web frameworks (HTTP propio en `saas_server.py`).
- Verificar todo: `python3 scripts/verify.py` (ver arriba — el gate).
- Test suelto: `python3 tests/run_tests.py` (honest runner; el tally vive en
  CI/`verify.py`, no en prosa).
- Cloud vitrina: `python3 -m lucidfence.core.cloud_publisher --cycles 2` → `data/cloud_state.json`.
  **No commitees ese fichero desde una rama**: lo republica `engine-cron` en main cada hora, así
  que tu PR conflictaría siempre (el job `runtime-artifacts` de CI lo rechaza). Si lo has tocado:
  `git checkout origin/main -- data/cloud_state.json`.
- Local SaaS: `python3 saas_server.py` (`:8765`).
- Client install: `./install.sh` or `docker compose up -d`.

## Directory meaning
- `lucidfence/` — el ÚNICO paquete Python. Todo lo importable vive aquí:
  - `core/` — engine, policies (risk), state_store, adapters (Applivery/Intune/Jamf),
    cve_feed_nvd, location_source (simulation), config_loader, cloud_publisher,
    roadmap_tooling.
  - `saas/` — tenants, auth local y RBAC.
  - `mcp/` — servidores MCP stdio read-only.
  - `plugins/` — índice de adapters verificado por hash + providers de terceros.
  - `cli.py` / `shell.py` — CLI de ciclo de vida y shell interactiva.
- `apps/` — entregables que NO son el servicio Python: `macos/` (app Swift + builder
  DMG) y `uem-gateway/` (Cloudflare Worker opcional).
- `scripts/` — utilidades de build, arranque, despliegue, QA y ops. Nada de
  librería vive aquí; si algo se importa, va a `lucidfence/`.
- `docs/` — toda la documentación; índice en `docs/README.md`. La raíz solo
  conserva README, LICENSE, CONTRIBUTING, SECURITY, CHANGELOG y este AGENTS.md
  (su ruta es la convención que leen los agentes: no moverla).
- `static/` — `dashboard.html` (SPA local, habla con `:8765`), `cloud.html` (vitrina
  serverless que lee `data/cloud_state.json` vía raw.githubusercontent), `app.js`.
- `data/cloud_state.json` — estado publicado para la vitrina (commiteado, lo sirve Pages).
- `data/cloud_tenants/<id>/data/` — tenants de la nube (multi-tenant real vía saas-api).
- `.github/workflows/` — engine-cron (backend serverless 15min), deploy-pages,
  saas-api (operaciones), deploy-fly (listo, requiere FLY_API_TOKEN del cliente).

## Known landmines
- `tests/run_tests.py` MUST stay honest. A `test_*.py` that does `raise SystemExit`
  at import used to abort discovery of all later files, hiding 11 failures. The
  runner catches SystemExit per-module — never reintroduce the hiding bug.
- `lucidfence/core/cloud_publisher.py` processes only `data/cloud_tenants/<id>/data/` that have
  BOTH `fleet_seed.json` AND `fences.json`. Don't mix with `data/tenants/` (basura de tests).
- GitHub Pages serves under `/lucidfence/` subpath → use relative links in static/,
  never absolute `/app`, `/cloud.html`, `/static/...` (causaba 404).
- The vitrina reads state from `raw.githubusercontent.com` (CORS `*`). Don't put
  secrets there. cloud_state.json is public by design (demo data).
- macOS caches directory listings — `os.listdir` may miss a freshly-created test
  file; `touch` the dir to invalidate before re-running the runner.

## Boundaries (delegated decision 2026-07-14)
- ALWAYS: verify at runtime; runner honest; $0 (free tiers only); tenant data stays
  on the client's machine.
- ASK FIRST: any paid dependency; any always-on backend needing OUR token (Fly/HF).
- NEVER: hardcode secrets; expose a token in the Pages client; use `flyctl auth
  login` headless (fails silently); leave zombie processes between sessions.

## Disciplina Karpathy (obligatoria al escribir o revisar código)
La skill `.claude/skills/karpathy-guidelines/SKILL.md` (MIT, de
multica-ai/andrej-karpathy-skills) es disciplina de la flota, no documentación.
Sus cuatro principios atacan los errores típicos de un equipo de IA y este repo
ya pagó cada uno al menos una vez:
1. **Piensa antes de codificar** — asunciones explícitas; ante ambigüedad,
   presenta interpretaciones en la PR en vez de elegir en silencio.
2. **Simplicidad primero** — el diff mínimo que resuelve; nada especulativo
   (la review de #284 creció de 3 líneas a 939 defendiendo escenarios
   imposibles: eso es lo prohibido).
3. **Cambios quirúrgicos** — cada línea tocada debe trazar a la petición; el
   código muerto ajeno se menciona, no se borra de paso.
4. **Ejecución dirigida a objetivo** — todo claim con criterio verificable:
   test que reproduce antes de arreglar, batería runtime para claims nuevos.

## Flota autónoma de loops (el modelo de operación hoy)
Este repo lo mantiene una flota de 9 loops agénticos coordinados por un
contrato escrito. Léelo antes de tocar nada estructural:
- **`docs/internal/LOOP.md`** — los 9 loops (Admin-value, Housekeeper,
  Guardián, Deps-sweeper, Growth, Centinela, Lanzamiento, Dirección, Roadmap),
  sus ramas dedicadas, el calendario sin solapes, y las 9 reglas de coordinación
  (incl. auto-merge total en verde y el estilo de reporting).
- **`docs/roadmap/PRODUCT_ROADMAP.md`** — el roadmap de producto VIVO (dueño:
  loop Roadmap). `roadmap.json` es histórico del tooling de auto-mejora,
  archivado; no reabrir.
- **`docs/internal/loop-constraints.md`** — la denylist absoluta y el único
  gate humano que queda (outreach a terceros).
- **`docs/internal/agency/ORG.md`** — el organigrama: cada loop es un
  departamento que delega decisiones de dominio en el bench de especialistas de
  `.claude/agents/` (subagentes nativos, taxonomía de agency-agents adaptada al
  repo). Los agentes deciden; el humano solo aprueba outreach.
- Cada cambio a `main` auto-mergea si `verify.py` + CI están verdes; nadie es
  el merger por defecto. El propietario solo recibe el digest semanal del
  loop Dirección y aprueba outreach.

## Quality floor
- Definition of Done ejecutable: **`python3 scripts/verify.py`** (canónico).
- Docs de referencia: `docs/references/definition-of-done.md`,
  `docs/references/testing-patterns.md`, `docs/references/security-checklist.md`.
