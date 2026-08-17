# docs/internal/STATE.md — Loop state for LucidFence (geofencing / UEM)

This file is the living state of the improvement loop. It is updated by the
maintainer (or a loop run) and reviewed by humans. It is NOT auto-merged by bots.

## Loop admin-value (patrón: `loop-admin-value.md`) — updated 2026-08-15

- **Level:** L2 (asistido; 1 PR/run con gate QA; gates humanos intactos)
- **Last run:** 2026-08-15 (ciclo 0: triage sembrado en sesión interactiva)
- **Base:** v1.5.0 publicada (release + brew tap alineados); enforcement
  observe→enforce con doble llave (#135); onboarding 4 UEMs + matriz de
  ubicación + día 2 (#136); batería runtime 28/28 en CI.

### Backlog priorizado (evidencia: análisis de practicidad 2026-08-15)

1. **Enforcement desde el dashboard** — hoy `enforcement.*` solo se toca por
   YAML; el admin debería ver Y editar la fase (con permiso + audit log del
   cambio). El chip ya muestra el estado (#135); falta el control.
2. ~~**Multi-UEM onboarding**~~ — **HECHO 2026-08-17 (#158)**: registro de
   providers con etiqueta de segmento de flota (móviles/portátiles) + guía
   `docs/integrations/MULTI_UEM.md`; de paso 2 fixes de seguridad (fuga de
   secretos en GET, DELETE sin permiso).
3. ~~**RBAC visible**~~ — **HECHO 2026-08-17 (#159)**: `GET /api/members` +
   `POST /api/members/role` (owner-only, guardarraíl del último propietario,
   audit), tarjeta "Equipo · Roles" en el dashboard, `docs/operations/RBAC.md`.
4. **Agente iOS empaquetado** — `ios_geofence` (geocercas on-device, lo más
   privado) sin guía de despliegue vía el propio MDM (perfil/app).
5. ~~**Quickstart guiado**~~ — **HECHO 2026-08-16**: `lucidfence quickstart`
   (entorno → app → dashboard → fuente de datos, autoverificado; check runtime
   en la batería + tests). Baja el time-to-first-value del admin nuevo.
6. **Windows geofencing lógico** — DSC ya existe; falta ubicación por red
   (osquery/IP) documentada y correlacionada como en Fleet.

### Derivado del loop Roadmap (2026-08-16, pasada ciclo 1)

Empujado desde `docs/roadmap/PRODUCT_ROADMAP.md` §Próximo (el loop Roadmap
prioriza; Admin-value ejecuta):

7. ~~**Corregir la tabla "No está terminado" del README**~~ — **HECHO
   2026-08-16**: 4 entregas marcadas como completas (release v1.5.0, guía de
   adaptadores, CONTRIBUTING, SECURITY.md).
8. ~~**Declarar pricing / modelo de negocio**~~ — **HECHO 2026-08-16** por
   decisión del propietario: 100% free OSS, sin pricing ni enterprise (ver
   §Overrides). Declarado en `README.md` §Modelo.

Queda abierto de producto: **onboarding externo** (README npm-style + FAQ para
terceros) — ver `PRODUCT_ROADMAP.md` §Próximo #2.

> Nota: el #1 del roadmap (verificar los 8 hallazgos Strix `open` de
> `security/findings.md`) es **p0 pero dueño del Centinela**, no de Admin-value;
> queda en su cola (jueves 22:07 UTC), no aquí.

### Watch list

- Cadencia de release: que formulas (repo+tap) no vuelvan a quedarse atrás —
  el workflow lo automatiza, pero el sha256 de las fórmulas sigue siendo paso
  manual post-release.
- Body de release v1.5.0 quedó con fallback ("Release v1.5.0") — cosmético,
  fix del awk ya mergeado (#134) para futuras; el propietario puede editarlo.
- `loop-audit` score (33/100 en julio) — rancio; recalcular en un run L1.

### Ruido descartado

- Reescribir el loop de mantenimiento existente: no — este loop es hermano,
  no sustituto.

### Overrides del propietario

- 2026-08-15: "todo lo que se anuncie debe validarse en runtime" (regla
  permanente; batería + gate CI).
- 2026-08-15: "gratis y del lado del cliente, siempre".
- 2026-08-15: "Fleet es importante" — paridad de primera clase con el resto
  de UEMs en cualquier mejora.
- 2026-08-16: **"La idea es que sea free open source."** El modelo es 100% free
  y open-source (Apache-2.0): sin pricing, sin edición enterprise, sin funciones
  de pago, sin telemetría. Cierra el gap de "modelo de negocio" (no hay uno de
  pago por diseño). Regla permanente para toda superficie pública y roadmap.

## Loop status (updated 2026-07-20)

- **Level:** L1 (report-only + human-gated merges)
- **Last run:** 2026-07-20 (stabilization QA pass)
- **Readiness score:** 33/100 → improving; roadmap 2026-2027 targets 80 by Q2'27
- **Kill switch:** `loop-pause` label on any PR, or `LOOP_PAUSE=1` env in CI

## Stabilization QA (2026-07-20) — ALL PASS

Evidence-based stabilization checkpoint (no claims without runtime proof):

- **Suite honesta:** 174/174 passed, 0 failed — run 3x consecutivas, sin flaky
  (la contaminación histórica de `cve._FEED` en `test_cloud_cve_feed` ya no reproduce).
- **Runtime `:8765`:** server arranca limpio (mode=live dry_run=True), sin errores en log.
  - `/` -> 200 (`LucidFence · Command Center`, 37.5 KB), `/api/health` -> 200 ok.
  - Endpoints protegidos -> 401 correcto (`/api/state`, `/api/tenants`, `/healthz`).
- **E2E auth:** signup crea user+org owner con token; demo-auth alimenta KPIs reales:
  6 devices, risk{risk,summary}, cve{cve_summary,devices}, 5 incidents, fences/routes OK.
- **Secretos:** `gitleaks` — 210 commits escaneados, **no leaks found**.
- **Vitrina serverless:** `lucidfence/core/cloud_publisher.py` publica `data/cloud_state.json`
  (9 dispositivos / 3 tenants / compliance 66.7%).
- **Docker:** no disponible en el entorno de build (macOS sin Docker) → sintaxis se
  valida en cliente/CI, según boundary de AGENTS.md.
- **Entorno limpio:** server de QA detenido, sin procesos zombie en `:8765`.

Estado: **producto estable y verificado en runtime**. Base v1.2.0. Próximo hito v1.3.0.

## What is DONE (this loop cycle)

- [x] Installed `loop-engineering` tooling and ran `loop-audit` (L0/33 baseline).
- [x] Reviewed all open GitHub PRs/issues on `adrimg3196/lucidfence`.
- [x] Merged PR #13 (Intune live adapter, Bounty #1) — respects frozen `MDMAdapter`
      contract, no secrets, 7/7 adapter tests + 156 full-suite green.
- [x] Closed duplicate PR #11 (Intune) — deleted contract tests + constructor Graph call.
- [x] Closed PR #12 (Jamf) — deleted contract tests, thin description; to be redone
      with the #13 pattern.
- [x] Closed PR #4 (CoC) — carried a Solana "bounty payout" wallet (spam vector);
      CoC to be added separately by maintainer without payment data.
- [x] Applied reviewer fixes from the Fleet Intelligence audit (cadence-based gap
      detection, minimum-evidence, future-timestamp rejection, bounds, a11y/responsive).
- [x] Re-implemented Jamf live adapter (Bounty #2) following the verified #13
      pattern — `live` flag, token cache, AuthError/TransportError mapping,
      device-list normalization, dry_run, `build_jamf_adapter_from_config`;
      issue #2 closed; suite 171 green.

## Open / next

- [ ] Resolve pre-existing `test_cloud_cve_feed` flakiness (global `cve._FEED`
      pollution across the full suite) — owner: engine/CVE feature session.
- [ ] Re-implement Jamf live (Bounty #2) following the PR #13 pattern.
- [ ] Add `loop-verifier` agent for maker/checker split on future adapter PRs.
- [ ] Add dependabot / scheduled loop-audit posting readiness score on PRs.

## Activity log (append-only)

- 2026-07-20: loop-audit baseline 33/100; scaffolding (STATE/LOOP/budget/run-log/CI) added.
- 2026-07-20: GitHub triage — 1 merge (#13), 3 closes (#11/#12/#4).
