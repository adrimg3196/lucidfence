# LucidFence · Command Center

> **Geofencing que no exfiltrra. Riesgo que se explica.**

Local-first **UEM Risk & Geofence Control Plane** que convierte la geolocalización de tu flota móvil en **riesgo explicable** (score 0-100) y acciones automáticas — **agnóstico a tu MDM** vía adapters.

- 🛡️ **Soberano**: 100% local, 0 exfiltración de datos de ubicación
- 🧠 **Risk Engine explicable**: cada dispositivo recibe un score 0-100 con la razón
- 🔌 **Multi-MDM**: Applivery (live) + Intune/Jamf (mock incluidos) + la comunidad añade el resto
- 📊 **Dashboard**: geovallas, inventario IT, comandos remotos, alertas, CVE/SOAR

---

## Por qué no tu MDM nativo

Tu MDM hace geofencing básico. Pero no correlaciona riesgo, no explica el porqué, y manda la ubicación de tu flota a la nube. LucidFence lo hace **local y explicable**.

| | MDM nativo (Intune/Jamf) | LucidFence |
|---|---|---|
| Geofencing | ✅ commodity | ✅ |
| Riesgo explicable (0-100 + razón) | ❌ | ✅ |
| Sin exfiltrar ubicación | ❌ (cloud) | ✅ (local) |
| Agnóstico a MDM | ❌ | ✅ (adapters) |
| SOAR + CVE + comandos on-demand | parcial | ✅ |

---

## Quickstart (1 comando)

```bash
git clone <tu-repo> lucidfence && cd lucidfence
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
│   ├── engine.py          # ciclo de geofencing + Risk Engine (moat, Enterprise)
│   ├── adapters/          # MDMAdapter: simulation / applivery / intune / jamf
│   │   ├── base.py        # interfaz congelada MDMAdapter
│   │   └── ADAPTER.md     # guía de contribución
│   ├── actions.py         # façade sobre core/adapters
│   ├── alerts.py          # alertas por umbral
│   ├── export.py          # CSV / HTML audit
│   └── ...
├── saas_server.py         # dashboard multi-tenant local (Flask-like, http.server)
├── static/                # SPA del dashboard (vanilla JS)
├── skills/                # Agent Skills installables
├── .claude-plugin/        # manifest de plugin (installable)
├── tests/                 # 115 tests + adapters
└── docs/                  # GTM: marketing-copy, community, launch, pricing
```

**Open-core:**
- 🟢 **Apache-2.0** (gratis): glue multi-MDM, geofencing, dashboard, comandos, alertas, export, adapters.
- 🔒 **Enterprise on-prem** (cerrado): Risk Engine scoring premium, SOAR gestionado, SSO/SAML, escala. El OSS genera inbound; el servicio gestionado + inteligencia de amenazas recurrente es la captura.

---

## Contribuir

1. Lee `CONTRIBUTING.md` (open-core, cómo crear adapters, Bounty Sprint).
2. Fork → branch `feature/<adapter-tu-mdm>` → PR con tests contra mock.
3. CI (`.github/workflows/ci.yml`) corre `tests/run_tests.py` + `node --check static/app.js`.

Plantillas en `.github/ISSUE_TEMPLATE/` y `.github/PULL_REQUEST_TEMPLATE.md`.

---

## Licencia

Core: **Apache-2.0** (ver `LICENSE`). Módulo Enterprise on-prem: propietario, disponible vía licencia de la consultora.

---

## Estado

- ✅ 115 tests core + 25 IT + 19 SaaS PASS
- ✅ 4 adapters (simulation/applivery/intune/jamf)
- ✅ Dashboard verificado (0 errores JS, KPIs vivos)
- 🟡 Live real de Intune/Jamf pendiente de Enterprise on-prem (hoy mock)
