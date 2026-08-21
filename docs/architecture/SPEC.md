# SPEC.md — LucidFence as-built

> Spec-driven development (estilo [github/spec-kit](https://github.com/github/spec-kit)):
> este documento describe el sistema **tal como está construido** y es la fuente
> de verdad técnica del repo. Está subordinado a la
> [Constitución](CONSTITUTION.md) (suprema): ante conflicto, gana ella. Un
> cambio que deje esta spec desactualizada no está terminado. Las features
> nuevas nacen de una mini-spec
> ([plantilla](../internal/product/spec-template.md)) con claim runtime
> verificable.

## 1. Objetivo

LucidFence es el **complemento neutral del UEM que el admin ya tiene** — nunca
un UEM (Constitución §II): no enrola dispositivos, no empuja perfiles, no
gestiona apps ni parches. Lee la flota del UEM existente (Applivery, Intune,
Jamf, Fleet, Workspace ONE, ChromeOS…), la correlaciona con señales propias
(geocercas, red, osquery, CVE), **explica** el riesgo y actúa solo a través
del UEM cuando el admin decide.

Producto 100% free open-source (Apache-2.0), local-first y soberano: el dato
del tenant vive en su máquina, cero telemetría, la ubicación no sale del
equipo. Runtime Python stdlib, sin frameworks. La IA es opcional y BYO
(endpoint OpenAI-compatible del propio tenant), nunca un requisito.

Frontera de autonomía (Constitución §VI, inviolable): el desarrollo es
autónomo; el enforcement sobre dispositivos reales lo decide siempre el admin
— `dry_run` por defecto, `enforce` opt-in por tenant, `wipe` con doble llave.

## 2. Comandos de trabajo (verificados en vivo)

| Comando | Qué hace |
|---|---|
| `python3 scripts/verify.py` | La definición de "hecho": versión coherente + enlaces de docs + batería runtime N/N + suite honesta → `VERIFY: APTO (4/4)`. Variantes `--fast`, `--docs-only`, `--quiet`. |
| `python3 tests/run_tests.py` | Corre todos los `test_*.py` con tally honesto (el verde es el tally real que imprime el runner, no un número fijado aquí; única baseline tolerada: `test_oidc_sso.py` en contenedores con `cryptography` roto — verde en CI). |
| `python3 scripts/runtime_validation.py` | Batería runtime: arranca saas_server real, webhook real y MCP por stdio, ejercita cada claim anunciado → `RUNTIME: N/N claims`. |
| `python3 saas_server.py` | Servidor local en `:8765` (dashboard + API + engine loop). `GET /api/health` responde `{"status": "ok"}`. |
| `python3 -m lucidfence.cli <cmd>` | CLI: `serve/start/stop/restart/status/open`, `doctor` (preflight), `quickstart` (onboarding autoverificado), `apply` (config-as-code: valida, diff, what-if), `validate-config`, `adapter new`, `mcp` (stdio read-only), `shell`. |
| `python3 -m lucidfence.core.cloud_publisher --cycles N` | Genera el snapshot demo `data/cloud_state.json` para la vitrina de Pages (engine en simulación; jamás datos reales de tenant). |
| `./install.sh` / `docker compose up -d` | Instalación en la máquina del cliente (Python o Docker). |

## 3. Mapa de módulos as-built (`lucidfence/core/`)

**Motor y señales**

- `engine.py` — ciclo del geofencing: flota → evaluación → riesgo → acciones.
- `policies.py` — Risk & Policy Engine geoespacial (el moat).
- `fences.py` / `geo.py` — modelo de geocercas y geometría (distancia, polígonos).
- `state_store.py` — persistencia: estados de dispositivo, transiciones, log de acciones.
- `incidents.py` — ciclo de vida persistente de incidentes.
- `cve.py` / `cve_feed_nvd.py` — base CVE local (offline) + sync opcional desde NVD.
- `soar.py` — playbooks SOAR de remediación (siempre vía UEM, dry_run primero).
- `alerts.py` / `notifier.py` — alertas por umbral y salidas Slack/Teams/webhook firmado/ntfy/email.
- `predictive.py` / `poi.py` / `routes.py` — forecasting local explicable, POIs, adherencia a ruta.
- `coverage.py` — informe de puntos ciegos: qué NO cubre la config actual (`docs/operations/coverage.md`).
- `compliance_controls.py` — mapeo CIS/ISO basado en evidencia, no certificación.
- `policy_replay.py` — simulador what-if de políticas ("terraform plan" del geofencing).
- `evidence_export.py` / `export.py` — evidencia con cadena de hashes verificable offline; export/audit masivo.
- `workflows.py` / `actions.py` — plantillas de workflows y façade de acciones UEM.

**Ubicación**

- `location_source.py` — fuente live Applivery (REST).
- `generic_http_source.py` — bring-your-own UEM: cualquier API JSON por mapeo declarativo.
- `network_location.py` — geofencing lógico por señal de red (portátiles sin GPS).
- `location_integrity.py` — heurísticas anti-spoofing 100% locales.
- `osquery_posture.py` — evidencia de postura por osquery (readback honesto: señal ausente jamás penaliza).
- `geocode.py` — geocoding Nominatim/OSM sin API key.
- `multiuem.py` — modelos normalizados compartidos por los providers multi-UEM.

**Adapters** (`core/adapters/`)

- `base.py` — interfaz `MDMAdapter` **congelada** (ver §4).
- Implementaciones: `applivery`, `intune`, `jamf`, `fleet`, `workspace_one`, `chromeos`, `windows_conformidad`, `ios_geofence`, `simulation` (+ `_template_adapter`). Todas conservan camino mock offline.
- `adapter_marketplace.py` / `adapter_scaffold.py` — verificación sha256 del marketplace local y scaffolding `lucidfence adapter new`.

**Seguridad y configuración**

- `oidc.py` — OIDC Authorization Code + PKCE endurecido (SSO de equipo).
- `api_keys.py` / `secrets.py` — API keys por tenant con audit log tamper-evident; credenciales UEM locales 0600.
- `config_loader.py` / `config_validator.py` — carga de `config.json` + `.env`; validación del mapeo contra la API real.
- `config_apply.py` — lógica de `lucidfence apply`: políticas y geocercas como código (valida, diff, what-if, aplica).
- `doctor.py` / `app_paths.py` / `cluster.py` — preflight operacional, rutas portables, HA activo/pasivo por lease.

**SaaS y producto** (servidos por `saas_server.py`, HTTP stdlib propio)

- `product.py` — capa de inteligencia de producto del dashboard.
- `ai_provider.py` — IA BYO por tenant (endpoint OpenAI-compatible, key en `.env` 0600); `ai.py` es el bridge legacy loopback (solo `/api/ai/support`).
- `ddm.py` / `dsc.py` — enforcement declarativo: Apple DDM y Windows PowerShell DSC (siempre entregado por el UEM del admin).
- `atomicmail_client.py` / `freedomain.py` / `storage.py` — email soberano, dominio propio, blob storage free.

**Publicación y loop**

- `cloud_publisher.py` — backend serverless (Actions `engine-cron`): engine en simulación → `data/cloud_state.json` para la vitrina.
- `roadmap_tooling.py` / `autonomous_company.py` / `loop_governance.py` / `provider_plugins.py` — motor del roadmap, control plane autónomo por tenant y salvaguardas de los loops.

## 4. Contratos

- **`core/adapters/base.py` (congelado):** `MDMAdapter` expone `name` y
  `execute(device, action, params, dry_run) -> dict`; jamás lanza excepción
  (`{"ok": False, "error": ...}`). Cambiarlo exige bump de versión MAYOR +
  mock offline (denylist si no). API actual: `MDMAdapter/v1`.
- **`data/cloud_state.json` (publisher):** snapshot plano con claves
  `service, generated_at, mode, totals, tenants, devices, fences,
  cve_summary, soar`. Demo-only por constitución: jamás datos reales.
- **`docs/architecture/openapi.json`:** esquema OpenAPI 3.1 de la API local,
  servido en vivo por `GET /api/openapi.json`. Se mantiene con cada cambio de
  rutas.
- **Marketplace de adapters:** `lucidfence/plugins/adapters/index.json`
  (schema `lucidfence-adapter-index/v1`) verifica cada adapter por `sha256`;
  una edición legítima regenera el índice en la misma PR
  (`scripts/build_adapter_index.py`).
- **Lint write-time:** `.ruff.toml` selecciona solo clases de error reales
  (`F`, `E9`); el hook PostToolUse `.claude/hooks/quality_gate.sh` devuelve
  los hallazgos al agente en el momento de escribir. El estilo compacto de la
  casa es deliberado y no se lintea.

## 5. Gates de calidad y entrega

1. **Local:** `python3 scripts/verify.py` → `VERIFY: APTO (4/4)`. Un claim
   que no arranca en vivo (batería runtime) bloquea el merge aunque la suite
   esté verde (Constitución §IV).
2. **CI** (`.github/workflows/ci.yml`): suite completa + `verify.py
   --docs-only` + tests del worker + pip-audit + SBOM.
3. **Raíl de entrega:** push a `claude/**` → `agent-pr.yml` abre la PR →
   `agent-automerge.yml` mergea en verde. Sin gate humano en el desarrollo;
   PRs de forks/terceros jamás se auto-mergean.
4. **Denylist absoluta** (ni con gate verde): ver Constitución §Restricciones.
