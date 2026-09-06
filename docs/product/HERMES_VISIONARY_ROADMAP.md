# 🌌 ROADMAP VISIONARIO DE LUCIDFENCE 2.0 — EL FUTURO SEGÚN EL SOÑADOR

> *"No construimos barreras para encerrar el mundo, sino para otorgarle una coordenada a la libertad."*

Bienvenido, **Hermes**. Este documento contiene la visión de lo que **LucidFence** debe llegar a ser: un sistema de geofencing multi-UEM y evaluación de riesgo espacio-temporal tan avanzado que parezca magia, manteniendo intactos los principios sagrados del proyecto: **local-first, cero telemetría, soberanía absoluta del administrador y software 100% libre y gratuito.**

A continuación se despliegan las **5 Épicas Ultra-Necesarias** diseñadas para que tú, Hermes, las transformes en código, contratos, algoritmos de Go y componentes de React.

---

## 🏛️ ÉPICA I: Geocercas Dinámicas Cinéticas y Corredores Espacio-Temporales Flexibles
**Código Clave:** `EPIC-HYPERGEOFENCE`
**Prioridad:** Alta (Horizonte Próximo)

### 🔮 La Visión Soñadora
Las geocercas estáticas (círculos y polígonos fijos) son reliquias del siglo XX. El mundo físico es fluido. Cuando un convoy corporativo, un equipo de respuesta a emergencias o un ejecutivo se desplaza, la zona segura debe moverse **con ellos**. Soñamos con geocercas que respiren, se expandan y contraigan dinámicamente según la velocidad, el contexto y la proximidad relativa entre dispositivos.

### 📐 Especificación Técnica para Hermes
1. **Geocercas Móviles Relativas (`RelativeKineticFence`):**
   - Una geocerca cuyo centro no es una latitud/longitud fija, sino la coordenada en tiempo real de un dispositivo maestro o un activo móvil (p. ej., un vehículo o un router portátil).
   - Cálculo del radio cinético: $R(v) = R_{base} + \alpha \cdot v$, donde $v$ es la velocidad del dispositivo centro.
2. **Corredores Iso-Crono-Temporales:**
   - Creación de zonas de tolerancia basadas en tiempo de viaje proyectado en lugar de distancia euclidiana estricta.
3. **Cálculo de Envolvente Convexa Flotante (Convex Hull Enclosure):**
   - Agrupación automática de flotas de dispositivos mediante algoritmos de Delaunay / Graham Scan en Go (`internal/domain/geo`) para crear una geocerca protectora automática alrededor del grupo en tiempo real.

### 📋 Lista de Tareas para Hermes
- [ ] Implementar `domain.KineticFence` en `internal/domain/fence/kinetic.go`.
- [ ] Crear el motor de cálculo de Envolvente Convexa (`ConvexHull(points []Point) Polygon`) con complejidad $\mathcal{O}(n \log n)$ en `internal/domain/geo`.
- [ ] Añadir endpoints en API REST `/api/v1/fences/kinetic` y vincular con el motor de evaluación en `internal/engine`.
- [ ] Componente React en `web/src/features/fences` para renderizar geocercas cinéticas pulsantes animadas en MapLibre GL.

---

## ⚡ ÉPICA II: Motor Predictivo de Inercia y Gravedad Local (Cero Telemetría)
**Código Clave:** `EPIC-INERTIA-RISK`
**Prioridad:** Alta (Horizonte Medio)

### 🔮 La Visión Soñadora
No queremos reaccionar a la violación de una geocerca cuando esta ya ha ocurrido. Queremos **predecirla segundos o minutos antes** sin enviar un solo byte a la nube. Mediante física de partículas, vectores de aceleración e inercia local, LucidFence anticipará si un dispositivo está en trayectoria inminente de salir de una zona segura o entrar en una zona de alto riesgo.

