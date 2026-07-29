# ZERO-BACKLOG

Backlog operativo de los turnos nocturnos de Zero. Los docs del repo
(AGENTS.md, LOOP.md, KANBAN.md) son contexto; esto es el registro de turnos.

## Roles log

| Fecha | Rol | Resumen |
|-------|-----|---------|
| 2026-07-30 | DEV NOCTURNO | DDM fase 2 (issue #52): canal de Jamf Pro con endpoints **verificados** contra el OpenAPI oficial v11.30 (`ddm_status` + `ddm_sync`); hueco declarado y documentado — Jamf no publica endpoint para subir declarations propias, así que `apply_ddm` sigue offline. Dos bugs de causa raíz de la fase 1: las acciones DDM no estaban en `VALID_ACTIONS` (engine y API las rechazaban: la capa declarativa era inalcanzable) y los booleanos stringificados de Jamf llegaban como `"true"` al modelo de estado. Suite 287 PASS / 2 FAIL (las 2 son el TypeGuard de Python 3.9, issue #51). |
| 2026-07-29 | DDM | Issue #40 cerrado: `lucidfence/core/ddm.py` genera declarations Apple (legacy + status-subscriptions + activation.simple) desde una `Policy`, con `ServerToken` determinista (idempotencia), gate `supports_ddm` por versión de OS y `parse_status_report`. Flag `MDMAdapter.supports_ddm` (False por defecto), `jamf` a True con acción `apply_ddm` offline. 14 tests golden sin red; suite 281 PASS + los 2 rojos py3.9 conocidos. |
| 2026-07-27 | BARRENDERO | Completada la migración a "gratis + donaciones": fuera Pro/Enterprise, `/api/plan*`, capability `org:billing` y 4 ficheros `static/saas_views*.js` muertos (530 líneas). Fix de causa raíz en `log_message` (POST a ruta desconocida devolvía 500 en vez de 404). Docs de pricing reescritos. Suite 267 PASS (= baseline main). |

## Hecho (2026-07-27)

- Migración free-only terminada (venía a medias sin commitear de un turno anterior).
- Bug preexistente arreglado: sanitizador de logs rompía `send_error(404)` en POST/DELETE (format `%d` con str) → 500s falsos.
- SBOM regenerado tras borrar los JS muertos.
- `.github/FUNDING.yml` (github: adrimg3196) — **pendiente: Adri debe activar GitHub Sponsors** para que el botón funcione.

## Ideas

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
- [ ] **Windows PowerShell DSC** (issue #41): `lucidfence/core/dsc.py` emite
      documentos DSC v3 (manifests JSON/YAML) con emisor fallback .ps1/MOF
      clásico. Idempotente (re-apply sin cambios = no-op), readback de
      compliance al pipeline de device state. Flag `supports_dsc` en
      `windows_conformidad`.
- [ ] **Android AMAPI** (issue #42): `lucidfence/core/amapi.py` genera el patch
      de policy AMAPI (restricciones por estado de geocerca) con
      `policyEnforcementRules` para escalado gradual; flag
      `supports_amapi_policy` en adapters con backend Android (applivery,
      intune, workspace_one). Readback vía `policyCompliant` /
      `nonComplianceDetails`. Matriz COBO vs work profile obligatoria — muchas
      restricciones dependen del modo de gestión.
- [ ] Matriz de soporte documentada en `docs/` (versiones OS, DDM vs legacy,
      DSC v2 vs v3, AMAPI COBO/BYOD) y fixtures golden en tests (sin red, sin
      host Windows, sin proyecto enterprise de Google). Apple y Windows ya tienen
      su matriz en `docs/operations/apple_ddm.md` y `docs/operations/windows_dsc.md`;
      queda unificarlas cuando el AMAPI (PR #53) entre.

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
