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
| **Publicación de release tags / versiones** | Tags existen, Releases en GitHub faltan | Existen tags git (`v1.0.0` → `v1.4.0`) pero no hay GitHub Releases con description y assets. Ver CHANGELOG.md y `git tag --list`. |
| **Docker / compose para terceros documentado** | Completo — docker-compose.yml + Dockerfile existen | `docker compose up -d` corre LucidFence always-on en localhost:8765. Perfil `internet-facing` levanta Caddy para TLS. Ver `docker-compose.yml`. |
| **Documentación de adapters UEM para contribuidores** | Parcial | Cada adapter (Applivery/Intune/Jamf) tiene código, pero no hay guide de "cómo agrego un adaptador UEM nuevo" público con el contrato de plugin. |
| **Vitrina pública viva / demo** | Completo — vitrina + demo walkthrough | `cloud.html` lee raw.githubusercontent, funcional. Demo paso a paso sin código en `docs/demo-walkthrough.md`. |
| **Pricing / modelo de negocio declarado** | No existe | Si esto es open-source product, debe declarar qué es OSS puro y qué sería enterprise (si acaso). |
| **Canales de soporte / issues triage** | No existe | No hay CONTRIBUTING, no hay etiquetas de issues, no hay respondedor que triague. |
| **Seguridad: disclosure policy** | No existe | No hay SECURITY.md, no hay disclosure path claro para alguien que encuentra bug de seguridad. |

Si quieres que esto sea **producto open-source que alguien usa sin que tú estés en medio**, la lista es esa. Primero: README externo + tests como gate de calidad públicos + release tags.

## Lo que sí funciona hoy

- Engine de compliance + política de riesgo: corre local, reporta dispositivos dentro/no-compliant/violaciones.
- Adapters UEM existentes: Applivery, Intune, Jamf (estado local después de ingest).
- Dashboard local en `:8765`.
- Cloud vitrina: `data/cloud_state.json` publicado, leído por `static/cloud.html`.
- Test runner honesto (105 tests = verde): gates reales, no stubs.
- Cron de estado local: `geofence_daily_report.sh` genera el resumen sin red.
- License: MIT (LICENSE), configurable en pyproject.toml si el mantenedor decide cambiar.

## Credits

Ver `AGENTS.md` para quién trabaja esto (agentes + Adri). Esto es desarrollo multi-agente concurrente + humano propietario, commits en nombres distintos.

## License

Apache-2.0 — ver `LICENSE` para los términos completos. Sin restricciones de uso, modificación, distribución. Corporaciones pueden adoptar esto sin revisión legal de copysleft.

---

*Full-local. Sin credenciales. Sin backend propietario de datos.*
