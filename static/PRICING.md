# LucidFence — Modelo de precios (GTM)

Definición oficial de los tres tiers comerciales de LucidFence. El `lucidfence_saas_seed.sh`
(el producto actual) ES el tier Freemium: código 100% local que el cliente despliega en su
propia infra con `0 €`. El resto del modelo monetiza el *hosting gestionado* (Pro) y el
*on-prem con SLA* (Enterprise).

> Moneda: EUR (€). Precios sin IVA. Facturación mensual recurrente para Pro; anual para
> Enterprise. Todos los planes incluyen el motor de geocercas, dashboard y whitelabel básico.

---

## 1. Freemium — Self-hosted (`lucidfence_saas_seed.sh`)

**Precio: 0 € / mes, para siempre.**

Es el producto actual: un script que deja el `Dockerfile` + `docker-compose.yml` + `CLIENTE.md`
listos para que el cliente corra LucidFence en su propia máquina/servidor. Sin tarjeta, sin
límite de tiempo, sin telemetría externa.

| Incluido | Límite |
|---|---|
| Dispositivos monitorizados | **hasta 25** |
| Geocercas / rutas | Ilimitadas |
| Dashboard + motor de geocercas local | ✅ |
| Alertas por email (Atomic Mail, gratis) | ✅ |
| IA local (MoA, modo libre) | ✅ |
| Whitelabel (1 tenant, dominio FreeDomain) | ✅ |
| Soporte | Comunidad (docs + GitHub) |
| CVE / SOAR en vitrina | Solo lectura |

**Imán freemium:** el self-hosted 0 € es la entrada de embudo. El límite de 25 dispositivos
empuja a las empresas reales a Pro; el deseo de no operar infra propia empuja a Pro gestionado.

---

## 2. Pro — Hosting gestionado por nosotros (nube del cliente)

**Precio: desde 2 € / dispositivo / mes.** Suscripción mensual recurrente. Nosotros operamos
el hosting always-on (VM dedicada en la región del cliente), backups, parches y actualizaciones.
El cliente conserva la soberanía de datos (su región, su dominio).

Modelo por volumen (precio por dispositivo baja con la escala):

| Tramo | Dispositivos | Precio | ≈ €/dispositivo |
|---|---|---|---|
| **Starter** (destacado) | hasta 50 | **49 € / mes** | 0,98 € |
| **Growth** | 51 – 250 | **199 € / mes** | 0,80 € |
| **Scale** | 251 – 1.000 | **0,60 € / dispositivo** | 0,60 € |
| **Custom** | +1.000 | Bajo acuerdo | < 0,60 € |

**Qué incluye Pro (todo lo de Freemium +):**
- Hosting gestionado 24/7 en la nube del cliente (nosotros operamos)
- SLA de disponibilidad **99,9 %**
- Backups automáticos + restauración
- Actualizaciones y parches sin downtime
- Dominio propio (+ FreeDomain si lo prefiere)
- Whitelabel **multi-tenant**
- IA real (MoA) siempre activa
- CVE / SOAR en vivo (alertas accionables)
- Soporte por email con respuesta < 24 h

> Comparativa de mercado (referencia, no vinculante): Jamf Pro ~4–8 $/dispositivo/mes;
> Intune ~6 $/usuario/mes. LucidFence Pro arranca en **0,98 €** y baja con el volumen.

---

## 3. Enterprise — On-prem + SSO + Soporte prioritario

**Precio: desde 1.500 € / mes (bajo acuerdo).** Contrato anual. Para despliegues grandes con
requisitos de cumplimiento, identidad corporativa y SLA estricto.

**Qué incluye Enterprise (todo lo de Pro +):**
- **On-prem / clúster multi-VM** en infra del cliente
- **SSO** (SAML 2.0 / OIDC) + **LDAP / Active Directory**
- **Soporte prioritario** — SLA 24/7, CSM dedicado, respuesta < 1 h en Sev1
- Integraciones a medida (SIEM, CMDB, ITSM)
- Audit logs + data residency en la región exigida
- Onboarding gestionado + playbook de bienvenida

---

## Mitos y reglas del modelo

- **Nunca cobramos por el self-hosted.** El `lucidfence_saas_seed.sh` es y será 0 €: es
  marketing de adquisición, no una limitación temporal.
- **El límite de 25 dispositivos en Freemium es el único "muro" de conversión.** Pro lo quita.
- **Enterprise nunca es "precio en la web".** Siempre "Desde 1.500 €/mes · Bajo acuerdo" con CTA
  a contacto/comercial, nunca checkout.
- **Sin costes ocultos de terceros:** Atomic Mail, FreeDomain y MoA local son gratuitos por
  diseño; el cliente solo paga nuestro hosting/soporte.

## Flujo de ingresos (para la tarjeta Revenue)

```
Freemium (0 €, self-hosted)  ──limit 25 dev──▶  Pro (2 €/dev/mes, hosting gestionado)
                                                      │
                                                      └──grandes cuentas──▶ Enterprise (≥1.500 €/mes, on-prem+SSO+SLA)
```

Canal de cobro: Stripe (suscripción recurrente) para Pro; contrato + transferencia para Enterprise.
Self-service: el formulario de signup captura email → oportunidad CRM en el board (tarjeta Growth).
