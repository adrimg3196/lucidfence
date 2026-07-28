# Self-service E2E SLA — GitHub Issue → tenant → vitrina

Fecha de validación: 2026-07-14 UTC
Estado: PASS — SLA ahora determinista (ver cambios de t_ada1c510)
Confianza: alta. El SLA es ahora determinista: la publicación de `data/cloud_state.json` se hace en el propio run de `saas-signup.yml` (no por push concurrente ni por esperar al cron).

## Resultado

El flujo self-service quedó validado end-to-end con un tenant real creado desde GitHub Issues y visible en `cloud.html` dentro del SLA prometido de ≤15 min.

- Tenant: `kanban-t314a3b3a-20260714-1524`
- Issue fuente: https://github.com/adrimg3196/lucidfence/issues/8
- Issue creado: 2026-07-14T15:25:50Z
- `saas-signup.yml`: success en 12s, run `29345296720`, iniciado 2026-07-14T15:25:54Z
- Comentario automático de creación de tenant: 2026-07-14T15:26:02Z
- `cloud.html` / `cloud_state.json` observado con el tenant: primer hit de polling a 2026-07-14T15:30:24Z
- `generated_at` del snapshot publicado: 2026-07-14T15:27:16Z
- Tiempo issue → visible en vitrina: ~4m34s
- Flota publicada: 4 dispositivos (`zebra-reparto-01`, `iphone-ventas-02`, `ipad-almacen-03`, `xcover-ops-04`)

## Evidencia

Fuentes verificadas:

1. Issue GitHub #8 con bloque `<!-- lucidfence-signup -->`, label `signup` y comentario de `github-actions` confirmando creación del tenant.
2. GitHub Actions `saas-signup.yml` run `29345296720`: completed/success, duración 12s.
3. `https://raw.githubusercontent.com/adrimg3196/lucidfence/main/data/cloud_state.json`: contiene `kanban-t314a3b3a-20260714-1524`, 4 dispositivos, 3 dentro y 1 fuera.
4. `https://adrimg3196.github.io/lucidfence/cloud.html`: selector filtrado por `kanban-t314a3b3a` muestra `kanban-t314a3b3a-20260714-1524 — 4 dev` y la tabla de flota con los 4 dispositivos.

## Nota operativa sobre el SLA

~~El mensaje de producto “en ≤15 min tu tenant aparece” se cumplió en la prueba observada. Aun así, la publicación no quedó demostrada como dependiente exclusivamente del cron `engine-cron.yml`: durante la ventana de prueba hubo pushes concurrentes y el snapshot publicado (`generated_at=2026-07-14T15:27:16Z`) apareció antes del siguiente cron visible en `gh run list --workflow engine-cron.yml`.~~

**Resuelto por t_ada1c510 (2026-07-14):** el SLA ya es determinista. El workflow `saas-signup.yml` ahora **regenera `data/cloud_state.json` con `cloud_publisher.py` y lo commitea/pushea en el MISMO run** que crea el tenant, inmediatamente después del commit del tenant. Ya no depende de un push concurrente ni de esperar al cron `engine-cron.yml` (que sigue corriendo cada 15 min solo para mantener viva la flota demo). El commit de publicación lleva el número de issue (`cloud: publicar vitrina tras signup (#N)`) y el paso está condicionado a `steps.parse.outputs.tenant_created == 'yes'`, de modo que issues sin bloque de signup no regeneran la vitrina.

Con esto, el SLA efectivo pasa de "5–15 min (cadencia del cron)" a **segundos tras el commit de tenant** (el tiempo de un ciclo de `cloud_publisher.py` + push), eliminando la dependencia de la cadencia de Actions scheduled.

## SLA documentado

SLA comercial recomendado: "tu tenant aparece en la vitrina en segundos tras el registro (publicado en el mismo run de GitHub Actions); objetivo ≤15 min como tope de seguridad".

SLA técnico observado en esta validación (antes del cambio): 4m34s desde creación del issue hasta visibilidad en vitrina pública. Tras t_ada1c510 el publish es inmediato tras el commit de tenant.

## Próximos pasos

1. ✅ **Hecho (t_ada1c510):** SLA determinista. `saas-signup.yml` ejecuta `cloud_publisher.py` y commitea `data/cloud_state.json` en el mismo run (sin depender del cron `engine-cron.yml`).
2. ✅ **Hecho (t_ada1c510):** el commit de tenant ahora propaga `ISSUE_NUMBER` (`cloud: tenant desde signup (#N)`) y hay un commit de publicación `cloud: publicar vitrina tras signup (#N)`.
3. Añadir monitor SLA: crear una alerta si `cloud_state.json` no contiene el tenant N minutos después del comentario automático en el issue.
