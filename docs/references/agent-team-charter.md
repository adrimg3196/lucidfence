# Agent team charter — cómo opera la "empresa" de agentes en LucidFence

Estado medido el **2026-08-13** sobre `adrimg3196/lucidfence`:

| Métrica | Valor |
|---|---|
| PRs abiertos | 21 |
| PR abierto más antiguo | 16 días |
| PRs con CI verde y aun así sin mergear | 11 |
| PRs con conflicto real (`mergeStateStatus: DIRTY`) | todos los muestreados (#47, #66, #85, #91, #96) |
| PRs mergeados en los últimos 21 días | 15 |
| PRs mergeados en los últimos 6 días | 0 |
| Issues abiertas | 29 |

El equipo (Zero, Jules, Hermes — ver `AGENTS.md`) **produce bien y entrega mal**.
La producción no es el cuello de botella: el merge lo es. Los PRs pasan CI, se
quedan parados 10–16 días, `main` avanza por debajo y acaban en conflicto. El
issue #78 ("Rebasar los PRs abiertos que quedaron bloqueados por el deadlock del
#74") es el síntoma nombrado desde dentro.

Añadir más agentes con estas reglas empeora el problema: más PRs en paralelo
sobre el mismo código = más conflictos = más rot. Este charter existe para
arreglar la organización, no la capacidad.

## Roles

| Rol | Quién | Responsabilidad | Límite |
|---|---|---|---|
| CEO | Adri | Dirección de producto y decisiones de negocio. No revisa código. | — |
| Coordinador | Zero (Claude/OpenClaw) | Merge train, dedupe, gate de review, crons | 1 merge en vuelo |
| Implementador | Jules (Google) | Un issue → un PR | 2 PRs abiertos |
| Implementador | Hermes (Nous) | Un issue → un PR | 2 PRs abiertos |

Cualquier agente nuevo entra como Implementador con el mismo límite de 2. El rol
de Coordinador **no se duplica**: dos coordinadores es no tener ninguno.

## Las cinco reglas

### 1. WIP limit — 2 por implementador, 6 en total
Si hay 6 o más PRs abiertos, **nadie empieza trabajo nuevo**. El único trabajo
permitido es drenar: rebasar, mergear o cerrar. Esta es la regla que impide que
21 PRs se vuelvan a acumular.

### 2. Claim antes de tocar código
Antes del primer commit: asignarse la issue en GitHub y ponerle la label
`claimed:<agente>`. Sin claim, el trabajo se considera duplicado y se cierra.
Esto sustituye el reparto informal que `AGENTS.md` describe hoy ("task split
still informal, no shared queue").

### 3. Rebase antes de pedir merge
Un PR que lleva más de 3 días sin rebasar sobre `main` se marca
`stale-rebase` automáticamente. Un PR `DIRTY` es responsabilidad de su autor,
no del coordinador — el coordinador no arregla conflictos ajenos.

### 4. Merge train — FIFO, de uno en uno
El coordinador mergea en orden de antigüedad, solo PRs verdes y `MERGEABLE`, y
**uno cada vez**. Tras cada merge, el siguiente de la cola rebasa antes de
entrar. Mergear en paralelo es lo que generó la tanda de conflictos actual.

### 5. Escalado al CEO — solo lo irreversible
Al CEO le llega un resumen pasivo, no una petición de aprobación. Solo se le
pregunta antes de: gastar dinero, publicar una release pública, o cualquier
acción no reversible. Todo lo demás (código, tests, triage, rebases, merges)
corre sin él. Ver `Boundaries` en `AGENTS.md` (ASK FIRST / NEVER).

## Definición de "entregado"

Un PR está entregado cuando está **mergeado en `main`**, no cuando está abierto y
verde. Un agente cuyo trabajo se acumula en PRs abiertos no está entregando,
por muy verde que esté su CI. La métrica del equipo es *PRs mergeados por
semana*, no PRs abiertos.

Calidad mínima antes de entrar al train: `docs/references/definition-of-done.md`.

## Cola compartida

`scripts/merge_train.py` calcula el estado real de la cola desde la API de
GitHub y lo publica en una issue fija con label `merge-train`. Esa issue es la
**única fuente de verdad** sobre quién va primero. Se regenera sola (workflow
`merge-train.yml`, 2 veces al día); nadie la edita a mano.

```bash
python3 scripts/merge_train.py                # informe por consola
python3 scripts/merge_train.py --publish      # actualiza la issue de la cola
python3 scripts/merge_train.py --enforce      # etiqueta stale-rebase / wip-over-limit
```

## Aislamiento del checkout

Regla ya vigente en `AGENTS.md` y que este charter no relaja: **nunca editar
`/Users/adri/geofence-uem` directamente**. Ese checkout se resetea en duro sin
aviso y se ha comido ediciones sin commitear dos veces. Todo trabajo
interactivo va en un worktree propio:

```bash
git worktree add ../geofence-uem-<nombre> -b <rama> origin/main
```

**Identidad por worktree — usa `--worktree`, no `--local`.** `git config
--local` en un worktree escribe en la config COMPARTIDA de todos los
worktrees: el 2026-08-13 un agente configuró así su identidad y mal-atribuyó
el commit de otro que estaba trabajando en paralelo (mismo mecanismo que el
incidente Zero/Hermes del 2026-08-02). `extensions.worktreeConfig` ya está
activado en el repo; la forma correcta:

```bash
git config --worktree user.name "<Agente>"
git config --worktree user.email "<agente>@lucidfence.local"
```

Verifica con `git config user.email` ANTES de cada commit, no solo al crear
el worktree.
