# ✨ Inspector de Puntos Ciegos y Falsos Verdes de Cobertura («Coverage Gap & Blindspot Inspector»)

## 1. Resumen ejecutivo

Las consolas de gestión de dispositivos (UEM) tradicionales muestran con detalle los dispositivos que administran activamente, pero sufren de una ceguera estructural: **son incapaces de reportar en negativo lo que NO están cubriendo**. Dispositivos registrados en el UEM que carecen de geocercas asignadas, agentes de postura que dejaron de transmitir check-ins hace semanas ("lost sheep"), zonas geográficas de la flota sin reglas de protección y endpoints huérfanos quedan ocultos en las métricas de conformidad habituales. Proponemos el **Inspector de Puntos Ciegos y Falsos Verdes de Cobertura**: un motor de auditoría negativa en local que cruza los inventarios federados de Intune, Jamf, Applivery, Fleet y osquery para identificar automáticamente brechas de visibilidad, vacíos de geoperímetro y dispositivos desatendidos antes de que se conviertan en vectores de incidente.

## 2. Propuesta en una frase

«Para el **CISO y Admin de TI**, que necesita **asegurar que el 100% de la flota esté efectivamente protegida sin zonas de sombra ni dispositivos desatendidos**, proponemos el **Inspector de Puntos Ciegos**, que permite **descubrir automáticamente dispositivos sin geocercas, agentes caducados y zonas huérfanas de cobertura en local y sin exfiltrar datos**, a diferencia de **los paneles de UEMs tradicionales que solo muestran los dispositivos con reporte exitoso y ocultan las brechas de visibilidad**.»

## 3. Problema

- **Persona:** CISO, Director de Seguridad de la Información, Auditor de Cumplimiento y Admin de TI.
- **Situación:** Una organización cuenta con 1,200 dispositivos en su inventario global. Durante una auditoría ISO 27001 o tras un incidente de pérdida de un portátil, el equipo de seguridad descubre que 45 dispositivos no tenían ninguna regla de geofencing configurada o que su agente de reporte llevaba 30 días inactivo sin que ninguna alerta se hubiera disparado.
- **Trabajo por realizar:** Identificar proactivamente el 100% de las brechas de cobertura en la flota, garantizando que ningún dispositivo quede fuera del perímetro de supervisión y que ninguna geocerca quede huérfana.
- **Fricción actual:** Los UEMs muestran métricas de éxito (p. ej. "98% compliant"), pero no ofrecen una vista negativa de los vacíos. Detectar los "lost sheep" exige cruzar listados de inventario en hojas de cálculo Excel.
- **Impacto:** Falsa sensación de seguridad, dispositivos desprotegidos fuera del radar del equipo de TI y hallazgos críticos en auditorías de seguridad.
- **Solución utilizada hoy:** Scripts ad-hoc o revisiones manuales periódicas de hojas de cálculo.

## 4. Evidencia

- **HECHO:** El backlog de producto en `docs/internal/product/BACKLOG.md` clasifica el Ítem #15 ("Informe de puntos ciegos / coverage gap") con veredicto **SÍ** y un impacto de nivel 4/5.
- **HECHO:** La arquitectura multi-UEM de LucidFence (`multiuem.py`) y el motor de estado (`state_store.py`) ya consolidan el inventario federado de dispositivos y sus geocercas asignadas en la estructura `DeviceState`.
- **INFERENCIA:** Los paneles de los UEMs comerciales están optimizados para métricas de éxito y ventas de licencias, evitando resaltar deficiencias o dispositivos no sincronizados.
- **HIPÓTESIS:** Presentar un informe claro de puntos ciegos en el dashboard local aumentará la eficacia de las operaciones de seguridad y acelerará la resolución de vacíos de cobertura.

## 5. Por qué ahora

1. **Crecimiento de flotas remotas e híbridas:** La dispersión geográfica de los empleados incrementa el riesgo de dispositivos que pierden contacto con la infraestructura corporativa.
2. **Requisito estricto de auditoría continua:** Marcos normativos modernos (NIS2, SOC 2, ISO 27001:2022) exigen demostrar que todos los activos en inventario disponen de controles de seguridad vigentes.
3. **Datos ya disponibles en LucidFence:** Toda la información necesaria para el análisis de vacíos existe en el engine local; solo requiere el motor de consulta negativa y la capa de presentación.

## 6. Por qué este producto

- **Independencia de proveedores:** Al federar múltiples UEMs, LucidFence es el único sistema capaz de identificar dispositivos registrados en Intune pero ausentes en Jamf o sin política en LucidFence.
- **Privacidad y procesamiento local:** El análisis de vacíos se ejecuta enteramente en la máquina del tenant sin enviar listados de inventario a servicios en la nube.
- **Cero costo por dispositivo:** Funciona dentro del modelo 100% Open Source (Apache-2.0).

## 7. Experiencia propuesta

