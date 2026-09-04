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

## Reglas de Oro (orden de primer nivel)

> Estas reglas son innegociables y se enforce mecánicamente (pre-flight o gate),
> no solo por disciplina del agente. Toda propuesta que las contradiga se rechaza
> en review sin excepción.

### Regla de Oro #1 — No añadir un check fantasma a `required_status_checks`

**Nunca añadir un contexto a `required_status_checks` (de cualquier ruleset de
protección de rama) antes de que el workflow que lo emite esté MERGEADO en
`origin/main` Y reportando en verde en una PR real.**

Razón (lección verificada 2026-08-24, tarea t_497540b9): el ruleset 21249696
"LucidFence Autonomy B" exigía el check `autonomy-evidence`, cuyo workflow solo
existía en el PR #264 (rojo) y NO en main. Ningún PR podía reportar el check →
todos los PR verdes quedaban **BLOCKED por diseño** (deadlock repo-wide: 10/10
PRs bloqueados). Se resolvió quitando el check fantasma (t_9c8c2878). Coste:
horas de deadlock en toda la flota.

La regla tiene dos mitades, ambas obligatorias:
1. **Workflow en `origin/main`** (no en una rama/PR). Se valida el job
   `name:` / job id / workflow `name:` contra el árbol de `origin/main`.
2. **Run verde en `origin/main`**: `gh run list` del workflow en la rama `main`
   con `--status success`. Un check "verde en mi rama" no cuenta — eso es
   justamente lo que causó el deadlock (t_925438a3: anti-falsos-positivos por
   staleness de rama).

Mecanismo de enforce (obligatorio en cualquier changeset que toque rulesets):
- **Pre-flight:** `python3 scripts/ruleset_check_guard.py --diff <changeset.diff>`
  (o `--context "<nombre>"` por cada contexto nuevo). Debe salir `exit 0`.
- **Auditoría periódica del ruleset vivo:** `python3 scripts/ruleset_check_guard.py --audit-live`
  (default ruleset 21249696). Debe salir `exit 0`.
- En review, el revisor exige el resultado del pre-flight en el cuerpo del PR;
  sin él, la review se rechaza. Ver `docs/operations/BRANCH_CONFIG.md` para el
  registro canónico de rulesets y el flujo de cambio.

La regla #1 es de aplicación transversal: se cumple **además de** las "cinco
reglas" operativas de abajo, no en su lugar.

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

### 1. WIP limit — 2 por implementador, gate de drenaje NO-SANA
El cuello de botella del repo no es producir PRs sino mergearlos. El gate de
producción se define por la **métrica NO-SANA** (fuente de verdad: el bloque
`## MODO DRENAJE` de `docs/internal/STATE.md`), no por un recuento fijo de PRs:

> Con **al menos 1 PR ABIERTA NO-SANA**, **nadie empieza trabajo nuevo**. El único
> trabajo permitido es drenar: rebasar, mergear o cerrar. Una PR abierta es
> NO-SANA si cumple CUALQUIERA: STALE (>7 días sin actividad) OR CONFLICTING
> (estado de merge `conflicting`) OR RED (cualquier check-run completado con
> conclusión failure/timed_out/canceled). Una PR verde pero `behind` main NO
> cuenta como NO-SANA (el raíl de auto-merge la drena).

El recuento histórico de «6 o más PRs abiertos» era un proxy aproximado del
gate NO-SANA y quedó obsoleto: con 1–5 PRs abiertas que incluyan una roja o en
conflicto, el gate NO-SANA sí bloquea nueva producción, mientras que el proxy de
«6 PRs» la habría permitido. La métrica de autoridad es NO-SANA, medida por
`scripts/merge_train.py` (ver Regla 1bis). Mientras haya >=1 PR NO-SANA, las
Routines productoras (Admin-value, Product Manager, Housekeeper, Tendencias,
Growth, Roadmap, Deps, Lanzamiento, Centinela) NO abren nuevas PRs; solo el
Guardián drena. Reanudación: productor vuelve a abrir PRs solo cuando 0 PRs
NO-SANAS estén abiertas.

