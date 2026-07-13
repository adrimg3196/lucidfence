# Product Marketing Context — LucidFence Command Center

*Last updated: 2026-07-13*

> Contexto validado por tribunal de marketing (CMO + DevRel + Growth-GTM).
> Moat = Risk Engine explicable + local-first sin exfiltrar. NO es "geofencing open-source" (commodity).

## Product Overview
**One-liner:** Local-first UEM Risk & Geofence Control Plane que convierte la geolocalización de tu flota en riesgo explicable y acciones automáticas — agnóstico al MDM.
**What it does:** Correlaciona geovallas + riesgo compuesto (0-100) + CVE + SOAR y decide (lock/wipe/locate/alert) en un dashboard 100% local, multi-tenant, sin enviar datos a la nube.
**Product category:** UEM / MDM security & geofencing control plane (open-core).
**Product type:** Open-source (Apache-2.0 core) + módulo Enterprise on-prem (SSO/SOAR/Risk Engine premium).
**Business model:** Apache-2.0 core gratis; Enterprise on-prem por licencia anual + retainer MSP. Freemium "soporte" secundario.

## Target Audience
**Target companies:** MSPs (managed service providers) de UEM que gestionan flotas heterogéneas de varios clientes con MDMs distintos; CISO/CTO soberanía-sensitive.
**Decision-makers:** MSP owner/CEO (economic buyer), CISO/CTO (soberanía), admin IT (usuario).
**Primary use case:** Controlar perimetralmente dispositivos móviles de campo (fuera de geovalla = alerta/acción) sin exfiltrar datos del cliente.
**Jobs to be done:**
- "Saber si un dispositivo salió de su zona autorizada y actuar"
- "Justificar el riesgo de un dispositivo a un auditor/cliente"
- "Gestionar varios MDMs desde un solo plano de control local"
**Use cases:** field workforce compliance, anti-robo perimetral, auditoría de flota, MSP multi-cliente.

## Personas
| Persona | Cares about | Challenge | Value we promise |
|---------|-------------|-----------|------------------|
| MSP owner | Margen, confianza cliente, 1 herramienta multi-MDM | Flotas con Intune+Jamf+Applivery, sin visión unificada ni local | Un plano de control local que agrega todos los MDMs |
| CISO/CTO | Soberanía, auditabilidad, sin exfil | Cloud UEM filtra datos de ubicación a 3rd parties | 100% local, Risk Engine explicable, auditable |
| Admin IT | Facilidad, alertas que funcionen | Geofencing nativo de MDM es básico/commodity | Alertas por umbral + comandos remotos on-demand |

## Problems & Pain Points
**Core problem:** Los MDMs nativos hacen geofencing básico pero no correlacionan riesgo/CVE/SOAR ni son local-first; los UEM cloud exfiltran ubicación.
**Why alternatives fall short:** SOTI/Workspace ONE/Intune = geofencing commodity, cerrado, cloud, sin Risk Engine explicable ni agnóstico a MDM. Geotab = telematics, no UEM.
**What it costs them:** Fugas de datos de ubicación (compliance), ciegos perimetrales, N tools por MDM.
**Emotional tension:** "No sé dónde están mis dispositivos de campo ni si están en riesgo, y no quiero mandar esos datos a la nube."

## Competitive Landscape
**Direct:** SOTI Mobicontrol, VMware Workspace ONE, Microsoft Intune — geofencing nativo pero commodity, cloud, cerrado, no agnóstico.
**Secondary:** GEOTAB (telematics), MDM genéricos — no correlacionan riesgo UEM.
**Indirect:** "No hacer nada" / hojas de cálculo de ubicación — insostenible a escala.

## Differentiation
**Key differentiators:**
- Risk Engine compuesto explicable (score 0-100 + políticas con razón)
- Local-first: 0 exfiltración de datos de ubicación
- Agnóstico a MDM vía framework de adapters (Applivery hoy live; Intune/Jamf incluidos en mock listos para live; Fleet/otros por la comunidad)
- SOAR + CVE + comandos remotos on-demand en un solo plano
**How we do it differently:** El core decide y explica; los MDMs solo son fuente/destino de datos.
**Why that's better:** Auditable, soberano, multi-MDM desde día 1.
**Why customers choose us:** MSP lo adopta para TODOS sus clientes sin vendor lock-in de nube.

## Objections
| Objection | Response |
|-----------|----------|
| "Intune ya hace geofencing" | Commodity y cloud; nosotros explicamos el riesgo y no exfiltramos |
| "¿Y si mi MDM no está soportado?" | Framework de adapters: tu equipo o la comunidad lo añade en un PR de fin de semana |
| "Open-source = inseguro" | Apache-2.0, auditable, local-first; el moat (Risk Engine) es el código que NO abrimos |

**Anti-persona:** Enterprise que quiere SaaS hosted multiregión gestionado por nosotros (no es nuestro modelo; somos on-prem/local).

## Switching Dynamics
**Push:** Cloud UEM filtra ubicación; geofencing nativo insuficiente; N paneles por MDM.
**Pull:** 1 plano local, riesgo explicable, multi-MDM.
**Habit:** "Ya tenemos Intune/Jamf".
**Anxiety:** "¿El adapter de mi MDM funcionará de verdad?" → mitigado con CI obligatorio + badge verified.

## Customer Language
**How they describe the problem:** "no sé dónde están los dispositivos de campo", "el MDM no me dice el riesgo", "no quiero mandar ubicación a la nube"
**How they describe us:** "el control plane que une mis MDMs sin subir datos"
**Words to use:** soberanía, explicable, auditable, local-first, agnóstico a MDM, riesgo, perímetro
**Words to avoid:** "tracking", "vigilancia", "cualquier MDM" (hasta tener ≥2 adapters reales)
**Glossary:**
| Term | Meaning |
|------|---------|
| Risk Engine | Motor que calcula score 0-100 de riesgo por dispositivo con razón |
| Adapter | Conector MDM (fuente de ubicación + destino de acciones) |
| Geovalla | Polígono/radio que define zona autorizada |
| SOAR | Playbook de orquestación que ejecuta acciones UEM |

## Brand Voice
**Tone:** Directo, técnico pero accesible, sin hype.
**Style:** Segundo persona, claims con prueba, específico.
**Personality:** Serio, soberano, ingeniero.

## Proof Points
**Metrics:** 115 tests PASS, 5 dispositivos demo, Risk Engine 0-100, 0 exfiltración.
**Customers:** MSPs tempranos (consultora UEM).
**Testimonials:** (pendiente de recoger de MSPs piloto)
**Value themes:**
| Theme | Proof |
|-------|-------|
| Soberanía | 100% local, 0 exfil |
| Explicable | Risk Engine score + razón |
| Multi-MDM | Framework de adapters |

## Goals
**Business goal:** Ser el control plane open-core de referencia para MSPs UEM.
**Conversion action:** Fork del repo + install del adapter de su MDM + demo MSP.
**Current metrics:** 0 stars (pre-lanzamiento).
