# Proposal NOVA Product Discovery: LucidFence 2.0 — Visionary Next-Gen Roadmap

- **Fecha:** 2026-09-10
- **Estado:** Propuesta de descubrimiento (Horizonte EXPLORE)
- **Autor:** Creador de Roadmap Visionario / Product Discovery NOVA
- **Destinatario de ejecución:** Hermes / Agentes de Implementación

---

## Executive Summary

LucidFence 2.0 ha consolidado la arquitectura local-first multi-UEM más rápida y transparente del mercado (Go, un solo binario, React 19, cero telemetría). Sin embargo, el panorama de amenazas físicas y ciberfísicas de 2026+ exige llevar la seguridad geográfica y la postura de dispositivos a una nueva frontera.

Esta propuesta define **6 capacidades ultra-necesarias y revolucionarias** que extienden el paradigma *Local-First* hacia *Zero-Knowledge*, *Post-Quantum* y *Mesh Offline Autonomous Security*. Estas especificaciones están diseñadas conceptualmente para que Hermes y la flota de agentes puedan convertirlas en especificaciones de arquitectura e implementaciones de producción en sucesivas iteraciones.

---

## 1. Visionary Feature Matrix

| ID | Nombre de la Función | Categoría | Propósito y Valor Transformador |
|---|---|---|---|
| **NOVA-01** | Zero-Knowledge Privacy Geofencing (ZK-Fence) | Criptografía / Privacidad | Demuestra pertenencia a geocercas mediante ZK-SNARKs sin exponer coordenadas GPS ni guardar rastros de ubicación. |
| **NOVA-02** | Dynamic P2P Mesh Geofencing (MeshFence) | Resiliencia Offline / IoT | Validación mutua de proximidad mediante BLE/UWB/Wi-Fi Direct cuando no hay internet o hay inhibición GPS. |
| **NOVA-03** | Post-Quantum Location Attestation (PQ-Attest) | Criptografía Poscuántica | Firmas ML-DSA/Dilithium ancladas en Secure Enclave/TPM 2.0 para certificar la inalterabilidad de la evidencia. |
| **NOVA-04** | Autonomous Threat-Hunting & Auto-Playbook AI Engine | Agéntica / SOAR | Descubrimiento autónomo de anomalías físicas y síntesis automática de políticas con simulación what-if predictiva. |
| **NOVA-05** | Spatio-Temporal Anomaly & Hardware Telemetry Fusion | Motor de Riesgo | Correlación de micro-movimientos, acelerómetro, térmica y batería para detectar clonación y sustitución física de hardware. |
| **NOVA-06** | Physical Access Control & IoT GateKeeper | Integración Ciberfísica | Puente local-first (OSDP/Wiegand/MQTT) que bloquea acceso físico/tarjetas NFC cuando el riesgo digital o geofence se viola. |

---

## 2. Especificación Detallada de Funciones Ultra-Necesarias

### NOVA-01: Zero-Knowledge Privacy Geofencing (ZK-Fence)

- **El Problema:** Muchas organizaciones dudan en implantar geofencing corporativo por objeciones de privacidad laboral, regulaciones GDPR/EU AI Act y resistencia de empleados preocupados por el rastreo continuo de coordenadas GPS.
- **La Solución Soñada:** El agente local en el dispositivo genera una prueba criptográfica de conocimiento cero (*Zero-Knowledge Proof*, ZK-SNARK). La prueba atestigua la proposición binaria: *"El dispositivo D se encuentra actualmente dentro del polígono P autorizado"* sin revelar la latitud, longitud, altitud ni velocidad exacta del usuario.
- **Integración con LucidFence 2.0:**
  - Creación de un paquete `internal/domain/zkp`.
  - La API recibe un payload `{ device_id, fence_id, zkp_proof, timestamp }`.
  - El motor valida la prueba matemática instantáneamente sin procesar ni almacenar coordenadas en `devices.json` ni en `events.jsonl`.
  - Cumplimiento 100% de privacidad garantizada por diseño.

### NOVA-02: Dynamic P2P Mesh Geofencing (MeshFence)

