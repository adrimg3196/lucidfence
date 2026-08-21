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
| `2026-08-21-declarative-enforcement.md` | LinkedIn/X (técnico) | Matriz declarativa VERIFICADA + asimetría DDM build-only vs DSC end-to-end + matiz lock-only + historia #205/#206 | ⛔ **EN HOLD** — disputa fáctica sobre "DSC end-to-end" (ver §HOLD abajo) |
| `2026-08-21-blast-radius-uem.md` | X (thread) + LinkedIn | Radio de explosión del UEM: destructivas human-gated + cooldown persistido + evidencia HMAC al SIEM propio + local-first + $0 | CTO co-firma pendiente + owner gate |
| `2026-08-21-no-goals.md` | LinkedIn/Reddit + X (corto) | "Lo que LucidFence NO hace": 6 no-goals publicados (incl. cero declarativo en Android #42, sin edición de pago) | PM alineación pendiente + CTO (solo puntos 4-5) + owner gate |

## ⛔ HOLD 2026-08-21 — `2026-08-21-declarative-enforcement.md` (Marketing)
La pieza está co-firmada pero **no es publicable**: el claim "Windows DSC = end-to-end
real vía Microsoft Graph" no se sostiene en `origin/main`.
Verificación de Marketing (hoy, contra `origin/main`):
- `windows_conformidad._apply_dsc` **solo genera** manifests (`dsc_v3`,
  `dsc_classic_ps1`, `dsc_classic_mof`) y devuelve `applied: True` — cero POST.
- El único `POST` del adapter (`windows_conformidad.py:91`) es la obtención de **token
  OAuth**; `_report_live` es un **GET** a `deviceManagement/managedDevices` para la
  acción `report` (read-back de conformidad, no entrega del manifest).
- La cita a `core/declarative.py` que el CTO marcó como falsa **es correcta hoy**:
  `engine.py:32` importa `declarative_path_for` desde `lucidfence.core.declarative`.
  Hay además una segunda definición en `ddm.py:123` (duplicidad real en código).
=> Hasta que el CTO resuelva, **ninguna pieza nueva usa el ángulo declarativo** y las
líneas afectadas del post de no-goals van marcadas `[⛔ CTO]`.

## RED LINE (del CTO, #110) — no negociable en ningún borrador
NO decir "Intune/Jamf live" incondicionalmente. Claim honesto obligatorio:
> Multi-UEM simultáneo por tenant: **Applivery live por defecto**; **Intune/Jamf en
> modo live al conectar tu token** (simulación sin token). Cero exfiltración.

## CORRECCIÓN DE GATE (Marketing, 2026-08-20) — claim SOAR webhook
Los borradores originales decían "webhook BYO con egress SSRF-hardened, cierra RFC1918
y DNS-rebinding". Verificado en runtime: la política `PublicEgressPolicy` (RFC1918 +
DNS-rebinding + pinned-IP) SÓLO existe en `lucidfence/core/oidc.py` (fetch de IdP OIDC).
El webhook de salida real (`lucidfence/core/notifier.py`) PERMITE deliberadamente SIEMs
internos (10.x/loopback); bloquear RFC1918 rompería ese caso de uso por diseño.
=> Claim corregido en linkedin-diferente.md y x-thread.md: webhook BYO **firmado
HMAC-SHA256 por tenant (`X-LucidFence-Signature`)**, dirigido al SIEM que ya uses.
Esto sigue siendo un claim verificado y honesto. `.cto_input_188.md` (Decisión 1)
había escrito "SSRF-hardened" para el webhook: el código NO lo respalda tal cual; el
wording de marketing ahora refleja el hardening real (firma por tenant, no egress-RFC1918).

## Estado de reconciliación (2026-08-21 · kanban t_0a1ba0d1)
- `docs/gtm/launch-copy/` (x-thread, linkedin, contributors) **reconciliado**:
  eliminado el claim pagado "Enterprise on-prem cerrado / open-core"; ahora usan
  framing 100% free OSS ($0, donaciones). Llevan banner RECONCILIADO; no son copy
  canónico (la copia aprobada vive aquí, en `outbox/`).
- `docs/gtm/{marketing-copy,launch-plan,PRODUCT_BRIEF,ACQUISITION_NARRATIVE,VALIDATION_SCRIPT}.md`
  **marcados SUPERSEDED** (pre-2026-07-27, framing open-core pagado). Históricos; no
  usar para outreach.
- Fuente de verdad de posicionamiento: `docs/gtm/revenue-model.md` + `docs/internal/STATE.md`
  override. Riesgo de integridad #110 cerrado para estos docs.

## Sign-off de messaging (CTO · kanban t_1def7405 — GAP de proceso cerrado)
Antes de aprobar cualquier `outbox/` item, corre el **Gate 2 de posicionamiento**
(cierra la reincidencia del claim de negocio descartado, no solo el matiz técnico #188):
```bash
python3.11 scripts/gtm_claim_linter.py --scope outbox
```
Devuelve `0 BLOCK` → apto. Cualquier `[BLOCK]` = posicionamiento prohibido
(enterprise pagado / open-core / on-prem cerrada / pricing). Proceso completo,
RED LINE técnica #188 y frases prohibidas en `docs/gtm/MESSAGING_SIGNOFF.md`.
Fuente de verdad de posicionamiento: `revenue-model.md` + `STATE.md` override.
