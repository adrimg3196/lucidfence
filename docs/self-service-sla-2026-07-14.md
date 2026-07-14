# Self-service E2E SLA — GitHub Issue → tenant → vitrina

Fecha de validación: 2026-07-14 UTC
Estado: PASS con nota operativa
Confianza: alta para el flujo observado; media para el SLA puramente basado en `schedule` porque durante la prueba la publicación efectiva llegó por un push concurrente que regeneró `data/cloud_state.json`.

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

El mensaje de producto “en ≤15 min tu tenant aparece” se cumplió en la prueba observada. Aun así, la publicación no quedó demostrada como dependiente exclusivamente del cron `engine-cron.yml`: durante la ventana de prueba hubo pushes concurrentes y el snapshot publicado (`generated_at=2026-07-14T15:27:16Z`) apareció antes del siguiente cron visible en `gh run list --workflow engine-cron.yml`.

Riesgo: si no hay ningún push concurrente y GitHub retrasa o salta el cron, el SLA efectivo puede depender de la cadencia real de Actions scheduled workflows, no solo de la expresión `*/15 * * * *`.

## SLA documentado

SLA comercial recomendado: “normalmente visible en 5–15 min; objetivo ≤15 min”.

SLA técnico observado en esta validación: 4m34s desde creación del issue hasta visibilidad en vitrina pública.

## Próximos pasos

1. Hacer determinista el SLA: al final de `saas-signup.yml`, disparar `engine-cron.yml` vía `workflow_dispatch` o ejecutar `cloud_publisher.py` y commitear `data/cloud_state.json` en el mismo workflow.
2. Corregir el mensaje de commit de `saas-signup.yml`: hoy sale `cloud: tenant desde signup (#)` porque `ISSUE_NUMBER` no está disponible en el step `Commitear tenant`; añadirlo a `env` en ese step.
3. Añadir monitor SLA: crear una alerta si `cloud_state.json` no contiene el tenant N minutos después del comentario automático en el issue.