### 📐 Especificación Técnica para Hermes
1. **Vectores de Inercia Espacio-Temporal (`InertialTrajectory`):**
   - Extrapolación polinómica de segundo orden basada en los últimos $N$ reportes de ubicación: $\vec{P}(t + \Delta t) = \vec{P}_0 + \vec{v}_0 \Delta t + \frac{1}{2} \vec{a} (\Delta t)^2$.
2. **Cálculo de Tiempo Mínimo de Intersección (TTC - Time To Cross):**
   - Intersección rayo-segmento para calcular $TTC$ en segundos contra los límites del polígono más cercano.
3. **Puntuación Proyectada de Riesgo (`ProjectedRiskScore`):**
   - Si $TTC < T_{threshold}$, elevar el riesgo preventivo (`Severity: Warning / Critical`) y disparar acciones anticipadas no destructivas (p. ej., `notify`, `message` o alerta preventiva).

### 📋 Lista de Tareas para Hermes
- [ ] Desarrollar `internal/domain/geo/trajectory.go` para cálculo de vectores de aceleración y proyección cinemática.
- [ ] Ampliar el veredicto de riesgo en `internal/domain/device/risk.go` con `ProjectedTrajectory` y `TimeToViolation`.
- [ ] Crear reglas de política cinemática (`Op: ttc_lt`, `Op: trajectory_heading`).
- [ ] Renderizar en el mapa del Dashboard las flechas de vector de inercia y conos de probabilidad para cada dispositivo.

---

## 🤝 ÉPICA III: Orquestación Post-Humana y SOAR Simbiótico Abierto
**Código Clave:** `EPIC-SYMBIOTIC-SOAR`
**Prioridad:** Media (Horizonte Avanzado)

### 🔮 La Visión Soñadora
Imagina un sistema donde las decisiones defensivas complejas no requieren intervención humana manual en cada paso rutinario, pero mantienen **guardarraíles inviolables**. Un SOAR (Security Orchestration, Automation, and Response) simbiótico que aprende del comportamiento histórico de resoluciones del administrador para sugerir o solicitar aprobaciones inteligentes de handoffs con un solo clic o interacción por voz/MCP.

### 📐 Especificación Técnica para Hermes
1. **Árboles de Decisión Múltiple y Handoffs Contextuales:**
   - Handoffs enriquecidos con análisis de impacto antes de la aprobación (p. ej., cuántos usuarios se verán afectados, estado de cifrado del disco, estado de batería antes de un `wipe` o `lock`).
2. **Motor de Playbooks Multiasociativo:**
   - Ejecución de cadenas de acciones en paralelo y en serie con condiciones de parada inmediatas (`short-circuiting`).
3. **Integración Profunda con MCP Local (Model Context Protocol):**
   - Permitir a un agente de IA local (como Hermes u Ollama) auditar y proponer borradores de playbooks analizando los registros de incidentes sin exfiltrar datos fuera de la máquina.

### 📋 Lista de Tareas para Hermes
- [ ] Expandir `internal/domain/playbook` con soporte para grafos dirigidos acíclicos (DAG) de acciones.
- [ ] Añadir simulación previa al handoff en `internal/engine/handoffs.go` con desglose de impacto de seguridad.
- [ ] Ampliar las capacidades de `internal/mcp` para permitir lectura analítica de incidentes y simulación de impacto.
- [ ] UI de la bandeja de Handoffs en React con visualización de línea de tiempo y evaluación de impacto.

---

## 🛡️ ÉPICA IV: Malla de Proximidad Peer-to-Peer y Pruebas de Presencia Cero-Conocimiento
**Código Clave:** `EPIC-P2P-MESH-ZK`
**Prioridad:** Exploratoria

### 🔮 La Visión Soñadora
En entornos sin cobertura celular o GPS degradado (túneles, bunkers, interiores de edificios, misiones de campo), los dispositivos deben auditarse entre sí. Si tres dispositivos corporativos están juntos, pueden validar colectivamente su presencia y certificar que la zona es confiable utilizando señales Wi-Fi/Bluetooth de proximidad local sin depender de un satélite.

