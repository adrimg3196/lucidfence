# LucidFence — Empresa de Desarrollo Autónoma (Kanban)

LucidFence se opera como una **empresa de desarrollo autónoma**: un board Kanban
donde cada especialista es un perfil de Hermes que ejecuta tareas de forma
independiente, y un conjunto de **disparadores automáticos** mantiene el flujo
sin intervención humana.

## Arquitectura

```
                        ┌─────────────────────────────────────────┐
                        │  Gateway (launchd, PID supervisor)         │
                        │  → dispatcher embebido cada 60s            │
                        │  → toma tareas ready → spawnea especialista│
                        └─────────────────────────────────────────┘
                                       │
                  ┌────────────────────┼─────────────────────┐
                  ▼                    ▼                     ▼
           tareas (board)      crons (disparadores)    self-service (issues)
```

## Board

- **Board:** `lucidfence` (`hermes kanban boards switch lucidfence`)
- **Lanes:** backlog → todo → ready → running → review → done (bloqueadas en `blocked`)
- **Equipo (assignees):** `default` (PM/orquestador) + 9 especialistas UEM/MDM:
  `apple-mdm-specialist`, `android-enterprise-specialist`, `windows-mdm-specialist`,
  `oem-frontline-specialist`, `integrations-specialist`, `applivery-api-specialist`,
  `chromeos-mdm-specialist`, `competitive-intel-specialist`, `vault-curator`.

## Disparadores automáticos

| Disparador | Mecanismo | Frecuencia | Qué hace |
|---|---|---|---|
| **Dispatch continuo** | `hermes gateway` (dispatcher embebido) | cada 60s | Toma tareas `ready` y las ejecuta con el especialista asignado en paralelo |
| **Seed diario** | cron `lucidfence-daily-seed` → `lucidfence_daily_seed.py` | 08:00 diario | Siembra 2 tareas de mejora rotando por un pool de ideas |
| **Monitor de salud** | cron `lucidfence-monitor` → `lucidfence_monitor.py` | cada 30 min | Si tests<110, vitrina cae o estado no accesible → crea tarjeta de fix automática |
| **Ingesta self-service** | cron `lucidfence-issue-ingest` → `lucidfence_issue_ingest.py` | cada 15 min | Issues de signup → tarjeta de onboarding comercial en el board |

## Scripts

- `scripts/lucidfence_kanban_seed.sh` — siembra el backlog inicial (13 tareas).
- `~/.hermes/scripts/lucidfence_daily_seed.py` — seed diario (cron).
- `~/.hermes/scripts/lucidfence_monitor.py` — health-check + auto-fix (cron).
- `~/.hermes/scripts/lucidfence_issue_ingest.py` — ingesta de prospects (cron).

> Los scripts de cron viven en `~/.hermes/scripts/` (requisito del scheduler) y
> apuntan a `LUCIDFENCE_ROOT=/Users/adri/geofence-uem`.

## Cómo operar

```bash
# Ver el board
HERMES_KANBAN_BOARD=lucidfence hermes kanban list

# Sembrar backlog (una vez)
bash scripts/lucidfence_kanban_seed.sh

# El gateway ya corre (launchd); el dispatch es automático.
# Para forzar un tick: hermes kanban dispatch --dry-run
```

## Notas de calidad

- El runner de tests es **honesto** (110 pass = green). El monitor lo vigila.
- Las tareas de código usan workspaces `scratch`/`worktree` aislados.
- El self-service del prospecto (issue → tenant → vitrina) y el board están
  conectados: un prospecto que se registra entra al flujo de la empresa.
