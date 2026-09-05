# LucidFence 2.0 — Diseño de la reescritura en Go

- **Fecha:** 2026-09-05
- **Estado:** aprobado sección a sección por el propietario (Adri) en sesión de brainstorming; pendiente de revisión final del documento.
- **Alcance del documento:** una sola spec para todo el proyecto. El plan de implementación se parte por hitos (§14); cada hito tiene su propio plan.

## 1. Resumen

LucidFence 1.x es un producto de geofencing multi-UEM local-first escrito en Python 3.11 (unas 84 000 líneas entre Python y shell, 304 ficheros Python, 25 workflows, 872 tests). El código de producto está mezclado con la maquinaria de una flota de agentes de IA que lo mantiene de forma autónoma, y los ficheros centrales son monolitos (`saas_server.py` 3 087 líneas con un solo `Handler` y unas 90 rutas enrutadas a mano; `engine.py` 1 359 líneas con un `run_once()` de 400; `app.js` 174 KB). El propietario ha decidido reescribirlo entero.

LucidFence 2.0 es una reescritura desde cero en **Go**, con un **único binario** que sirve API, dashboard, CLI y MCP, un frontend **React + TypeScript** embebido, y un repositorio que contiene **solo producto**: la oficina de agentes sale del repo. El corte se hace **sustituyendo `main` desde el primer push**, con el código 1.x preservado en el tag `v1.6.1-python-final` y la rama `legacy/python`.

## 2. Decisiones tomadas (y por quién)

| # | Decisión | Elección del propietario |
|---|----------|--------------------------|
| 1 | Alcance | Todo el repo (producto, tooling, workflows, docs). |
| 2 | Stack | Cambio de lenguaje a Go. |
| 3 | Entrega | Reemplazar `main` ya; lo viejo a `legacy/python` + tag. |
| 4 | Flota de agentes | Raíles mínimos (`agent-pr` + `agent-automerge`) con gate de CI duro. GTM, recon, loops, brand: fuera del repo. |
| 5 | Frontend | UI "SaaS 2026" guiada por taste-skill (leonxlnx/taste-skill); decisión técnica delegada al agente: React 19 + TypeScript + Vite + Tailwind v4 + shadcn/ui. |
| 6 | Arquitectura | A: monolito modular, un binario, fronteras de paquete validadas en CI. |

## 3. Principios que se conservan y principios que cambian

**Se conservan** (los ADRs 0005-0011 de 1.x se reescriben con el mismo espíritu):

1. **Local-first, cero telemetría, cero exfiltración de ubicación.** El dato del tenant vive en la máquina del tenant. La única publicación externa es el snapshot demo de la vitrina, sin secretos y con datos simulados.
2. **Complemento del UEM, nunca un UEM.** No enrola, no empuja perfiles, no gestiona apps ni parches. Lee, correlaciona, decide riesgo y ordena acciones al UEM que ya existe.
3. **El runtime lo decide el admin.** `observe` por defecto (todo dry-run), `enforce` solo explícito por tenant, allowlist de acciones en vivo, doble llave para `wipe`. Ningún componente puede debilitarlo; hay tests que lo bloquean.
4. **Gratis y open source (Apache-2.0).** Sin pricing, sin edición enterprise.
5. **Honestidad verificable.** Todo claim de producto se comprueba en vivo en CI contra el binario real (batería runtime), no solo con tests unitarios.
6. **Estado en ficheros JSON/JSONL en disco**, sin base de datos.

**Cambian:**

- Python stdlib-first → **Go**, binario estático, stdlib más una allowlist mínima de dependencias.
- Runner de tests propio → `go test` y Vitest/Playwright.
- Servidor HTTP artesanal de 3 000 líneas → `net/http` con patrones de método y path, un fichero por recurso.
- Vanilla JS sin build → React + TypeScript compilado en CI y embebido en el binario.
- Auto-merge total sin gate humano → auto-merge solo dentro de límites (tamaño, rutas, CODEOWNERS) y con gate de CI estricto.

## 4. Alcance funcional

### 4.1 Se conserva (núcleo del producto)

