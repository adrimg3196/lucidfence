# Changelog

All notable changes to LucidFence are documented here.

## [Unreleased]

- fix(ci): relajar ruleset de ramas de datos a solo protección-contra-borrado — `LucidFence Autonomy B` ahora aplica solo a `~DEFAULT_BRANCH` (antes `~DEFAULT_BRANCH` + `~ALL`), de modo que `engine-cron`/`recon-social-cron` pueden empujar directo a `cloud-state`/`recon-state` sin `GH013` (#270). Registro en `docs/operations/BRANCH_CONFIG.md`.
- fix(ci): desatascar deadlock repo-wide por check fantasma — el ruleset `LucidFence Autonomy B` (21249696) exigía `autonomy-evidence`, pero su workflow solo vivía en el PR #264 (rojo) y no en `main`, así que **todos los PR verdes del repo quedaban `BLOCKED` por diseño** (p.ej. #289: 14/14 checks en verde y aun así `mergeStateStatus=BLOCKED`). Se quitó `autonomy-evidence` de `required_status_checks`; los 9 checks reales y demás reglas siguen intactos. Se volverá a requerir cuando su workflow aterrice en `main` y reporte en verde. Regla anti-deadlock añadida en `docs/operations/BRANCH_CONFIG.md` (t_9c8c2878).
- fix(ci): el health-check nocturno vuelve a poder alertar — `nightly-health-check`
  llevaba **10 runs consecutivos en rojo** (2026-08-13..2026-08-22) con
  `ModuleNotFoundError: No module named 'requests'`, no porque la vitrina
  estuviese caída (estaba viva todo el tiempo) sino porque `scripts/check_vitrina.py`
  importaba el contrato del snapshot desde `lucidfence.core.cloud_publisher`, que
  arrastra `engine → actions → adapters → applivery → import requests`, y el
  workflow lo ejecuta sin `pip install`. El contrato se extrae al módulo HOJA
  `lucidfence/core/published_schema.py` (stdlib puro, reexportado por el publisher:
  misma tupla, fuente única intacta) y el checker vuelve a ser stdlib puro como
  promete su docstring. Con test de regresión que bloquea los terceros en un
  subproceso y exige que el checker arranque igual — el test de contrato anterior
  comprobaba que el workflow *llama* al checker, no que pueda *ejecutarlo*.
- gitops/repo-higiene: `.gitattributes` con `merge=union` para los logs append-only
  de los loops (`loop-run-log.md`, `release/history.md`, `trends/signals.md`,
  `security/findings.md`, `growth/experiments.md`, `growth/mentions.md`) — corta
  conflictos crónicos del merge train (#118, tarea t_e207227e).
- gitops/repo-higiene: `lucidfence/plugins/adapters/index.json` ya no genera
  conflictos de merge manuales: se regenera desde los `.py` mergeados vía el
  driver custom `regen-adapter-index` (ver CONTRIBUTING.md → "Setup del repo").
  Antes producía conflictos y hashes obsoletos que rompían `test_adapter_marketplace_manifest_is_hash_verified`.
- feat(gitops): `lucidfence apply` — políticas y geocercas como código (GitOps sin servidor) (#186)
- feat(coverage): informe de puntos ciegos del tenant (`GET /api/coverage`) (#184)

## [1.6.0] - 2026-08-18

### Added

- feat(enforcement): rollout seguro para pilotos reales — `enforcement.mode: observe|enforce`, `live_actions` (gating por acción) y doble llave para `wipe` (`allow_wipe` + `wipe_allowlist`); estado visible en `/api/status` y editable desde el dashboard con permiso + auditoría
- feat(compliance): acción `set_compliance` — Intune la ejecuta vía Graph (managedDevice → objeto Entra → `PATCH isCompliant`) para que Conditional Access corte el acceso; Jamf y Fleet degradan con el mecanismo equivalente de su plataforma
- feat(onboarding): `lucidfence quickstart` — del install a ver la flota en pasos autoverificados (entorno → app → dashboard → fuente de datos); baja el time-to-first-value del admin nuevo
- feat(multi-uem): registro de proveedores con etiqueta de segmento de flota (móviles/portátiles) + guía `docs/integrations/MULTI_UEM.md`
- feat(rbac): gestión de miembros y roles visible en el dashboard (`GET /api/members`, `POST /api/members/role`; owner-only, guardarraíl del último propietario, auditado)
- feat(ios): exportador de config de despliegue on-device (managed app config + `.mobileconfig`, stdlib); solo geocercas de política, nunca coordenadas ni `device_id`
- feat(location): geofencing lógico por red para Windows/portátiles sin GPS — mapeo declarado por el operador de IP-CIDR/SSID/BSSID → sitio con coordenadas; local-first, sin geoip de terceros, nunca inventa la posición
- feat(audit): tarjeta "Registro de auditoría" en el dashboard — cadena de hashes con verdicto de integridad y export CEF a SIEM; da pantalla al rol `auditor`
- feat(risk): Lockdown Mode (Apple DDM, OS 27 / WWDC 2026) como señal de postura del motor de riesgo — un dispositivo fuera de geocerca con Lockdown Mode desactivado sube de riesgo y es direccionable por política; readback honesto (`None`/desconocido nunca penaliza)
- docs: guía de arranque externa `docs/GETTING_STARTED.md` (npm-style: qué necesitas, instalar, comprobar, FAQ, cómo reportar bugs)

### Fixed

- fix(security): SSRF en el asistente de proveedores — `endpoint`/`base_url` de `/api/providers[/test]` ahora validados (solo https externo, sin loopback/privado/link-local), con test de regresión (PoC)
- fix(location): la paginación por cursor de la fuente live perdía todos los dispositivos desde la página 3 (separador de URL calculado sobre `url` en vez de `path`), lo que hacía descartar el ciclo entero; corregido con test de regresión

## [1.5.0] - 2026-08-15

### Added

- feat(alertas): webhooks multi-canal de incidentes — genérico con firma HMAC-SHA256 verificable en el receptor y canal ntfy, con fan-out (#120)
- feat(risk): detección de spoofing de ubicación con señales explicables — velocidad imposible, flip de país sin movimiento, accuracy anómala (#121, endurecido en #127)
- feat(policies): simulador what-if — `POST /api/policies/replay` evalúa una policy candidata contra el histórico de trails sin ejecutar acciones (#122)
- feat(sdk): `lucidfence adapter new <nombre>` genera un adapter MDM + contract test listos para contribuir (#123)
- feat(compliance): `GET /api/evidence/export` — informe por periodo con cadena de hashes verificable offline y registro en la auditoría del tenant (#124)
- feat(mcp): tool `lucidfence_explain_risk` — score, razones, señales y políticas de un dispositivo (#125, fix de parsing en #127)
- feat(posture): integración osquery en el ciclo del engine + señales al Risk Engine (#116)
- feat(poi): servicio de Points of Interest con API y tool MCP (#55)
- feat(ci): gate `runtime-validation` — 25 claims ejecutados en vivo en cada PR (#129) y workflow `release.yml` para publicar releases con asset y smoke del artefacto
- feat(pages): publicación continua de la superficie estática en GitHub Pages con guardarraíl de integridad (#128)

### Changed

- feat(ui): rediseño de landing/vitrina con pase de diseño anti-slop; accesibilidad (focus-visible, reduced-motion) y CTA de descarga en primer viewport (#126, #119)
- fix(security): pin de `cryptography` alineado con la lock + guardarraíl anti-divergencia (#117); testimonios y métricas sin fuente retirados de la vitrina (#119)
- fix(windows-dsc): escapado de comillas en documentos DSC (#114); state store robusto ante registros corruptos (#103); coordenadas 0.0 sobreviven (#100)
- chore(sbom): `sbom.cdx.json` deja de versionarse; lo genera CI (#115)

### Added (previo, sin release)

- feat(ddm): enforcement declarativo Apple DDM para policies de geocerca (`lucidfence/core/ddm.py`, acción `apply_ddm` en el adapter Jamf) — issue #40
- feat(ddm): canal DDM de Jamf Pro — `ddm_status` (readback de `GET /v1/ddm/{clientManagementId}/status-items`) y `ddm_sync` (`POST /v1/ddm/{clientManagementId}/sync`), endpoints verificados contra el OpenAPI oficial v11.30; subir declarations propias sigue siendo hueco declarado porque Jamf no publica endpoint — issue #52

### Changed

- feat(free)!: LucidFence es gratis para siempre — eliminados los planes Pro/Enterprise, `/api/plan`, `/api/plan/upgrade` y la capability `org:billing`; `FREE_PLAN` único con enlace de donaciones (`.github/FUNDING.yml`); tenants legacy migran a `free` al cargar
- docs(revenue): `docs/gtm/revenue-model.md` reescrito como modelo gratis+donaciones; `docs/pricing-model.md` eliminado

### Fixed

- fix(ddm): las acciones DDM no estaban en `VALID_ACTIONS`, así que `Engine.run_command` y el endpoint de comandos las rechazaban con "accion no valida" — la capa declarativa era inalcanzable desde el producto
- fix(ddm): los `StatusItem.value` de Jamf son string siempre; `passcode.is-compliant` llegaba como `"true"` a un campo que el modelo de estado espera `bool`
- fix(server): el sanitizador de `log_message` convertía args numéricos a str y rompía `send_error(404)` (formato `%d`) — cualquier POST/DELETE a ruta desconocida devolvía 500 en vez de 404
- fix(build)!: `sbom.cdx.json` deja de estar versionado (lo genera CI como artifact) y desaparece el `assert committed == sbom` — un artefacto que hashea todos los `.py` fijado por igualdad exacta hacía que main y toda rama tocaran las mismas dos líneas, conflicto garantizado en el 100% de los PRs — issue #74
- fix(tests): `test_roadmap_tooling` restaura los bytes exactos de `roadmap.json` (el round-trip por `update_feature()` re-estampaba `meta.updated`) y `data/actions_log.jsonl` se destrackea — correr la suite dejaba el árbol sucio en dos ficheros versionados
- ci(runtime-artifacts): un PR que modifique `data/cloud_state.json` falla en CI — ese snapshot lo republica `engine-cron` en main cada hora, así que toda rama que lo toque conflicta con main

### Removed

- chore(barrendero): `static/saas_views*.js` (4 ficheros, 530 líneas muertas: ningún HTML los cargaba) + SBOM regenerado

## [1.3.0] - 2026-07-21

### Added

- feat(webapp-testing/docker): Playwright E2E cloud+dashboard + GH Actions docker workflow
- feat(webapp-testing): Playwright smoke for cloud install panel
- feat(docs): add operations, design, and contributing review checklist
- feat(frontend): improve cloud install panel and add Playwright smoke test
- feat(perf): engine loop regression guard + tick benchmark (20 samples)
- feat(a11y): add skip-link, lang/title/canonical/description, nav aria-label on dashboard/cloud
- feat(monitoring): health monitor hardened with structured JSON logs, Prometheus-like /metrics, /healthz, /readyz (#18 renewal)
- feat(security): close M1-M4 hardening gates + CVE feed isolation (#16, #17)
- feat(platform): installer always-on launchd/systemd
- feat(operations): health monitor + GH issue on failure (#18)
- feat(platform): installer always-on launchd/systemd (#15)
- feat(adapters/chromeos): ChromeOS read-only reporter (BOUNTY #20) [MERGE]
- feat(adapters/windows): Windows conformidad reporter (BOUNTY #21) [MERGE]
- feat(adapters/chromeos): ChromeOS read-only reporter (Bounty #20)
- feat(adapters/windows): Windows conformidad read-only reporter (Bounty #21)
- feat(adapters/sdk): contract tests + SDK template (Bounty #14)
- feat: roadmap anual + estructura mejora tooling + /loop MoA (LucidFence)
- feat(incidents): realtime email+webhook fanout, SOAR HMAC, rate-limit, security hardening — plus CVE feed test isolation
- feat(adapters/jamf): live mode via Jamf Pro API (Bounty #2) — token cache, error mapping, dry_run, tests 7/7
- feat(fleet-intelligence): reviewer fixes — expected cadence gaps, min-evidence, future-timestamp rejection, bounds, a11y/responsive
- feat(adapters/intune): live mode via Microsoft Graph (Bounty #1)
- feat: add explainable fleet intelligence
- feat: add secure macOS desktop app
- feat: ship LucidFence as local-first Homebrew app
- feat(i18n): dashboard bilingue ES/EN (toggle persistente) + README.en
- feat(desktop): .app nativa de LucidFence (launcher macOS, /bin/bash, sin firma)
- feat(packaging): Homebrew formula + release v1.0.0 (canal de descarga soberano)
- feat(cli): comando 'lucidfence serve' soberano + server respeta LUCIDFENCE_PORT
- feat(kanban): empresa autónoma + trabajo de especialistas
- feat(kanban): empresa de desarrollo autónoma LucidFence
- feat(saas): self-service multi-tenant via GitHub Issues (sin token del usuario)

### Fixed

- fix(pr22 merge): resolver conflicto ADAPTER.md y admitir SDK contract tests + template (#22)
- fix: deliver direct compliance PDF reports
- fix(vitrina): comando brew correcto de 3 partes (tap implícito)
- fix(tests+packaging): elimina test de self-service obsoleto + bin/lucidfence ejecutable
- fix(self-service): parser lee body del issue via gh api si ISSUE_BODY llega vacio
- fix(cloud): publicar estado con riesgo geografico y departamento reales
- fix(engine): fences_path default a fences.json del repo root en modo live
- fix: seed demo robusto + fences_path derivado de sim_seed_path
- fix(server+engine): seed cuenta demo + default fences_path
- fix(ci): suite verde 119/0 — revert cambios rotos del equipo + compat 3.9 + fix route_exit
- fix(engine): route_exit dispara accion notify (dedupe por ruta)
- fix(ci): revertir cambios del equipo que rompian la API + compat 3.9
- fix(ci): compatibilidad Python 3.9 + endpoint SaaS
- fix(tests): make suite concurrency-safe — ephemeral ports + hermetic server
- fix(pm): ajuste rate-limit signup a 100/h para no bloquear la suite QA
- fix(saas-signup): disparar en issues opened y filtrar por bloque lucidfence-signup (sin if con labels)

### Changed

- refactor(vitrina): CTA de descarga soberano + elimina self-service nuestro
- refactor(empresa): modo SaaS FREE-FIRST — norte = tracción no revenue

### Testing

- test(intune-live): restore requests.post after monkeypatch to avoid cross-test pollution
- test: reicon contract robusto contra dashboard.html
- test: valida rutas auth en server (no en saas.js obsoleto)
- test: quita refs a saas.js obsoleto (modelo free)
- test: apunta reicon a dashboard.html (saas.html borrado, modelo free)

### Documentation

- docs: add docs/operations/RUNBOOK.md operator playbook (BOUNTY #19, WS5) [MERGE]
- docs: add docs/operations/RUNBOOK.md operator playbook (Bounty #19, WS5)
- docs(roadmap): enlaza milestones GitHub v1.3.0-v2.1.0 (roadmap ejecutable)
- docs: roadmap anual 2026-2027 (Q3'26→Q2'27) + social preview asset
- docs: add Adapter Hall of Fame (Intune #13 credited) + anti-spam policy; mark Intune/Jamf as live-capable (live when client token connected, mock/simulation otherwise)
- docs: link desktop preview download
- docs(vitrina): documenta tap Homebrew (brew install adrimg3196/lucidfence resuelve)

### Other

- cloud: actualizar estado en vivo (2026-07-21T09:14:40Z)
- Merge branch 'feature/installer-always-on-15': installer always-on (#15)
- cloud: actualizar estado en vivo (2026-07-21T06:40:08Z)
- cloud: actualizar estado en vivo (2026-07-21T04:12:03Z)
- cloud: actualizar estado en vivo (2026-07-21T00:57:35Z)
- cloud: actualizar estado en vivo (2026-07-20T23:29:18Z)
- cloud: actualizar estado en vivo (2026-07-20T22:27:43Z)
- cloud: actualizar estado en vivo (2026-07-20T21:21:26Z)
- cloud: actualizar estado en vivo (2026-07-20T20:02:33Z)
- cloud: actualizar estado en vivo (2026-07-20T18:26:01Z)
- cloud: actualizar estado en vivo (2026-07-20T16:18:50Z)
- chore: stabilization QA pass (174/174, runtime :8765 verified, 0 leaks); add playwright E2E + analysis reqs
- cloud: actualizar estado en vivo (2026-07-20T14:54:03Z)
- cloud: actualizar estado en vivo (2026-07-20T12:38:14Z)
- cloud: actualizar estado en vivo (2026-07-20T10:37:34Z)
- chore(loop): add loop-engineering scaffolding (STATE/LOOP/budget/constraints/CI) — readiness 33→93
- cloud: actualizar estado en vivo (2026-07-20T07:49:53Z)
- cloud: actualizar estado en vivo (2026-07-20T04:49:42Z)
- cloud: actualizar estado en vivo (2026-07-20T01:11:16Z)
- cloud: actualizar estado en vivo (2026-07-19T23:37:05Z)
- cloud: actualizar estado en vivo (2026-07-19T22:31:27Z)
- cloud: actualizar estado en vivo (2026-07-19T21:31:37Z)
- cloud: actualizar estado en vivo (2026-07-19T20:35:31Z)
- cloud: actualizar estado en vivo (2026-07-19T19:49:39Z)
- cloud: actualizar estado en vivo (2026-07-19T18:35:17Z)
- cloud: actualizar estado en vivo (2026-07-19T17:39:19Z)
- cloud: actualizar estado en vivo (2026-07-19T16:32:47Z)
- cloud: actualizar estado en vivo (2026-07-19T15:38:53Z)
- cloud: actualizar estado en vivo (2026-07-19T14:44:54Z)
- cloud: actualizar estado en vivo (2026-07-19T13:48:50Z)
- cloud: actualizar estado en vivo (2026-07-19T12:10:10Z)
- cloud: actualizar estado en vivo (2026-07-19T11:23:24Z)
- cloud: actualizar estado en vivo (2026-07-19T10:12:36Z)
- cloud: actualizar estado en vivo (2026-07-19T08:39:23Z)
- cloud: actualizar estado en vivo (2026-07-19T06:20:04Z)
- cloud: actualizar estado en vivo (2026-07-19T03:48:15Z)
- cloud: actualizar estado en vivo (2026-07-19T00:05:57Z)
- cloud: actualizar estado en vivo (2026-07-18T23:06:19Z)
- cloud: actualizar estado en vivo (2026-07-18T22:03:52Z)
- cloud: actualizar estado en vivo (2026-07-18T21:03:06Z)
- cloud: actualizar estado en vivo (2026-07-18T20:10:20Z)
- cloud: actualizar estado en vivo (2026-07-18T19:21:21Z)
- cloud: actualizar estado en vivo (2026-07-18T18:05:00Z)
- cloud: actualizar estado en vivo (2026-07-18T17:10:34Z)
- cloud: actualizar estado en vivo (2026-07-18T16:08:13Z)
- cloud: actualizar estado en vivo (2026-07-18T15:10:41Z)
- cloud: actualizar estado en vivo (2026-07-18T14:05:31Z)
- cloud: actualizar estado en vivo (2026-07-18T12:34:44Z)
- cloud: actualizar estado en vivo (2026-07-18T11:34:00Z)
- cloud: actualizar estado en vivo (2026-07-18T10:37:54Z)
- cloud: actualizar estado en vivo (2026-07-18T09:05:51Z)
- cloud: actualizar estado en vivo (2026-07-18T07:17:08Z)
- cloud: actualizar estado en vivo (2026-07-18T05:40:59Z)
- cloud: actualizar estado en vivo (2026-07-18T03:26:56Z)
- cloud: actualizar estado en vivo (2026-07-18T00:05:57Z)
- cloud: actualizar estado en vivo (2026-07-17T23:04:55Z)
- cloud: actualizar estado en vivo (2026-07-17T22:04:40Z)
- cloud: actualizar estado en vivo (2026-07-17T21:05:49Z)
- cloud: actualizar estado en vivo (2026-07-17T20:05:53Z)
- cloud: actualizar estado en vivo (2026-07-17T19:00:18Z)
- cloud: actualizar estado en vivo (2026-07-17T17:58:01Z)
- cloud: actualizar estado en vivo (2026-07-17T16:56:26Z)
- cloud: actualizar estado en vivo (2026-07-17T15:53:06Z)
- cloud: actualizar estado en vivo (2026-07-17T14:26:40Z)
- cloud: actualizar estado en vivo (2026-07-17T12:57:02Z)
- cloud: actualizar estado en vivo (2026-07-17T11:50:54Z)
- cloud: actualizar estado en vivo (2026-07-17T10:28:18Z)
- cloud: actualizar estado en vivo (2026-07-17T08:54:16Z)
- cloud: actualizar estado en vivo (2026-07-17T06:33:36Z)
- cloud: actualizar estado en vivo (2026-07-17T04:20:49Z)
- cloud: actualizar estado en vivo (2026-07-17T01:09:04Z)
- cloud: actualizar estado en vivo (2026-07-16T23:34:44Z)
- cloud: actualizar estado en vivo (2026-07-16T22:36:45Z)
- cloud: actualizar estado en vivo (2026-07-16T21:42:25Z)
- cloud: actualizar estado en vivo (2026-07-16T20:32:23Z)
- cloud: actualizar estado en vivo (2026-07-16T19:37:34Z)
- cloud: actualizar estado en vivo (2026-07-16T18:17:38Z)
- cloud: actualizar estado en vivo (2026-07-16T17:00:50Z)
- cloud: actualizar estado en vivo (2026-07-16T15:55:44Z)
- cloud: actualizar estado en vivo (2026-07-16T14:29:16Z)
- cloud: actualizar estado en vivo (2026-07-16T12:21:00Z)
- cloud: actualizar estado en vivo (2026-07-16T11:00:12Z)
- cloud: actualizar estado en vivo (2026-07-16T08:59:49Z)
- cloud: actualizar estado en vivo (2026-07-16T06:39:16Z)
- cloud: actualizar estado en vivo (2026-07-16T04:22:49Z)
- cloud: actualizar estado en vivo (2026-07-16T01:05:17Z)
- cloud: actualizar estado en vivo (2026-07-15T23:38:46Z)
- cloud: actualizar estado en vivo (2026-07-15T22:40:38Z)
- cloud: actualizar estado en vivo (2026-07-15T21:44:53Z)
- cloud: actualizar estado en vivo (2026-07-15T20:46:50Z)
- cloud: actualizar estado en vivo (2026-07-15T19:50:21Z)
- cloud: actualizar estado en vivo (2026-07-15T18:43:15Z)
- cloud: actualizar estado en vivo (2026-07-15T17:35:53Z)
- chore: pin Homebrew v1.1.1 checksum
- Harden lifecycle and fix local map routing
- chore: pin Homebrew release checksum
- cloud: actualizar estado en vivo (2026-07-15T16:07:32Z)
- chore: formula v1.0.4 sha final
- chore: formula v1.0.4 final sha (sin precios)
- ui: '0 €' -> 'Gratis' en tarjeta de traccion
- chore: formula v1.0.4 sha (sin precios)
- docs/ui: elimina toda referencia a precios/planes (todo free)
- chore: formula v1.0.4 (sin precios)
- chore: elimina precios/planes (todo free, soberano)
- chore: formula v1.0.3 (dashboard bilingue)
- chore: limpia tenant de prueba qa-autonomo del repo
- Merge branch 'main' of https://github.com/adrimg3196/lucidfence
- cloud: actualizar estado en vivo (2026-07-15T13:08:42Z)
- cloud: operación  ()
- sec(auth): PBKDF2 via hashlib estandar + release limpio para cliente
- cloud: actualizar estado en vivo (2026-07-15T12:47:53Z)
- chore(release): limpia repos + regenera release v1.0.0 con tarball sin basura
- chore: limpia archivos obsoletos del repo (basura de trabajo)
- cloud: actualizar estado en vivo (2026-07-15T11:18:56Z)
- cloud: actualizar estado en vivo (2026-07-15T09:46:40Z)
- cloud: actualizar estado en vivo (2026-07-15T07:46:23Z)
- cloud: actualizar estado en vivo (2026-07-15T05:51:44Z)
- cloud: actualizar estado en vivo (2026-07-15T03:28:52Z)
- cloud: actualizar estado en vivo (2026-07-15T00:02:52Z)
- cloud: actualizar estado en vivo (2026-07-14T23:09:28Z)
- cloud: actualizar estado en vivo (2026-07-14T22:11:26Z)
- cloud: actualizar estado en vivo (2026-07-14T21:12:40Z)
- cloud: actualizar estado en vivo (2026-07-14T20:06:56Z)
- cloud: actualizar estado en vivo (2026-07-14T18:57:37Z)
- chore: limpiar tenant QA autonomo de la vitrina de produccion
- cloud: publicar vitrina tras signup (#10)
- cloud: tenant desde signup (#10)
- chore: sync runtime data + board tras ciclo autonomo
- cloud: actualizar estado en vivo (2026-07-14T17:45:22Z)
- chore: datos generados tras suite
- chore: estado de tenants/vitrina tras correccion de tests
- cloud: actualizar estado en vivo (2026-07-14T16:36:10Z)
- chore(kanban): sincroniza monitor mejorado por el equipo autónomo
- cloud: tenant desde signup (#)
