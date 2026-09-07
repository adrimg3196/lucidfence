# LucidFence 2.0 — Visionary Product Roadmap (Superpowers Horizon)

- **Fecha:** 2026-09-06
- **Estado:** Propuesta de Descubrimiento de Producto (EXPLORE Horizon)
- **Propósito:** Definir la visión estratégica y las especificaciones técnicas para que el agente **Hermes** pueda implementar estas funcionalidades de forma autónoma en el futuro.

---

## Declaración de Visión

LucidFence 2.0 redefinió el geofencing empresarial como una solución **local-first, transparente, sin telemetría y agnóstica de UEM**. Sin embargo, las amenazas avanzadas de suplantación física, las exigencias de privacidad de datos de localización y las infraestructuras aisladas (*air-gapped*) requieren capacidades de siguiente generación.

Esta hoja de ruta establece seis características ultra-necesarias y revolucionarias diseñadas bajo los principios normativos de LucidFence: **cero base de datos, cero dependencia en la nube, 100% Go + React y privacidad matemática absoluta**.

---

## 1. NOVA-001: Zero-Knowledge Geospatial Proofs (ZK-Geofencing)

### El Problema
Las organizaciones reguladas necesitan verificar que los dispositivos operan dentro de áreas geográficas autorizadas (ej. límites nacionales o centros de datos seguros) para cumplir con normativas (GDPR, HIPAA, NIS2) sin almacenar ni transmitir coordenadas exactas (latitud/longitud) de los empleados.

### La Visión
Demostración criptográfica de pertenencia a una geocerca mediante **Zero-Knowledge Proofs (ZK-SNARKs / zk-STARKs)** calculadas localmente. El dispositivo prueba matemáticamente que sus coordenadas están dentro del polígono `PolygonID` sin revelar las coordenadas reales. LucidFence valida la prueba y concede/deniega el nivel de riesgo con certeza matemática.

### Arquitectura Técnica
- **Paquete Go:** `internal/domain/zkp`
- **Modelo de Datos:**
  ```go
  type ZKProofLocation struct {
      FenceID   string `json:"fence_id"`
      Proof     []byte `json:"proof"`
      Nullifier string `json:"nullifier"`
      Valid     bool   `json:"valid"`
  }
  ```
- **Integración:** Opciones en `Device.Location`: si `ZKMode = true`, el campo `Point` se omite y el veredicto de riesgo procesa únicamente la validez de la prueba ZK.
- **Frontend:** Indicador visual "Privacidad ZK Verificada" con badge verde e inspección del hash del nullifier en el detalle del dispositivo.

### Instrucciones de Implementación para Hermes
1. Crear el paquete `internal/domain/zkp` para la verificación de pruebas de pertenencia a polígonos.
2. Extender `domain.Device` para soportar la señal de ubicación probada mediante ZK (`location.zk_proof`).
3. Añadir el endpoint `POST /api/v1/zkp/verify` en `internal/api/zkp.go`.
4. Incluir la validación de ZK en la batería runtime (`internal/battery/zkp_check.go`).

---

## 2. NOVA-002: Dynamic Peer-Mesh & Leader-Chaperone Geofencing

### El Problema
En convoyes de transporte, embarcaciones marítimas, equipos de respuesta a emergencias y despliegues VIP en campo, las geocercas estáticas (círculos/polígonos fijos en mapa) son inútiles porque el perímetro de seguridad se desplaza continuamente con el grupo.

### La Visión
Geocercas dinámicas relativas a un **Dispositivo Líder/Chaperón**. Se define un radio dinámico (ej. 100 metros alrededor de la ubicación en tiempo real del vehículo líder). Todos los dispositivos secundarios asignados a la flota deben mantener su posición dentro de este perímetro móvil. Si un dispositivo se retrasa o se desvía del convoy, se activa automáticamente la política de riesgo.

