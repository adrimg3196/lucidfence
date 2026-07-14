# LucidFence — Modelo de Ingresos y Flujo de Cobro

*Especificación canónica de monetización (2026-07-14).*
*Reconcicia el GTM de `docs/pricing-model.md` (open-core) con el SaaS multi-tenant que ya existe en el código (`saas/tenant.py`, `saas_server.py`, `static/`).*

Principio rector: **el producto corre 100% local y tus datos no salen de la máquina**. Por eso el imán es el self-hosted gratuito, y la captura de ingresos es *servicio gestionado* (Pro) y *contrato on-prem* (Enterprise) — no vender la licencia del core, sino operarlo y darle SLA.

---

## 1. Las tres vías de ingreso

| Vía | Modelo de cobro | Value metric | Ciclo | Quién compra |
|-----|----------------|--------------|-------|-------------|
| **Free (freemium)** | $0 | — (es el embudo) | — | Cualquiera (self-host) |
| **Pro (gestionado/hosting)** | Suscripción recurrente **por dispositivo gestionado / mes** | dispositivos bajo gestión | Mensual / anual | Head of IT, ops de campo |
| **Enterprise (on-prem + SLA)** | Contrato anual + **SLA** + soporte prioritario | dispositivos + módulos cerrados | Anual (firmado) | CISO / compras |

### 1.1 Free = imán freemium (self-hosted)
- El repo es Apache-2.0. Cualquiera clona y corre el SaaS localmente.
- El script `scripts/lucidfence_saas_seed.sh` siembra las tareas de negocio (pricing, landing, growth, CS, soporte, revenue…) y es el punto de entrada del embudo: el usuario prueba el producto real en su máquina, hoy mismo, sin tarjeta.
- Límites del tier Free (ver `saas/tenant.py` → `PLAN_LIMITS`):
  - 5 dispositivos, 3 geovallas, retención 7 días.
  - Features: map, devices, basic_actions, risk_center.
- Soporte: comunidad (GitHub Discussions).

### 1.2 Pro = hosting gestionado (suscripción recurrente)
- **Nosotros operamos la nube del cliente** (deploy gestionado, p. ej. Fly.io o el tenant del cliente) y cobramos una cuota recurrente.
- Precio base de catálogo (hoy en el código): **49 €/mes** por organización, con límites:
  - 250 dispositivos, 50 geovallas, retención 90 días.
  - Features: + policies, compliance, export, webhooks, sso_mock.
- **Value metric real = dispositivo gestionado / mes.** El precio de catálogo (49 €/mes por org) es el ancla; la facturación final se calcula por dispositivo para escalar con el valor (más flota = más riesgo que controlar = más valor). Implementación sugerida: `precio_base + (dispositivos - incluidos) × precio_por_dispositivo`.
- Onboarding self-service: el lead crea el tenant vía GitHub Issue → aparece en `cloud.html` en ≤15 min (ver `docs/self-service-sla-2026-07-14.md`). Al convertir, se le asigna plan Pro y se activa la suscripción recurrente.

### 1.3 Enterprise = on-prem + SLA
- El cliente despliega en su infraestructura (on-prem o VPC propia). **Nosotros firmamos un contrato anual + SLA**.
- Límites de catálogo: 10.000 dispositivos, 1.000 geovallas, retención 365 días.
- Features cerradas/ premium: + audit_log, multi_region_mock, priority_support.
- Precio: **"Bajo demanda"** (cotización por volumen + módulos). Incluye:
  - SSO/SAML + RBAC avanzado.
  - SLA de disponibilidad y tiempo de respuesta (ver §5).
  - Soporte prioritario / account manager.
  - Co-desarrollo de adapters a medida (el cliente propone, nosotros priorizamos).
- Es la vía de mayor ARPU y la que cierra el moat (Risk Engine / CVE / SOAR permanecen cerrados).

---

## 2. Flujo de cobro documentado en el código (estado actual)

El SaaS ya implementa el *esqueleto* del flujo de planes. **Hoy es facturación simulada (mock): no se procesa ningún pago real.** Esto está etiquetado explícitamente en la UI (`static/saas_views2.js`: *"Facturación simulada. No se procesa ningún pago real"*).

### 2.1 Catálogo de planes — `saas/tenant.py` (`PLAN_LIMITS`, línea 122)
```python
PLAN_LIMITS = {
  "free":       {max_devices:5,     max_fences:3,    retention_days:7,   price:"0€/mes",    ...},
  "pro":        {max_devices:250,   max_fences:50,   retention_days:90,  price:"49€/mes",   ...},
  "enterprise": {max_devices:10000, max_fences:1000, retention_days:365, price:"Bajo demanda", ...},
}
```
Cada `Org` guarda `plan` y `limits` aislados en `data/tenants/<org_id>/`.

### 2.2 Selección de plan en el alta — `static/saas.js`
- El formulario de signup muestra los 3 planes (`saas.html` plan-grid) y envía `plan` en `POST /api/auth/signup` (línea 145). Al crear la org, `TenantStore.create()` aplica `PLAN_LIMITS[plan]`.

### 2.3 Cambio de plan — `saas_server.py` (`POST /api/plan/upgrade`, línea 933)
- Endpoint protegido por RBAC: requiere capacidad **`org:billing`**, que solo tiene el rol **owner** (`saas/auth.py` → `ROLE_CAPS`). Un `admin`/`operator`/`viewer` recibe 403.
- `TenantStore.update_plan()` reescribe `org.plan` y `org.limits` y persiste en `_orgs.json`.
- La vista Facturación (`static/saas_views2.js`, función `v2.billing`) muestra los 3 planes, el plan activo, el uso actual (dispositivos/geovallas vs límite) y un botón que llama a `/api/plan/upgrade`.