- **Geocercas y rutas.** Círculo y polígono; acciones por evento (`on_enter`, `on_exit`, `on_violation`, `on_unknown`); violación sostenida cada N ciclos; rutas con corredor en metros y acciones al salir; puntos de interés (GeoJSON); alta de geocerca por dirección vía Nominatim (opcional, con allowlist de egress).
- **Inventario y ubicación.** Modelo de dispositivo normalizado (identidad, plataforma, SO, modelo, fabricante, serie, IMEI, batería, almacenamiento, cifrado, operador, usuario, departamento, fechas de enrolado y check-in, etiqueta, modo de gestión, propiedad, supervisión, lockdown, salud hardware, referencias por proveedor). Fuente simulada con seed determinista; fuente en vivo vía conectores. Enriquecimiento por red (SSID/BSSID → sitio). Integridad de ubicación (teletransporte, velocidad imposible, precisión).
- **Motor de riesgo explicable.** Señales: `time_of_day`, `shift_match`, `device_health`, `device_posture`, `location_integrity`, `zone_risk`, `route_state`. Políticas con condiciones, acciones, severidad, plantillas. Simulador what-if de políticas contra el histórico. Puntuación 0-100 con severidad y razones textuales; `risk_score` nulo cuando la evaluación falla.
- **Acciones UEM con frenos.** `lock`, `wipe`, `message`, `locate`, `reboot`, `clear_passcode`, `set_compliance`, `custom`. Deduplicación por ciclo, cooldown por dispositivo y acción, dry-run por defecto, observe/enforce, allowlist de acciones en vivo, doble llave de wipe (`allow_wipe` y `wipe_allowlist`). Log de acciones.
- **Incidentes, alertas y SOAR.** Incidentes con ciclo de vida, analítica y exportación. Reglas de alerta. Playbooks SOAR: acciones no destructivas se ejecutan; destructivas generan un handoff pendiente de aprobación humana.
- **Integraciones de salida.** Webhook firmado HMAC-SHA256 (cabecera `X-LucidFence-Signature: sha256=<hex>` sobre el cuerpo exacto, compatible con 1.x), formato OCSF Detection Finding opcional, ntfy, allowlist de egress.
- **Conectores UEM.** `simulation`, `applivery`, `intune`, `jamf`, `fleet`, `workspaceone`. Contrato único; nunca tumban el ciclo.
- **Multi-UEM.** Varios proveedores a la vez, dispositivo normalizado, reconciliación de identidad entre UEMs, vista federada, salud por proveedor, auditoría de mínimo privilegio de credenciales (scopes declarados vs necesarios según enforcement).
- **Postura y vulnerabilidades.** Ingesta de resultados osquery (fichero de resultados), enriquecimiento CVE desde NVD con caché local y comando de refresco.
- **Informes.** Puntos ciegos (coverage), segunda opinión (UEM afirma vs observado), informe ejecutivo, exportaciones CSV y HTML imprimible, informe de evidencia con cadena de hashes verificable offline.
- **Auth y tenants.** Usuarios locales, sesiones, organizaciones (tenants locales), roles `owner`, `admin`, `operator`, `viewer`, `auditor` con capacidades, API keys con auditoría encadenada, OIDC genérico opcional.
- **CLI y MCP.** `serve`, `start`, `stop`, `restart`, `status`, `open`, `doctor`, `apply`, `validate`, `migrate`, `mcp`, `demo snapshot`, `version`. MCP por stdio, solo lectura.
- **Superficie pública.** Landing, vitrina que lee el snapshot demo de la rama `cloud-state`, manual ES/EN.

### 4.2 Se elimina

- Empresa autónoma, loops, governance, roadmap tooling, free tier, plugins de proveedores de IA, marketplace de adapters, seeds de kanban, recon, GTM linter, brand, marketing, vídeos, `loop_improve.py`.
- Cliente de email atomicmail, whitelabel y FreeDomain, chat de IA y gateway OpenAI-compatible.
- Enrutado declarativo DDM/DSC, transmisor SSF/CAEP, predicción de movimiento, HA por lease, blob storage, PDF artesanal.
- Adapters mock de ChromeOS, Windows conformidad e iOS geofence (sus campos de postura viven en el modelo de dispositivo y en el seed de simulación).
- App macOS Swift, worker Cloudflare, deploy Fly.io, publicación PyPI, `server.py` legado.
- Vistas: IA, empresa, objetivos, roadmap, ROI, inteligencia, workflows. La analítica útil pasa a la visión general; las plantillas de workflows pasan a plantillas de políticas.

### 4.3 Fuera de alcance

- Repo `lucidfence-web` (PWA aparte): no se toca.
- Migración del histórico de eventos/acciones 1.x: no se migra (solo configuración y seed, §5.6).

## 5. Arquitectura del backend

### 5.1 Estructura del repositorio

```
lucidfence/
├─ cmd/lucidfence/          main: subcomandos y arranque; sin lógica de negocio
├─ internal/
│  ├─ domain/               tipos y reglas puras: geo, fences, routes, pois, devices,
│  │                        policies, risk, actions, incidents, alerts, playbooks. Cero I/O.
│  ├─ engine/               ciclo de evaluación, guardarraíles, dedupe, cooldown, handoffs
│  ├─ uem/                  contrato Adapter, registro, tipos comunes
│  │  ├─ simulation/  applivery/  intune/  jamf/  fleet/  workspaceone/
│  ├─ store/                JSON/JSONL atómico en disco; un lock por org
│  ├─ auth/                 usuarios, sesiones, orgs, roles, API keys, OIDC, token local
│  ├─ api/                  router net/http, un fichero por recurso, middleware
│  ├─ notify/               webhook HMAC, OCSF, ntfy, egress allowlist, cola de entregas
│  ├─ posture/              osquery, sitios de red, CVE/NVD
│  ├─ reports/              coverage, segunda opinión, ejecutivo, evidencia, CSV/HTML
│  ├─ mcp/                  JSON-RPC 2.0 por stdio, solo lectura
│  ├─ battery/              batería runtime contra el binario real (la usa CI)
│  ├─ migrate/              importador del directorio de datos 1.x
│  └─ web/                  embed.FS del frontend compilado
├─ web/                     fuente React + TypeScript (dos entradas: app y site)
├─ deploy/                  Dockerfile, compose (+Caddy opcional), systemd, launchd, install.sh
├─ docs/                    ARCHITECTURE.md, adr/, openapi.yaml, manual/, GETTING_STARTED.md
├─ scripts/                 solo utilidades de build/CI (limits.sh, battery.sh)
└─ .github/workflows/       ci.yml, release.yml, publish-site.yml, publish-demo.yml,
                            agent-pr.yml, agent-automerge.yml
```