- **El Problema:** En zonas sin cobertura celular/Wi-Fi, subterráneos o escenarios de ataque con inhibidores de frecuencia (GPS jamming/spoofing), las geocercas tradicionales pierden señal y entran en estado `unknown`.
- **La Solución Soñada:** Red P2P ad-hoc entre dispositivos corporativos cercanos mediante Ultra-Wideband (UWB), Bluetooth Low Energy (BLE) y Wi-Fi Direct. Los dispositivos actúan como nodos de confianza distribuida: si al menos 3 dispositivos verificados forman una malla en un perímetro, validan colectivamente la pertenencia física de la flota en el área.
- **Integración con LucidFence 2.0:**
  - Nuevo productor de señales en `internal/domain/risk/signal_mesh.go`.
  - Indicador `mesh_neighbors_count` y `mesh_trust_score`.
  - Si el GPS cae, la geocerca se mantiene activa en modo `mesh_verified`, impidiendo falsos positivos de riesgo o bloqueos no deseados.

### NOVA-03: Post-Quantum Location Attestation (PQ-Attest)

- **El Problema:** La computación cuántica inminente y las herramientas avanzadas de spoofing de kernel amenazan con falsificar las firmas criptográficas de evidencia en informes de auditoría.
- **La Solución Soñada:** Implementar certificación de evidencia de ubicación y postura firmada con esquemas post-cuánticos estandarizados por NIST (ML-DSA / Crystals-Dilithium y Falcon), combinada con mediciones de hardware firmadas por el TPM 2.0 o Apple Secure Enclave.
- **Integración con LucidFence 2.0:**
  - Extensión de `reports/evidence` para incluir `pq_signature` y `tpm_quote`.
  - Verificación offline de la cadena de evidencia garantizando inalterabilidad absoluta frente a ataques criptográficos avanzados.

### NOVA-04: Autonomous Threat-Hunting & Auto-Playbook AI Engine

- **El Problema:** Crear reglas de políticas y playbooks SOAR manualmente requiere horas de análisis por parte de los administradores de seguridad.
- **La Solución Soñada:** Un motor agéntico local que analiza continuamente los patrones de desplazamiento de la flota, variaciones de riesgo por hora/sitio y desviaciones anormales de comportamiento. El motor sintetiza de forma autónoma sugerencias de políticas en la gramática nativa de LucidFence (`domain/policy`) e imparte simulación what-if contra el histórico.
- **Integración con LucidFence 2.0:**
  - Endpoint `POST /api/v1/playbooks/synthesis`.
  - Visualización en el Dashboard con un botón *"Aprobar e Industrializar Política"* con 1-click.

### NOVA-05: Spatio-Temporal Anomaly & Hardware Telemetry Fusion

- **El Problema:** Ataques sofisticados de clonación de tarjetas SIM, duplicación de identificadores de hardware (IMEI/Serie) o ataques man-in-the-middle en conectores UEM.
- **La Solución Soñada:** Un evaluador multidimensional que analiza la huella física y bio-métrica del hardware: giroscopio, micro-variaciones de temperatura de batería, patrones de degradación de almacenamiento y tiempo de viaje espacio-temporal (física de transporte).
- **Integración con LucidFence 2.0:**
  - Nuevo paquete `internal/domain/integrity/spatiotemporal.go`.
  - Detección de velocidad de viaje física imposible (p. ej., Madrid a Tokio en 20 minutos) y disonancia de huella térmica de hardware.

### NOVA-06: Physical Access Control & IoT GateKeeper

- **El Problema:** La seguridad digital y la seguridad física del edificio funcionan en islas separadas. Si un portátil es robado o su geocerca se viola fuera de la oficina, el ladrón aún podría usar el pase o la tarjeta NFC para acceder físicamente a las instalaciones.
- **La Solución Soñada:** Un adaptador de salida local-first (OSDP, BACnet, MQTT, Home Assistant) que revoca instantáneamente los pases de acceso físico, puertas y tornos del edificio asociados al usuario en cuanto su dispositivo entra en estado no conforme o alto riesgo.
- **Integración con LucidFence 2.0:**
  - Nuevo módulo de salida en `internal/notify/gatekeeper`.
  - Acción SOAR `revoke_physical_access` / `restore_physical_access`.

---

## 3. Instrucciones de Ejecución para Hermes

Hermes y los agentes de desarrollo abordarán estas características en fases sucesivas:
1. Diseñar las especificaciones de arquitectura e interfaces Go puras en `internal/domain/`.
2. Mantener de forma estricta los principios rectores de LucidFence 2.0: un solo binario, local-first, cero telemetría, Apache-2.0.
3. Incorporar tests unitarios y validación en la batería runtime (`internal/battery`).
