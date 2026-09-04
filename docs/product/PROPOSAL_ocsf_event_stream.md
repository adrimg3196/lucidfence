# ✨ Bus Criptográfico de Eventos OCSF y Stream SOC Local-First («OCSF Event Stream & Local SIEM Connector»)

## 1. Resumen ejecutivo

Los Centros de Operaciones de Seguridad (SOC) y equipos de SecOps gastan recursos significativos escribiendo y manteniendo conectores y parsers a medida para ingestar alertas de herramientas de geofencing y gestión de endpoints en sus plataformas SIEM/XDR (Splunk, Microsoft Sentinel, Elastic Security, AWS Security Lake). La falta de un formato estándar genera cuellos de botella en la ingesta y dificulta la correlación de incidentes. Proponemos el **Bus Criptográfico de Eventos OCSF y Stream SOC Local-First**: un motor de serialización y transmisión local que convierte instantáneamente todos los veredictos de geocercas, violaciones de postura y eventos de remediación SOAR de LucidFence al esquema estándar internacional OCSF (Open Cybersecurity Schema Framework - categoría Findings, clase Detection Finding). Toda alerta generada por LucidFence se emite en formato OCSF nativo firmado con hash SHA-256 encadenado, permitiendo su ingesta directa e inmediata por cualquier SIEM corporativo desde la máquina local del tenant, sin exfiltración de datos hacia nubes intermedias.

## 2. Propuesta en una frase

«Para los **equipos de SecOps y Analistas de SOC**, que necesitan **integrar alertas de geofencing y postura en su SIEM corporativo sin desarrollar parsers propietarios ni enviar datos a nubes de terceros**, proponemos el **Bus de Eventos OCSF Local-First**, que permite **emitir eventos de seguridad normalizados al estándar OCSF v1.1.0 firmados criptográficamente desde el propio entorno del tenant**, a diferencia de **los agentes UEM propietarios que utilizan formatos JSON opacos y requieren conectores cloud de pago**.»

## 3. Problema

- **Persona:** Analista de SOC, Ingeniero de Detección (Detection Engineer) y CISO.
- **Situación:** Un SOC supervisa miles de eventos de seguridad en Splunk o Microsoft Sentinel. Cuando LucidFence detecta una violación de geoperímetro o una manipulación de ubicación, el evento debe llegar al SIEM para correlacionarse con el tráfico de red y los logs de identidad (Okta/Entra ID).
- **Trabajo por realizar:** Normalizar e ingestar eventos de seguridad espacial y postura en tiempo real dentro del pipeline de telemetría del SOC sin costo adicional de desarrollo o licencias.
- **Fricción actual:** Los productos de MDM/UEM emiten eventos con esquemas propietarios incoherentes, lo que obliga al equipo de ingeniería de datos a escribir expresiones regulares y parsers personalizados para cada herramienta.
- **Impacto:** Retrasos en la detección de incidentes, costos elevados de mantenimiento de parsers y fallos de correlación en el SIEM.
- **Solución utilizada hoy:** Parsers personalizados desarrollados manualmente en Logstash, Fluentd o pipelines de Splunk.

## 4. Evidencia

- **HECHO:** El backlog de producto en `docs/internal/product/BACKLOG.md` clasifica el Ítem #17 ("Eventos normalizados OCSF hacia SIEM/ITSM") con veredicto **SÍ** e impacto 3/5.
- **HECHO:** LucidFence ya cuenta con un sistema de notificación de incidentes y webhooks configurables (`lucidfence/core/incident_notifications.py`).
- **HECHO:** OCSF (Open Cybersecurity Schema Framework) se ha consolidado como el estándar abierto impulsado por la industria (AWS, Splunk, IBM, Palo Alto, Cloudflare) para normalización de eventos de seguridad.
- **INFERENCIA:** Proporcionar eventos en OCSF v1.1.0 nativo elimina cualquier barrera de adopción en empresas con SIEMs modernos.
- **HIPÓTESIS:** La compatibilidad OCSF inmediata facilitará la aprobación de LucidFence por parte de los equipos de arquitectura de seguridad enterprise.

## 5. Por qué ahora

1. **Adopción masiva de OCSF:** AWS Security Lake, Microsoft Sentinel y Splunk nativamente soportan ingesta OCSF en 2026.
2. **Exigencia de interoperabilidad:** Equipos de SOC rechazan herramientas aisladas que no se integran de forma transparente en su bus de eventos.
3. **Estructura limpia en LucidFence:** Los veredictos de geocerca e incidentes de postura en LucidFence contienen exactamente la metainformación exigida por la clase OCSF `Detection Finding` (actividades, gravedad, dispositivo, geolocalización, marcas temporales).

## 6. Por qué este producto

- **Alineación total con "Local-First" y Privacidad:** El formateador OCSF se ejecuta en la máquina del tenant; el evento OCSF se envía directamente al endpoint SIEM elegido por el cliente (vía webhook local, syslog o HTTP Event Collector).
- **Inmutabilidad y Firma Criptográfica:** Cada payload OCSF generado incorpora el digest SHA-256 encadenado del registro de evidencias de LucidFence.
- **Cero licencias de terceros:** Implementación pura en Python stdlib sin dependencias de SDKs externos pesados.

