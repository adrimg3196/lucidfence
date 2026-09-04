# ✨ Streaming Criptográfico de Eventos OCSF para SIEM/SOC (Open Cybersecurity Schema Framework)

## 1. Resumen ejecutivo

En los centros de operaciones de seguridad (SOC) modernos, la fragmentación de formatos de logs dificulta la correlación de eventos en tiempo real. LucidFence genera hoy eventos de violaciones de geocercas, veredictos de riesgo e incidentes en un formato JSON propietario. Proponemos el **Streaming Criptográfico de Eventos OCSF**: un emisor y formateador local-first que traduce los veredictos de riesgo e incidentes de LucidFence al estándar abierto **OCSF (Open Cybersecurity Schema Framework - Detection Finding Class v1.1+)**. Cada evento transmitido a sistemas SIEM/ITSM (Splunk, Microsoft Sentinel, Elastic, Datadog) incluye la firma de cadena criptográfica de evidencia SHA-256 generada en la propia máquina del tenant, garantizando la inmutabilidad y autenticidad del evento en la plataforma de destino sin depender de intermediarios propietarios en la nube.

## 2. Propuesta en una frase

«Para el **Ingeniero de SOC y Analista de Ciberseguridad**, que necesita **ingerir eventos de ubicación y postura en su SIEM sin construir parsers personalizados**, proponemos el **Streaming Criptográfico OCSF**, que permite **transmitir alertas e incidentes estandarizados y firmados criptográficamente hacia cualquier SIEM/ITSM**, a diferencia de **los sistemas UEM cerrados que exigen APIs propietarias y conectores de pago**.»

## 3. Problema

- **Persona:** SOC Analyst, Security Engineer, SIEM Administrator, Threat Hunter.
- **Situación:** Monitoreo unificado de amenazas de la flota corporativa en el SIEM/SOC de la empresa (Splunk, Microsoft Sentinel, Elastic, Datadog).
- **Trabajo por realizar:** Ingerir eventos de violaciones de perímetro y postura de endpoints en tiempo real para correlacionarlos con alertas de identidad y red.
- **Fricción actual:** Los datos de geocercado y UEM vienen en formatos JSON dispares y propietarios. El equipo de SOC debe escribir y mantener parsers Regex/Logstash a medida para cada plataforma, y no hay garantía criptográfica de que los eventos no hayan sido alterados en tránsito.
- **Impacto:** Retrasos en la detección de amenazas (MTTD elevado), gastos de ingeniería en mantenimiento de integraciones y falta de validez probatoria de los logs ante auditorías forenses.
- **Solución utilizada hoy:** Desarrollo de scripts Python intermedios o compra de conectores de pago en la nube para traducir JSON propietarios a esquemas utilizables.

## 4. Evidencia

- **HECHO:** `lucidfence/core/evidence_export.py` ya genera hashes SHA-256 encadenados e inmutables para cada evento e incidente procesado por LucidFence.
- **HECHO:** `lucidfence/core/webhooks.py` soporta el envío de alertas HTTP/HTTPS autenticadas hacia destinos externos configurables.
- **HECHO:** El backlog de producto en `docs/internal/product/BACKLOG.md` clasifica el Ítem #17 ("Eventos normalizados OCSF hacia SIEM/ITSM") con el veredicto explícito **SÍ** y un impacto de 3-4/5.
- **INFERENCIA:** OCSF se ha consolidado como el estándar de facto impulsado por la Linux Foundation, AWS, Splunk y IBM para la interoperabilidad de ciberseguridad.
- **HIPÓTESIS:** Ofrecer eventos OCSF nativos reducirá a cero el esfuerzo de integración con SIEMs y posicionará a LucidFence como un ciudadano de primera clase en el ecosistema Enterprise SOC.
- **DESCONOCIDO:** Las subclases de OCSF más prioritarias para los usuarios (Detection Finding vs Incident Finding vs Device Config State).

## 5. Por qué ahora

1. **Adopción de OCSF en la Industria:** Splunk, Sentinel, Elastic y Datadog soportan ingesta nativa de OCSF v1.1+.
2. **Infraestructura Existente en LucidFence:** Motor de webhooks (`webhooks.py`) y motor de firma criptográfica de evidencia (`evidence_export.py`) totalmente operativos.
3. **Soberanía y Privacidad:** Al generarse el formato OCSF directamente en la máquina del tenant, la empresa decide a qué SIEM enviar sus datos sin intermediarios SaaS de terceros.

## 6. Por qué este producto

Ningún UEM del mercado emite eventos OCSF firmados criptográficamente desde la máquina del cliente. LucidFence combina el estándar abierto OCSF con la inmutabilidad de hashes encadenados en una solución $0 Free Open Source.

## 7. Experiencia propuesta

1. **Configuración del Webhook OCSF:** El admin configura un webhook en LucidFence seleccionando el formato **OCSF (v1.1 Detection Finding)** y la URL de destino de su SIEM (p. ej. HTTP Event Collector de Splunk o Log Analytics Data Collector de Sentinel).
2. **Generación del Evento:** Ante una salida de geocerca o detección de postura degradada, LucidFence procesa el veredicto de riesgo.
3. **Mapeo y Firma en Local:**
   - Traduce el veredicto a la clase OCSF `Detection Finding` (Class ID 2004).
   - Adjunta el objeto `evidence_chain` con el hash SHA-256 inmutable.
