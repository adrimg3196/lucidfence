# LucidFence

**Multi-UEM local-first. BYOI (Bring Your Own Infrastructure).** Tu data en tu máquina, tú firmas los tokens UEM, tú controlas el despliegue. No hay backend propietario que guarde dispositivos ni credenciales.

## Qué es

Engine de geofencing + política de riesgo que habla con los adaptadores UEM que tú ya tienes (Applivery, Intune, Jamf, y más). Genera el estado de compliance, lo expone en un dashboard local, y opcionalmente publica un snapshot público para la vitrina.

Local-first: el estado de los dispositivos vive en tu máquina. La nube es solo publicar un JSON demo si quieres la vitrina → raw.githubusercontent (CORS `*`, sin secretos por diseño).

## Rápido

```bash
# 1 — instalar
./install.sh
# o
docker compose up -d

# 2 — correr local
python3 saas_server.py            # :8765

# 3 — tests (honestos, 105 = verde)
python3 tests/run_tests.py
```

Dashboard: `http://localhost:8765` → `static/dashboard.html` (SPA local que habla con `:8765`).

## Stack

- Python 3.11, stdlib-first. HTTP propio en `saas_server.py` (no web frameworks).
- Cada adaptador UEM es un plugin para `core/` — engine, policies, state_store, adapters, cve_feed_nvd, location_source (simulation).
- Cloudflare Worker opcional para el gateway UEM (`apps/uem-gateway/`).
- App macOS Swift opcional (`apps/macos/` + builder DMG).

## Archivos que importan

```
lucidfence/          # el único paquete Python (todo lo importable)
core/                # engine, policies (risk), state_store, adapters, cve_feed_nvd, location_source
saas/                # tenants, auth local, RBAC
mcp/                 # servidores MCP stdio read-only
plugins/             # índice de adapters verificado por hash + providers de terceros
cli.py / shell.py    # CLI de ciclo de vida y shell interactiva

apps/
  macos/             # app Swift + builder DMG
  uem-gateway/       # Cloudflare Worker opcional

data/
  cloud_state.json           # estado publicado para la vitrina (commiteado, lo sirve Pages)
  cloud_tenants/<id>/data/  # tenants de la nube (multi-tenant real vía saas-api)

static/
  dashboard.html     # SPA local
  cloud.html         # vitrina serverless (lee data/cloud_state.json vía raw.githubusercontent)
  app.js

docs/                # toda la documentación; índice en docs/README.md
tests/               # runner honesto: tests/run_tests.py
```

## No está terminado (el openly honest gaps)

Esta sección es realidad, no marketing. Se actualiza cuando se cierra un gap.

| Área | Estado | Qué falta |
|------|--------|-----------|
| **README público / onboarding de terceros** | Estado inicial — README externo + alineación de licencia | README de usuario externo (npm-style): qué necesita, cómo instala, como chequea que funciona, FAQ mínima, cómo reporta bugs. Este README es interno. |
| **CI real (no solo cron de state)** | Funcional — CI completa ya existe | GitHub Actions ya gatea: python tests, frontend syntax check, dependency audit (pip-audit + CycloneDX SBOM), runtime-artifacts (rechaza cambios a cloud_state.json en PR), secret-scan (gitleaks). Ver `.github/workflows/ci.yml`. |
| **Publicación de release tags / versiones** | Completo — GitHub Releases publicadas | v1.5.0 publicada como GitHub Release con description y asset; `release.yml` construye, instala y arranca el artefacto antes de publicar. Ver CHANGELOG.md y la pestaña Releases. |
| **Docker / compose para terceros documentado** | Completo — docker-compose.yml + Dockerfile existen | `docker compose up -d` corre LucidFence always-on en localhost:8765. Perfil `internet-facing` levanta Caddy para TLS. Ver `docker-compose.yml`. |
| **Documentación de adapters UEM para contribuidores** | Completo — guía pública | `docs/contributing/new-adapter-guide.md`: cómo agregar un adaptador UEM nuevo con el contrato `MDMAdapter` y el camino mock offline. Scaffolding con `lucidfence adapter new`. |
| **Vitrina pública viva / demo** | Completo — vitrina + demo walkthrough | `cloud.html` lee raw.githubusercontent, funcional. Demo paso a paso sin código en `docs/demo-walkthrough.md`. |
| **Pricing / modelo de negocio declarado** | Declarado — 100% free OSS | **No hay pricing.** LucidFence es software libre y open-source bajo Apache-2.0: sin tier de pago, sin edición enterprise, sin funciones de pago, sin telemetría. Todo el producto es gratis para usar, modificar y distribuir. Ver §Modelo abajo. |
| **Canales de soporte / issues triage** | Funcional | `CONTRIBUTING.md` con el flujo; issues de terceros triados por la flota (etiquetado + respuesta), autores externos nunca auto-mergeados. |
| **Seguridad: disclosure policy** | Completo | `SECURITY.md` con el disclosure path; el loop Centinela ataca el propio LucidFence en localhost (método Strix) y registra hallazgos con PoC. |