## 7. Experiencia propuesta

1. **Configuración:** En la configuración de webhooks o SIEM de LucidFence, el admin activa la opción **"Formato OCSF (v1.1.0)"** para las alertas de incidentes.
2. **Generación de Evento:** Cuando el engine detecta una transición de geocerca (p. ej. entrada no autorizada en zona de riesgo) o un fallo de postura (cifrado desactivado), el módulo `ocsf.py` transforma la alerta interna en un documento JSON OCSF `Detection Finding` (Category 2: System Activity, Class 2004: Detection Finding).
3. **Payload Normalizado:** El evento contiene:
   - `activity_id`: ID de actividad (1: Create, 2: Update).
   - `severity_id`: Gravedad normalizada (Informational, Low, Medium, High, Critical).
   - `device`: Objeto de dispositivo con IP, nombre, SO e identificadores únicos.
   - `location`: Coordenadas de geolocalización y nombre del geoperímetro.
   - `evidence`: Hash SHA-256 inmutable vinculado al registro de auditoría local.
4. **Transmisión Segura:** El evento se emite hacia el SIEM configurado mediante el webhook HTTPS con firma HMAC-SHA256 existente.

## 8. Momento mágico

«El ingeniero de SOC conecta el webhook de LucidFence a su instancia de Splunk o Microsoft Sentinel y observa cómo las alertas de geofencing e integridad de endpoints se mapean automáticamente en sus paneles corporativos sin haber tenido que escribir una sola línea de código de parsing.»

## 9. Diferenciación y ventaja defensiva

- **Estándar abierto de la industria:** Supera a las soluciones de UEM que fuerzan el uso de APIs o formatos JSON propietarios.
- **Firma de evidencia criptográfica integrada:** Garantiza la no manipulación del evento desde su generación en el endpoint hasta su ingesta en el SIEM.
- **Formato nativo sin capas intermedias:** No requiere agentes de conversión ni servicios SaaS adicionales.

## 10. Alcance por etapas

### Experimento
Crear en `lucidfence/core/ocsf.py` las funciones de mapeo de incidentes de LucidFence hacia el esquema JSON OCSF `Detection Finding` (clase 2004), validando contra el esquema oficial.

### Primera versión (Thin Slice)
Añadir soporte de formato OCSF en el emisor de webhooks de `incident_notifications.py`, permitiendo seleccionar el formato OCSF o JSON nativo.

### Expansión
Soportar clases adicionales de OCSF como `Device Config State Change` (clase 2001) para cambios en configuraciones de geocercas y postura.

### Visión North Star
Exportador OCSF en tiempo real compatible con conectores de streaming local (Apache Kafka, Vector, Fluentbit) para entornos de alta escala.

## 11. Fuera de alcance

- Almacenamiento centralizado de logs OCSF en servidores de LucidFence.
- Gestión directa de las reglas de correlación internas del SIEM del cliente.

## 12. Implicaciones técnicas

- **Nuevo módulo backend:** `lucidfence/core/ocsf.py` (Python stdlib puro).
- **Entradas:** Estructuras de incidentes y veredictos de `incident_notifications.py` y `engine.py`.
- **Salidas:** Diccionario / JSON conforme a la especificación OCSF v1.1.0 (Class 2004 Detection Finding).
- **Pruebas:** Pruebas unitarias en `tests/test_ocsf.py` validando la presencia de todos los campos obligatorios de la especificación OCSF.

## 13. Seguridad, privacidad y confianza

- **Control total del tenant:** El tenant decide a qué SIEM o endpoint envía sus eventos OCSF.
- **Autenticación HMAC-SHA256:** Cada envío de evento vía webhook utiliza firma HMAC para evitar ataques de suplantación.
- **Sin exfiltración:** Ninguna copia del evento se envía a LucidFence ni a terceros.

## 14. Valor para el negocio

- **Facilidad de integración Enterprise:** Elimina la mayor fricción técnica para el despliegue de LucidFence en infraestructuras de SOC avanzadas.
- **Interoperabilidad:** Posiciona a LucidFence como un ciudadano de primera clase dentro del ecosistema de ciberseguridad moderno.

## 15. Métricas

- **Métrica de resultado:** Reducción a 0 del tiempo de desarrollo de conectores de ingesta por parte de los clientes.
- **Métrica de uso:** Porcentaje de webhooks configurados utilizando la transmisión en formato OCSF.
- **Métrica de calidad:** 100% de cumplimiento del esquema JSON de OCSF v1.1.0 en las pruebas sintácticas.

## 16. Evaluación

- **Problema:** 4/5
- **Alcance:** 5/5
- **Impacto:** 4/5
- **Estrategia:** 5/5
- **Diferenciación:** 5/5
- **Viabilidad:** 5/5 (Serialización stdlib pura)
- **Evidencia:** 4/5
- **Riesgo:** 1/5 (Componente de salida pura)

- **Confianza:** Alta
- **Esfuerzo relativo:** Pequeño-Medio (S-M)
- **Horizonte recomendado:** `EXPLORE`