### 5.2 Reglas de dependencia (validadas por depguard en CI)

| Paquete | Puede importar del proyecto |
|---------|-----------------------------|
| `domain` | nada |
| `uem` y conectores | `domain` |
| `store` | `domain` |
| `posture`, `reports`, `notify` | `domain`, `store` |
| `engine` | `domain`, `uem`, `store`, `notify`, `posture` |
| `auth` | `domain`, `store` |
| `api` | `engine`, `auth`, `store`, `reports`, `domain` (nunca un conector concreto) |
| `mcp` | `api` (cliente HTTP local) |
| `cmd` | todo |

### 5.3 Modelo de dominio (tipos principales)

- `geo.Point{Lat, Lng}`; funciones: haversine, punto en polígono (ray casting), distancia a polilínea.
- `Fence{ID, Name, Kind(circle|polygon), Center, RadiusM, Polygon []Point, Rules{ViolationIntervalCycles, DwellSeconds}, Actions []FenceAction{Action, When, Params, Enabled}}`.
- `Route{ID, Name, CorridorM, Waypoints []Point, DeviceIDs, Actions}`; `POI` como Feature GeoJSON con `Category`, `Tags`, `Metadata`.
- `Device{ID, Name, Platform, Inventory{...}, Location{Point, AccuracyM, Source, ObservedAt}, Network{SSID, BSSID, IP}, Posture{...}, ProviderRefs map[string]string, Risk Verdict, FenceState, InsideFence, RouteState, RouteDeviationM, EvaluationError string}`.
- `Verdict{Score *float64, Severity, Reasons []string, MatchedPolicies []string, EvaluatedAt, Provenance, Verified}`.
- `Policy{ID, Name, Description, When []Condition{Field, Op, Value}, Actions []PolicyAction, Enabled, Severity, Source, TemplateID}`. `Field` admite campos del dispositivo, `fence_state`, `route_state` y `signal:<nombre>.<clave>`. `Op` ∈ {eq, ne, gt, gte, lt, lte, in, contains}.
- `Action` (enum) y `ActionResult{Adapter, OK, DeviceID, Action, Params, DryRun, Simulated, Error, CommandID, Note, Timestamp, FenceID, Trigger}`.
- `Transition{Timestamp, DeviceID, From, To}`, `Incident{ID, DeviceID, Severity, Kind, Title, Status(open|ack|closed), OpenedAt, ClosedAt, Evidence}`, `AlertRule`, `Playbook{ID, Name, Conditions, Actions, Enabled}`, `Handoff{ID, DeviceID, Action, Params, Reason, Status(pending|approved|rejected|executed), RequestedAt, DecidedBy}`.
- `Enforcement{Mode(observe|enforce), LiveActions []Action, AllowWipe bool, WipeAllowlist []string, ActionCooldownSeconds int}`.

### 5.4 Ciclo del motor

Un goroutine por org ejecuta el ciclo con ticker (`interval_seconds`); `POST /api/v1/engine/run-once` lo dispara bajo el mismo mutex con `TryLock`: si hay un ciclo en curso se responde `409` y no se solapa. Pasos:

1. Pedir ubicaciones e inventario a cada proveedor; registrar salud por proveedor (último error, latencia, dispositivos).
2. Normalizar dispositivos y reconciliar identidades entre proveedores (serie, IMEI, nombre normalizado).
3. Por dispositivo, con `recover()` individual: geocerca (estado y dwell), ruta (corredor y desviación), integridad de ubicación (contra la observación previa), postura (osquery y red), enriquecimiento CVE.
4. Calcular señales y veredicto de riesgo; emparejar políticas.
5. Detectar transiciones y violaciones sostenidas.
6. Decidir acciones (geocerca, ruta, política) y pasarlas por guardarraíles: dedupe por ciclo → cooldown → observe/enforce → allowlist de acciones en vivo → doble llave de wipe. Ejecutar vía adapter.
7. Evaluar playbooks SOAR: no destructivas se ejecutan (con los mismos guardarraíles); destructivas crean handoffs.
8. Abrir, actualizar o cerrar incidentes; evaluar alertas.
9. Notificar (webhooks, ntfy) a través de la cola de entregas.
10. Persistir estados, transiciones, acciones, incidentes y estadísticas del ciclo.

