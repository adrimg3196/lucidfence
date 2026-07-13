# LucidFence · Command Center

> **Geofencing que no exfiltrra. Riesgo que se explica.**

[![Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Multi-MDM](https://img.shields.io/badge/MDM-Applivery%20%7C%20Intune%20%7C%20Jamf-9cf)](core/adapters/ADAPTER.md)
[![Local-first](https://img.shields.io/badge/architecture-100%25%20local-blue)](saas_server.py)

Local-first **UEM Risk & Geofence Control Plane** que convierte la geolocalización de tu flota móvil en **riesgo explicable** (score 0-100 **con su razón**) y acciones automáticas — **agnóstico a tu MDM** vía adapters.

- 🛡️ **Soberano**: 100% local, 0 exfiltración de datos de ubicación
- 🧠 **Risk Engine explicable**: cada dispositivo recibe un score 0-100 **con la razón** — nunca un número mágico
- 🔌 **Multi-MDM**: Applivery (live) + Intune/Jamf (mock incluidos) + la comunidad añade el resto
- 📊 **Dashboard**: geovallas, inventario IT, comandos remotos, alertas, CVE/SOAR
- ✅ **Evidence gate**: un hallazgo de riesgo solo cuenta si está respaldado por señales reales (anti-overclaim)

---

## El moat (por qué existe LucidFence)

Los MDM nativos (Intune, Jamf, Applivery, SOTI, Workspace ONE) hacen **geofencing commodity**: te dicen "está dentro/fuera" y mandan la ubicación de tu flota a **su** nube. No correlacionan riesgo, no explican el porqué, y tu soberanía de datos se la quedan ellos.

**LucidFence invierte la premisa:**

| | MDM nativo | LucidFence |
|---|---|---|
| Geofencing | ✅ commodity | ✅ |
| **Riesgo explicable** (0-100 **+ razón**) | ❌ caja negra | ✅ score + `reasons` |
| **Sin exfiltrar ubicación** | ❌ (cloud del vendor) | ✅ 100% local |
| Agnóstico a MDM | ❌ atado al tuyo | ✅ vía adapters |
| SOAR + CVE en vivo + comandos on-demand | parcial | ✅ |

El moat no es el geofencing (eso lo tiene cualquiera). Es el **Risk Engine explicable + soberanía de datos**. Un CISO puede pedir "¿por qué este dispositivo es crítico?" y LucidFence responde con la señal concreta (disco casi lleno, sin cifrar, fuera de geovalla, SO sin parchear) — no un número opaco.

---

## Risk Engine explicable (cómo funciona)

Cada evaluación producida por `core/policies.py` devuelve:

```json
{
  "device_id": "movil-e9",
  "risk_score": 100.0,
  "severity": "critical",
  "reasons": ["ubicación fuera de geovalla", "almacenamiento sin cifrar", "SO sin parchear de seguridad"],
  "provenance": "tool",
  "verified": true
}
```

- `reasons`: la justificación legible por humano de cada punto de riesgo.
- `provenance`: `tool` (respaldado por señales) · `none` · `context`.
- `verified`: `true` **solo si el score tiene razón**. Un score > 0 sin señal se marca `verified:false` (salvaguarda anti-hallucinación — honest by construction).

Esto es el patrón *evidence gate* que usan los harness de red-teaming de élite: **un claim no es válido sin provenancia**.

---

## Quickstart (1 comando)

```bash
git clone https://github.com/adrimg3196/lucidfence.git && cd lucidfence
pip install -r requirements.txt
./start_all.sh
```

Abre **http://127.0.0.1:8765** — el dashboard arranca con una flota demo (5 dispositivos, riesgo, geovallas). MoA (IA) corre en :8085.

> Sin claves de IA: MoA funciona en modo demo. Para IA real, añade una clave en `moa/.env`.

### Modo live (con tu MDM real)

En **Ajustes**, pega tu token de UEM (p.ej. `APPLIVERY_API_KEY`). El producto pasa de simulación a **live** y lee la ubicación real de tu flota.

---

## Adapters MDM (la superficie de contribución)

El producto es agnóstico al MDM. Cada conector implementa la interfaz `MDMAdapter`:

| Adapter | Estado | Modo |
|---------|--------|------|
| `simulation` | ✅ incluido | demo 100% local |
| `applivery` | ✅ live | lee ubicación + delega comandos vía webhook |
| `intune` | 🟡 mock | listo para live vía Enterprise on-prem (Graph) |
| `jamf` | 🟡 mock | listo para live vía Enterprise on-prem (Pro API) |

¿Tu MDM no está? Es un **PR de fin de semana**: copia `core/adapters/applivery.py`, implementa `MDMAdapter` (ver `core/adapters/ADAPTER.md`), añade tests contra mock, abre PR. CI obligatorio + badge **verified**.

➡️ **Adapter Bounty Sprint + Hall of Fame**: los primeros adapters verificados de los MDMs más pedidos entran al Hall of Fame del README y su autor se vuelve *Adapter Maintainer*.

---

## Arquitectura (open-core)

```
lucidfence/
├── core/
│   ├── engine.py          # ciclo de geofencing + Risk Engine (moat)
│   ├── policies.py        # Risk Engine explicable + device posture + evidence gate
│   ├── adapters/          # MDMAdapter: simulation / applivery / intune / jamf
│   │   ├── base.py        # interfaz congelada MDMAdapter
│   │   └── ADAPTER.md     # guía de contribución
│   ├── cve_feed_nvd.py    # sync de CVEs en vivo desde NVD (red local)
│   ├── actions.py         # façade sobre core/adapters
│   ├── export.py          # CSV / HTML audit
│   └── ...
├── saas_server.py         # dashboard multi-tenant local (http.server, sin deps)
├── static/                # SPA del dashboard (vanilla JS)
├── skills/                # Agent Skills installables
├── .claude-plugin/        # manifest de plugin (installable)
├── tests/                 # 115 tests + adapters + evidence gate
└── docs/                  # GTM: marketing-copy, community, launch, pricing
```

**Open-core:**
- 🟢 **Apache-2.0** (gratis): glue multi-MDM, geofencing, dashboard, comandos, alertas, export, adapters, Risk Engine explicable.
- 🔒 **Enterprise on-prem** (cerrado): SOAR gestionado, SSO/SAML, escala, inteligencia de amenazas recurrente. El OSS genera inbound; el servicio gestionado es la captura.

---

## Seguridad

Auditado con lente CISO:
- Tokens de sesión `os.urandom(32)` + TTL server-side; passwords PBKDF2-HMAC-SHA256 salteados (100k rounds).
- RBAC capability-based en ~30 endpoints; escalación cross-tenant cerrada (403).
- Path traversal bloqueado en `/static/`; XSS stored escapado; command injection imposible (action whitelist).
- **0 secretos en el repo.** Los datos de runtime (`data/_users.json`, `data/_sessions.json`, tenants) están en `.gitignore` y se escriben con `chmod 600`.

---

## Contribuir

1. Lee `CONTRIBUTING.md` (open-core, cómo crear adapters, Bounty Sprint).
2. Fork → branch `feature/<adapter-tu-mdm>` → PR con tests contra mock.
3. CI (`.github/workflows/ci.yml`) corre `tests/run_tests.py` + `node --check static/app.js`.

Plantillas en `.github/ISSUE_TEMPLATE/` y `.github/PULL_REQUEST_TEMPLATE.md`.

---

## Licencia

Core: **Apache-2.0** (ver `LICENSE`). Módulo Enterprise on-prem: propietario, disponible vía licencia.

---

## Estado

- ✅ 115 tests core + 25 IT + 19 SaaS PASS
- ✅ Risk Engine explicable + evidence gate (anti-overclaim)
- ✅ 4 adapters (simulation/applivery/intune/jamf)
- ✅ Dashboard verificado (0 errores JS, KPIs vivos)
- 🟡 Live real de Intune/Jamf pendiente de Enterprise on-prem (hoy mock)