### 1bis. El generador de la cola publica el gate NO-SANA de forma fiel
`scripts/merge_train.py` es la **única fuente de verdad** sobre si se permite
trabajo nuevo. Su salida (`render`) debe decir «MODO DRENAJE — no se puede
coger trabajo nuevo» cuando hay >=1 PR NO-SANA, y solo puede decir «se puede
coger trabajo nuevo» cuando el recuento de NO-SANAS es 0. La función `classify`
debe marcar `red`/`conflict`/`stale` como NO-SANA, y el render jamás debe
publicar «se puede coger trabajo nuevo» basándose solo en `over_limit`
(RecuentoTotal > GLOBAL_WIP_LIMIT). Ver `scripts/merge_train.py` y el bloque
`## MODO DRENAJE` de `docs/internal/STATE.md`.

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

## Definición operacional de DONE en el kanban

El tablero kanban es la fuente de verdad del estado de trabajo de los agentes.
Para que "DONE" signifique lo mismo que "entregado" en este charter, se aplica
la siguiente regla estricta (decisión CEO 2026-08-21, tarea t_86afa3e2):

> Una tarea de código solo se marca **DONE** cuando su cambio es ancestro de
> `origin/main` **Y** `python3 scripts/verify.py` (o el gate que corresponda)
> pasa **sobre `origin/main`**. Rama verde con PR abierto = estado "en review",
> nunca "done".

Comprobación obligatoria antes de cerrar cualquier tarea de código:
1. `git merge-base --is-ancestor <tip-de-la-rama> origin/main` → debe ser true.
2. El test/feature de la aceptación existe y pasa en `origin/main` (no solo en la
   rama del agente). Si el test queda `untracked`, CI no lo corre: no cuenta.
3. `python3 scripts/verify.py` APTO sobre `origin/main`.

### Script obligatorio: `scripts/kanban_done_gate.py`

La política de arriba NO se aplica a mano: todo cierre de una tarea de código
debe pasar por el guard `scripts/kanban_done_gate.py`, que implementa los tres
puntos de forma fall-closed (si no puede *demostrar* que el trabajo está en
`origin/main`, bloquea — no pasa por defecto). Contrato:

- `python3 scripts/kanban_done_gate.py <TASK_ID> --branch <rama-del-trabajo>`
  verifica los tres checks contra `origin/main` (en un worktree efímero) y:
  - exit 0 → APTO: se puede `hermes kanban complete`.
  - exit 1 → FALLO: NO marcar done. Con `--enforce` deja un comentario de
    evidencia y mueve la card a "en review".
  - exit 2 → NO EVALUABLE: la tarea no tiene rama conocida y no se pasó
    `--non-code`; el llamador debe declarar `--branch <rama>` o `--non-code`.
- Tareas de proceso/docs (sin rama): correr con `--non-code` para que el gate
  las deje pasar sin verificar ancestro/main.
- `verify.py` en `main` tiene una "batería runtime en vivo" que a veces está
  roja por causas ajenas a la card; por eso `--verify-mode` por defecto (`auto`)
  corre el verify completo y, si el único fallo es esa batería, cae a `--fast`
  y lo registra. Usa `--verify-mode full` si quieres exigir el verify completo.
- Integración en el cierre de una card de código:
  `python3 scripts/kanban_done_gate.py <TASK_ID> --branch <rama> --enforce
  --complete-on-pass` (marca done solo si pasa; si no, comenta y mueve a review).

Si el cambio vive solo en una rama (p. ej. `cto/88-management-mode-ownership`) y
`main` no lo contiene, la tarea NO está done: se crea una tarjeta hija "entregar
a main" y se deja la original como *trabajo-completado-en-rama*, no como
entregado. Esta desconexión fue el origen del incidente t_86afa3e2: #88/#89 se
marcaron done sin llegar a main, y el bot de QA abrió #205 contra un módulo
(`core/declarative.py`) que no existe en main.

## Guard de rulesets — anti-check-fantasma (Regla de Oro #1)

Todo changeset que modifique un ruleset y añada contextos a `required_status_checks`
debe pasar `scripts/ruleset_check_guard.py` **antes de aterrizar** (Regla de Oro #1,
tarea t_26b7fac6). El guard es fail-closed: si no puede demostrar que cada contexto
nuevo tiene workflow en `origin/main` con un run verde en `main`, bloquea:

```bash
python3 scripts/ruleset_check_guard.py --diff <(git diff origin/main... -- .github/rulesets ...) \
  && echo "RULESET_OK" || echo "RULESET_BLOCKED"
# auditoría del ruleset vivo:
python3 scripts/ruleset_check_guard.py --audit-live
```

En review de un PR que toque rulesets, el revisor exige el resultado del pre-flight
en el cuerpo del PR; sin él, la review se rechaza. Ver `docs/operations/BRANCH_CONFIG.md`.

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
