# Product Roadmap — LucidFence

Roadmap estratégico de producto gestionado por **NOVA ✨**.

## Visión del Producto
LucidFence es el motor de geofencing y riesgo físico local-first multi-UEM. Tu dato de ubicación vive en tu máquina y nunca sale de tu infraestructura.

---

## Horizontes del Roadmap

### NOW (En ejecución y comprometido para la release 2.0)
- **LucidFence 2.0 Core (Hitos M1 - M5):** Reescritura completa en Go de un solo binario con dashboard React embebido, geocercas, rutas, motor de riesgo explicable 0-100, guardarraíles (observe/enforce), conectores multi-UEM (Applivery, Intune, Jamf, Fleet, Workspace ONE), alertas SOAR y MCP stdio.

---

### NEXT (Prioridad estratégica para refinamiento)
*(Oportunidades validadas pendientes de capacidad asignada tras release 2.0)*

---

### LATER (Apuestas a medio y largo plazo)
*(Iniciativas estratégicas condicionadas a la madurez de la plataforma 2.0)*

---

### EXPLORE (Hipótesis y Oportunidades en Discovery)

#### ✨ LucidGeo-Attest: Bóveda de Atestación de Ubicación Cero-Conocimiento para Zero Trust
- **Propuesta:** Emisión local de claims JWT/OIDC criptográficos de riesgo de ubicación e integridad sin coordenadas geográficas (`/api/v1/auth/attest/location-risk`), permitiendo a proveedores de identidad Zero Trust (Okta, Entra ID, Cloudflare Access) autorizar sesiones sin exfiltrar posiciones GPS a la nube.
- **Documento de Oportunidad:** [`docs/product/2026-09-10-lucidgeo-attest-zero-knowledge-location-risk.md`](../product/2026-09-10-lucidgeo-attest-zero-knowledge-location-risk.md)
- **Tipo de apuesta:** Plataforma / Adyacente
- **Confianza:** Alta | **Esfuerzo:** Medio
- **Estado:** EXPLORE

---

### PARKED (Descartadas o en pausa)
*(Ninguna propuesta aparcada en este ciclo)*
