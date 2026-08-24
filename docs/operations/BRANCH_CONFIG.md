# Registro de configuración de ramas (branch protection)

Registro canónico de las reglas de protección de ramas de `adrimg3196/lucidfence`
(GitHub **rulesets**, no branch protection clásica). Cualquier cambio en la
protección de ramas debe actualizar este archivo y la entrada del CHANGELOG.

Última verificación: 2026-08-24T14:22+02:00 (desbloqueo de deadlock repo-wide por
check fantasma `autonomy-evidence`, tarea t_9c8c2878 / PR #264 / PR #289).

## Regla de oro

- `main` (rama por defecto) mantiene PR + 9 checks de CI + historial lineal.
- Las **ramas de datos** (`cloud-state`, `recon-state`) son efímeras y las escriben
  directamente los workflows programados (`engine-cron`, `recon-social-cron`).
  Por tanto **NO** pueden tener requisito de PR ni checks: solo protección contra
  **borrado** (`deletion`). Cualquier ruleset que aplique a `~ALL` o a estas ramas
  con reglas `pull_request` / `required_status_checks` rompe el push programado
  (error `GH013`).

### REGLA DE PRECEDENCIA (anti-deadlock) — añadida 2026-08-24

> **Nunca añadir un contexto a `required_status_checks` de un ruleset antes de que
> el workflow que lo emite esté mergeado en `main`.**
>
> Orden correcto: (1) mergear el workflow a `main`; (2) verificar en un PR real que
> el workflow reporta el contexto esperado en verde; (3) **solo entonces** marcar el
> contexto como requerido en el ruleset.
>
> Romper esta regla crea un **deadlock por diseño**: el ruleset exige un check que
> solo puede producir un PR (que a su vez está bloqueado por el mismo ruleset).
> Caso real: `autonomy-evidence` se requirió en el ruleset 21249696 el 2026-08-23
> pero su workflow solo vivía en el PR #264 (rojo) → todos los PR verdes del repo
> quedaron `BLOCKED` hasta el fix de 2026-08-24 (ver Registro de cambios).

## Rulesets activos

| ID | Nombre | Target (`include`) | Reglas | Estado | Último cambio |
|----|--------|--------------------|--------|--------|---------------|
| 21249696 | `LucidFence Autonomy B` | `~DEFAULT_BRANCH` (solo `main`) | `deletion`, `required_linear_history`, `pull_request` (0 aprobaciones, resolution de threads), `required_status_checks` (**9 contextos**; `autonomy-evidence` temporalmente NO requerido hasta que aterrice en `main`), `copilot_code_review` | active | 2026-08-24T14:22:19+02:00 |
| 21250970 | `Luci` | `~ALL` | `deletion` (solo contra borrado) | active | 2026-08-23T22:32:00+02:00 |

### Explicación por ruleset

- **`LucidFence Autonomy B`** — protege `main`. Requiere PR con resolución de
  threads, historial lineal y 9 checks de CI. Bypass de integraciones
  (DeployKey, GitHub Apps de CI) en `always` para no frenar el merge automático.
  **Histórico:** en su creación incluía `~ALL` además de `~DEFAULT_BRANCH`, lo que
  heredaba el requisito de PR+checks a `cloud-state`/`recon-state` y provocaba
  `GH013` en los pushes programados (ver #270). El 2026-08-24 se eliminó `~ALL`,
  quedando solo `~DEFAULT_BRANCH`. No se creó ningún ruleset adicional.
  **2026-08-24T14:22Z (t_9c8c2878):** se eliminó el contexto `autonomy-evidence` de
  `required_status_checks` porque el workflow que lo emite (`autonomy-evidence.yml`)
  solo existía en el PR #264 (rojo) y no en `main`. Mientras tanto, los 9 checks
  reales permanecen intactos. Se volverá a añadir `autonomy-evidence` a lo requerido
  cuando su workflow esté mergeado en `main` y reportando en verde (ver Regla de
  precedencia).
- **`Luci`** — red de seguridad global (`~ALL`) que impide el borrado de cualquier
  rama, incluida `main` y las de datos. No impone PR ni checks, así que no bloquea
  los pushes directos de los crons a `cloud-state`/`recon-state`.

## Resultado verificado (#270)

- Pre-relax: `engine-cron` programado (run `32700808614`, 07:16Z) fallaba con
  `remote: error: GH013: Repository rule violations found for refs/heads/cloud-state`
  al hacer `git push origin cloud-state`.
- Post-relax: `engine-cron` programado (run `32704832665`, 08:09Z) **en verde** y
  empujó `482441c..34b82d5` a `cloud-state`.
- `recon-social-cron` (tras el fix #272 que lo mueve de `main` a `recon-state`):
  push exitoso a `recon-state` en el run `32701653434`.

## Registro de cambios (rulesets)

### 2026-08-24T14:22Z — DEADLOCK repo-wide por check fantasma (t_9c8c2878)

**Síntoma:** todos los PR verdes del repo aparecían `mergeStateStatus=BLOCKED`
aunque tuvieran 14/14 checks en verde y `mergeable=MERGEABLE` (p.ej. PR #289).
Causa: el ruleset 21249696 (`LucidFence Autonomy B`) requería el contexto
`autonomy-evidence`, pero el workflow que lo emite
(`.github/workflows/autonomy-evidence.yml`) **no existía en `origin/main`** — solo
vivía en la rama `bootstrap/autonomy-b-control-plane` del PR #264 (que a su vez
tenía 9 `evidence-*` checks en rojo). Resultado: ningún PR podía reportar el check,
así que todos quedaban bloqueados por diseño. Los merges recientes se hacían a mano
con el admin del propietario (`adrimg3196`) porque el bypass salta el ruleset.

**Resolución (Opción A del CTO):** se eliminó `autonomy-evidence` de
`required_status_checks` del ruleset 21249696, conservando los otros 9 checks
requeridos y todas las demás reglas (`deletion`, `required_linear_history`,
`pull_request`, `copilot_code_review`) y los 14 bypass actors. Verificación post-fix:
el JSON vivo del ruleset ya NO contiene `autonomy-evidence` (`any(== "autonomy-evidence")`
→ `false`). Tras forzar un recompute (re-run de un check en el head de #289), el
`mergeStateStatus` de #289 pasó de `BLOCKED` → `BEHIND` (estado normal por estar
detrás de `main`), y los 10 PRs abiertos pasaron de `BLOCKED` a `BEHIND`/`MERGEABLE`.
Deadlock roto sin bajar ninguna barra real de calidad.

**Backup del JSON original (pre-fix):** `/tmp/ruleset_21249696_backup.json`
(guardado por el worker antes del `PUT`; contiene `autonomy-evidence` y los 14
bypass actors). Para revertir: re-añadir `autonomy-evidence` al array
`required_status_checks` del ruleset 21249696 vía
`gh api -X PUT repos/adrimg3196/lucidfence/rulesets/21249696 --input <json>`
**solo cuando el workflow esté en `main`** (ver Regla de precedencia).

**Cuándo re-añadir `autonomy-evidence` a lo requerido:**
1. El PR #264 (o sucesor que traiga `autonomy-evidence.yml`) se mergea a `main`.
2. Se verifica en un PR real que el contexto `autonomy-evidence` reporta en verde.
3. Se hace `PUT` al ruleset 21249696 re-insertando el contexto.

## Flujo de cambio

1. Modificar el ruleset via `gh api` (o UI de GitHub → Settings → Rules).
2. **Antes de marcar un check como requerido, confirmar que su workflow está en
   `main` y reporta en verde** (ver Regla de precedencia / anti-deadlock).
3. No añadir `~ALL` ni las ramas de datos a rulesets con `pull_request`/`required_status_checks`.
4. Verificar un run programado en verde que avance la rama de datos correspondiente.
5. Actualizar esta tabla + CHANGELOG + cerrar el issue de regresión.