1. **Disparador:** El admin accede al Dashboard local o ejecuta el comando CLI `lucidfence coverage-gap`.
2. **Diagnóstico Negativo (Vista de Puntos Ciegos):** El dashboard despliega el panel **"Puntos Ciegos y Cobertura de Flota"**, categorizado en cuatro métricas de sombra:
   - **Dispositivos Huérfanos ("Lost Sheep"):** Dispositivos en el inventario UEM que no han reportado ubicación ni postura en > 7 días.
   - **Brecha de Geocercado:** Dispositivos activos que no tienen asignada ninguna regla de geofencing o política de perímetro.
   - **Cercas Sin Dispositivos:** Geocercas declaradas en la configuración pero que no aplican a ningún dispositivo de la flota actual.
   - **Desalineación de Agentes:** Dispositivos detectados por osquery local pero no registrados en la consola UEM correspondiente.
3. **Detalle Explicable:** Al seleccionar cualquier categoría, se muestra la lista detallada de dispositivos afectados con su último check-in conocido, UEM de origen y recomendación de acción.
4. **Acción de Remediación:** El admin puede:
   - Exportar el informe de puntos ciegos en JSON/CSV firmado criptográficamente.
   - Aplicar una política por defecto de geofencing a los dispositivos sin cerca.
   - Disparar una solicitud de re-checkin o re-enrollment a través del adaptador UEM de origen.

## 8. Momento mágico

«El administrador abre el informe de puntos ciegos y descubre inmediatamente 18 portátiles que figuraban como activos en el UEM pero no tenían ninguna política de geoperímetro asignada, pudiendo subsanar la brecha en menos de dos minutos.»

## 9. Diferenciación y ventaja defensiva

- **Análisis de espacio negativo:** Ninguna consola de UEM comercial del mercado analiza o reporta las brechas en negativo.
- **Trazabilidad Multi-UEM:** Detecta inconsistencias de inventario entre distintas consolas MDM de la misma empresa.
- **Integración con exportación de evidencia:** Los informes de puntos ciegos se integran con `evidence_export.py` para justificar acciones ante auditores.

## 10. Alcance por etapas

### Experimento
Implementar en `lucidfence/core/coverage_gap.py` una función de auditoría pura que evalúe los dispositivos del `state_store.py` y retorne la estructura de datos con los 4 tipos de vacíos.

### Primera versión (Thin Slice)
Añadir el endpoint `/api/v2/coverage-gap` en `saas_server.py` y una pestaña de "Puntos Ciegos" en `static/dashboard.html` con exportación a JSON.

### Expansión
Añadir alertas automáticas vía webhook cuando el porcentaje de cobertura de la flota descienda por debajo de un umbral configurable (p. ej. < 95%).

### Visión North Star
Recomendaciones inteligentes de geocercado basadas en patrones de desplazamiento históricos, sugiriendo la creación de perímetros automáticos para grupos de dispositivos desatendidos.

## 11. Fuera de alcance

- Reinstalación automática remota de agentes desinstalados (se gestiona mediante recomendación al admin o acción a través del UEM).
- Monitoreo de dispositivos personales no registrados en el inventario de la empresa.

## 12. Implicaciones técnicas

- **Nuevo módulo backend:** `lucidfence/core/coverage_gap.py` (Módulo stdlib puro).
- **Entradas:** `state_store.py`, `fences.json`, `policies.json`.
- **Salidas:** Diccionario estructurado `CoverageGapReport` con recuentos, porcentaje de cobertura y listas de dispositivos.
- **Pruebas:** Pruebas unitarias en `tests/test_coverage_gap.py` verificando la detección exacta de dispositivos sin cerca y cercas sin dispositivos.

## 13. Seguridad, privacidad y confianza

- **Operación puramente de lectura:** No realiza modificaciones en los dispositivos ni en los UEMs.
- **Procesamiento 100% local:** No transmite datos de cobertura fuera de la máquina del tenant.
- **Firmado de evidencia:** Los informes generados incluyen digest SHA-256 encadenado.

## 14. Valor para el negocio

- **Aumento inmediato de postura de seguridad:** Permite cerrar brechas desatendidas antes de que sean explotadas o detectadas por auditores externos.
- **Posicionamiento como herramienta de auditoría:** Atrae a responsables de cumplimiento que buscan verificar la cobertura real de sus herramientas de gestión.

## 15. Métricas

- **Métrica de resultado:** Mantenimiento de la cobertura de geocercado de la flota por encima del 98%.
- **Métrica de uso:** Frecuencia de consulta del panel de Puntos Ciegos y ejecuciones del reporte.
- **Métrica de calidad:** 0 falsos positivos en la clasificación de dispositivos desatendidos.

## 16. Evaluación

- **Problema:** 5/5
- **Alcance:** 5/5
- **Impacto:** 4/5
- **Estrategia:** 5/5
- **Diferenciación:** 5/5
- **Viabilidad:** 5/5 (Módulo stdlib liviano sobre estado existente)
- **Evidencia:** 5/5
- **Riesgo:** 1/5 (Riesgo nulo, operación de lectura pura)

- **Confianza:** Alta
- **Esfuerzo relativo:** Pequeño (S)
- **Horizonte recomendado:** `EXPLORE`