Los guardarraíles viven exclusivamente en `engine/guardrails.go` y se aplican también a la ejecución de handoffs aprobados y a las acciones manuales desde la API.

### 5.5 Persistencia

```
<data>/
├─ orgs/<org>/
│  ├─ fences.json  routes.json  pois.json  policies.json  playbooks.json  alerts.json
│  ├─ providers.json  settings.json  devices.json  handoffs.json  incidents.json
│  ├─ events.jsonl  actions.jsonl  stats.jsonl  deliveries.jsonl
│  └─ seed.json                     (solo modo simulación)
├─ auth/  users.json  sessions.json  apikeys.json  audit.jsonl  local-token (0600)
├─ secrets/<org>/<provider>.json    (0600; nunca en respuestas ni logs)
└─ cache/  cve.json
```

Escritura atómica (fichero temporal + `rename`), JSONL solo append, un `sync.RWMutex` por org en el store, ficheros de datos con permisos 0600 y directorios 0700. Cada fichero lleva `schema_version`.

### 5.6 Migración desde 1.x

`lucidfence migrate --from <dir de datos 1.x> [--org <id>]` importa geocercas, rutas, POIs, políticas, seed de simulación y proveedores (sin credenciales) a los esquemas 2.0, informa de lo importado y lo omitido, y nunca sobrescribe datos 2.0 existentes sin `--force`. Se verifica con fixtures reales copiadas de `legacy/python` a `internal/migrate/testdata/`.

### 5.7 Contrato de conector

```go
type Adapter interface {
    Name() string
    Capabilities() Capabilities // Actions []Action, Inventory, Location, Posture bool
    FetchDevices(ctx context.Context) ([]domain.Device, error)
    Execute(ctx context.Context, dev domain.Device, action domain.Action,
            params map[string]any, dryRun bool) domain.ActionResult
    TestConnection(ctx context.Context) ConnectionResult
}
```

Reglas: `Execute` nunca hace `panic` ni devuelve error como tipo, siempre `ActionResult` con `OK=false` y `Error` textual; el constructor no contacta con el proveedor; sin credenciales el conector queda en modo mock y lo declara. Añadir un conector = un paquete nuevo + una línea en `uem.Registry`. Endpoints por proveedor (de 1.x, se conservan): Applivery `GET /organizations/{org}/mdm/devices` y `POST .../devices/{id}/commands`; Intune vía Microsoft Graph `deviceManagement/managedDevices` con client credentials; Jamf Pro `api/v1/mobile-devices/{id}/commands` con client credentials; Fleet REST con bearer; Workspace ONE `API/mdm/devices` con tenant-code y Basic.

### 5.8 Configuración, secretos y dependencias

- `config.json`: `data_dir`, `listen` (`127.0.0.1:8765` por defecto), `interval_seconds`, `mode` (`simulation|live`), `map.tiles_url`, `map.enabled`, `egress.hosts`, `egress.allow_private`, `oidc` (opcional).
- Secretos: variables `LUCIDFENCE_*` o ficheros 0600 en `<data>/secrets/`. Nunca en `GET`, logs, MCP ni frontend.
- Allowlist de dependencias Go (test la lee de `go.mod`): `github.com/coreos/go-oidc/v3`, `golang.org/x/oauth2`, `golang.org/x/crypto` (argon2), `github.com/google/go-cmp` (tests). Todo lo demás, stdlib.
- Go 1.26 o superior. `log/slog` con nivel configurable. Binario estático (`CGO_ENABLED=0`).

## 6. API, autenticación, RBAC e integraciones

### 6.1 API HTTP (`/api/v1`)

| Recurso | Métodos |
|---------|---------|
| `health`, `readyz` | GET (sin auth; sin secretos) |
| `auth/login`, `auth/logout`, `auth/me`, `auth/setup`, `auth/oidc/{provider}/start`, `auth/oidc/{provider}/callback` | POST / GET |
| `org`, `members`, `members/{id}/role`, `apikeys`, `apikeys/{id}`, `audit` | GET, POST, PATCH, DELETE según recurso |
| `devices`, `devices/{id}`, `devices/{id}/actions`, `devices/{id}/trail` | GET, POST |
| `fences`, `fences/{id}`, `routes`, `routes/{id}`, `pois`, `pois/{id}` | GET, POST, PUT, DELETE |
| `policies`, `policies/{id}`, `policies/templates`, `policies/replay` | GET, POST, PUT, DELETE, POST |
| `providers`, `providers/{id}`, `providers/catalog`, `providers/test`, `providers/least-privilege`, `fleet/federated` | GET, POST, PUT, DELETE |
| `incidents`, `incidents/{id}`, `incidents/analytics`, `incidents/export` | GET, PATCH |
| `alerts`, `alerts/{id}`, `alerts/evaluate` | GET, POST, PUT, DELETE |
| `playbooks`, `playbooks/{id}`, `handoffs`, `handoffs/{id}/approve`, `handoffs/{id}/reject` | GET, POST, PUT, DELETE |
| `events`, `actions` | GET (paginado con `limit` y `cursor`) |
| `engine/status`, `engine/run-once` | GET, POST |
| `reports/overview`, `reports/coverage`, `reports/second-opinion`, `reports/executive`, `reports/evidence`, `reports/export` | GET |
| `settings`, `settings/enforcement`, `settings/webhooks`, `settings/egress`, `settings/validate`, `config/apply` | GET, PUT, POST |
| `cve/refresh` | POST |

