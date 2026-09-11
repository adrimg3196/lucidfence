# 🌟 Roadmap Soñador de Funciones Ultra-Necesarias para Hermes

> **Documento de Visión y Especificación de Producto para la Flota de Desarrollo Hermes**
> *Autor:* Creador de Roadmap Soñador & Estratega de Producto LucidFence
> *Filosofía:* Innovación Radical sin Compromiso de Privacidad · Local-First Absoluto · Zero-Telemetry · Open Source (Apache-2.0)

---

## 🎯 Manifiesto de Visión

LucidFence 2.0 ha demostrado que es posible construir un motor de geofencing multi-UEM ultrarrápido, explicable y soberano en Go. Pero el futuro de la seguridad física y digital de los dispositivos corporativos exige dar un salto de gigante: **de la reacción basada en reglas estáticas a la Inteligencia Ambiental Soberana**.

Este documento especifica **6 funciones ultra-necesarias y revolucionarias** que aún no existen en el producto comercial tradicional ni en las soluciones SaaS propietarias, diseñadas minuciosamente para que **Hermes** las cree e integre en el backend en Go y el dashboard en React.

---

## 🚀 Especificación de Características (Horizonte EXPLORE)

---

### 🔮 NOVA-01: Predicción Local de Trayectorias y Anomalías Spatio-Temporales (Edge ONNX ML Engine)

#### 💡 ¿Por qué es Ultra-Necesaria?
Las geocercas tradicionales son reactivas: solo se activan cuando el dispositivo ya cruzó el perímetro. Si un portátil corporativo de alta confidencialidad viaja a 120 km/h directamente hacia una frontera de alto riesgo o una zona no autorizada, esperar a que cruce la línea es demasiado tarde.

#### 🛠️ Diseño Técnico e Implementación para Hermes:
1. **Motor In-Process ONNX Runtime (Go):** Incorporar un modelo ultraligero de inteligencia espacio-temporal (LSTM/Transformer cuantizado a INT8) ejecutado mediante binding puro en Go (`github.com/owulveryck/onnx-go` o motor WASM embebido).
2. **Entrenamiento y Modelado 100% Local:** El modelo aprende los patrones de desplazamiento habituales de la flota analizando exclusivamente los archivos `events.jsonl` localizados en el disco del tenant. **Cero bytes salen de la máquina**.
3. **Señal de Riesgo Preventivo (`predictive_deviation`):**
   - Inyecta una nueva señal en `internal/domain/risk`: `RiskSignalPredictiveAnomaly`.
   - Genera una alerta temprana $N$ minutos antes de una violación prevista de corredor o geocerca, permitiendo aplicar un bloqueo preventivo antes del traspaso físico.

---

### 🛡️ NOVA-02: Verificación Cruzada P2P Mesh de Proximidad (Proximity Zero-Trust Witness Protocol)

#### 💡 ¿Por qué es Ultra-Necesaria?
El GPS Spoofing y el falseamiento de ubicación por software/hardware (SDR, moka-apps en Android/iOS) invalida los reportes convencionales de ubicación. Un atacante puede hacer que un dispositivo en un entorno hostil simule estar dentro de las oficinas centrales.

#### 🛠️ Diseño Técnico e Implementación para Hermes:
1. **Testigos Criptográficos Locales (Local Peer Witnessing):**
   - Dispositivos gestionados en la misma red local (mDNS/UDP broadcast o Bluetooth Low Energy) intercambian tokens de atestación firmados con efímeras claves asimétricas.
2. **Prueba de Co-Ubicación Criptográfica (Proof of Proximity):**
   - Un dispositivo solo se considera "verdaderamente dentro de la geocerca de la oficina" si al menos $K$ dispositivos vecinos atestiguan su presencia física con un sello temporal indiscutible.
3. **Módulo Go:** `internal/domain/integrity/mesh.go`
   - Valida la coincidencia de firmas de testigos sin necesidad de triangular coordenadas con servicios de mapas externos.

---

### ⚡ NOVA-03: Geocercas Efímeras Autónomas por Inteligencia de Amenazas Contextuales (Dynamic Threat Geofencing)

#### 💡 ¿Por qué es Ultra-Necesaria?
Los incidentes de ciberseguridad y físicos (p. ej., redes Wi-Fi rogue desatadas en un aeropuerto específico, conferencias de hackers, desastres naturales o protestas con confiscación de dispositivos) ocurren de forma imprevista y requieren perímetros de seguridad inmediatos.

#### 🛠️ Diseño Técnico e Implementación para Hermes:
1. **Suscripción Local a Feeds de Amenazas (Local Feed Ingestion):**
   - Módulo en `internal/posture/threats.go` que consume feeds públicos o privados firmados (JSON/STIX2) con allowlist de egress estricta.