### 2.4 Puntos de integración para cobro real (lo que falta)
Para convertir el mock en cobro real, conectar una pasarela (Stripe / Paddle / LemonSqueezy — ver nota §6) en estos 3 puntos:
1. **Signup** (`/api/auth/signup` + `static/saas.js`): crear la suscripción en la pasarela al elegir Pro y pasar a `checkout`.
2. **Upgrade** (`/api/plan/upgrade`): al cambiar a Pro/Enterprise, disparar el cobro/prórroga y, al confirmar el pago, ejecutar `update_plan()`. Hoy `update_plan()` se llama sin pasarela.
3. **Webhook de la pasarela** → nuevo endpoint `POST /api/billing/webhook` que actualiza `org.plan` y el estado de pago (renovación, cancelación, dunning).
4. **Enforcement de límites** (ver §4): hoy los límites se *muestran* pero no se *bloquean* en las rutas de escritura.

---

## 3. Value metric y precios (decisión de pricing)

- **Cobrar por dispositivo gestionado / mes (o /año).** Escala con el valor real; el comprador es el responsable de flota, no un seat de admin.
- **Ancla y decoy** (de `docs/pricing-model.md`):
  - Mostrar **Enterprise** primero (ancla alta: "Bajo demanda").
  - **Pro** como "mejor valor" (decoy): 49 €/mes por org + precio por dispositivo.
  - Free como imán (freemium) visible pero sin ser la oferta principal.
- **No** freemium de "soporte" como primario: el OSS ya es gratis; el ingreso es servicio gestionado + contrato.

---

## 4. Estado de enforcement de límites (honestidad técnica)

`saas_server.py` declara en su docstring *"Plan limits (mock billing) enforced on write paths"*, pero en la implementación actual **no hay bloqueo duro** en las rutas de escritura: `max_devices` / `max_fences` solo se leen y se muestran en la vista de Facturación; no se rechaza un `POST /api/fences` o la adición de un dispositivo que supere el límite del plan.

**Acción requerida para cobrar Pro de verdad:** añadir el chequeo en las rutas de escritura (devices, fences) devolviendo `402 Payment Required` / `403` cuando `count >= limits[max_*]`, y un webhook de la pasarela que degrade el plan a `free` si el pago falla. Hasta entonces, el tiering es una *promesa de catálogo*, no una barrera técnica.

---

## 5. SLA (Enterprise / Pro gestionado)

- **SLA comercial self-service observado** (`docs/self-service-sla-2026-07-14.md`, validación 2026-07-14, PASS): *"normalmente visible en 5–15 min; objetivo ≤15 min"* desde que el lead abre el issue hasta que su tenant aparece en `cloud.html`. En la prueba real: 4m34s.
- **SLA Enterprise (contrato):** definir en el contrato — disponibilidad (p. ej. 99.9%), tiempo de respuesta de incidente (p. ej. P1 < 1 h), y ventana de soporte. El código ya crea tarjetas de soporte por cada incidencia (`Soporte` en el seed) y el rol `priority_support` existe en `enterprise`.
- **Soberanía:** al ser local-first, el SLA se refiere a *operación y soporte*, no a uptime de una nube nuestra (salvo en Pro gestionado donde nosotros operamos el hosting).

---

## 6. Notas de implementación / riesgos

- **Pasarela de pago:** el repo NO incluye Stripe/Paddle/etc. (grep de `stripe|paddle|…` solo encuentra `saas/tenant.py`). Elegir Paddle o LemonSqueezy para IVA/SaaS europeo sin fricción; Stripe para control total. Nunca commitear secrets (`.env.example` solo placeholders, CI gitleaks bloquea — ver memoria de proyecto).
- **Soberanía de datos como argumento de venta:** enfatizar en landing que Free/Enterprise corren en infra del cliente; solo Pro gestionado implica hosting nuestro (y aun así los datos del tenant están aislados por `data/tenants/<org_id>/`).
- **Moat vs incumbent:** el core (geofence + glue multi-MDM) es commodity; el moat cerrado es Risk Engine / CVE / SOAR, que no se abren ni en Enterprise (se licencian por contrato).

---

## 7. Checklist de revenue

- [x] Catálogo Free/Pro/Enterprise definido en `saas/tenant.py` (`PLAN_LIMITS`).
- [x] Selección de plan en signup (`static/saas.js`).
- [x] Cambio de plan vía `/api/plan/upgrade` con RBAC (`org:billing`, solo owner).
- [x] Vista de Facturación con uso vs límite (`static/saas_views2.js`).
- [x] Imán freemium: `scripts/lucidfence_saas_seed.sh` + self-host Apache-2.0.
- [x] Self-service validado E2E (issue → tenant → vitrina, SLA ≤15 min).
- [ ] **Conectar pasarela real** en signup + upgrade + webhook.
- [ ] **Enforcement duro de límites** en rutas de escritura (devices/fences).
- [ ] Degradación automática de plan en fallo de pago (dunning).
- [ ] Contrato Enterprise + SLA firmado (plantilla).
- [ ] Tabla de tiers + CTA en `static/index.html` (landing) — ver tarea *Commercial*.

---

*Siguiente paso sugerido: la tarea hermana "Commercial: landing con pricing tiers" debe consumir este doc como fuente de verdad de precios y mostrar Free/Pro/Enterprise con el CTA de registro self-service.*