Errores con forma única `{"error": "<mensaje>", "code": "<slug>", "detail": {...}}`. Cada ruta se registra con su capacidad; un test recorre el registro y falla si falta alguna, y otro comprueba que toda ruta registrada aparece en `docs/openapi.yaml`.

### 6.2 Autenticación

- Sesión con cookie `HttpOnly; Secure (si TLS); SameSite=Strict` más cabecera `X-LucidFence-CSRF` en peticiones mutantes.
- `Authorization: Bearer <api key>` para automatización; las keys se muestran una sola vez y se guardan hasheadas.
- Token local en `<data>/auth/local-token` (0600) para CLI y MCP en la misma máquina; equivale a rol `admin` de la org por defecto y solo se acepta desde loopback; el MCP lo usa pero solo invoca endpoints de lectura (verificado por test).
- Primer arranque sin usuarios: el dashboard muestra el asistente de configuración (`auth/setup`) que crea el owner. No hay sesión anónima.
- Contraseñas con argon2id; login con límite de intentos por ventana; sesiones con caducidad y rotación al cambiar rol.
- OIDC genérico opcional (issuer, client id/secret, redirect exacta, allowlist de dominios, org de aprovisionamiento).

### 6.3 Roles y capacidades

| Capacidad | owner | admin | operator | viewer | auditor |
|-----------|:-----:|:-----:|:--------:|:------:|:-------:|
| `org:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `org:update` | ✓ | ✓ | | | |
| `org:delete` | ✓ | | | | |
| `user:invite`, `user:remove` | ✓ | ✓ | | | |
| `user:role` | ✓ | | | | |
| `apikey:manage` | ✓ | ✓ | | | |
| `device:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `device:write`, `device:action` | ✓ | ✓ | ✓ (action) | | |
| `fence:read`, `route:read`, `policy:read`, `incident:read`, `report:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `fence:write`, `route:write` | ✓ | ✓ | ✓ | | |
| `fence:delete`, `route:delete`, `policy:write` | ✓ | ✓ | | | |
| `engine:run` | ✓ | ✓ | ✓ | | |
| `engine:config` (enforcement, webhooks, egress, proveedores) | ✓ | ✓ | | | |
| `incident:write`, `alert:write`, `playbook:write` | ✓ | ✓ | ✓ | | |
| `handoff:approve` | ✓ | ✓ | ✓ | | |
| `report:export` | ✓ | ✓ | | | ✓ |
| `audit:read` | ✓ | ✓ | | | ✓ |

### 6.4 Integraciones de salida

- **Webhook firmado.** `POST` JSON con `X-LucidFence-Signature: sha256=<hmac-sha256 hex del cuerpo>`, `X-LucidFence-Event` (`incident.opened`, `incident.closed`, `handoff.pending`, `action.executed`, `alert.fired`), `X-LucidFence-Delivery` (id único) y `X-LucidFence-Timestamp`. La firma cubre solo el cuerpo, como en 1.x, para no romper receptores existentes. Reintentos 3 con backoff exponencial acotado; estado en `deliveries.jsonl` y en `health`.
- **OCSF** Detection Finding (`class_uid` 2004) opcional por webhook; sin coordenadas.
- **ntfy** con `Title`, `Priority` y bearer opcional.
- **Egress allowlist.** Toda URL de salida (webhooks, ntfy, Nominatim, tiles no aplican al servidor) pasa por `notify.Egress`: host en allowlist, resolución DNS y rechazo de IPs privadas o loopback salvo `allow_private`.

### 6.5 SOAR y handoffs

Playbook = condiciones (misma gramática que las políticas) + acciones. Por ciclo y dispositivo, cada playbook que casa produce acciones. `notify`, `message`, `locate` se ejecutan con los guardarraíles. `lock`, `wipe`, `clear_passcode`, `reboot` generan un `Handoff` `pending` (uno por dispositivo, acción y playbook mientras siga pendiente). La aprobación (`handoff:approve`) ejecuta la acción pasando por los guardarraíles; el rechazo lo cierra. Un test de invariante comprueba que ninguna acción destructiva de un playbook llega al adapter sin handoff aprobado.

### 6.6 MCP

Servidor JSON-RPC 2.0 por stdio (`lucidfence mcp`), herramientas de solo lectura: `list_devices`, `get_device`, `list_fences`, `list_incidents`, `risk_summary`, `coverage_report`. Habla con la API local con el token local. No expone ni acepta credenciales.

## 7. Frontend

### 7.1 Lectura de diseño y diales (taste-skill)

- **Dashboard:** producto B2B de operaciones de seguridad para admins de IT/UEM, lenguaje calmado y denso estilo Linear/Vercel, Tailwind v4 + shadcn/ui + Geist, movimiento contenido. `DESIGN_VARIANCE 4 / MOTION_INTENSITY 3 / VISUAL_DENSITY 7`.
- **Landing y vitrina:** landing B2B para compradores técnicos con restricción trust-first. `6 / 4 / 4`. taste-skill aplica completo, incluido su pre-flight.
- **Marca:** acento único verde bosque `#3E7A5E` (paleta "Forest"), neutros cálidos (stone), rojo/ámbar/azul solo para severidad y estado de datos. Geist + Geist Mono autoalojadas con `font-display: swap`. Radio 8 px en todo lo interactivo, píldora solo en badges de estado. Modo claro y oscuro desde los mismos tokens. `prefers-reduced-motion` respetado. Sin emojis en la UI; iconos Phosphor con un solo grosor (1.5).

