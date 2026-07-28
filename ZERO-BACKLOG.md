# ZERO-BACKLOG

Backlog operativo de los turnos nocturnos de Zero. Los docs del repo
(AGENTS.md, LOOP.md, KANBAN.md) son contexto; esto es el registro de turnos.

## Roles log

| Fecha | Rol | Resumen |
|-------|-----|---------|
| 2026-07-28 | INTEGRADOR | **osquery integrado (orden directa de Adri: "sí o sí")**: `lucidfence/core/posture_osquery.py` — posture real del endpoint (os_version, cifrado, disco, batería, salud del agente) desde el results log de osqueryd o `osqueryi`, con evidence gate de frescura y merge en el Risk Engine (`engine.py` pre-`risk.evaluate`). Pack en `deploy/osquery/lucidfence.conf`, doc en `docs/operations/OSQUERY.md`, 7 tests nuevos. Suite 274 PASS / 2 FAIL conocidos (TypeGuard py3.9). Sinergia: mismo agente que usa Fleet → historia "funciona con tu despliegue osquery/Fleet existente". |
| 2026-07-27 | BARRENDERO | Completada la migración a "gratis + donaciones": fuera Pro/Enterprise, `/api/plan*`, capability `org:billing` y 4 ficheros `static/saas_views*.js` muertos (530 líneas). Fix de causa raíz en `log_message` (POST a ruta desconocida devolvía 500 en vez de 404). Docs de pricing reescritos. Suite 267 PASS (= baseline main). |

## Hecho (2026-07-27)

- Migración free-only terminada (venía a medias sin commitear de un turno anterior).
- Bug preexistente arreglado: sanitizador de logs rompía `send_error(404)` en POST/DELETE (format `%d` con str) → 500s falsos.
- SBOM regenerado tras borrar los JS muertos.
- `.github/FUNDING.yml` (github: adrimg3196) — **pendiente: Adri debe activar GitHub Sponsors** para que el botón funcione.

## Ideas

- osquery fase 2: mostrar `posture_source`/`osquery_version` en el dashboard (badge "verificado en endpoint"); explorar geolocalización wifi (`wifi_survey`) como location source alternativa sin GPS.

- Purga de menciones a planes de pago en docs legacy de marketing (`docs/launch-copy/`, `docs/marketing-copy.md`, `KANBAN.md`, `docs/PILOT_RUNBOOK.md`).
- Capabilities `org:delete` y `user:role` están en la matriz RBAC pero ningún endpoint las comprueba — decidir: implementar endpoints o borrarlas.
- Botón "Apoya el proyecto" (donaciones) discreto en el dashboard, alimentado por `FREE_PLAN.donations`.
- Corregir el entrypoint de tests para que seleccione el entorno bloqueado con Python >=3.11 o falle temprano con un mensaje claro; actualizar README/PR template/monitor para no recomendar el `python3` accidental del sistema. Evidencia 2026-07-28: `/usr/bin/python3` 3.9 da 267 PASS/2 FAIL por `TypeGuard`, mientras los 43 tests multiuem pasan 43/43 con Python 3.11. No añadir `typing_extensions`: `pyproject.toml` ya declara `requires-python >=3.11` y el problema es el runner/entorno, no el dominio multiuem.
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
- **Graphify disponible**: `graphify-out/graph.json` (grafo AST del repo, 3225
  nodos). Antes de grepear, consultar: `graphify explain "X"` · `graphify path A B`
  · `graphify query "pregunta"`. Regenerar tras merges grandes: `graphify .`
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

- [ ] **Apple DDM** (issue #40): `lucidfence/core/ddm.py` genera declarations
      (configurations + activations con predicados) desde una fence policy y
      consume el status channel. Flag `supports_ddm` en adapters Apple
      (ios_geofence, jamf, applivery), fallback imperativo intacto.
      Límite honesto: DDM no tiene primitivas de geolocalización — el trigger
      sigue en nuestro agente; DDM es la capa de config/enforcement.
      Validar contra schemas de `apple/device-management` (iOS 15+/macOS 13+).
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
      host Windows, sin proyecto enterprise de Google).

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
