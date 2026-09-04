# Loop budget & kill switch

Token/cost caps and the emergency stop for LucidFence improvement loops.
Enforced manually by the maintainer and (where possible) by CI.

## Aggregator policy (2026-08-22, decision t_bae7f2e4)

The `/loop` MoA improvement loop MUST stay 100%-free, consistent with the
SOAR/Multi-UEM claim (#188/#110) and the 100%-free posture of 2026-08-16.

- **Default aggregator ($0):** the local MoA server at `127.0.0.1:8085`, called
  with `moa_dry=true` (free local synthesis, no API keys, no cost). Same server
  already consumed by `lucidfence/core/ai.py`.
- **Fallback ($0):** deterministic local heuristic merge when MoA is down.
- **Opus 4.8 (PAID, opt-in ONLY):** used solely when an operator sets
  `LUCIDFENCE_CLAUDE_CLI=<absolute path to the claude binary>`. Auto-discovery
  of `claude` in PATH is intentionally DISABLED so the loop can never silently
  incur Opus spend. Enabling Opus requires explicit Product sign-off (business-
  model impact) recorded here; it breaks 100%-free.

This resolves the Finance & Ops alert of 2026-08-22: `loop_improve.py` previously
auto-selected `claude` (Opus 4.8, paid) as the aggregator, the only paid component
in the fleet. It is now the free local MoA by default.

## El recurso escaso REAL: tiempo de agente, no tokens de MoA (medido 2026-09-01)

Todo lo de arriba gobierna el aggregator del `/loop` MoA — que es **gratis**.
No gobierna el recurso que de verdad se agota y que ya tumbó rutinas: la
**cuota de uso de la cuenta**, consumida por el tiempo de agente de las 15
Routines programadas.

### Evidencia (no estimación: `last_run` real de cada Routine)

Tres Routines murieron **en 7-10 segundos**, sin ejecutar nada. Las sanas
corren entre 2 min y 5 h, así que no es un fallo de tarea sino de arranque.
Causa leída directamente de la sesión muerta de Deps-sweeper
(`cse_01PW28brvD6xVVhGaX19N9oX`):

```
post_turn_summary.status_detail: "You're out of usage credits."
rate_limit_info: {"rateLimitType":"seven_day_overage_included","status":"rejected"}
```

Ninguna de las tres es un bug del repo. Se quedaron sin cuota:

| Routine | cron | resultado |
|---|---|---|
| Tendencias → Producto | `30 23 * * 3` | FALLO en 7 s |
| Deps-sweeper | `40 22 * * 3` | FALLO en 10 s |
| Centinela seguridad | `7 22 * * 4` | FALLO en 7 s |

### Reparto medido del tiempo de agente (~14,3 h/semana)

| h/semana | % | Routine |
|---:|---:|---|
| 5,3 | 37% | Growth (martes) — **una sola pasada de 5 h 16 min** |
| 4,8 | 34% | Radar UEM/MDM (L-V) — 58 min × 5 |
| 1,9 | 13% | Housekeeper (diario) |
| 0,9 | 7% | Guardián CI/PRs (diario) |
| 1,4 | 9% | las otras seis, juntas |

**Growth + Radar = 71% del presupuesto de la flota.** Y las tres que mueren
están programadas justo detrás: miércoles 22:40 y 23:30, jueves 22:07 —
después de que Growth se coma 5 h el martes por la noche.

### Política

- **Tope de tiempo por pasada: 90 min.** Una Routine que pasa de ahí no está
  trabajando, está dando vueltas: debe cerrar con lo que tenga y dejar el
  resto anotado para el siguiente ciclo. Growth (5 h 16 min) y Radar (58 min)
  son los dos únicos que hoy se acercan o lo superan.
- **Los loops caros no van pegados a otros.** Growth (martes noche) precede
  directamente a las tres que fallan. Separar los pesados de los ligeros es
  gratis y evita que el caro deje sin cuota al barato.
- **Prioridad cuando la cuota aprieta**, de más a menos: (1) Daily del
  propietario y Guardián CI/PRs — son los ojos; (2) Housekeeper y Entrega de
  producto — mantienen el producto vivo; (3) Growth, Radar, Tendencias — son
  exploración, y la exploración puede esperar una semana sin que nada se
  rompa.
- **Un fallo por cuota NO es un fallo del repo.** Antes de investigar código,
  mirar `last_run`: una muerte en <30 s con `status_detail` de créditos es
  presupuesto, no bug. Perseguirlo como bug quema el tiempo que falta.

### Lo que este documento NO puede hacer

Nada de esto se enforcea desde el repo: las Routines viven en la plataforma,
no en `.github/workflows`. Los topes de arriba los aplica quien edita las
Routines (el propietario, o un agente con permiso para `update_trigger`).
Escribirlo aquí sirve para que la silla de Finanzas audite contra la realidad
medida en vez de contra los tokens de MoA, que son gratis y nunca fueron el
problema.

## Caps

- **Per-loop-run token cap:** 200k tokens (report-only triage).
- **Per-day token cap:** 500k tokens across all loops.
- **Max PRs reviewed per run:** 10.
- **Max attempts per fix:** 3 — after 3 failed verifier runs, escalate to human
  (do NOT keep retrying the same failing action).

## Kill switch

- Set the `loop-pause` label on any PR → loop stops commenting/acting on it.
- CI: set `LOOP_PAUSE=1` (repo secret or workflow input) to skip loop jobs.
- Manual: delete or pause the scheduled workflow.

## No-progress detection

- If a fix attempt fails the verifier 3×, write a short note to `docs/internal/loop-run-log.md`
  and stop. A human decides next steps.
- If readiness score drops >10 points week-over-week, open a maintenance issue.

## Allowlist (auto-merge)

Only these are auto-mergeable by a loop:
- Loop scaffolding docs (docs/internal/STATE.md, docs/internal/LOOP.md, docs/internal/loop-budget.md, docs/internal/loop-run-log.md).
- `loop-audit` CI workflow and dependabot patches for loop tooling.

Everything else (adapters, engine, desktop, security) requires human merge.

## Co-signed paid opt-in (Opus 4.8) — #188

Product sign-off for the paid aggregator path in `loop_improve.py` (the
`PAID_OPTIN_APPROVED #188` marker). Co-signed by CTO + PM.

- **Activation gate (unchanged, must stay):** the Opus 4.8 tier is ONLY used when
  the operator exports an ABSOLUTE path in `LUCIDFENCE_CLAUDE_CLI`. No env var ⇒
  the aggregator falls back to the 100%-free local MoA. Default fleet config sets
  nothing ⇒ billed cost is $0.00.
- **Exposure if the gate IS opened (informed figure, 2026-08-24 audit):** at
  measured fleet load (11.86M input + 248K output tokens/day over 67 runs / 6
  days), the Opus 4.8 tier costs **~$196/day ≈ $5,894/month ≈ $71,716/year**.
  This is authorized exposure, not current spend — billed cost of the fleet today
  is $0.00 (all 23 cron jobs + 12 profiles on `tencent/hy3:free`).
- **PM decision:** the co-sign is INFORMED, not nominal. The $0 / free-tier-only
  posture of LucidFence (AGENTS.md boundary) is NOT relaxed — this remains opt-in
  only. Any future change to the default (activating paid by default) requires a
  new ASK-FIRST + co-sign, not a silent flip.
- **Source of truth for the figure:** this file. `loop_improve.py` carries the
  same number inline next to the #188 marker.