### 7.2 Stack

React 19, TypeScript estricto, Vite, Tailwind v4 (`@theme` en `styles/tokens.css`), shadcn/ui como componentes propios, `@phosphor-icons/react`, `motion/react` solo para transiciones de estado, MapLibre GL (tiles OSM por defecto, URL configurable y desactivable), Recharts, TanStack Query (sondeo del estado del motor cada 15 s), react-hook-form + zod, react-router, i18n propio ES/EN con claves tipadas. Tipos del cliente generados desde `docs/openapi.yaml` con `openapi-typescript`. Node 24 LTS o superior solo para desarrollo y CI. Allowlist de dependencias npm validada en CI.

### 7.3 Estructura

```
web/src/
├─ app/         rutas, layout (sidebar, topbar, paleta de comandos), guards de permisos
├─ api/         cliente tipado generado + hooks de Query por recurso
├─ features/    una carpeta por vista: componentes, hooks, tests
├─ components/  ui/ (shadcn propio), map/, data-table/, states/ (Loading, Empty, Error)
├─ lib/         i18n, formato, permisos, utilidades
└─ styles/      tokens.css
```

Dos entradas de Vite: `app` (dashboard, salida a `internal/web/dist`, embebida) y `site` (landing, vitrina, manual, salida publicada en GitHub Pages). Límite de 300 líneas por componente validado en CI.

### 7.4 Vistas

Setup inicial (crear owner → demo o conectar UEM → probar conexión → resumen, enforcement en observe) · Login · Visión general · Mapa en vivo · Dispositivos (tabla densa con filtros; detalle con inventario, riesgo explicado, eventos, acciones, trail) · Geocercas · Rutas · POIs · Políticas y riesgo (editor, plantillas, what-if) · Incidentes · Alertas · Playbooks y handoffs (bandeja de aprobaciones) · Registro de acciones · Eventos · Conectores (asistente por proveedor, probar conexión, mínimo privilegio, vista federada) · Informes (puntos ciegos, segunda opinión, ejecutivo, evidencia, exportar) · Ajustes (enforcement, webhooks, egress, org, mapa) · Miembros y API keys.

Toda vista implementa cuatro estados: cargando (esqueleto con la forma final), vacío (con acción para poblar), error contextual y contenido. Formularios con etiqueta encima, ayuda y error debajo, contraste WCAG AA verificado. La UI oculta lo que el rol no puede hacer y la API lo rechaza igualmente.

### 7.5 Sitio público

`site` contiene la landing, la vitrina (lee `cloud_state.json` desde la rama `cloud-state` vía raw.githubusercontent, esquema con claves obligatorias `service`, `generated_at`, `mode`, `totals`, `tenants`, `devices`, `fences` más `cve_summary` y `soar`) y el manual ES/EN. Se publica con `publish-site.yml` bajo el subpath `/lucidfence/` con enlaces relativos.

## 8. Distribución

- **Release con GoReleaser:** binarios estáticos para darwin/arm64, darwin/amd64, linux/arm64, linux/amd64, windows/amd64; checksums; SBOM (CycloneDX); attestación de procedencia con GitHub Attestations; imagen Docker distroless multi-arch en GHCR; actualización automática de la fórmula binaria en `adrimg3196/homebrew-lucidfence`.
- `deploy/install.sh`: descarga el binario de la release, verifica checksum, instala en `~/.local/bin` o `/usr/local/bin`, opcionalmente registra el servicio (launchd/systemd).
- `deploy/docker-compose.yml` con perfil `internet-facing` (Caddy TLS). `deploy/systemd/lucidfence.service`, `deploy/launchd/com.lucidfence.plist`.
- Desaparecen PyPI y Fly.io.

