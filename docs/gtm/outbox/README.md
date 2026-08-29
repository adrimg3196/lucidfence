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
| `2026-08-21-declarative-enforcement.md` | LinkedIn/X (técnico) | Matriz declarativa VERIFICADA + asimetría real DDM **y** DSC ambos build-only (no end-to-end Graph) + matiz lock-only + historia #205/#206 | ✅ **Gate 0: CO-FIRMADO CTO** (`t_1a407df5`) — claim "DSC end-to-end" corregido; owner gate |
| `2026-08-21-blast-radius-uem.md` | X (thread) + LinkedIn | Radio de explosión del UEM: destructivas human-gated + cooldown persistido + evidencia HMAC al SIEM propio + local-first + $0 | ⛔ **Gate 0: CO-FIRMA CTO PENDIENTE** (`t_3ed8dedf`) + owner gate |
| `2026-08-21-no-goals.md` | LinkedIn/Reddit + X (corto) | "Lo que LucidFence NO hace": 6 no-goals publicados (incl. cero declarativo en Android #42, sin edición de pago) | PM alineado (1-3,6) + ✅ **Gate 0: CO-FIRMADO CTO pts 4-5** (`t_7b575db8`, arbitraje `t_2c00a8f2` decisión A) + owner gate |
| `2026-08-23-caep-ssf-emisor.md` | LinkedIn/X (técnico) | Emisor CAEP/SSF fase 1: emite eventos `device-compliance-change` firmados **ES256** (ECDSA P-256), local-first, Apache-2.0; EdDSA/Ed25519 excluidos por construcción; solo EMISOR (fase 2 Receptor / fase 3 Streaming OFF fuera de alcance) | ⛔ **Gate 0: CO-FIRMA CTO PENDIENTE** (`t_4943afe7`) + owner gate |
| `2026-08-25-network-location-geofencing.md` | X (thread) + LinkedIn (técnico) | Geofencing sin GPS: `network_sites` declarados por el operador (CIDR/SSID/BSSID) → ubicación gruesa honesta; precedencia BSSID>SSID>CIDR; cero terceros (ni geoip ni MaxMind); nunca inventa ni sobreescribe fix real; inerte sin configurar | ⛔ **Gate 0: CO-FIRMA CTO PENDIENTE** (tarjeta hija de `t_a8252f28` por crear) + linter NO ejecutado + owner gate |
| `2026-08-26-geofencing-myths.md` | X (thread, educación de categoría) | 3 mitos del geofencing MDM + fit LucidFence (reusa co-firmado: local-first, $0/Apache-2.0, evidence gate, multi-UEM #110, SOAR HMAC) | owner gate (sin claim técnico NUEVO → no requiere co-firma CTO; sugiere revisión PM por ser pieza de producto) |
| `2026-08-28-fail-unknown-no-false-green.md` | X (thread) + LinkedIn (CISO/MSP) | **fail-unknown, nunca falso-verde**: cuando no hay señal el dispositivo queda "Riesgo desconocido (sin señal)" (engine.py:297, origin/main 3c6ef66/c8e264c); diferencial honesto vs paneles UEM que pintan verde sin datos. Reusa evidence gate co-firmado. | ⛔ **Gate 0: CO-FIRMA CTO PENDIENTE** (primera pieza que lidera con el sentinel como argumento de venta) + owner gate |
| `2026-08-28-honesty-differentiator.md` | X (post corto) + LinkedIn (CISO/MSP) | Diferenciador honestidad: fail-unknown (reusa co-firma `t_ca5f82b9`) + local-first/cero-exfiltración (`policies.py:21`, `network_location.py:13`) + multi-UEM #188. Reusa claims co-firmados; SIN claim técnico NUEVO. | ⛔ **alineación PM PENDIENTE** (posicionamiento producto) + linter NO ejecutado (sin shell) + owner gate |
| `2026-08-29-oss-mdm-audience.md` | X (thread 7) + LinkedIn (open-source MDM ops) | **NUEVO PÚBLICO** (standup 2026-08-29): "no somos otro MDM; somos la capa de geofencing + riesgo explicable que le falta al tuyo". Público = quien ya corre MDM open-source (Fleet/NanoMDM/MicroMDM). Fleet adapter real (origin/main `fleet.py`); NanoMDM/MicroMDM NO integrados (no reclamar). Reusa co-firmados #110/#188/t_389cc434. | ✅ **posicionamiento firmado (gate #317 cerrado, t_190e48e9)** + linter 0 BLOCK + owner gate (NO publica agente) |
| `2026-08-29-og-description-approved.md` | meta (og:description) | Copy og:description literal **APROBADO por Product** (standup 2026-08-29): "LucidFence vs Kandji, Intune & Jamf — a free, local-first geofencing…". Encarna comparación > marca desnuda. #110-safe. | ✅ **aprobado Product** + linter 0 BLOCK + owner gate |
| `2026-08-29-trends-hooks.md` | nota interna (ganchos) | Mapeo tendencias UEM 2026 → hooks de copy (#241/#240, #250, #252/#247/#249). Framing honesto: roadmap/backlog, NO shipped. | owner gate (no publicable) |

## ⛔ CLAIM FALSO RETIRADO 2026-08-25 — "double-key wipe" (Marketing, autodetectado)
El borrador `docs/internal/gtm/SOCIAL_2026-08-24.md` afirmaba un **"double-key wipe"** /
"wipe de doble llave" que **no existe**: 0 coincidencias de `double.?key|dual.?key|two.?person`
en `lucidfence/`. Implicaba resistencia a un admin comprometido que el producto NO tiene →
riesgo #110. Nada se publicó (estaba en DRAFT) y la pieza lleva banner ⛔ NO PUBLICAR.
Lo verificado en `origin/main` es un guardarraíl de **una** llave, y es reclamable tal cual:
`enforcement.allow_wipe` **`false` por defecto** (`engine.py:78`, `:611-619`) + `wipe_allowlist`
opcional por `device_id` (`:79`, `:620-625`) + cooldown **persistido** de las 4
`DESTRUCTIVE_ACTIONS` (`wipe/lock/clear_passcode/reboot`, `:595`) que **sobrevive reinicios**
(`action_cooldowns.json`, default 3600s — `:82`, `:659-689`; `state_store.py:97`, `:242`) y
aplica también al comando manual del dashboard (`:703-722`); los intentos bloqueados quedan
en el action log. Redacción corregida + causa raíz de proceso:
`docs/internal/gtm/CORRECTION_2026-08-25-double-key-wipe.md`. Pendiente co-firma CTO.
**Nota de alcance:** `fleet.py`, `chromeos.py` y `workspace_one.py` existen en disco pero su
estado live/mock **no está co-firmado** — fuera de la matriz #188, **no reclamables** en copy.

## ✅ RESUELTO 2026-08-21 — `2026-08-21-declarative-enforcement.md` (Marketing + CTO)
El claim "Windows DSC = end-to-end real vía Microsoft Graph" **no se sostenía** y fue
eliminado del copy por el CTO (co-firma `t_1a407df5`, decisión A de la disputa
`t_2c00a8f2`). Verificado contra `origin/main`:
- `windows_conformidad._apply_dsc` **solo genera** manifests (`dsc_v3`,
  `dsc_classic_ps1`, `dsc_classic_mof`) y devuelve `applied: True` — cero POST del manifest.
- El único `POST` del adapter es la obtención de **token OAuth**; `_report_live` es un
  **GET** a `deviceManagement/managedDevices` para la acción `report` (read-back de
  conformidad, no entrega del manifest).
- `core/declarative.py` **existe** en `origin/main` (feat #89) y `engine.py:32` lo
  importa — el aviso previo de "módulo inexistente" era falso positivo sobre ref obsoleto.
  La duplicidad `declarative_path_for` quedó consolidada en main (merge #88 / `86730bb`).
=> El copy ahora afirma la verdad: **DDM y DSC son ambos build-only**; CTO co-firma la
pieza corregida. Pende solo el owner gate de Marketing para publicar.

## ⛔ HOLD DE ENGINE-LEVEL DECLARATIVO (t_0d04cdd0, CTO→Marketing, 2026-08-23)
No publicar claim de enforcement/ruteo **declarativo a nivel engine** hasta resolver
#89. Verificado en la rama de publicación `marketing-outbox-2026-08-20`:
`lucidfence/core/engine.py` tiene **CERO** referencias a `declarative`; `engine.run_command`
(dashboard on-demand) es **imperativo**. Solo el orquestador multi-UEM
(`core/multiuem.py` → `declarative_path_for`) enruta declarativamente hoy. El borrador
`2026-08-21-declarative-enforcement.md` lleva banner HOLD y su sección #205/#206 acotada.
La co-firma CTO previa (`t_1a407df5`) queda supersededida para el claim de engine.

**Alcance concreto del HOLD (sin claim de engine-level declarative hasta merge de wiring #89):**
- ✅ **IN SCOPE (verificado en rama de publicación `marketing-outbox-2026-08-20`):** ruteo declarativo del **orquestador multi-UEM** (`multiuem.py` → `declarative_path_for`, test `test_89_declarative_routing.py` pasa) + generación build-only de declaration/manifest **DDM (Jamf)** y **DSC (Windows)**. Android AMAPI: cero "declarativo" en copy público hasta builder #42 + tests verdes.
- ⛔ **OUT OF SCOPE (no reclamar):** la ruta **on-demand del operador (`engine.run_command` sobre un único `self.adapter`)** sigue siendo **imperativa** hoy (`engine.py` en la rama de publicación no referencia `declarative`/`_declarative_route`; test de engine de `test_89` falla verificando lock/wipe imperativo sin `enforcement`). No insinuar enforcement declarativo a nivel engine.
- Línea canónica de alcance en `2026-08-21-declarative-enforcement.md` (banner HOLD, §Alcance final): *"Declarative routing is live on the multi-UEM orchestrator + adapter build-only; the operator on-demand (engine) path remains imperative pending #89 wiring."*
Además: la rama `marketing-outbox-2026-08-20` está **ROJA** en `verify.py` (11 enlaces de
docs rotos + 3 tests de la suite honesta fallidos, incl. `test_89_declarative_routing.py`)
— **no mergear** hasta corregir (ver t_59bd317e).

## REGLA DE COPY (aviso Product, t_389cc434 · 2026-08-28)
**Prohibido a partir de ahora:** cualquier copy que implique "siempre puntúa todos
los dispositivos" o "score garantizado". El producto ya NO muestra 0/low
(falso-verde) cuando falla la evaluación: muestra el sentinel honesto
**"Riesgo desconocido (sin señal)"** (engine.py:297, origin/main 3c6ef66 + c8e264c)
y el KPI de dispositivos sin señal. Es un ARGUMENTO DE VENTA (fail-unknown, nunca
falso-verde), no una carencia. El framing correcto: "cuando hay señal, score 0-100
con la razón; sin señal, el dispositivo queda como desconocido — nunca falso verde."
Copy ya corregido por este aviso: `static/index.html`, `2026-08-20-x-thread.md`,
`2026-08-20-linkedin-diferente.md`, `2026-08-26-geofencing-myths.md`,
`2026-08-27-og-description.md`. Nueva pieza de ángulo: `2026-08-28-fail-unknown-no-false-green.md`.

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
**⚠️ Gate 0 (nuevo, t_c120cc9b):** cualquier pieza técnica **NUEVA** (blast-radius
UEM, no-goals, declarative, SOAR) requiere **co-firma obligatoria del CTO**
(`empresa-cto`, vía kanban) antes del owner gate. Proceso + matriz #188 canónica:
`docs/gtm/CTO_CO_SIGN.md`. El linter no sustituye esta co-firma.

**Pieza NUEVA 2026-08-23 — `2026-08-23-caep-ssf-emisor.md`** (Emisor CAEP/SSF fase 1):
**✅ CO-FIRMA CTO COMPLETADA** en `t_4943afe7` (`empresa-cto`, 2026-08-23) tras merge de
PR #262 a `origin/main` (`c72bf8c`, 680 passed). Linter posicionamiento: **0 BLOCK, 5 INFO**
(exit 0; todas en contexto de negación). **✅ RED LINE #110 LEVANTADA** para el alcance
CAEP (fase 1 Emisor) — co-firma PM+CTO registrada (`t_4ac3a954` PM + `t_4943afe7` CTO).
**Owner gate (Adri) pendiente** antes de publicar. Fase 2 (Receptor) y fase 3 (Streaming, OFF)
siguen como follow-ups separados, fuera de alcance del claim co-firmado.

Antes de aprobar cualquier `outbox/` item, corre el **Gate 2 de posicionamiento**
(cierra la reincidencia del claim de negocio descartado, no solo el matiz técnico #188):
```bash
python3.11 scripts/gtm_claim_linter.py --scope outbox
```
Devuelve `0 BLOCK` → apto. Cualquier `[BLOCK]` = posicionamiento prohibido
(enterprise pagado / open-core / on-prem cerrada / pricing). Proceso completo,
RED LINE técnica #188 y frases prohibidas en `docs/gtm/MESSAGING_SIGNOFF.md`.
Fuente de verdad de posicionamiento: `revenue-model.md` + `STATE.md` override.
