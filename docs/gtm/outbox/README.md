# Outbox de Growth — borradores para aprobación del propietario

Todo borrador aquí es **NO publicable por el agente**. El loop de Growth NO tiene
cuenta en X/LinkedIn/Reddit/HN; publica el propietario (Adri) con copy/paste tras
aprobar el PR `outreach:` o este outbox. Máx. 1 publicación externa por ciclo
(regla del loop Growth, `docs/internal/growth/README.md`).

## Ciclo 2026-08-20 (Marketing & Growth Bot)

Borradores generados hoy, construidos SOBRE consultas CTO/PM **ya cerradas** en kanban:
- `t_8f3731df` (done) — CTO→Marketing: matriz real UEMs live/mock para copy #188.
- `t_d000d423` (done) — Marketing: copy multi-UEM CON MATIZ (#188/#110).
- `t_1e921803` (done) — CTO→PM: 4 decisiones abiertas #188 cerradas.
- `t_544e867b` (done) — CTO fusionó `cto/multiuem-adapters-soar` → claim multi-UEM+SOAR desbloqueado.

=> No se creó tarea de consulta nueva a CTO/Product: el messaging ya está alineado y verificado en runtime.

## Piezas

| Archivo | Plataforma | Claim central | Aprobación |
|---|---|---|---|
| `2026-08-20-linkedin-diferente.md` | LinkedIn (CISO/MSP) | Soberanía + riesgo explicable + multi-UEM(matiz) + SOAR | owner gate |
| `2026-08-20-x-thread.md` | X/Twitter (thread) | "Tu MDM te cobra el geofencing con tu ubicación" | owner gate |
| `2026-08-20-quien-es.md` | X/LinkedIn (corto) | Verticales: logística, retail, field service, sanidad, banca, defensa, gob, MSP | owner gate |

## RED LINE (del CTO, #110) — no negociable en ningún borrador
NO decir "Intune/Jamf live" incondicionalmente. Claim honesto obligatorio:
> Multi-UEM simultáneo por tenant: **Applivery live por defecto**; **Intune/Jamf en
> modo live al conectar tu token** (simulación sin token). Cero exfiltración.

## Pendiente sugerida al propietario
Los borradores en `docs/gtm/launch-copy/` (x-thread, linkedin, contributors) aún usan
"modo mock" para Intune/Jamf y no llevan el matiz ni los claims SOAR de #188. Al
fusionar este outbox, refrescarlos al wording verificado de arriba (tarea ya hecha
`t_d000d423`, pero los drafts launch-copy no se actualizaron).