2. **Generación Automática de Geocercas Efímeras (`FenceKindEphemeral`):**
   - Cuando se detecta un BSSID de Wi-Fi malicioso conocido o un incidente geolocalizado en una coordenada, LucidFence crea automáticamente una geocerca de cuarentena con caducidad $T$ (TTL).
3. **Regla de Evaluación:**
   - Si un dispositivo entra en la zona efímera de amenaza, activa automáticamente el playbook de mitigación (p. ej., forzar VPN, deshabilitar Wi-Fi o solicitar aprobación de handoff).

---

### 🔐 NOVA-04: Bóveda de Evidencia con Firma Post-Cuántica (Post-Quantum Hardware Vault)

#### 💡 ¿Por qué es Ultra-Necesaria?
Para auditorías legales, juicios laborales o investigaciones forenses de fuga de información, las trazas de ubicación tradicionales pueden ser impugnadas. Con el advenimiento de la computación cuántica, las firmas RSA y ECDSA convencionales serán vulnerables.

#### 🛠️ Diseño Técnico e Implementación para Hermes:
1. **Atadura a Hardware Seguro (TPM 2.0 / Secure Enclave):**
   - Extensión de `internal/domain/integrity` para validar atestaciones de hardware emitidas por el chip de seguridad del dispositivo.
2. **Esquema de Firma Post-Cuántica (ML-DSA / CRYSTALS-Dilithium):**
   - Implementación en Go del estándar NIST FIPS 204 para firmar el log de evidencias en `actions.jsonl` y los informes de auditoría PDF/HTML.
3. **Verificador Offline Independiente:**
   - CLI `lucidfence verify-evidence --file report.json` que comprueba la cadena de hashes e inmunidad cuántica sin requerir conexión al servidor ni a internet.

---

### 🌐 NOVA-05: Malla Multi-Tenant Aislada de Alta Disponibilidad y Failover Offline (Air-Gapped Mesh Sync)

#### 💡 ¿Por qué es Ultra-Necesaria?
En entornos críticos (defensa, infraestructuras estratégicas, buques, centros de datos aislados o embajadas), la conexión a la nube es inexistente o intermitente. LucidFence debe funcionar en alta disponibilidad local sin depender de ningún punto único de fallo.

#### 🛠️ Diseño Técnico e Implementación para Hermes:
1. **Protocolo P2P Anti-Entropía (Gossip Protocol):**
   - Implementación pura en Go en `internal/store/sync.go` basada en CRDTs (Conflict-free Replicated Data Types).
2. **Sincronización P2P Cifrada de Par a Par:**
   - Varias instancias locales de LucidFence en la misma red privada sincronizan de forma atómica sus estados de dispositivos, incidentes y handoffs sin centralización.
3. **Consenso Local:**
   - Si un nodo cae, la evaluación del riesgo y la ejecución de acciones sobre el UEM continúa de manera transparente desde cualquier otro nodo con capacidades activas.

---

### ⌛ NOVA-06: Handoffs Criptográficos con Candado Temporal y Protocolo "Dead-Man's Switch"

#### 💡 ¿Por qué es Ultra-Necesaria?
Cuando ejecutivos o personal clave viajan con información confidencial a jurisdicciones con riesgo de incautación forzosa de dispositivos, el administrador no siempre tiene conectividad ni tiempo para ejecutar un borrado manual remoto.

#### 🛠️ Diseño Técnico e Implementación para Hermes:
1. **Interruptor de Hombre Muerto Local (Dead-Man's Switch):**
   - Si un dispositivo entra en una geocerca de alto riesgo geopolítico y no recibe un heartbeat de verificación del usuario/admin en un intervalo $T$ configurado, el motor ejecuta la acción programada de forma autónoma.
2. **Cifrado de Custodia Temporal (Time-Lock Encryption):**
   - Las claves de desencriptado o restauración de parámetros de seguridad quedan bloqueadas criptográficamente hasta una fecha/hora especificada o mediante autorización multifirma de $M$ de $N$ custodios (`internal/auth/custody.go`).

---

## 🗺️ Matriz de Priorización para Hermes

```
   Alto Impacto  ▲
                 │   [NOVA-01] Predicción ML        [NOVA-03] Threat Geofencing
                 │   [NOVA-02] P2P Mesh Witness     [NOVA-06] Dead-Man's Switch
                 │
                 │   [NOVA-04] Post-Quantum Vault   [NOVA-05] Air-Gapped Sync
                 └─────────────────────────────────────────────────────────►
                                                               Complejidad
```

---

## 📋 Directiva Final para Hermes

Hermes, cuando estés listo para abordar el horizonte **EXPLORE**:
1. Implementa cada función respetando los límites de líneas de código Go (≤ 400 líneas por fichero) y TypeScript (≤ 300 líneas por componente).
2. Garantiza que **cero datos de ubicación salgan del proceso local**.
3. Añade la comprobación correspondiente en `internal/battery` para asegurar que cada claim de producto se verifique en vivo durante la CI.
