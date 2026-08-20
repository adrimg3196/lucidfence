# Políticas y geocercas como código: `lucidfence apply`

La config del tenant (`fences.json` + `policies.json`) puede vivir en git y
aplicarse con un comando, estilo GitOps. Fleet popularizó este flujo para
posture (YAML validado con errores precisos por release); LucidFence lo trae
al geofencing con dos diferencias: **no necesita servidor** (el comando opera
sobre el data dir local) y añade el **replay what-if** — antes de aplicar,
reproduce el cambio contra el histórico real de la flota y te dice qué habría
disparado. Ningún otro producto del sector enseña el efecto de una config
antes de activarla.

```
lucidfence apply --fences fences.json [--policies policies.json] \
                 [--data-dir <dir>] [--yes]
```

Por defecto es **dry-run**: imprime el plan y no escribe nada. Solo `--yes`
aplica. Exit code `0` únicamente si la config candidata es válida.

## Las 4 fases

1. **VALIDAR** — con los mismos validadores que usa el engine
   (`validate_fences` / `validate_policies`): ids duplicados, círculo sin
   centro/radio, polígono con <3 puntos o auto-intersectado, `when` vacío,
   ops fuera de `eq|ne|gt|gte|lt|lte|in|contains`, acciones fuera del catálogo
   que los adapters ejecutan, severidades inválidas. Cada error en una línea
   con `fichero: id: motivo`. Cualquier error → exit 1 y no se aplica nada.
2. **DIFF** — compara por id contra la config viva del data dir e imprime
   `+` (añadido), `~` (cambiado), `-` (eliminado). La comparación es sobre la
   forma canónica que ve el engine, no sobre el formato del fichero.
3. **WHAT-IF** — reproduce las políticas que quedarían activas tras el apply
   (las candidatas, o las vivas si solo cambias geocercas) contra el histórico
   local (`trails.jsonl`) con `policy_replay`: "con esta config habrían
   disparado N acciones". Si el cambio trae geocercas, el estado dentro/fuera
   se recalcula contra las candidatas. Sin histórico lo dice tal cual
   ("sin histórico para simular") — nunca inventa. Marca `[aproximado]` cuando
   la policy usa señales no espaciales (postura de hoy sobre posiciones de
   ayer) y avisa si incluye acciones destructivas.
4. **APLICAR** (solo `--yes`) — escritura atómica (tmp + `os.replace`) del
   candidato tal cual en `<data-dir>/fences.json` y `<data-dir>/policies.json`.
   El engine carga la config al arrancar: reinicia o recarga la app
   (`lucidfence restart`) para que tome efecto.

El comando **jamás toca un dispositivo**: solo escribe ficheros locales. El
runtime sigue mandando en el engine (dry_run por defecto, enforce opt-in,
wipe con doble llave).

## Flujo GitOps recomendado

1. La config vive en un repo git (`fences.json`, `policies.json`).
2. Cada cambio llega por PR; en CI corre
   `lucidfence apply --fences fences.json --policies policies.json --data-dir <dir>`
   (dry-run): valida, enseña el diff y el what-if en el log de la PR, y el
   exit code bloquea el merge si la config es inválida.
3. Al desplegar (merge a main), el mismo comando con `--yes` aplica y se
   recarga la app.

## Ejemplo de salida (dry-run)

```
LucidFence · apply · dry-run (usa --yes para aplicar)
Data dir: /home/op/.local/state/lucidfence

[1/4] VALIDAR
  OK  fences.json: 3 geocercas válidas
  OK  policies.json: 4 políticas válidas

[2/4] DIFF contra la config viva del data dir
  fences.json:
    + almacen-norte
    ~ demo-hq
    - cerca-obsoleta
  policies.json:
    sin cambios

[3/4] WHAT-IF (replay del cambio sobre el histórico local)
  pol-rooted-outside: con esta config habrían disparado 14 acciones (notify×7, wipe×7)
  en 3 dispositivo(s) sobre 5000 puntos [aproximado]
    ATENCIÓN: incluye acciones destructivas: wipe

[4/4] APLICAR
  dry-run: no se ha escrito nada. Repite con --yes para aplicar.
```

Y un candidato roto falla con el id y el motivo, uno por línea:

```
[1/4] VALIDAR
  ERROR fences.json: patio-sur: polygon is self-intersecting (invalid)
  ERROR policies.json: pol-turno: condición 'fence_state' con op desconocido 'equals' (usa contains|eq|gt|gte|in|lt|lte|ne)

2 error(es) de validación: no se aplica nada.
```
