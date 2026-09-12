# LucidFence Product Roadmap

**Producto:** LucidFence (Local-First Multi-UEM Geofencing & Risk Engine)
**Licencia:** Apache-2.0
**Arquitectura:** Go single-binary with embedded React Web Dashboard

---

## Horizontes de Desarrollo

### 1. NOW (Horizonte Inmediato) - LucidFence 2.0 Go Core
- [x] Motor de geocercado esférico y cálculo de distancias (M0/M1).
- [x] Motor de riesgo explicable (0–100) y señales de postura/integridad (M2).
- [x] Integración de conectores UEM (Applivery, Intune, Jamf, Fleet, Workspace ONE).
- [x] Ejecución de acciones de remediación con guardarraíles (observe/enforce, doble llave `wipe`).
- [x] Notificaciones egress seguras (Webhooks con HMAC, OCSF, ntfy).
- [x] Dashboard React embebido e interfaz local-first.

---

### 2. NEXT (Próximos Hitos)
- [ ] Ampliación de cobertura de políticas declarativas (Apple DDM / Windows DSC / Android AMAPI).
- [ ] Protocolo MCP (Model Context Protocol) extendido para integración con asistentes de IA locales.
- [ ] Soporte para geocercas complejas avanzadas (polígonos multisectoriales y zonas de exclusión dinámica).

---

### 3. EXPLORE (Horizonte de Descubrimiento e Innovación - Propuestas NOVA)

Documento de referencia: [`docs/product/visionary-features-roadmap.md`](../product/visionary-features-roadmap.md)

* **NOVA-001: Predicción Intuitiva de Anomalías de Ruta y Geomalla Dinámica Local-First**
  - Inferencia ML local sin telemetría externa para anticipar brechas de perímetro.
  - Geomallas móviles sincronizadas con activos en movimiento.

* **NOVA-002: Doble Llave Criptográfica Descentralizada y Custodia Cero-Confianza**
  - Quórum multiclave WebAuthn/FIDO2/YubiKey para acciones destructivas (`wipe`).
  - Protocolo Break-Glass efímero con expiración atómica en disco.

* **NOVA-003: Traductor Adaptativo y Sincronización Automática Multi-UEM**
  - Compilador cruzado de reglas de seguridad para heterogeneidad de UEMs.
  - Failover dinámico de canal de mando entre conectores UEM y Fleet osquery.

* **NOVA-004: Simulador Digital Twin Geosuperpuesto y Replicación de Ataques**
  - Recreación sintética 3D/4D de la flota y simulación de vector de ataque GPS/Spoofing.
  - Análisis de impacto previas a despliegue en producción.

* **NOVA-005: Pasaporte Criptográfico e Inmutable de Auditoría por Dispositivo**
  - Certificación de cumplimiento normativo (NIS2, ISO27001) mediante ZKP (Zero-Knowledge Proofs).
  - Trazabilidad soberana y privacidad total para el empleado.
