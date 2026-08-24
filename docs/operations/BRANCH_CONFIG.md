# Registro de configuración de ramas (branch protection)

Registro canónico de las reglas de protección de ramas de `adrimg3196/lucidfence`
(GitHub **rulesets**, no branch protection clásica). Cualquier cambio en la
protección de ramas debe actualizar este archivo y la entrada del CHANGELOG.

Última verificación: 2026-08-24 (cine requerido para cerrar #270 / regresión engine-cron).

## Regla de oro

- `main` (rama por defecto) mantiene PR + 10 checks + historial lineal.
- Las **ramas de datos** (`cloud-state`, `recon-state`) son efímeras y las escriben
  directamente los workflows programados (`engine-cron`, `recon-social-cron`).
  Por tanto **NO** pueden tener requisito de PR ni checks: solo protección contra
  **borrado** (`deletion`). Cualquier ruleset que aplique a `~ALL` o a estas ramas
  con reglas `pull_request` / `required_status_checks` rompe el push programado
  (error `GH013`).

## Rulesets activos

| ID | Nombre | Target (`include`) | Reglas | Estado | Último cambio |
|----|--------|--------------------|--------|--------|---------------|
| 21249696 | `LucidFence Autonomy B` | `~DEFAULT_BRANCH` (solo `main`) | `deletion`, `required_linear_history`, `pull_request` (0 aprobaciones, resolution de threads), `required_status_checks` (10 contextos), `copilot_code_review` | active | 2026-08-24T09:27:46+02:00 |
| 21250970 | `Luci` | `~ALL` | `deletion` (solo contra borrado) | active | 2026-08-23T22:32:00+02:00 |

### Explicación por ruleset

- **`LucidFence Autonomy B`** — protege `main`. Requiere PR con resolución de
  threads, historial lineal y los 10 checks de CI. Bypass de integraciones
  (DeployKey, GitHub Apps de CI) en `always` para no frenar el merge automático.
  **Histórico:** en su creación incluía `~ALL` además de `~DEFAULT_BRANCH`, lo que
  heredaba el requisito de PR+checks a `cloud-state`/`recon-state` y provocaba
  `GH013` en los pushes programados (ver #270). El 2026-08-24 se eliminó `~ALL`,
  quedando solo `~DEFAULT_BRANCH`. No se creó ningún ruleset adicional.
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

## Flujo de cambio

1. Modificar el ruleset via `gh api` (o UI de GitHub → Settings → Rules).
2. No añadir `~ALL` ni las ramas de datos a rulesets con `pull_request`/`required_status_checks`.
3. Verificar un run programado en verde que avance la rama de datos correspondiente.
4. Actualizar esta tabla + CHANGELOG + cerrar el issue de regresión.