Onboarding externo (README npm-style, FAQ) es lo que sigue abierto de esta lista.

## Lo que sí funciona hoy

- Engine de compliance + política de riesgo: corre local, reporta dispositivos dentro/no-compliant/violaciones.
- Adapters UEM existentes: Applivery, Intune, Jamf, Fleet (estado local después de ingest).
  Onboarding por UEM con mínimo privilegio en [`docs/integrations/`](docs/integrations/)
  (Intune, Jamf, Applivery, Fleet) y la [matriz de ubicación](docs/integrations/LOCATION_MATRIX.md)
  con lo que cada UEM da de verdad.
- Rollout seguro para pilotos: `enforcement.mode: observe|enforce`, gating por
  acción y doble llave para wipe. Runbook: [`docs/operations/ENFORCEMENT.md`](docs/operations/ENFORCEMENT.md);
  día 2 (servicio, backup, upgrade): [`docs/operations/DAY2.md`](docs/operations/DAY2.md).
- Dashboard local en `:8765`.
- Postura opcional con osquery: SO, almacenamiento, cifrado y batería,
  correlacionados con el riesgo geoespacial. Ver
  [`docs/integrations/OSQUERY.md`](docs/integrations/OSQUERY.md).
- Cloud vitrina: `data/cloud_state.json` publicado, leído por `static/cloud.html`.
- Test runner honesto (`python3 tests/run_tests.py`): gates reales, no stubs; el tally vive en CI, no aquí (los números en prosa caducan).
- Cron de estado local: `geofence_daily_report.sh` genera el resumen sin red.
- License: Apache-2.0 (`LICENSE`), alineada con `pyproject.toml` y la fórmula Homebrew.

## Modelo (free & open-source)

LucidFence es **software libre y open-source, 100% gratis**. No hay modelo de
negocio de pago:

- **Sin pricing, sin tiers.** No existe una edición "pro", "enterprise" ni
  "cloud de pago". Todo el producto —engine, adaptadores UEM, dashboard, SaaS
  local multi-tenant, MCP— está en este repo bajo Apache-2.0.
- **Sin funciones de pago ni upsell.** Nada queda detrás de un muro. Nada exige
  una licencia comercial.
- **Sin telemetría, sin exfiltración.** Los datos del tenant viven en su
  máquina; no hay backend propietario que los recoja.
- **BYOI (Bring Your Own Infrastructure).** Tú corres el despliegue con tus
  propias credenciales UEM y tus tiers gratuitos; el proyecto no cobra ni
  intermedia.

Apache-2.0 permite a cualquiera —persona o empresa— usarlo, modificarlo y
distribuirlo sin coste ni restricción. Si alguien construye un servicio de pago
encima, es cosa suya; el proyecto en sí es y seguirá siendo gratis.

## Credits

Ver `AGENTS.md` para quién trabaja esto (agentes + Adri). Esto es desarrollo multi-agente concurrente + humano propietario, commits en nombres distintos.

## License

Apache-2.0 — ver `LICENSE` para los términos completos. Sin restricciones de uso, modificación, distribución. Corporaciones pueden adoptar esto sin revisión legal de copysleft.

---

*Full-local. Sin credenciales. Sin backend propietario de datos.*
