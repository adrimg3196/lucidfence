# SPEC.md — LucidFence (replanteado con agent-skills)

> Spec-driven development. Este documento es la fuente de verdad del proyecto.
> Vive en version control mientras el trabajo está en curso.

## 1. Objective

LucidFence es geofencing UEM/MDM **100% local y soberano**: monitoriza flotas de
dispositivos, evalúa conformidad por geocerca, calcula riesgo por dispositivo,
escanea CVE en apps de la flota y ejecuta playbooks SOAR de remediación — con IA
local (MoA), email soberano (Atomic Mail) y dominio propio (FreeDomain). $0, sin
telemetría, sin proveedor de pago.

**Modelo de negocio (decisión del 2026-07-14):** el producto comercial es una
*app local que se instalan los clientes* en su propia infra (soberano, $0 para
el proveedor). La vitrina SaaS serverless en GitHub Pages es la captación
comercial siempre-on ($0, fuera de nuestra máquina).

## 2. Commands (cómo trabajar en este repo)

| Comando | Qué hace |
|---|---|
| `python3 tests/run_tests.py` | Corre TODOS los `test_*.py` (runner honesto, tally real). 105 pass = verde. |
| `python3 cloud_publisher.py --cycles 2` | Genera `data/cloud_state.json` (vitrina cloud). |
| `python3 saas_server.py` | Levanta el SaaS local en `:8765` (dashboard + API + engine). |
| `./install.sh` | Instala LucidFence en la máquina del cliente (Docker o Python). |
| `docker compose up -d` | Levanta el stack siempre-on del cliente. |
| `gh workflow run engine-cron.yml` | Fuerza un ciclo del backend serverless en la nube. |

## 3. Project Structure

```
geofence-uem/
├── saas_server.py            # SaaS + API HTTP + engine loop
├── core/                     # engine, policies, state_store, adapters, cve_feed, location_source
├── static/                   # dashboard.html (SPA local), cloud.html (vitrina), app.js, vendor/
├── data/
│   ├── cloud_state.json      # estado publicado para la vitrina (lo sirve Pages vía raw)
│   └── cloud_tenants/        # tenants de la nube creados vía saas-api (multi-tenant real)
├── tests/                    # test_*.py descubiertos por run_tests.py
├── scripts/saas_api_op.py    # operaciones serverless (create_tenant/add_fence/remove_tenant)
├── cloud_publisher.py        # backend serverless: engine → cloud_state.json
├── docker-compose.yml        # stack always-on para clientes
├── install.sh                # installer de un comando para clientes
├── .github/workflows/        # engine-cron, deploy-pages, saas-api, deploy-fly, ci
├── .claude/ .gemini/ .agents/ # comandos y agents del marco agent-skills
├── references/               # definition-of-done, testing-patterns, security-checklist
├── agents/                   # code-reviewer, security-auditor, test-engineer
├── SPEC.md  tasks/plan.md    # spec-driven + planning
└── CLAUDE.md  AGENTS.md      # reglas de proyecto (context-engineering)
```

## 4. Code Style

- Python 3.11, stdlib-first. Sin frameworks web (HTTP propio en `saas_server.py`).
- Nombres en español para dominio (geocerca, conformidad, dispositivo); inglés para API.
- Funciones pequeñas, una responsabilidad. Sin comentarios que expliquen el *qué*.
- Commits atómicos (~100 líneas), mensaje tipo `feat(scope): ...`.
- Sin secretos en el repo; `.env.example` solo placeholders.

## 5. Testing Strategy

- `tests/run_tests.py`: descubre todos los `test_*.py`, corre cada `test_*`,
  captura `SystemExit` (tests que corren su propia suite al importar) y reporta
  tally honesto. NO oculta fallos.
- Cada feature nueva: test que falla sin el cambio y pasa con él.
- Tests de integración arrancan el server en `:8765` de forma hermética.
- Cobertura donde hay cambio planeado; no global forzado en legacy.
- E2E de la vitrina: verificar en navegador que cloud.html renderiza KPIs/mapa/flota.

## 6. Boundaries (qué siempre hacer / preguntar / nunca hacer)

**Siempre:**
- Verificar en runtime (correr el server / abrir la vitrina), no solo "compila".
- Mantener el runner de tests honesto (tally real, exit code correcto).
- Coste $0: solo free tiers; nada que facture.
- Soberanía: los datos de tenant viven en la máquina del cliente, no en la nuestra.

**Preguntar primero:**
- Cualquier dependencia de pago o cuenta con secreto del proveedor.
- Exponer un backend always-on que requiera token nuestro (Fly/HF) — delegar al cliente.

**Nunca:**
- Hardcodear secretos / tokens en el repo.
- Exponer un token en el cliente de Pages (inaceptable para producto comercial).
- Usar `flyctl auth login` headless (falla silenciosamente) — lo hace el cliente.
- Dejar procesos zombi colgando entre sesiones.
