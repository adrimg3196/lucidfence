# Roadmap de Producto LucidFence 2.0

Hoja de ruta estratégica de LucidFence. Estructurada en los horizontes **NOW** (estado actual), **NEXT** (próximos hitos) y **EXPLORE** (propuestas de visión y descubrimiento NOVA para su desarrollo futuro por Hermes).

---

## NOW: Hito M2 - Riesgo y Acciones (Versión 2.0.0-alpha.2)

- **Motor de Riesgo Explicable**: Evaluación de 7 señales independientes (velocidad, país, geocercas, precisión, edad de ubicación, postura, integridad) sin base de datos ni telemetría.
- **Acciones UEM de Doble Llave**: Soporte para `observe`, `lock`, `wipe` con guardarraíles estrictos.
- **Conectores UEM**: Applivery, Microsoft Intune, Jamf Pro, Fleet, VMware Workspace ONE.
- **Notificaciones y Auditoría**: Notificaciones OCSF firmadas, soporte ntfy y trazabilidad atómica local en JSON/JSONL.
- **Local-First & Cero Cloud**: Binario único Go compilado con frontend React embebido.

---

## NEXT: Hito M3 - Playbooks SOAR y Consolidación de Experiencia

- **Playbooks Automatizados**: Motor SOAR declarativo sobre la gramática de políticas con gate de aprobación humana.
- **Integración de Postura osquery / Fleet**: Ingestión fault-tolerant de logs JSONL con principios fail-closed.
- **Soporte Declarativo Avanzado**: DDM (Apple), DSC (Windows) y AMAPI (Android).
- **Dashboard UI / UX**: Interfaz React embebida completa con vistas de mapa interactivas, gestión de incidentes y simulación de flota en vivo.

---

## EXPLORE: Horizonte Soñador NOVA (Propuestas para Hermes)

Propuestas de descubrimiento estratégico para llevar la seguridad geográfica local a la siguiente frontera. Ver detalle en `docs/product/nova-visionary-features.md`.

### 1. Geofencing Temporal y Predictivo Cero-Cloud
- **Iniciativa**: Detección de desviaciones de ruta y cálculo de riesgo predictivo mediante modelos probabilísticos en memoria (Markov Chains/grafos de tiempo).
- **Paquetes involucrados**: `internal/domain/integrity`, `internal/domain/risk`.

### 2. Hyper-Fencing 3D y Altitud Indoor
- **Iniciativa**: Geocercas en 3D (Latitud, Longitud, Altitud/Planta) utilizando altímetro barométrico local, Wi-Fi RTT y BLE Mesh.
- **Paquetes involucrados**: `internal/domain/geo`, `internal/domain/fence`.

### 3. Malla de Verificación P2P Proximidad Cero-Trust
- **Iniciativa**: Validación cruzada de presencia entre dispositivos corporativos adyacentes vía UWB/BLE para erradicar el GPS Spoofing.
- **Paquetes involucrados**: `internal/domain/integrity`, `internal/domain/risk`.

### 4. Matriz de Defensas Autónomas Cero Latencia
- **Iniciativa**: Ejecución instantánea en microsegundos de respuestas en el borde (aislamiento de memoria, purga de claves) en violaciones críticas.
- **Paquetes involucrados**: `internal/domain/playbook`, `internal/domain/action`.

### 5. Malla de Decepción Geográfica y HoneyFences
- **Iniciativa**: Geocercas señuelo para atrapar malware de suplantación y recolectar evidencia forense OCSF en tiempo real.
- **Paquetes involucrados**: `internal/domain/fence`, `internal/notify`.

### 6. Soberanía de Datos y Cumplimiento Multijurisdiccional Dinámico
- **Iniciativa**: Adaptación automática de políticas de retención y cifrado al cruzar fronteras nacionales (GDPR, ITAR, HIPAA).
- **Paquetes involucrados**: `internal/domain/geo`, `internal/domain/policy`.
