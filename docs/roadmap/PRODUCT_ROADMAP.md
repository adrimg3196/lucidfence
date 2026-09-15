# LucidFence 2.0 Product Roadmap & Vision

Este documento detalla la hoja de ruta estratégica para la evolución de **LucidFence 2.0**. Mantiene los principios inquebrantables del producto: **Local-First, Cero Telemetría, Complemento Multi-UEM, Gratis y Open Source (Apache-2.0)**.

---

## Horizontes de Desarrollo

### 1. NOW (Release Actual - 2.0.0-alpha.2)
- Motor de riesgo explicable (0–100) en Go puro.
- Geocercas circulares y poligonales con pertenencia matemática.
- Integración Multi-UEM (Applivery, Intune, Jamf, Fleet, Workspace ONE).
- Soporte declarativo nativo (Apple DDM, Windows DSC, Android AMAPI).
- Dashboard embebido React (SPA local) y API HTTP `/api/v1`.
- Ejecución con guardarraíles: modo `observe` por defecto.

### 2. NEXT (Hito M3 - Próximo Alcance)
- Integración avanzada con osquery postura local con fail-closed.
- Informes automatizados OCSF y alertas vía ntfy/webhook firmado.
- Optimización de rendimiento de cálculo esférico y trailing espacial.

### 3. EXPLORE (Propuestas Visionarias para Construcción por Hermes)

Las siguientes 5 iniciativas revolucionarias están listas para ser diseñadas e implementadas secuencialmente por **Hermes**:

| ID | Iniciativa | Archivo de Especificación | Propósito | Impacto Local-First |
|---|---|---|---|---|
| **EXP-01** | **LucidMesh** | `docs/product/01-lucidmesh-p2p-consensus.md` | Malla local P2P cifrada (BLE/Wi-Fi Direct) para validación cruzada de coordenadas y postura sin pasar por la nube. | Alta resiliencia ante GPS jamming/spoofing en zonas aisladas. |
| **EXP-02** | **ChronosFence** | `docs/product/02-chronosfence-predictive-risk.md` | Motor probabilístico espacio-temporal para detección de cinemática imposible y alertas predictivas pre-borde. | Previene brechas antes del cruce de frontera sin almacenar trayectorias crudas. |
| **EXP-03** | **ZK-Geofence** | `docs/product/03-zk-geofence-attestation.md` | Pruebas de conocimiento cero (ZK-SNARKs) que atestiguan ubicación dentro de la cerca sin revelar coordenadas GPS exactas. | Cumplimiento total de privacidad (GDPR) frente a auditores. |
| **EXP-04** | **GhostFence** | `docs/product/04-ghostfence-airgap-protocol.md` | Protocolo autónomo de contención Air-Gap en el cliente ante evasión simultánea de red y postura física. | Protección inmediata de datos robados en recintos blindados. |
| **EXP-05** | **PolicyGen** | `docs/product/05-policygen-declarative-synthesis.md` | Compilador determinista local de reglas de riesgo a políticas declarativas nativas (Apple DDM, Windows DSC, Android AMAPI). | Automatización total del ciclo de vida declarativo multi-UEM. |

---

## Guía de Ejecución para Hermes
Para construir cualquiera de las iniciativas en el horizonte `EXPLORE`, consultar la spec correspondiente en `docs/product/` y los aprendizajes normativos en `.jules/nova.md`.