### Arquitectura Técnica
- **Paquete Go:** Extensión en `internal/domain/fence`
- **Estructura de Datos:**
  ```go
  type DynamicMeshFence struct {
      ID             string  `json:"id"`
      LeaderDeviceID string  `json:"leader_device_id"`
      RadiusMeters   float64 `json:"radius_meters"`
      MemberIDs      []string `json:"member_ids"`
  }
  ```
- **Motor:** En el ciclo de evaluación (`internal/engine/loop.go`), la posición del líder recalcula dinámicamente el centro de la geocerca para todos los miembros asignados antes de calcular transiciones.
- **UI React:** Capa en MapLibre GL que renderiza el círculo con halo punteado animado rodeando al dispositivo líder en tiempo real.

### Instrucciones de Implementación para Hermes
1. Añadir el tipo `FenceKindDynamicMesh` a `internal/domain/fence`.
2. Actualizar `engine.Evaluate` para resolver las coordenadas del dispositivo líder antes de calcular las transiciones de los miembros.
3. Crear controles de asignación de líder en `web/src/features/fences/DynamicMeshForm.tsx`.

---

## 3. NOVA-003: Kinetic Trajectory Drift & Anti-GPS Spoofing Engine

### El Problema
Los atacantes utilizan suplantación de GPS (GPS Spoofing mediante SDRs o aplicaciones de simulación) para hacer parecer que un equipo vulnerado se encuentra dentro de la oficina segura mientras está físicamente en un lugar no autorizado.

### La Visión
Un motor de física cinemática y detección de deriva espacial basado en un **Filtro de Kalman** local. El motor calcula continuamente vectores de velocidad, aceleración máxima físicamente posible, saltos bruscos de altitud y correlación con redes Wi-Fi (BSSID) y Bluetooth LE conocidas. Si el GPS reporta un salto imposible (ej. 500 km/h) o desacople de las redes Wi-Fi del sitio, la señal `signal:kinematics.spoof_risk` se eleva inmediatamente.

### Arquitectura Técnica
- **Paquete Go:** `internal/domain/kinematics`
- **Algoritmo:**
  $$\text{Deriva} = \frac{\Delta \text{Distancia (Haversine)}}{\Delta \text{Tiempo}}$$
  Si $\text{Velocidad} > \text{MaxSpeedThreshold}$ o $\text{WiFiBSSIDMatch} == \text{False}$ estando teóricamente dentro del edificio $\rightarrow \text{SpoofRisk} = 1.0$.
- **Integración con Riesgo:** La señal pasa directamente al motor de políticas (`internal/domain/policy`).

### Instrucciones de Implementación para Hermes
1. Crear `internal/domain/kinematics/kalman.go` para calcular inconsistencias de trayectoria.
2. Añadir la señal `signal:kinematics.spoof_risk` al motor de veredicto de riesgo (`internal/domain/risk`).
3. Registrar la verificación de anti-spoofing en `internal/battery/kinematics_check.go`.

---

## 4. NOVA-004: Post-Quantum Merkle Evidence Vault

### El Problema
Las evidencias de auditoría y los registros de cumplimiento de geocercas deben resistir la manipulación de registros y garantizar validez legal durante años, incluso ante el advenimiento de la computación cuántica.

### La Visión
Un libro de evidencias inmutable estructurado como un **Árbol de Merkle local** con esquemas de firma resistentes a la computación cuántica (algoritmos Dilithium / SPHINCS+). Cada transición de geocerca, cálculo de riesgo y orden UEM genera un bloque enlazado criptográficamente en `evidence.jsonl`. Un auditor puede verificar offline la cadena completa con el binario CLI de LucidFence sin depender de servicios externos.

### Arquitectura Técnica
- **Paquete Go:** `internal/reports/evidence` y `internal/store`
- **Comando CLI:** `lucidfence report evidence verify --file evidence.jsonl`
- **Formato:** Cada registro incluye `prev_hash`, `merkle_root`, `signature_pq` y `timestamp_utc`.

