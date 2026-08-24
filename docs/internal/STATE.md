# docs/internal/STATE.md — Loop state for LucidFence (geofencing / UEM)

This file is the living state of the improvement loop. It is updated by the
maintainer (or a loop run) and reviewed by humans. It is NOT auto-merged by bots.

## MODO DRENAJE (decisión CEO, tarea kanban t_df367332 — 2026-08-21)

- **Mandato:** throttle de la producción de PRs mientras exista al menos 1 PR ABIERTA NO-SANA.
- **Definición de NO-SANA (2026-08-24, recalibrado por CEO tras verificar que el raíl roto no era la única causa):** una PR abierta es NO-SANA si cumple CUALQUIERA:
  1. STALE: >7 días sin actividad (updated_at antiguo), o
  2. CONFLICTING: estado de merge `conflicting`, o
  3. RED: cualquier check-run completado con conclusión failure/timed_out/canceled.
  Una PR verde pero `behind` main NO cuenta como NO-SANA (el raíl de auto-merge la drena).
- **Estado:** ACTIVO. Las Routines productoras (Admin-value, Product Manager, Housekeeper, Tendencias, Growth, Roadmap, Deps, Lanzamiento, Centinela) NO deben abrir nuevas PRs mientras haya >=1 PR NO-SANA. El Guardián (dueño del merge-train #118) es el único que drena; el resto queda en pausa de apertura.
- **Mantenido hasta:** merge de PR #289 (repara el raíl de auto-merge no-op). Tras #289, el raíl drena las verdes; el throttle persiste solo por las NO-SANAS reales (ej. #264, #280, #283 al momento de este cambio).
- **Regla de reanudación:** productor vuelve a abrir PRs solo cuando 0 PRs NO-SANAS estén abiertas.

## Loop admin-value (patrón: `loop-admin-value.md`) — updated 2026-08-15

- **Level:** L2 (asistido; 1 PR/run con gate QA; gates humanos intactos)
- **Last run:** 2026-08-15 (ciclo 0: triage sembrado en sesión interactiva)
- **Base:** v1.5.0 publicada (release + brew tap alineados); enforcement
  observe→enforce con doble llave (#135); onboarding 4 UEMs + matriz de
  ubicación + día 2 (#136); batería runtime 28/28 en CI.

### Backlog priorizado (evidencia: análisis de practicidad 2026-08-15)

1. ~~**Enforcement desde el dashboard**~~ — **HECHO**: el control existe y está
   cableado (`static/dashboard.html` `#enfSelect` → `POST /api/settings/enforcement`,
   gated a owner/admin por `engine:config`, con audit y recarga del engine). El
   chip muestra el estado (#135) y el select edita la fase (observe|enforce).
2. ~~**Multi-UEM onboarding**~~ — **HECHO 2026-08-17 (#158)**: registro de
   providers con etiqueta de segmento de flota (móviles/portátiles) + guía
   `docs/integrations/MULTI_UEM.md`; de paso 2 fixes de seguridad (fuga de
   secretos en GET, DELETE sin permiso).
3. ~~**RBAC visible**~~ — **HECHO 2026-08-17 (#159)**: `GET /api/members` +
   `POST /api/members/role` (owner-only, guardarraíl del último propietario,
   audit), tarjeta "Equipo · Roles" en el dashboard, `docs/operations/RBAC.md`.
4. ~~**Agente iOS empaquetado**~~ — **HECHO 2026-08-17 (#160)**: exportador de
   config de despliegue (managed app config + `.mobileconfig`, stdlib) +
   `docs/integrations/IOS_ONDEVICE.md`; cero exfiltración (solo geocercas de
   política, nunca coords/device_id — test con datos envenenados).
5. ~~**Quickstart guiado**~~ — **HECHO 2026-08-16**: `lucidfence quickstart`
   (entorno → app → dashboard → fuente de datos, autoverificado; check runtime
   en la batería + tests). Baja el time-to-first-value del admin nuevo.
6. ~~**Windows geofencing lógico**~~ — **HECHO 2026-08-17**: ubicación gruesa por
   señal de red para portátiles/Windows sin GPS. `lucidfence/core/network_location.py`
   (stdlib `ipaddress`; mapeo declarado por el operador IP-CIDR/SSID/BSSID → sitio
   con coords + radio; cero geoip de terceros, nunca inventa, `accuracy_m` = radio,
   `location_source="network"`); enriquecimiento inerte-por-defecto en
   `location_source.py` (nunca sobreescribe GPS real); `docs/integrations/NETWORK_LOCATION.md`
   + matriz actualizada; 20 tests (CIDR/SSID/BSSID, precedencia, envenenado).
7. **Postura Apple DDM (OS 27) como señal del motor de riesgo** — *derivado del
   loop Tendencias 2026-08-18, ver `docs/internal/trends/signals.md`.* En WWDC 2026
   Apple hizo DDM **obligatorio** en la generación OS 27 y añadió nuevos *status
   items*: **Lockdown Mode**, **salud de hardware** (baseband, cámara, Face/Touch
   ID, NFC, UWB), tipo de enrolamiento y Shared iPad. LucidFence ya soporta DDM
   (`supports_ddm` en jamf, `apply_ddm`, `docs/operations/apple_ddm.md`); el
   siguiente paso de producto es **ingerir esos status por el canal `device_state`
   que ya existe** (merge, no reemplazo) y dejar que las políticas correlacionen,
   p. ej., "fuera de geocerca **y** Lockdown Mode desactivado" o salud de hardware
   degradada. Fuente: [Jamf WWDC26](https://www.jamf.com/blog/wwdc26-key-takeaways-for-apple-admins/),
   [42Gears](https://www.42gears.com/blog/wwdc-2026-whats-new-apple-device-management/).
   Esfuerzo medio; empezar por el status de Lockdown Mode (booleano, alto valor).
   **Primer incremento HECHO 2026-08-18** (mergeado vía `claude/pm-features` /
   `claude/trends-loop`): `lockdown_mode` y `supervised` como señales
   readback-honestas del motor de riesgo (None nunca penaliza), con tests y
   docs. **Segundo incremento HECHO 2026-08-19** (cierra el ítem):
   `hardware_health` (Optional[dict]) viaja LocationReport→DeviceState→engine;
   `sig_device_posture` emite `hardware_degraded`(+componentes) SOLO ante
   False/"degraded|failed|error" explícito (desconocido jamás penaliza);
   +10 riesgo con razón, field `hardware_degraded` en políticas, 6 tests,
   check runtime (46/46), sección en `docs/operations/apple_ddm.md`.
   **El backlog numerado queda drenado**: el siguiente trabajo sale de los SÍ
   de `docs/internal/product/BACKLOG.md`.
9. ~~**Segunda opinión: lo que el UEM dice vs lo que se observa**~~ — **HECHO
   2026-08-23** (backlog evaluado #13): `lucidfence/core/second_opinion.py`
   (función pura stdlib) + `GET /api/second-opinion` (`device:read`,
   tenant-scoped) + 16 tests + 3 checks runtime (54/54) +
   `docs/operations/second_opinion.md`. Contrasta la afirmación del UEM
   (`compliant`, cifrado, fecha del check-in) contra canales que el UEM no
   controla (postura osquery, readback DDM de hardware, integridad de
   ubicación, CVE de apps), con evidencia de **ambos lados**. El hallazgo que
   lo habilitó: la postura de osquery **sobrescribía** `encryption_enabled` y
   borraba la afirmación del UEM — la contradicción era indetectable;
   `DeviceState.uem_claimed_encryption` conserva ahora las dos caras.
   **Nº1 pendiente ahora: #12 panel único multi-UEM con riesgo normalizado.**
8b. ~~**Políticas y geocercas como código (`lucidfence apply`)**~~ — **HECHO
   2026-08-19** (backlog evaluado #1; tendencia GitHub validada: Fleet 4.90
   redobla en GitOps): validar → diff `+/~/-` → **what-if con replay del
   histórico local** (nadie del sector lo tiene) → apply atómico solo con
   `--yes`. Nuevo `validate_policies` espejo de `validate_fences`,
   `core/config_apply.py`, 8 tests, 2 checks runtime (45/45),
   `docs/operations/config_as_code.md`.
8. ~~**Informe de puntos ciegos (coverage gap)**~~ — **HECHO 2026-08-19**
   (backlog evaluado #15, `docs/internal/product/BACKLOG.md`):
   `lucidfence/core/coverage.py` (función pura stdlib, readback-honesta) +
   `GET /api/coverage` (gating `device:read`, tenant-scoped) + 10 tests +
   3 checks runtime (43/43) + `docs/operations/coverage.md`. El negativo que
   ningún panel del sector enseña: dispositivos sin señal, "lost sheep" sin
   reportar, cercas vacías — visible para el admin, jamás acción automática.

### Pasada de la flota completa sobre el producto (2026-08-17)

Con la entrega desbloqueada, los loops corrieron en paralelo sobre el producto;
cada uno entregó una mejora real y verificada (`verify.py` APTO 4/4). Todas
mergeadas en **#164**:

- **Centinela (seguridad):** SSRF corregida en `/api/providers[/test]` —
  `endpoint`/`base_url` ahora validados con `_safe_webhook_url` (solo https
  externo). Antes: escaneo de infra interna + reflejo de respuesta. Test PoC.
- **Revisión (correctness):** bug de paginación por cursor en
  `location_source.py` (separador sobre `url` en vez de `path`) que perdía todo
  dispositivo desde la página 3 y hacía descartar el ciclo. Fix de un token + test.
- **Admin-value:** tarjeta "Registro de auditoría" en el dashboard (integridad de
  la cadena + export CEF a SIEM); da pantalla al rol `auditor`. Cero backend nuevo.
- **Realidad (honestidad):** corregido el claim falso "105 tests" (real 525) y un
  enlace roto en `demo-walkthrough.md`.

### Derivado del loop Roadmap (2026-08-16, pasada ciclo 1)

Empujado desde `docs/roadmap/PRODUCT_ROADMAP.md` §Próximo (el loop Roadmap
prioriza; Admin-value ejecuta):

7. ~~**Corregir la tabla "No está terminado" del README**~~ — **HECHO
   2026-08-16**: 4 entregas marcadas como completas (release v1.5.0, guía de
   adaptadores, CONTRIBUTING, SECURITY.md).
8. ~~**Declarar pricing / modelo de negocio**~~ — **HECHO 2026-08-16** por
   decisión del propietario: 100% free OSS, sin pricing ni enterprise (ver
   §Overrides). Declarado en `README.md` §Modelo.

~~Queda abierto de producto: **onboarding externo**~~ — **HECHO 2026-08-17**:
`docs/GETTING_STARTED.md` (npm-style: qué necesitas, instalar, comprobar que
funciona, primer paso real conectando UEM, FAQ, cómo reportar bugs/seguridad),
enlazada desde el README y con la fila "No está terminado" #73 cerrada.

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
