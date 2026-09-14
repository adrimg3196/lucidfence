# Roadmap Estratégico de Producto — LucidFence 2.0 ✨

Este documento define la gobernanza y dirección estratégica de producto para **LucidFence 2.0**. El roadmap se organiza por horizontes temporales y niveles de certidumbre en lugar de fechas cerradas, reflejando el compromiso con la entrega continua de valor y la constante investigación de necesidades de mercado.

---

## 1. Gobernanza del Roadmap

- **NOW**: Iniciativas validadas, con alcance definido y capacidad asignada (Hitos de desarrollo activos de LucidFence 2.0).
- **NEXT**: Oportunidades prioritarias con evidencia suficiente, pendientes de diseño final o asignación de capacidad.
- **LATER**: Apuestas estratégicas a medio/largo plazo dependientes del progreso de hitos anteriores.
- **EXPLORE**: Hipótesis visionarias y oportunidades de producto propuestas por **NOVA ✨** bajo investigación y validación (sin compromiso de implementación hasta aprobación humana explícita).
- **PARKED**: Oportunidades descartadas, prematuras o superadas por alternativas superiores.

---

## 2. Horizontes del Roadmap

### 🔴 NOW (Hitos de Construcción Activa LucidFence 2.0)

| Iniciativa | Descripción | Estado | Spec / Ref |
|---|---|---|---|
| **M0 Día 0** | Esqueleto Go, CI completo, raíles de agentes, CODEOWNERS | Completado | `docs/superpowers/plans/2026-09-05-m0-dia-0.md` |
| **M1 Núcleo Demo** | Engine simulación, store, auth básica, API REST v1, Web App React | Completado | `docs/superpowers/plans/2026-09-05-m1-nucleo-demo.md` |
| **M2 Riesgo y Acciones** | Políticas, guardarraíles, incidentes, alertas, SOAR, handoffs, webhooks HMAC/OCSF/ntfy | Completado (v2.0.0-alpha.2) | `docs/superpowers/plans/2026-09-06-m2-riesgo-y-acciones.md` |

### 🟡 NEXT

| Iniciativa | Descripción | Estado |
|---|---|---|
| **M3 Conectores UEM** | Integración nativa con Applivery, Intune, Jamf, Fleet y Workspace ONE; reconciliación de flota | Planificado |
| **M4 Informes y Auth Completa** | Informes de evidencias, cobertura, segunda opinión, RBAC completo, OIDC y servidor MCP | Planificado |

### 🔵 LATER

| Iniciativa | Descripción | Estado |
|---|---|---|
| **M5 Release Pública 2.0** | Landing, vitrina pública, manuales ES/EN, GoReleaser, paquete Homebrew | Planificado |

### 🟣 EXPLORE (Propuestas Visionarias de NOVA ✨)

| Oportunidad | Resumen | Tipo de Apuesta | Oportunidad Documentada |
|---|---|---|---|
| **LucidGeo-Attest** | Pasarela local de atestación criptográfica de cumplimiento geográfico de conocimiento cero para integración con Okta, Entra ID, Ping y SASE sin exfiltración de coordenadas GPS. | Plataforma / Adyacente | [`docs/product/lucidgeo-attest.md`](../product/lucidgeo-attest.md) |

---

## 3. Principios Rectores

- **El roadmap no es una lista de funciones**: Explica cómo aumentará el valor del producto para usuarios y organizaciones reguladas.
- **Local-first e Inviolabilidad de la Privacidad**: Ninguna iniciativa en el roadmap comprometerá el principio de almacenamiento y procesamiento 100 % local.
- **Transición Transparente**: Toda propuesta en `EXPLORE` requiere aprobación humana explícita para ser promovida a `NEXT` o `NOW`.