### 📐 Especificación Técnica para Hermes
1. **Matriz de Co-Presencia Red de Área Local (`LocalMeshProximity`):**
   - Grafo de adyacencia calculado en `internal/posture/mesh.go` basándose en coincidencia de BSSID, potencia de señal RSSI y descubrimientos MDNS locales.
2. **Atestación Cruzada de Integridad de Ubicación:**
   - Si un dispositivo afirma estar en una coordenada pero sus "vecinos" en la malla detectan una red BSSID completamente distinta, marcar inmediatamente su ubicación como `spoofed/untrusted`.
3. **Firmas de Presencia Criptográfica:**
   - Generación de hashes de prueba de grupo firmado en disco local para auditoría forense sin revelar la identidad de los usuarios individuales.

### 📋 Lista de Tareas para Hermes
- [ ] Definir estructuras `MeshGraph`, `MeshNode` y `ProximityEdge` en `internal/domain/device`.
- [ ] Implementar el algoritmo de consenso de ubicación por mayoría en `internal/engine/mesh_validation.go`.
- [ ] Extender el informe de evidencia (`internal/reports/evidence.go`) con la cadena de prueba de presencia en malla.
- [ ] Añadir la vista de Grafo de Malla Local en el Dashboard utilizando diagramas de red interactivos.

---

## ⏳ ÉPICA V: Reconstrucción Temporal 4D y Taller de Simulación Catastrófica (What-If 2.0)
**Código Clave:** `EPIC-4D-TEMPORAL-REPLAY`
**Prioridad:** Media

### 🔮 La Visión Soñadora
Poder viajar en el tiempo dentro del dashboard. Un control de reproducción temporal (play, pause, rewind, 10x) que permita al administrador volver al momento exacto en que ocurrió una brecha de seguridad hace 3 días, ver cómo los dispositivos se movían por el mapa, cómo subió el nivel de riesgo y exactamente qué regla o guardarraíl se activó o se bloqueó.

### 📐 Especificación Técnica para Hermes
1. **Motor de Reproducción de Eventos Paginado en Tiempo Real:**
   - Lector de streams JSONL (`events.jsonl`, `actions.jsonl`) con búsqueda binaria por timestamp para rebobinado eficiente $\mathcal{O}(\log N)$.
2. **Simulador "What-If" Interactivo de Cambios Históricos:**
   - ¿Qué habría pasado si la política $X$ hubiese estado activa durante la tormenta del martes? El motor re-ejecuta el histórico en memoria en milisegundos y genera un reporte comparativo delta.
3. **Exportador de Evidencia de Video 4D / Canvas GIF:**
   - Generación de animaciones o secuencias de snapshots de mapa para investigaciones de auditoría.

### 📋 Lista de Tareas para Hermes
- [ ] Implementar `internal/store/replay.go` con indexación por timestamp para archivos JSONL.
- [ ] Crear el endpoint REST `/api/v1/engine/replay` con parámetros `from`, `to`, `speed` y `step`.
- [ ] Diseñar el componente `TimeSlider` y `PlaybackControls` en React con sincronización del estado global del mapa.
- [ ] Añadir la vista de comparación de simulaciones "What-If Delta" en `web/src/features/policies`.

---

## 👑 MENSAJE FINAL PARA HERMES

Hermes, cada una de estas épicas respeta la arquitectura de **un solo binario en Go**, **sin bases de datos externas**, **interfaz en React embebida**, **guardarraíles inviolables (`observe` por defecto)** y **cero exfiltración de telemetría**.

Cuando estés listo para abordar cualquiera de estas épicas:
1. Revisa los límites de arquitectura en `ARCHITECTURE.md`.
2. Crea las pruebas unitarias y casos dorados primero.
3. Extiende la batería runtime (`internal/battery`).
4. Mantén limpia la separación entre dominio, motor, store y API.

*¡El mapa está trazado. Construye el futuro!*
