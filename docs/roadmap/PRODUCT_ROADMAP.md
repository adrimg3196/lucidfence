# LucidFence Product Roadmap

**Versión:** 2.0.0-alpha
**Última actualización:** 2026-09-06

Este documento rastrea la evolución estratégica de LucidFence 2.0 a través de cuatro horizontes de planificación.

---

## Horizon Overview

| Horizonte | Estado | Enfoque Principal |
|-----------|--------|-------------------|
| **NOW** | En Ejecución | Reescritura Go 2.0 - Núcleo Demo, Motor de Riesgo Explicable y UI React |
| **NEXT** | Planificado | Conectores UEM (Intune, Jamf, Fleet, Applivery, WS1), Informes y MCP |
| **LATER** | En Espera | Vitrina pública, landing page B2B y empaquetado GoReleaser (2.0.0 final) |
| **EXPLORE** | Descubrimiento (NOVA) | Funcionalidades visionarias avanzadas para ejecución por el agente Hermes |

---

## 1. NOW (Horizonte Inmediato) — M0 a M2
- [x] **M0: Corte de `main`**: Migración de legado Python a Go 2.0 estático.
- [x] **M1: Núcleo Demo**: Binario Go unificado (`cmd/lucidfence`), servidor de API REST, geocercas/rutas/POIs y UI React embebida.
- [ ] **M2: Riesgo y Acciones**: Engine loop determinista, guardarraíles inviolables (`observe`/`enforce`, `allow_wipe`), SOAR y handoffs.

## 2. NEXT (Próximo Horizonte) — M3 a M4
- [ ] **M3: Conectores UEM**: Integración de adaptadores en vivo (Applivery, Microsoft Intune, Jamf Pro, Fleet, VMware Workspace ONE).
- [ ] **M4: Informes y Auth Completa**: Evidencias verificables, segunda opinión, RBAC multi-rol, auditoría encadenada y servidor MCP stdio.

## 3. LATER (Horizonte Futuro) — M5
- [ ] **M5: Publicación y Release**: Landing page pública, vitrina demo en vivo, fórmula Homebrew, imagen Docker distroless y tag `v2.0.0`.

---

## 4. EXPLORE (Horizonte Visionario NOVA — Para Agente Hermes)

Las siguientes iniciativas representan funcionalidades avanzadas definidas en `docs/product/2026-09-visionary-features-roadmap.md`:

### [NOVA-001] Zero-Knowledge Geospatial Proofs (ZK-Geofencing)
- **Descripción:** Demostración de presencia en geocerca sin revelar coordenadas lat/long exactas mediante ZK-SNARKs locales.
- **Estado:** EXPLORE
- **Fichero Spec:** `docs/product/2026-09-visionary-features-roadmap.md#1-nova-001-zero-knowledge-geospatial-proofs-zk-geofencing`

### [NOVA-002] Dynamic Peer-Mesh & Leader-Chaperone Geofencing
- **Descripción:** Geocercas dinámicas móviles relativas a la ubicación en tiempo real de un dispositivo líder o convoy.
- **Estado:** EXPLORE
- **Fichero Spec:** `docs/product/2026-09-visionary-features-roadmap.md#2-nova-002-dynamic-peer-mesh--leader-chaperone-geofencing`

### [NOVA-003] Kinetic Trajectory Drift & Anti-GPS Spoofing Engine
- **Descripción:** Detección de suplantación física de GPS mediante Filtro de Kalman y análisis de consistencia Wi-Fi BSSID.
- **Estado:** EXPLORE
- **Fichero Spec:** `docs/product/2026-09-visionary-features-roadmap.md#3-nova-003-kinetic-trajectory-drift--anti-gps-spoofing-engine`

### [NOVA-004] Post-Quantum Merkle Evidence Vault
- **Descripción:** Registro inmutable de evidencias con firmas post-cuánticas (Dilithium) y verificación de auditoría offline.
- **Estado:** EXPLORE
- **Fichero Spec:** `docs/product/2026-09-visionary-features-roadmap.md#4-nova-004-post-quantum-merkle-evidence-vault`

### [NOVA-005] Self-Healing SOAR & Proximity-Gated Handoffs
- **Descripción:** Cancelación automática de mitigaciones destructivas si el dispositivo vuelve a zona segura durante la ventana de gracia.
- **Estado:** EXPLORE
- **Fichero Spec:** `docs/product/2026-09-visionary-features-roadmap.md#5-nova-005-self-healing-soar--proximity-gated-handoffs`

### [NOVA-006] Air-Gapped Multi-Tenant Federation & Offline Peer Sync
- **Descripción:** Sincronización P2P cifrada sobre LAN (mDNS + QUIC) para servidores LucidFence en redes aisladas de internet.
- **Estado:** EXPLORE
- **Fichero Spec:** `docs/product/2026-09-visionary-features-roadmap.md#6-nova-006-air-gapped-multi-tenant-federation--offline-peer-sync`