## 9. Gate de CI y raíles de agentes

### 9.1 `ci.yml` (obligatorio en PR y main; todo bloqueante)

1. **Formato y estática Go:** `gofmt -l`, `go vet`, `staticcheck`, `golangci-lint` con `depguard` (§5.2), `gocyclo` (máx. 15), `funlen` (máx. 60 líneas).
2. **Límites físicos** (`scripts/limits.sh`): ningún `.go` > 400 líneas, ningún componente `.tsx` > 300, ninguna función > 60. Sin excepciones sin issue enlazada en un comentario `// limits:allow #N`.
3. **Dependencias:** tests que comparan `go.mod` y `package.json` con las allowlists.
4. **Tests:** `go test -race -cover ./...` con suelos por paquete (`domain` y `engine` 85 %, resto 70 %); Vitest; test de paridad rutas ↔ OpenAPI ↔ capacidades.
5. **Batería runtime** (`scripts/battery.sh`): compila, arranca el binario en demo, ejecuta `internal/battery` (health, ciclo, riesgo explicable con razones, observe bloquea wipe, webhook firmado verificado por un receptor de prueba, OCSF sin coordenadas, MCP por stdio, migrate con fixtures) y lo para. Salida `RUNTIME: N/N`.
6. **Frontend:** `tsc --noEmit`, ESLint, build de `app` y `site`.
7. **E2E:** Playwright contra el binario recién compilado (flujo de §12).
8. **Seguridad:** gitleaks, govulncheck, `npm audit --audit-level=high`.

### 9.2 CODEOWNERS

`ARCHITECTURE.md`, `.github/`, `go.mod`, `web/package.json`, `scripts/limits.sh`, los ficheros de allowlist e `internal/engine/guardrails*.go` requieren aprobación del propietario aunque CI esté verde.

### 9.3 Raíles de agentes

- `agent-pr.yml`: push a `agent/**` abre PR con plantilla (qué, por qué, cómo se verificó) y etiqueta `agent`.
- `agent-automerge.yml`: mergea con squash si CI verde, ≤ 400 líneas cambiadas, ningún fichero CODEOWNERS tocado y sin etiqueta `needs-human`. En cualquier otro caso deja comentario y espera.
- No hay merge-train, loops, recon, GTM, seeds, monitor, deadman, cron-watchdog, daily-analysis ni health-monitor. `release.yml`, `publish-site.yml` y `publish-demo.yml` (snapshot demo cada hora con el binario a la rama `cloud-state`) completan la lista de seis workflows.

## 10. Día 0: el corte de `main`

1. Tag `v1.6.1-python-final` y rama `legacy/python` desde el `main` actual; push de ambos.
2. Cerrar las 14 PRs abiertas con un comentario estándar que enlaza a `legacy/python` y a esta spec. Etiquetar las 57 issues `v1-triage`; fijar una issue que anuncie 2.0 y el plan de re-triaje.
3. Protección de rama: retirar el check `gtm-claim-lint`; exigir los jobs de `ci.yml`; activar CODEOWNERS; mantener la regla de no borrado.
4. Primer push a `main`: un commit que elimina el árbol Python y deja el esqueleto Go compilable con CI verde, `README.md` de transición, `CHANGELOG.md` con `2.0.0-dev`, `ARCHITECTURE.md` y esta spec. Los schedules 1.x mueren con sus ficheros.
5. Trabajo en el clon `~/lucidfence-v2` con identidad git del propietario. Nunca en `~/geofence-uem` (checkout compartido que se resetea) ni en `~/lucidfence` (checkout de Hermes).
6. Automatización local: `launchctl unload ~/Library/LaunchAgents/com.openmausbot.lf-daily.plist`; archivar el tablero `lucidfence` de Hermes kanban. Los crons de Zero/Jules en OpenClaw que apuntan al repo se listan en el cierre para que el propietario los reconfigure.
7. Homebrew, Docker `latest` y Pages siguen sirviendo 1.6.1 hasta la release 2.0.0 porque dependen de releases y no de `main`.

## 11. Manejo de errores

- **Conectores:** error como valor en `ActionResult`/`ConnectionResult`; salud del proveedor registrada; el ciclo sigue.
- **Motor:** `recover()` por dispositivo; el dispositivo queda con `EvaluationError` y `Risk.Score = nil`; el ciclo continúa y el fallo se cuenta en las estadísticas.
- **Store:** fallo de escritura → estado en memoria intacto, `health.persistence = degraded`, `doctor` lo explica.
- **API:** errores tipados con `code`; 4xx sin internos; 5xx con id de petición en log.
- **Notificaciones:** reintentos acotados; no entregados persistidos y visibles.
- **Arranque:** validación de `config.json` con campo y motivo; puertos ocupados y permisos de directorio con mensaje llano.

## 12. Pruebas

