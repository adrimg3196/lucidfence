# Dirección — resumen ejecutivo semanal (el único canal al propietario)

Especificación del loop Dirección: cada lunes consolida la semana de la
flota de loops en UN informe ejecutivo y lo notifica (push + email). El
propietario no lee logs ni PRs para saber cómo va el proyecto: lee esto.

## Contenido del informe (en este orden)

1. **TL;DR** — 3 frases máximo.
2. **Lo nuevo** — features/mejoras mergeadas a `main` desde el informe
   anterior (PRs `feat:`/mejoras del Admin-value), en lenguaje de producto.
3. **Lo corregido** — fixes, limpieza aterrizada (Housekeeper), CI
   arreglado (Guardián), deps actualizadas.
4. **Tracción** — snapshot + delta vs informe anterior: stars, forks, issues abiertas,
   descargas por release (campo `download_count`
   de los assets), releases nuevas. Fuente: MCP de GitHub
   (`search_repositories` con `repo:adrimg3196/lucidfence` y
   `list_releases`). Sin inventar métricas que la API no da (los clones/
   views del traffic API requieren permisos de admin: si la llamada falla,
   se omite la fila, no se estima).
5. **Te espera** — PRs abiertas que aguardan decisión del propietario
   (Housekeeper, Deps-sweeper, gates humanos), con un veredicto de una
   línea cada una.
6. **Salud de la flota** — última línea de cada loop en el run-log común;
   loops que no corrieron cuando tocaba, en rojo.

## Mecánica

- Serie temporal: cada run añade UNA línea JSON a `traction.jsonl`
  (`{"date": "AAAA-MM-DD", "stars": n, "forks": n,
  "open_issues": n, "release_downloads": {"vX.Y.Z": n, ...}}`). Los deltas
  del informe salen de comparar con la línea anterior. Append-only.
- Informe: `docs/internal/exec/AAAA-MM-DD.md`, con front matter
  `type: exec-report` y `date:`.
- Todo va en una PR desde `claude/exec-digest` (solo ficheros de
  `docs/internal/exec/` + su línea de run-log), mergeable con el gate QA.
- El resumen del mensaje final de la sesión ES la notificación que le llega
  al propietario: escribirlo como para un CEO — resultados y decisiones,
  no procedimiento.

## Reglas

- Deltas honestos: primera aparición de una métrica = "primera medición",
  no delta. Métrica no disponible = fila omitida con nota, nunca estimada.
- Sin relleno: una semana floja es un informe corto.
- Este loop no toca producto: si detecta un problema, lo deriva a la cola
  del loop dueño (contrato de coordinación, regla 3).
