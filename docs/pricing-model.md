# LucidFence — Modelo de Monetización (Open-Core)

*Generado con skill `pricing` + dictamen Growth del tribunal.*
*Principio: OSS genera inbound y confianza; el servicio gestionado + inteligencia de amenazas recurrente es la captura. Nunca abrir Risk Engine/CVE/SOAR.*

---

## Estructura de tiers (Good-Better-Best)

### Community (Apache-2.0, GRATIS)
- Todo el core: glue multi-MDM, geofencing, dashboard, comandos remotos, alertas, export.
- Adapter framework + Applivery adapter.
- Self-host, multi-tenant local.
- Soporte: GitHub Discussions (comunidad).
- **Value metric:** gratis por diseño (es el embudo).

### Enterprise on-prem (DE PAGO, licencia anual)
- SSO/SAML + RBAC avanzado.
- SOAR premium (playbooks gestionados).
- **Risk Engine scoring premium** (modelos de amenazas recurrente, no en OSS).
- Escala (miles de dispositivos), SLA, soporte prioritario.
- **Value metric:** por dispositivo gestionado / año (escala con valor).

### MSP Program (RECOMENDADO, es el wedge)
- Para MSPs que gestionan varios clientes: licencia anual + **retainer de servicio gestionado**.
- Cada cliente del MSP en su tenant on-prem; el MSP paga por flota total.
- Incluye co-desarrollo de adapters (el MSP propone, nosotros priorizamos).
- **Value metric:** flota total MSP + retainer (recurrente).

---

## Value Metric (clave de `pricing`)
Cobrar por **dispositivo gestionado / año** en Enterprise/MSP. Escala con el valor real (más flota = más riesgo que controlar = más valor). No por seat (el admin IT no es el buyer).

## Ancla y decoy
- Mostrar Enterprise primero (ancla alta).
- MSP Program como "mejor valor" (decoy effect).

## Por qué no freemium de "soporte" como primario
El tribunal dijo: freemium soporte = flujo secundario. El OSS ya es gratis; el ingreso es Enterprise on-prem + retainer MSP. El soporte de comunidad es gratis por diseño.

## Riesgo incumbent (Microsoft/Google copia el core) = BAJO
El core (geofence + glue multi-MDM + dashboard) es commodity; copiarlo competiría con sus propias ventas MDM. El moat (Risk Engine/CVE/SOAR) es cerrado y Apache obliga a abrir modificaciones de cualquier fork suyo.

## Checklist de pricing
- [ ] LICENSE Apache-2.0 en repo core
- [ ] Módulo Enterprise on-prem documentado (qué es cerrado y por qué)
- [ ] Tabla de tiers en README/landing
- [ ] Value metric = dispositivo/año (Enterprise/MSP)
- [ ] CTA "Agenda demo MSP" en landing
- [ ] Retainer recurrente como captura principal

---
*Siguiente: ejecutar el refactor a `MDMAdapter` (DevRel) para que el "Community tier" sea realmente multi-MDM.*
