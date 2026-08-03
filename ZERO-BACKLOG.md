# ZERO-BACKLOG

Backlog operativo de los turnos nocturnos de Zero. Los docs del repo
(AGENTS.md, LOOP.md, KANBAN.md) son contexto; esto es el registro de turnos.

## Roles log

| Fecha | Rol | Resumen |
|-------|-----|---------|
| 2026-08-02 | CONSTRUCTOR | Issue #42 (Android AMAPI) cerrado: cierra el frente declarativo prioritario. Se rescató la IDEA del PR #53 de Jules y se descartó su implementación — estaba construida sobre `cameraDisabled` y `wifiConfigsLockdownEnabled`, **ambos marcados deprecated** en la referencia REST actual (viola la directriz "sin dependencias obsoletas"), era passthrough de dict sin validar, y el PR además borraba `ddm.py`/`dsc.py` por estar rameado de un main viejo. `lucidfence/core/amapi.py` nuevo, con el esquema verificado contra la doc oficial (2026-08-02): emite `cameraAccess` y `deviceConnectivityManagement.configureWifi`, valida los enums en vez de hacer `str()`, y devuelve `update_mask` — la doc de `policies.patch` dice que **sin `updateMask` se modifican TODOS los campos**, así que un parche parcial sin máscara borraba el resto de la política del tenant. Invariantes de `policyEnforcementRules` que AMAPI exige y el prototipo incumplía: `blockAction`/`wipeAction` van en pareja obligatoria y `blockAfterDays < wipeAfterDays`. Matriz de modos real (fully managed / COPE / BYOD) con las restricciones no soportadas declaradas en `skipped`, no enviadas en silencio. `supports_amapi_policy` **solo** en `applivery` (verificado vía MCP de su doc: `PUT .../mdm/android/enterprise/policies/{emmPolicyId}` con `config` = "Google Android Enterprise policy configuration object"); Intune y WS1 quedan en False con el hueco declarado, mismo criterio que dejó `supports_ddm` solo en `jamf`. Suite 387 PASS / 0 FAIL (baseline 344). |
| 2026-08-01 | MANTENEDOR | P0 #74 cerrado por la causa raíz: `sbom.cdx.json` (artefacto que hashea todos los `.py`) sale de git y muere el `assert committed == sbom`; también el paso 2 de `scripts/pre-commit.sh`, que sin el fichero habría abortado TODO commit con `.py` (hueco que el PR #75 no cubría). Verificado con `git merge-tree` que el SBOM no era el único generador: `data/cloud_state.json` — snapshot que engine-cron republica en main cada hora — conflicta en el 100% de los PRs abiertos, así que job de CI `runtime-artifacts` que lo rechaza en rama. Tercer foco: la suite dejaba sucios `roadmap.json` (restauración por bytes) y `data/actions_log.jsonl` (destrackeado). Suite 344 PASS / 0 FAIL y `git status` limpio después de correrla. |
| 2026-07-30b | DEV NOCTURNO | Issue #70 cerrado: `Engine.run_command` persiste el `device_state` que devuelve el adapter (readback `ddm_status`) con merge-no-reemplazo — un report parcial no pisa campos ausentes, `ok=False` y `dry_run` no mutan, `ddm_errors` queda en el action log. Campos nuevos `passcode_compliant` y `filevault_enabled` en `DeviceState`. Hook en el punto compartido (sirve igual al readback DSC de Windows), sin tocar la ruta imperativa. Suite 289 PASS / 2 FAIL (los 2 TypeGuard py3.9, issue #51 con PRs #69/#66 en vuelo). |
| 2026-07-30 | DEV NOCTURNO | DDM fase 2 (issue #52): canal de Jamf Pro con endpoints **verificados** contra el OpenAPI oficial v11.30 (`ddm_status` + `ddm_sync`); hueco declarado y documentado — Jamf no publica endpoint para subir declarations propias, así que `apply_ddm` sigue offline. Dos bugs de causa raíz de la fase 1: las acciones DDM no estaban en `VALID_ACTIONS` (engine y API las rechazaban: la capa declarativa era inalcanzable) y los booleanos stringificados de Jamf llegaban como `"true"` al modelo de estado. Suite 287 PASS / 2 FAIL (las 2 son el TypeGuard de Python 3.9, issue #51). |
| 2026-07-29 | DDM | Issue #40 cerrado: `lucidfence/core/ddm.py` genera declarations Apple (legacy + status-subscriptions + activation.simple) desde una `Policy`, con `ServerToken` determinista (idempotencia), gate `supports_ddm` por versión de OS y `parse_status_report`. Flag `MDMAdapter.supports_ddm` (False por defecto), `jamf` a True con acción `apply_ddm` offline. 14 tests golden sin red; suite 281 PASS + los 2 rojos py3.9 conocidos. |
| 2026-07-27 | BARRENDERO | Completada la migración a "gratis + donaciones": fuera Pro/Enterprise, `/api/plan*`, capability `org:billing` y 4 ficheros `static/saas_views*.js` muertos (530 líneas). Fix de causa raíz en `log_message` (POST a ruta desconocida devolvía 500 en vez de 404). Docs de pricing reescritos. Suite 267 PASS (= baseline main). |

## Hecho (2026-07-27)

- Migración free-only terminada (venía a medias sin commitear de un turno anterior).
- Bug preexistente arreglado: sanitizador de logs rompía `send_error(404)` en POST/DELETE (format `%d` con str) → 500s falsos.
- SBOM regenerado tras borrar los JS muertos.
- `.github/FUNDING.yml` (github: adrimg3196) — **pendiente: Adri debe activar GitHub Sponsors** para que el botón funcione.

## Hecho (2026-08-01)

- Issue #74 (P0) resuelto de raíz, más los dos generadores de conflicto que el
  issue no nombraba (`data/cloud_state.json` y la suciedad que dejaba la suite).
- Los PRs abiertos siguen necesitando **rebase manual**: el conflicto del SBOM
  pasa a ser `modify/delete` y se resuelve con `git rm sbom.cdx.json`; el de
  `data/cloud_state.json` con `git checkout origin/main -- data/cloud_state.json`.
- Rama `zero-nightly` reseteada a main: sus 9 commits huérfanos (DDM fase 2 y
  #70) ya estaban en main por otra vía — verificado con `git diff` sobre
  `lucidfence/core/ddm.py` (idéntico). Worktree obsoleto `/private/tmp/lf-zero`
  eliminado.

## Ideas

- `test_sbom_contains_locked_dependencies_and_source_manifest` quedó algo
  auto-referencial al quitar la copia commiteada: recalcula el filtro de
  `build_sbom` para comprobar el conteo. Anclarlo mejor: aserción de
  determinismo (`build_sbom(ROOT) == build_sbom(ROOT)`) y que todo pin `==` de
  `requirements.lock` aparezca en los purls.
- El SBOM ya no se versiona: si algún día hace falta trazabilidad histórica de
  supply chain, adjuntarlo a los releases de GitHub, no a los commits.
- `data/cloud_tenants/**` es el mismo patrón que `cloud_state.json` (estado de
  runtime versionado); hoy no genera conflictos, pero es candidato a la misma
  regla si empieza a moverse.
- Purga de menciones a planes de pago en docs legacy de marketing (`docs/launch-copy/`, `docs/marketing-copy.md`, `KANBAN.md`, `docs/PILOT_RUNBOOK.md`).
- Capabilities `org:delete` y `user:role` están en la matriz RBAC pero ningún endpoint las comprueba — decidir: implementar endpoints o borrarlas.
- Botón "Apoya el proyecto" (donaciones) discreto en el dashboard, alimentado por `FREE_PLAN.donations`.
- Migrar los 2 tests multiuem que fallan por `TypeGuard` (Python 3.9 del sistema) a `typing_extensions` o guardas de versión — único rojo de la suite.
- Rehacer `tests/coverage_analysis_cloud.md` tras la limpieza de billing.

## Notas para el siguiente turno

- **PRIORIDAD nº1 (orden de Adri 2026-07-28): frente declarativo DDM-DSC-AMAPI**
  — ver sección `## DDM-DSC` abajo. Issues #40 (Apple DDM), #41 (Windows DSC)
  y #42 (Android AMAPI) ya sembrados con label `agent-ready`. Nightly y Jules
  deben avanzar esto ANTES que el resto de ideas.
- **PRIORIDAD nº2 (decisión Adri+Zero 2026-07-28): SSO login opcional OIDC**
  — issue #44 (`agent-ready`), ver sección `## SSO-OIDC` abajo. Se evaluó y
  DESCARTÓ Clerk (rompe el "100% local, nothing leaves the machine" y duplica
  la auth existente); la mejora correcta es OIDC opt-in por organización sobre
  `lucidfence/saas/auth.py`, con login local siempre como fallback.
- **Graphify disponible**: `graphify-out/graph.json` (grafo AST del repo, 3846
  nodos / 8237 edges tras el turno del 2026-07-30). Antes de grepear, consultar:
  `graphify explain "X"` · `graphify path A B` · `graphify query "pregunta"`.
  Refrescar con `graphify update .` (incremental, sin LLM) tras cada tanda de commits.
- **Verificar antes de escribir un endpoint de terceros**: la doc de Jamf publica
  su OpenAPI en `developer.jamf.com/jamf-pro/reference/jamf-pro-api/llms.txt`
  (índice completo de endpoints en markdown). Sirvió para confirmar el hueco de
  las declarations en vez de inventar una ruta. Mismo patrón para el resto de MDMs.
- Rama de trabajo: `zero-nightly`. La rama local `gt/migrar-a-gratis-donaciones` quedó obsoleta (sin commits propios) — borrar cuando el PR se mergee.
- La suite se ejecuta con `python3 tests/run_tests.py` (hermética: exige el puerto 8765 libre; mata cualquier `saas_server.py` colgado antes).

## API-SDK-MCP

Directriz de producto de Adri (2026-07-28, vigente siempre): LucidFence se diseña
API-first con tecnología 100% actual, contemplando TODOS los escenarios de consumo.
Progreso de cada frente se registra aquí.

- [ ] **API pública**: spec OpenAPI versionada en el repo como contrato único; el
      dashboard consume la misma API (sin rutas privadas duplicadas).
- [ ] **SDKs oficiales**: Python y/o JS, ligeros, generados sobre la spec,
      publicables gratis (PyPI/npm).
- [ ] **Servidor MCP oficial**: agentes IA gestionan geocercas/eventos/alertas vía
      Model Context Protocol. Candidato ideal a prototipo de una noche.
- [ ] **Webhooks/eventos** para integraciones de terceros.

Restricción transversal: coste 0 (free tiers), sin dependencias obsoletas.

## DDM-DSC

Directriz de producto de Adri (2026-07-28): capa de enforcement **declarativa**
para mejor rendimiento — el estado converge en el dispositivo, no en bucles
imperativos del servidor.

- [x] **Apple DDM** (issue #40) — HECHO 2026-07-29. `lucidfence/core/ddm.py`
      + `docs/operations/apple_ddm.md` + `tests/test_ddm.py` (14 golden, sin red).
      Flag `supports_ddm` solo en `jamf`: la doc pública de Applivery no
      describe superficie DDM (verificado vía MCP `applivery-docs` 2026-07-29),
      así que NO se marca — se activará cuando lo documenten.
      `Predicate` es passthrough a propósito: Apple no publica las variables de
      predicado en su repo de schemas y no inventamos sintaxis.
- [x] **Apple DDM fase 2** (issue #52) — HECHO 2026-07-30. Canal de Jamf Pro con
      los dos endpoints que Jamf **sí** publica, verificados contra su OpenAPI
      v11.30 y citados en el PR y en `docs/operations/apple_ddm.md`:
      `GET /v1/ddm/{clientManagementId}/status-items` (acción `ddm_status`, el
      readback alimenta `device_state` vía `parse_status_report`) y
      `POST /v1/ddm/{clientManagementId}/sync` (acción `ddm_sync`, 204 sin cuerpo).
      **Hueco declarado**: subir declarations propias no existe por API — solo
      `GET /v1/dss-declarations/{id}`, de lectura; las personalizadas se
      despliegan por UI (Blueprints). Por eso `apply_ddm` sigue offline en vez de
      inventar la llamada; cuando Jamf lo publique, el cambio es local a
      `_apply_ddm`.
      Dos bugs de causa raíz de la fase 1, corregidos: las acciones DDM no
      estaban en `VALID_ACTIONS` (el engine y el endpoint de comandos las
      rechazaban con "accion no valida" — la capa declarativa era inalcanzable
      desde el producto) y los `StatusItem.value` de Jamf son string siempre, así
      que `passcode.is-compliant` llegaba como `"true"` a un campo `bool`.
      No hay hook nuevo en el engine a propósito: `apply_ddm` lee `fence_state`
      del `DeviceState` que ya recibe, así que `Engine.run_command` selecciona el
      juego correcto sin código extra.
- [x] **Windows PowerShell DSC** (issue #41) — HECHO (PR #43 mergeado):
      `lucidfence/core/dsc.py` + `tests/test_windows_conformidad_dsc.py` +
      `docs/operations/windows_dsc.md` ya están en main.
      Enunciado original: `lucidfence/core/dsc.py` emite
      documentos DSC v3 (manifests JSON/YAML) con emisor fallback .ps1/MOF
      clásico. Idempotente (re-apply sin cambios = no-op), readback de
      compliance al pipeline de device state. Flag `supports_dsc` en
      `windows_conformidad`.
- [x] **Android AMAPI** (issue #42) — HECHO 2026-08-02. `lucidfence/core/amapi.py`
      + `docs/operations/android_amapi.md` + `tests/test_amapi.py` (43 golden,
      sin red, sin proyecto enterprise de Google). Esquema verificado contra la
      referencia REST oficial el 2026-08-02.
      **Dos correcciones sobre el enunciado original**, ambas con fuente:
      1. Los campos que el issue y el PR #53 daban por buenos, `cameraDisabled`
         y `wifiConfigsLockdownEnabled`, están **deprecated** en la referencia
         actual. Se emiten sus sustitutos: `cameraAccess` y
         `deviceConnectivityManagement.configureWifi`.
      2. `supports_amapi_policy` va **solo en `applivery`**, no en los tres
         adapters Android. Gestionar Android Enterprise no implica exponer el
         documento de política por API: Applivery documenta el passthrough
         (`PUT /v1/organizations/{org}/mdm/android/enterprise/policies/{emmPolicyId}`,
         campo `config` = "Google Android Enterprise policy configuration
         object", verificado vía el MCP de su doc); Intune y WS1 no publican
         equivalente, así que quedan en False con el hueco declarado. Mismo
         criterio que dejó `supports_ddm` solo en `jamf`.
      **Invariantes que AMAPI exige** y `build_enforcement_rules` valida:
      `blockAction` y `wipeAction` van en pareja obligatoria, y
      `blockAfterDays < wipeAfterDays`. `build_policy_patch` devuelve además
      `update_mask` porque `policies.patch` sin `updateMask` modifica TODOS los
      campos modificables — un parche parcial sin máscara borraría el resto de
      la política del tenant.
      Matriz de modos aplicada en código: lo que no aplica al modo se declara en
      `skipped` con su motivo, no se envía en silencio (kiosco solo fully
      managed; bloqueo de Wi-Fi excluye BYOD). `apply_amapi_policy` genera
      offline, como `apply_ddm`: publicar exigiría el `emmPolicyId` del tenant y
      mutaría la política de un cliente real.
- [ ] Matriz de soporte documentada en `docs/` (versiones OS, DDM vs legacy,
      DSC v2 vs v3, AMAPI COBO/BYOD) y fixtures golden en tests (sin red, sin
      host Windows, sin proyecto enterprise de Google). Apple y Windows ya tienen
      su matriz en `docs/operations/apple_ddm.md` y `docs/operations/windows_dsc.md`;
      Android ya la tiene en `docs/operations/android_amapi.md`. Las tres
      existen: queda **unificarlas** en una sola tabla (issue #72).
      Nota para quien la unifique: el PR #53 (Jules, AMAPI) queda **obsoleto**;
      se rescató la idea y se descartó la implementación (campos deprecados,
      sin validación, y borraba `ddm.py`/`dsc.py` por venir de un main viejo).

Regla transversal: capacidad aditiva — la ruta imperativa actual no se rompe.

## SSO-OIDC

Decisión de producto (Adri delegó, Zero decidió, 2026-07-28): login enterprise
vía **OIDC opcional por organización**, NO Clerk ni ningún IdP cloud obligatorio.
Los compradores UEM quieren entrar con SU IdP (Entra ID, Google Workspace, Okta,
Keycloak); el modo 100% local sigue siendo el default intacto.

- [ ] **OIDC opt-in** (issue #44): `lucidfence/saas/oidc.py` — Authorization
      Code Flow + PKCE, stdlib-first, discovery `.well-known`, validación JWKS
      de id_token. Rutas `GET /api/auth/oidc/login|callback` en `saas_server.py`
      que desembocan en la sesión LOCAL normal (RBAC de `auth.py` sin cambios).
      Config por org en Settings (issuer, client_id, client_secret cifrado,
      dominio permitido, rol JIT por defecto). Botón "Continuar con SSO" en
      `static/` solo si la org lo tiene configurado; login local con contraseña
      SIEMPRE disponible (break-glass). Tests con IdP mock (JWKS estático) +
      negativos (state/nonce/iss inválidos, dominio no permitido).

Guardarraíl: sin OIDC configurado, cero llamadas de red — la promesa
"nothing leaves the machine" no se toca.

## Plan persistente nocturno — 2026-08-01

**Objetivo:** endurecer el núcleo de geolocalización/geocercas y convertir
calidad, seguridad y linting en gates reproducibles de coste cero. Este plan es
el estado recuperable del cron: el siguiente worker debe leerlo antes de actuar,
marcar una sola tarea `in_progress` y registrar el resultado verificable.

**Modo:** solo tareas locales/offline; sin servicios de pago, sin credenciales
reales y sin llamadas a UEMs en los tests. Una tarea no está hecha por tener
código: requiere su comando de verificación verde y `git status` sin artefactos
de runtime nuevos.

### Fase 1 — preservar coordenadas cero en fuentes de ubicación

**Estado:** pending

- Corregir `AppliveryLocationSource._extract_last_location` para no usar `or`
  al escoger latitud/longitud: `0.0` es válido en ecuador y Greenwich.
- Añadir regresiones para shapes anidado y plano con `lat=0`, `lng=0`, además
  de ausencia real (`None`). Extender el mismo contrato al mapper genérico.
- **Hecho cuando:** los tests nuevos fallan antes del cambio, pasan después y
  `python3 tests/run_tests.py` termina con 0 fallos bajo Python >=3.11.

### Fase 2 — validar coordenadas y números no finitos en el borde de entrada

**Estado:** pending

- Rechazar `NaN`, `Infinity`, latitudes fuera de `[-90, 90]`, longitudes fuera
  de `[-180, 180]` y radios no finitos/<=0 antes de crear `LocationReport` o
  evaluar una `Fence`; no convertirlos silenciosamente en ubicación fiable.
- Cubrir `Fence.from_raw`, `validate_fences`, fuente Applivery y
  `GenericHTTPLocationSource._to_report` con tests parametrizados sin red.
- **Hecho cuando:** cada entrada inválida produce un resultado explícito y
  estable (problema de validación o reporte omitido), sin excepción que aborte
  el ciclo, y pasan los tests focalizados más la suite completa.

### Fase 3 — fijar la semántica geométrica de borde y antimeridiano

**Estado:** pending

- Especificar si un punto sobre el borde de un polígono cuenta como dentro y
  aplicar esa regla de forma determinista en `point_in_polygon`.
- Añadir casos golden: borde/vértice, polígono cóncavo, coordenadas negativas,
  cercanía de polos y geocerca que cruza `+180/-180`. Si el algoritmo actual
  no soporta antimeridiano, normalizar longitudes localmente con stdlib.
- **Hecho cuando:** el contrato queda documentado junto al código, todos los
  golden pasan y el benchmark existente de 10k geofences mantiene su umbral.

### Fase 4 — gate gratuito de lint y tipos, sin reescritura masiva

**Estado:** pending

- Medir primero `ruff check` y un type-checker sobre `lucidfence/core/geo.py`,
  `fences.py`, `location_source.py` y `generic_http_source.py`; registrar el
  baseline, no ocultarlo con `continue-on-error`.
- Fijar versiones/hashes en el lock de tooling y añadir un job CI focalizado.
  Corregir solo los hallazgos de estos módulos; no formatear todo el repo.
- **Hecho cuando:** el gate falla ante una fixture deliberadamente inválida,
  luego pasa limpio en CI/local y no introduce SaaS ni dependencia de pago.

### Fase 5 — seguridad del conector HTTP de ubicación

**Estado:** pending

- Añadir pruebas contra SSRF/configuración peligrosa: esquemas distintos de
  HTTPS (permitir HTTP solo para loopback local explícito), redirects a destinos
  no permitidos, timeout acotado y respuestas sobredimensionadas/no JSON.
- Verificar que errores y logs no exponen cabeceras `Authorization` ni valores
  sustituidos desde entorno. Todo test usará servidor local/mock, nunca red real.
- **Hecho cuando:** los negativos quedan cubiertos, gitleaks y pip-audit siguen
  verdes, y el conector conserva el modo local sin credenciales configuradas.

### Gate de completitud del plan

- [ ] Las cinco fases figuran `complete`, nunca solo descritas como "hechas".
- [ ] Cada fase enlaza commit/PR o diff y salida literal de sus tests focalizados.
- [ ] `python3 tests/run_tests.py`: 0 fallos con el Python soportado (>=3.11).
- [ ] CI: tests, lint/tipos, pip-audit, SBOM y gitleaks verdes.
- [ ] Ningún fichero bajo `graphify-out/` ni snapshot de runtime se commitea.

### Errores/limitaciones observados al crear el plan

| Hallazgo | Impacto | Siguiente acción |
|---|---|---|
| Graphify devolvió 58 nodos y truncó a 21 con budget 700 | La consulta amplia no mostró todo el subgrafo | Se usaron `explain` y `affected` sobre `_sync_geofences`; no se inventaron relaciones |
| `planning-with-files` aparece `excluded` por la allowlist del agente | Sus hooks no se inyectan automáticamente en este worker | El plan se aplicó manualmente; no tocar `openclaw.json` sin autorización |
