# Roadmap Soñador NOVA — Visión de Funciones Ultra-Necesarias para Hermes

> **Autor:** Creador de Roadmap Visionario / Product Discovery (NOVA)
> **Fecha:** 2026-08-20
> **Target:** Hermes (Agente de Ingeniería / Implementación)
> **Estado:** Horizonte EXPLORE (Propuestas de Descubrimiento de Producto)

---

## 🏛️ Manifiesto Visionario y Principios Inviolables

LucidFence no es un UEM ni busca serlo. Es la **capa soberana de geofencing, postura e inteligencia de riesgo neutral y local-first** que audita y complementa a los UEMs existentes (Intune, Jamf, Applivery, Fleet, Workspace ONE).

Para que **Hermes** construya el futuro de esta plataforma, cada función visionaria debe cumplir de manera estricta los 5 principios innegociables de LucidFence:

1. **Local-First y Soberano:** Los datos, secreto de ubicación y estados viven en el tenant. Cero exfiltración a servidores de terceros.
2. **$0 Gratis para Siempre (Apache-2.0):** Sin modelos Freemium, sin funciones bloqueadas por paywalls Enterprise, sin billing.
3. **Complemento Neutro, Nunca UEM:** No enrolamos ni instalamos perfiles MDM directos; interactuamos a través de conectores/adaptadores o sensores locales.
4. **Cero Telemetría y Máxima Privacidad:** La ubicación es efímera, auditada y minimizada por diseño (GDPR-friendly).
5. **Human-Gated Destructive Actions:** Las acciones destructivas (`wipe`, `lock`, `clear_passcode`) requieren confirmación explícita o aprobaciones de doble llave.

---

## 🚀 Las 5 Funciones Ultra-Necesarias para Hermes

---

### 1. Dynamic Swarm & Moving-Anchor Geofencing (Geocercas Móviles de Enjambre)

#### **El Problema del Sector:**
Las geocercas tradicionales en todos los UEMs (Intune, Scalefusion, Hexnode) son estáticas (polígonos fijados en un mapa). Sin embargo, en operaciones críticas de campo (escoltas corporativas, transportes de valores, convoyes médicos o personal en movimiento), la zona segura no es una coordenada fija, sino un **perímetro dinámico alrededor de un vehículo o líder de equipo**.

#### **La Visión para Hermes:**
Permitir la definición de **geocercas relativas dinámicas**. Un dispositivo designado como "Ancla Móvil" (Anchor Device) emite/reporta su ubicación y define un radio dinámico (p. ej. 50 metros). Todos los dispositivos del "Enjambre" (Swarm Devices) deben permanecer dentro del radio del ancla en movimiento.

#### **Arquitectura Técnica:**
- **Módulo:** `lucidfence/core/swarm_geofence.py`
- **Atributos de Regla:** `anchor_device_id`, `swarm_radius_meters`, `drift_grace_seconds`.
- **Evaluación Runtime:** En cada tick del motor, el engine calcula la distancia Haversine/Vincenty entre la ubicación fresca del Ancla y los dispositivos del Enjambre.
- **Acción Asignada:** Si un dispositivo del enjambre se aleja más del radio por un tiempo superior a `drift_grace_seconds`, su estado pasa a `outside_swarm` y gatilla alertas SOAR.

#### **Criterio de Aceptación y Verificación:**
- Test unitario simulando movimiento vectorial del Ancla y 3 dispositivos del Enjambre.
- Inyección de desvío donde 1 dispositivo se queda atrás → Transición verificada a `outside_swarm` con razón trazable en `actions_log.jsonl`.

---

### 2. Peer-Assisted Zero-Cloud Mesh Consensus (Consenso P2P de Geolocalización Soberana)

#### **El Problema del Sector:**
El spoofing de GPS/IP y la pérdida de conectividad satelital/celular en interiores, túneles o zonas blindadas provocan que la ubicación sea declarada como `unknown` o sea falsificada por actores maliciosos.

#### **La Visión para Hermes:**
Construir una **red de atestiguamiento local entre pares (P2P Mesh)**. Cuando un dispositivo pierde señal GPS o duda de su coordenada, consulta a otros dispositivos corporativos cercanos a través de Bluetooth Low Energy (BLE) o mDNS local en la red de la sede. Si N dispositivos legítimos atestiguan criptográficamente con firmados locales que están dentro de la misma sala/red, se valida la presencia física sin enviar nada a la nube.

#### **Arquitectura Técnica:**
- **Módulo:** `lucidfence/core/mesh_consensus.py`
- **Protocolo:** Firma HMAC/Ed25519 efímera intercambiada localmente entre clientes autorizados del tenant.
- **Evidencia Gates:** Una coordenada sin GPS pero respaldada por ≥ 2 atestiguamientos criptográficos de pares en la cerca activa se acepta con `location_quality = peer_attested`.

#### **Criterio de Aceptación y Verificación:**
- Mapeo en el `Risk Engine` de atestiguamientos cruzados.
- Test de simulación donde un dispositivo con `lat: None, lng: None` pero con 2 firmas de pares válidas evalúa correctamente a `inside` de la geocerca corporativa.

