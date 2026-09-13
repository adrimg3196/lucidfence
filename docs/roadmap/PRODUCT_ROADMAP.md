# LucidFence Product Roadmap

Este documento define la visión y la evolución del producto LucidFence a través de horizontes estratégicos, manteniendo intactos los principios fundamentales: **local-first, cero telemetría, complemento multi-UEM, explicación transparente del riesgo, gratis y open source (Apache-2.0)**.

---

## Horizontes de Desarrollo

### 🟢 Horizon 1: NOW (LucidFence 2.0 Core - Go & React)
*En desarrollo / Producción activa (M0 - M5)*
- **Binario único en Go:** Arquitectura ligera, sin dependencias de runtime externos.
- **Geocercas & Rutas:** Soporte esférico preciso para círculos, polígonos complejos y corredores de ruta con POIs.
- **Motor de Riesgo Explicable:** Puntuación 0-100 basada en señales puras (`time_of_day`, `shift_match`, `device_health`, `device_posture`, `location_integrity`, `zone_risk`, `route_state`).
- **Guardarraíles & Freno Humano:** Modo `observe` por defecto, doble llave de `wipe`, handoffs pendientes para acciones destructivas.
- **Multi-UEM Integrado:** Conectores nativos para Applivery, Intune, Jamf, Fleet, Workspace ONE y simulación.
- **Informes & Evidencia:** Segunda opinión, cobertura de puntos ciegos, exportación HTML/CSV y cadena de evidencias hash.

---

### 🟡 Horizon 2: NEXT (Consolidación & Automatización Avanzada)
*Próximos lanzamientos inmediatos*
- **Generador Automático de Políticas Basado en Plantillas de Cumplimiento:** Cobertura de normativas (ISO 27001, NIS2, SOC2, GDPR).
- **Integración de Telemetría osquery Extendida:** Ingesta en tiempo real de eventos de postura del sistema operativo.
- **Dashboard de Auditoría Criptográfica:** Verificación visual instantánea de firmas HMAC y logs tamper-evident.

---

### 🔮 Horizon 3: EXPLORE (Visionary & Dreamer Roadmap para Hermes)
*Propuestas de frontera e innovación radical diseñadas para la implementación autónoma de Hermes*

El horizonte **EXPLORE** está dedicado a características de nueva generación que transforman LucidFence de un motor de geofencing reactivo a una plataforma de **Inteligencia Ambiental de Seguridad Local y Soberana**.

| Código | Función Ultra-Necesaria | Impacto Clave | Estado |
| :--- | :--- | :--- | :--- |
| **NOVA-01** | **Predicción Local de Trayectorias y Anomalías (Edge ONNX ML)** | Detecta anomalías de comportamiento espacio-temporal sin enviar ningún dato de posición fuera del binario local. | Proposal / Spec Ready |
| **NOVA-02** | **Verificación Cruzada P2P Mesh (Proximity Zero-Trust Witness)** | Dispositivos cercanos actúan como testigos criptográficos locales vía BLE/Wi-Fi Subnet para neutralizar el GPS Spoofing. | Proposal / Spec Ready |
| **NOVA-03** | **Geocercas Efímeras Autónomas (Dynamic Threat Geofencing)** | Crea zonas de cuarentena o resguardo dinámicas ante alertas territoriales de ciberamenazas e inteligencia contextual. | Proposal / Spec Ready |
| **NOVA-04** | **Bóveda de Evidencia Post-Cuántica (Post-Quantum Hardware Vault)** | Firma atestaciones físicas de ubicación con esquemas ML-DSA / Dilithium y TPM 2.0 / Secure Enclave. | Proposal / Spec Ready |
| **NOVA-05** | **Malla Multi-Tenant Aislada de Alta Disponibilidad (Air-Gapped P2P Sync)** | Sincronización P2P resiliente entre instancias LucidFence locales en entornos sin conexión a internet ni nube. | Proposal / Spec Ready |
| **NOVA-06** | **Handoffs Criptográficos con Candado Temporal (Dead-Man Switch Protocol)** | Protocolos de ejecución de emergencia con custodia temporal y multas de autorización ante fronteras geopolíticas. | Proposal / Spec Ready |

---

*Para la especificación técnica completa de las propuestas del horizonte EXPLORE, consultar [`docs/product/DREAMER_ROADMAP_HERMES.md`](../product/DREAMER_ROADMAP_HERMES.md).*
