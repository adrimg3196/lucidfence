# LucidFence — SaaS 100% local

Plataforma **multi-tenant** de geofencing + UEM (Unified Endpoint Management) que
corre íntegramente en tu máquina. Sin nube, sin bases de datos externas, sin
keys de terceros obligatorias. Inspirada en **Fleet** (UEM multi-tenant + RBAC)
y **Radar** (geofencing-as-a-service), pero 100% local y listo para demo comercial.

> Estado: backend + API + dashboard SPA completos y verificados (QA end-to-end 19/19 PASS).
> Modo por defecto: **simulación** (`dry_run=True`) con una flota simulada de
> dispositivos y 3 geovallas. Para datos reales de Applivery, pega tu token en
> Ajustes (live mode).

---

## Arranque rápido

```bash
cd /Users/adri/lucidfence
python3 saas_server.py
# Abre http://127.0.0.1:8765
```

1. **Crear cuenta** → el primer usuario se convierte en *owner* de su organización.
2. La flota simulada arranca sola (autostart). Pulsa **Forzar ciclo** para evaluar ya.
3. Explora Resumen, Mapa, Dispositivos, Risk Center, Políticas, Conformidad,
   Facturación, Usuarios, Ajustes.

---

## Arquitectura

```
saas_server.py      Servidor HTTP unificado (ThreadingHTTPServer, HTTP/1.0).
                    Monta el core existente por organización (tenant isolation).
saas/
  auth.py           Registro/login, hashing de contraseñas (PBKDF2-SHA256
                    25k vueltas, puro-python, sin dependencias nativas),
                    sesiones por cookie HttpOnly, RBAC (owner/admin/operator/viewer).
  tenant.py         Aislamiento por inquilino: data/tenants/<org_id>/, planes.
saas/plans.py       Planes mock Free / Pro / Enterprise con límites
                    (dispositivos, geovallas, retención, features). Sin pasarela real.
core/               Motor de geofencing reutilizado (engine, fences, geo,
                    state_store, actions, compliance, risk…) — sin reescribir.
static/
  saas.html         Shell SPA (login + command center), tema claro/oscuro.
  saas.js           Auth, router de vistas, helpers de API, render base.
  saas_views.js     Vistas: overview, devices, map (Leaflet), risk.
  saas_views2.js    Vistas: policies, compliance, billing, users, settings.
data/               Todo el estado. _users.json / _orgs.json / _sessions.json
                    (global) + tenants/<org_id>/ (por inquilino).
```

### Aislamiento multi-tenant
Cada organización tiene su propio subdirectorio `data/tenants/<org_id>/` con su
`device_states.json`, `events.jsonl`, `actions_log.jsonl`, `config.json`, etc.
El motor (`Engine`) se instancia **una vez por org** y se cachea en memoria.
Un usuario solo accede a las orgs donde tiene un rol.

### RBAC (capability-scoped)
| Rol        | capabilities                                                  |
|------------|---------------------------------------------------------------|
| owner      | todo + billing + gestión de usuarios                          |
| admin      | igual que owner excepto facturación                           |
| operator   | leer flota, forzar ciclo, ver riesgo/conformidad              |
| viewer     | solo lectura                                                 |

El backend evalúa `AuthStore.can(role, capability)` en cada endpoint protegido.
El QA verifica que un *viewer* NO puede hacer upgrade de plan (403).

---

## API REST (resumen)

Todos los endpoints `/api/*` (excepto `/api/auth/*`) requieren cookie de sesión.

| Método | Ruta                  | Descripción                              |
|--------|-----------------------|------------------------------------------|
| POST   | /api/auth/signup     | Crear cuenta + org                       |
| POST   | /api/auth/login      | Login → cookie de sesión                 |
| POST   | /api/auth/logout     | Cerrar sesión                            |
| GET    | /api/org             | Org actual + plan + rol                  |
| GET    | /api/orgs            | Orgs del usuario                         |
| POST   | /api/orgs/<id>/switch| Cambiar de organización activa           |
| GET    | /api/status          | Estado del motor + conteos de dispositivos|
| POST   | /api/run-once        | Forzar un ciclo de evaluación            |
| GET    | /api/devices         | Estados de dispositivos (?state=inside)  |
| GET    | /api/devices/<id>    | Detalle + trail + eventos + conformidad  |
| GET    | /api/risk            | Risk Center (scoring de dispositivos)    |
| GET    | /api/policies        | Políticas de geovalla + resumen producto |
| POST   | /api/policies        | Crear/editar política                     |
| GET    | /api/compliance      | % conformidad + serie temporal            |
| GET    | /api/analytics       | KPIs de negocio (geofencing de producto) |
| GET    | /api/report          | Informe ejecutivo markdown                |
| POST   | /api/plan/upgrade    | Cambiar plan (mock)                       |
| GET    | /api/users           | Listar usuarios de la org                |
| POST   | /api/users           | Invitar usuario (owner/admin)            |
| POST   | /api/users/<id>/role | Cambiar rol                               |
| DELETE | /api/users/<id>      | Revocar acceso                           |
| GET/POST| /api/settings        | Token Applivery + modo live/sim/dry_run   |

QA automático: `python3 qa_saas.py` (usa http.client directo, sin proxy).

---

## Calidad / QA

- `python3 qa_saas.py` → 19/19 PASS (auth, cookies, multi-tenant, RBAC, geofence
  engine, risk, policies, compliance, analytics, report, plan upgrade, invite,
  protección de ruta sin auth, HTML servido).
- JS validado con `node --check` (sin errores de sintaxis).
- Modo simulación por defecto: ninguna llamada de red a Applivery sin token.

---

## Notas de seguridad local

- Passwords: PBKDF2-HMAC-SHA256, 25.000 vueltas, sal por dispositivo (puro python,
  compatible con la build de Python del sistema que no trae `hashlib.scrypt`/`secrets`).
- Sesiones: token aleatorio en cookie `HttpOnly; SameSite=Lax`, 7 días.
- **Local only**: no se publica nada, no hay exfiltración. El token de Applivery
  se guarda solo en `data/tenants/<org_id>/config.json` (0600 recomendado) y jamás
  se loguea.

## Próximos pasos sugeridos (no bloqueantes)
- Webhooks de salida (cuando un dispositivo entra/sale de una geovalla) → POST a URL local.
- Export CSV/PDF de informes.
- SAML/OIDC para login enterprise (mock).
- Rate limiting por tenant.