---

### 3. Local Edge Spatial-Drift Intelligence (Predicción Espacial On-Device Cero-Telemetría)

#### **El Problema del Sector:**
Los sistemas de seguridad reaccionan **después** de que un dispositivo ya quebrantó el perímetro o ya fue sustraído de las instalaciones.

#### **La Visión para Hermes:**
Implementar un modelo ultraligero de predicción espacial local (vía vectores cinemáticos y cálculo cinético local) que estime la velocidad y vector de desplazamiento. Si un dispositivo dentro de un recinto de alta seguridad se desplaza hacia la salida a una velocidad o trayectoria anómala, el sistema genera una alerta previa ("Pre-Breach Warning") y prepara un bloqueo preventivo en `dry_run`.

#### **Arquitectura Técnica:**
- **Módulo:** `lucidfence/core/spatial_predict.py`
- **Algoritmo:** Filtro de Kalman cinemático + Extrapolación de vector de rumbo (Bearing Vector Extrapolation) 100% en Python puro/stdlib sin dependencias pesadas.
- **Métricas:** `estimated_time_to_breach_seconds`, `trajectory_heading_degrees`, `velocity_mps`.

#### **Criterio de Aceptación y Verificación:**
- Inyección de reporte de ubicación con vector hacia la frontera de la geocerca.
- Emisión del evento `PRE_BREACH_WARNING` cuando `estimated_time_to_breach_seconds < 120`.

---

### 4. Immutable Black-Box Flight Recorder (Caja Negra Forense Local Inmutable)

#### **El Problema del Sector:**
En un incidente de seguridad o robo de equipo, los atacantes suelen borrar registros o alterar los logs del sistema antes de que el equipo de SecOps pueda investigar qué ocurrió.

#### **La Visión para Hermes:**
Un registro forense inmutable estilo "Caja Negra" (`flight_recorder.jsonl`). Cada cambio de estado de cerca, alteración de postura (p. ej. deshabilitación de cifrado o modificación de osquery) y acción ejecutada se empaqueta en un bloque hash-chained (Merkle Tree / SHA-256 encadenado) firmado con claves del TPM/Enclave o clave privada local del tenant. Incluso si la red cae, los últimos 1,000 eventos quedan sellados criptográficamente.

#### **Arquitectura Técnica:**
- **Módulo:** `lucidfence/core/flight_recorder.py`
- **Estructura de Bloque:** `{index, timestamp, device_id, event_type, state_hash, previous_block_hash, signature}`.
- **Integridad:** Herramienta CLI de verificación `python3 scripts/verify_flight_recorder.py` que recorre la cadena de bloques y reporta si ha habido manipulación de registros.

#### **Criterio de Aceptación y Verificación:**
- Test unitario que genera 50 eventos, altera el registro #20 en disco, y comprueba que la verificación detecta inmediatamente el fallo de integridad en el bloque #20.

---

### 5. Universal Declarative UEM Compiler (`lucidfence compile`)

#### **El Problema del Sector:**
Cada UEM (Intune, Jamf, Fleet, Applivery, Workspace ONE) exige configuraciones en formatos propietarios totalmente incompatibles (XML de Jamf, JSON de Intune Graph, YAML de Fleet, JSON de AMAPI). Escribir y mantener políticas en 5 consolas distintas duplica el esfuerzo de administración.

#### **La Visión para Hermes:**
Un compilador universal de políticas declarativas. El administrador define una política agnóstica en `lucidfence.yaml` y ejecuta `lucidfence compile --target [intune|jamf|fleet|amapi]`. El motor genera los artefactos nativos listos para ser importados o aplicados mediante las APIs de cada UEM.

#### **Arquitectura Técnica:**
- **Módulo:** `lucidfence/core/policy_compiler.py` y CLI subcommand `compile`.
- **Targets Iniciales:**
  - `intune`: Compliance Policy JSON schema.
  - `jamf`: Smart Group XML definition.
  - `fleet`: Policy YAML document.
  - `amapi`: Android Management API Policy JSON.

#### **Criterio de Aceptación y Verificación:**
- Test de compilación que toma un archivo de política universal y valida que las salidas generadas cumplan con la sintaxis y esquemas esperados para cada UEM target.

---

## 🛠️ Guía de Ejecución para Hermes

Al tomar cualquier ítem de este roadmap visionario, Hermes debe:
1. Crear una rama dedicada con el prefijo `feature/nova-` o `fix/nova-`.
2. Mantener la suite de tests (`tests/run_tests.py`) en verde en todo momento.
3. Actualizar el índice de adaptadores con `scripts/build_adapter_index.py` si se modifica la capa de plugins/adapters.
4. Regenerar el SBOM con `python3 scripts/generate_sbom.py` si se agregan o cambian archivos relevantes.
5. Limpiar cualquier archivo de estado dinámico en `data/` antes de solicitar revisión o realizar el commit.