4. **Transmisión Segura:** Emite el payload OCSF por HTTPS hacia el SIEM configurado.
5. **Visualización en SIEM:** El analista de SOC ve de inmediato la alerta estructurada en sus dashboards de Splunk/Sentinel sin necesidad de configurar ningun parser manual.

## 8. Momento mágico

«El analista de SOC configura la URL de su SIEM en LucidFence. Tres minutos después, cuando una laptop sale de la zona segura, una alerta formateada perfectamente en OCSF aparece en la consola del SOC con el origen, las coordenadas, el nivel de severidad y el hash de prueba de auditoría, lista para desencadenar un playbook de respuesta sin haber escrito una sola línea de código de parsing.»

## 9. Diferenciación y ventaja defensiva

- **Prueba Criptográfica Integrada:** Cada evento OCSF incluye el hash SHA-256 del bloque de evidencia local.
- **Estandarización Total:** Mapeo directo a OCSF v1.1+ (clase 2004 Detection Finding y clase 2001 Incident Finding).
- **Zero-Cloud Middleware:** Ingesta directa desde el tenant al SIEM, eliminando costos de licenciamiento por conectores en la nube.

## 10. Alcance por etapas

### Experimento
Crear un módulo `lucidfence/core/ocsf.py` con funciones puras para mapear objetos `RiskVerdict` e `Incident` a diccionarios compatibles con el esquema OCSF Detection Finding v1.1.

### Primera versión (Thin Slice)
Añadir la opción de formato `ocsf` en la configuración de `webhooks.py` e integrar la validación del esquema OCSF mediante pruebas unitarias.

### Expansión
Añadir soporte para transporte syslog/CEF para entornos SIEM legados que no dispongan de endpoints HTTP.

### Visión North Star
Bi-directional OCSF enrichment: recibir comandos de mitigación firmados desde el SOAR corporativo en formato OCSF para ejecutar respuestas automatizadas a través de los adaptadores UEM.

## 11. Fuera de alcance

- Alojamiento de un servidor SIEM propio dentro de LucidFence.
- Modificación del esquema oficial de la Linux Foundation OCSF.

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** `lucidfence/core/webhooks.py`, `lucidfence/core/evidence_export.py`, `lucidfence/core/engine.py`.
- **Integraciones:** Webhooks HTTP/HTTPS existentes.
- **Datos necesarios:** `RiskVerdict` y estructura de evidencias.
- **Dependencias:** Estrictamente biblioteca estándar de Python (stdlib).
- **Incertidumbres técnicas:** Ninguna.

## 13. Seguridad, privacidad y confianza

- **Cifrado en Tránsito:** Exige endpoints HTTPS con TLS 1.3 por defecto.
- **Autenticación:** Soporta Tokens Bearer y Headers de Autenticación de API.
- **Inmutabilidad:** Cada evento OCSF lleva adjunto el hash SHA-256 del registro de auditoría inmutable.

## 14. Valor para el negocio

- **Integración Enterprise Inmediata:** Facilita la adopción de LucidFence en grandes organizaciones con SOCs consolidados.
- **Reducción de Costes Operativos:** Elimina el tiempo empleado por los equipos de seguridad en mantener scripts de traducción de logs.

## 15. Métricas

- **Métrica de resultado:** Tiempo de integración con el SIEM del cliente < 5 minutos.
- **Indicador adelantado:** Número de webhooks configurados con formato OCSF.
- **Métrica de uso:** Volumen de eventos OCSF transmitidos mensualmente.
- **Guardrails:** 100% de cumplimiento del esquema oficial OCSF Detection Finding v1.1.

## 16. Evaluación

- **Problema:** 4/5
- **Alcance:** 4/5
- **Impacto:** 4/5
- **Estrategia:** 5/5
- **Diferenciación:** 4/5
- **Deleite:** 4/5
- **Viabilidad:** 5/5 (traducción de formato pura en Python)
- **Evidencia:** 5/5
- **Riesgo:** 1/5
- **Efecto compuesto:** 4/5

- **Confianza:** Alta
- **Esfuerzo relativo:** Pequeño (S)
- **Reversibilidad:** Alta
- **Tipo de apuesta:** Integración / Plataforma
- **Horizonte recomendado:** `EXPLORE`

## 17. Riesgos y motivos para no construirla

- **Riesgo de cambios en el esquema OCSF:** La especificación OCSF evoluciona con el tiempo.
- **Mitigación:** Fijar la versión del esquema en `v1.1.0` e implementar pruebas de contrato de esquema.

## 18. Preguntas abiertas

1. ¿Deberíamos soportar la exportación OCSF en lotes (batch export) además de streaming en tiempo real?
2. ¿Qué campos opcionales del esquema OCSF son más valorados por los equipos de respuesta ante incidentes (CSIRT)?

## 19. Próximo experimento recomendado

Escribir una prueba de serialización que tome un veredicto de riesgo real y genere el JSON OCSF, validando los campos obligatorios (`activity_id`, `category_uid`, `class_uid`, `severity_id`, `finding_info`).

## 20. Recomendación final

**Aprobar para Explore / Desarrollar módulo de mapeo OCSF.** Esta propuesta fortalece el posicionamiento de LucidFence como el complemento de geocercas más interoperable y amigable con el SOC en el mercado.