- **Unitarias Go:** geometría con casos dorados (incluidos polígonos cóncavos y el antimeridiano); transiciones y dwell; matching de políticas y puntuación con ficheros dorados; tabla completa de guardarraíles; store (atomicidad, concurrencia, permisos); matriz RBAC completa contra §6.3; vectores HMAC extraídos de los tests Python 1.x; OCSF sin coordenadas.
- **Conectores:** `httptest` con respuestas grabadas por fabricante (tomadas de los tests 1.x y de la documentación pública), refresco de token, mapeo de errores, fuzz de `Execute`. Tests en vivo con `LUCIDFENCE_LIVE_<PROVEEDOR>=1` y credenciales por entorno, saltados por defecto.
- **Contrato:** rutas ↔ OpenAPI ↔ capacidades; `schema_version` y claves obligatorias de cada fichero de datos; claves del snapshot de la vitrina; fixtures 1.x para `migrate`.
- **Batería runtime:** `internal/battery` (§9.1 paso 5).
- **Frontend:** Vitest + Testing Library por vista con los cuatro estados; Playwright contra el binario: setup → demo → mapa renderiza → detalle de dispositivo → what-if de política → aprobar un handoff → exportar evidencia.

## 13. Criterios de "hecho" para 2.0.0

1. Un binario; en una máquina limpia `lucidfence serve` deja el dashboard usable en demo en menos de un minuto.
2. Toda la lista de §4.1 implementada, cada punto con test y, si es en vivo, con claim en la batería.
3. Gate de CI verde con suelos de cobertura y límites de tamaño.
4. Playwright verde contra el binario.
5. `migrate` verificado con fixtures 1.x.
6. Docs: README (ES/EN), ARCHITECTURE, ADRs reescritos, manual ES/EN, GETTING_STARTED, SECURITY, CONTRIBUTING con guía de conectores.
7. Release: tag → binarios, Docker, tap actualizado, sitio publicado, snapshot demo fluyendo.
8. Landing y vitrina pasan el pre-flight de taste-skill.

## 14. Fases

Cada hito termina con batería y Playwright verdes y una pre-release `2.0.0-alpha.N` instalable.

| Hito | Contenido |
|------|-----------|
| **M0 Día 0** | §10 completo: corte de main, esqueleto compilable, `ci.yml` con todos los pasos (aunque cubran poco), raíles, CODEOWNERS, automatización local pausada. |
| **M1 Núcleo demo** | `domain`, `store`, `engine` con simulación, CLI (`serve`, `doctor`, `version`, `open`), `auth` mínima (setup, login, sesión, token local), API de devices/fences/routes/pois/engine, dashboard con setup, visión general, mapa, dispositivos y geocercas. |
| **M2 Riesgo y acciones** | Políticas, señales, what-if, guardarraíles, acciones, eventos, incidentes, alertas, webhooks/OCSF/ntfy, egress, SOAR y handoffs; vistas correspondientes. |
| **M3 Conectores** | Applivery, Intune, Jamf, Fleet, Workspace ONE; multi-UEM y reconciliación; mínimo privilegio; osquery; CVE; vista de conectores; `migrate`; `apply` y `validate`. |
| **M4 Informes y auth completa** | Informes y exportaciones, evidencia, orgs, roles completos, API keys y auditoría, OIDC, MCP, vistas de informes, miembros y ajustes; `start/stop/status/restart`. |
| **M5 Público y release** | Landing, vitrina y manual con taste-skill, `publish-site` y `publish-demo`, GoReleaser, tap, install.sh, docs finales, 2.0.0. |

## 15. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Perder comportamiento sutil de 1.x al reescribir (dedupe, cooldown, reglas de riesgo). | Los tests Python de `legacy/python` se usan como especificación: cada regla se porta con un caso dorado equivalente antes de implementar. |
| Sin credenciales reales de Intune/Jamf/Fleet/WS1 durante el desarrollo. | Respuestas grabadas en `httptest`; tests en vivo opt-in; el propietario puede validar Applivery con credencial propia. |
| Tamaño del proyecto (unas 20-25 k líneas de Go y 15 k de TypeScript). | Hitos con pre-releases probables; plan por hito; límites de fichero que fuerzan modularidad desde el primer commit. |
| La flota vuelve a generar sprawl. | CODEOWNERS, límite de 400 líneas por PR de agente, allowlists de dependencias, depguard, fronteras en `ARCHITECTURE.md` con test. |
| taste-skill está pensado para landings, no para dashboards. | Se aplica completo al sitio público; en el dashboard solo sus reglas transversales (acento único, tipografía, formas, estados, contraste). |
| Usuarios 1.x que actualizan por Homebrew. | `migrate` documentado en el CHANGELOG y en `doctor`; 1.6.1 sigue disponible como release y en `legacy/python`. |
| El corte de `main` deja un periodo sin producto usable en `main`. | Releases y Pages no dependen de `main`; el README de transición lo explica; `legacy/python` queda enlazado. |