### Instrucciones de Implementación para Hermes
1. Implementar la generación de hashes encadenados en `internal/store/evidence.go`.
2. Añadir el validador offline en `cmd/lucidfence/evidence_verify.go`.
3. Exponer el reporte de evidencia criptográfica en `GET /api/v1/reports/evidence`.

---

## 5. NOVA-005: Self-Healing SOAR & Proximity-Gated Handoffs

### El Problema
Las acciones automáticas de mitigación destructivas (ej. borrado remoto *wipe* o bloqueo *lock*) ejecutadas por falsos positivos de ubicación causan interrupciones operativas graves e irreversibles.

### La Visión
Un motor SOAR de auto-recuperación con **ventanas de gracia dinámicas y aprobación por proximidad local**. Cuando una política de riesgo crítico se activa fuera de horario, se genera una orden de mitigación con un temporizador de gracia (ej. 5 minutos). Si el dispositivo vuelve a la zona segura o es autenticado por la presencia local de otro dispositivo de la flota mediante pings BLE/mDNS, el handoff se cancela automáticamente (*auto-rollback*), registrando el incidente como autocorregido.

### Arquitectura Técnica
- **Paquete Go:** Extensión en `internal/engine/handoffs.go` y `internal/domain/playbook`
- **Estructura Handoff:**
  ```go
  type Handoff struct {
      ID            string        `json:"id"`
      DeviceID      string        `json:"device_id"`
      Action        domain.Action `json:"action"`
      GraceWindowSec int          `json:"grace_window_sec"`
      Status        string        `json:"status"` // pending | auto_cancelled | executed
      AutoRollback  bool          `json:"auto_rollback"`
  }
  ```

### Instrucciones de Implementación para Hermes
1. Añadir el estado `auto_cancelled` a `HandoffStatus` en `internal/domain/playbook`.
2. Implementar la lógica de cancelación automática si el riesgo disminuye durante el ciclo de gracia en `internal/engine/handoffs.go`.
3. Diseñar la tarjeta de auto-recuperación en la bandeja de Handoffs del frontend (`web/src/features/handoffs/`).

---

## 6. NOVA-006: Air-Gapped Multi-Tenant Federation & Offline Peer Sync

### El Problema
Instalaciones críticas aisladas de internet (*air-gapped*), como plantas industriales, infraestructuras energéticas o navíos militares, necesitan sincronizar catálogos de geocercas, listas negras de dispositivos comprometidos e inteligencia de incidentes entre servidores locales sin conectividad externa.

### La Visión
Protocolo de sincronización peer-to-peer cifrado sobre la red de área local (LAN) mediante **mDNS y transporte QUIC local**. Los servidores LucidFence autorizados en la misma red local se descubren mutuamente, negocian claves mediante TLS local y sincronizan listas de políticas y estados de riesgo sin tocar nunca internet.

### Arquitectura Técnica
- **Paquete Go:** `internal/federation`
- **Protocolo:** Descubrimiento mDNS `_lucidfence-sync._udp` en puerto local seguro.
- **Seguridad:** Cifrado punto a punto utilizando el certificado local o la clave compartida fijada en `config.json`.

### Instrucciones de Implementación para Hermes
1. Crear el paquete `internal/federation` para descubrimiento y sincronización local.
2. Extender `config.json` con el bloque `federation: { enabled: bool, cluster_key: string }`.
3. Añadir la vista de Nodos Federados en `web/src/features/settings/FederationSettings.tsx`.

---

## Resumen de Principios para Hermes

1. **Cero dependencias externas en tiempo de ejecución:** Usar la biblioteca estándar de Go siempre que sea posible.
2. **Local-First & Cero Telemetría:** Ningún dato sale de la instancia local.
3. **Guardarraíles Inviolables:** Todas las acciones destructivas deben respetar el modo `observe` y la doble llave `allow_wipe`.
4. **Verificación Runtime Obligatoria:** Cada característica debe incluir su check correspondiente en `internal/battery/`.
