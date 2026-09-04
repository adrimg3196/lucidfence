# ✨ Descubrimiento de Puntos Ciegos y Dispositivos Perdidos (Multi-UEM Coverage Gap & Lost Sheep Discovery)

## 1. Resumen ejecutivo

En infraestructuras corporativas heterogéneas, uno de los mayores riesgos de ciberseguridad es la falta de visibilidad sobre los dispositivos "huérfanos" o "perdedores de cobertura" (*Lost Sheep*): endpoints registrados en la consola MDM/UEM que carecen de geocercas asignadas, dispositivos que dejaron de emitir reportes de ubicación o postura sin ser desincronizados, o geocercas activas sin ningún dispositivo protegido. Proponemos el **Descubridor de Puntos Ciegos y Vacíos de Cobertura (Coverage Gap & Lost Sheep Discovery)**: una función de auditoría en negativo que analiza en tiempo real el inventario unificado multi-UEM y la matriz de políticas de LucidFence para exponer de forma inmediata todos los vacíos de cobertura, sin necesidad de instalar agentes adicionales ni violar la privacidad de los usuarios.

## 2. Propuesta en una frase

«Para el **CISO y Responsable de Operaciones de TI**, que necesita **garantizar el 100% de cobertura de seguridad en su flota de dispositivos**, proponemos el **Descubridor de Puntos Ciegos**, que permite **identificar en negativo dispositivos no protegidos, geocercas inactivas y latidos perdidos sin instalar agentes ni rastrear continuamente la ubicación**, a diferencia de **los UEMs tradicionales que solo muestran estadísticas positivas de los dispositivos que responden correctamente**.»

## 3. Problema

- **Persona:** CISO, IT Security Auditor, Lead Systems Administrator.
- **Situación:** Preparación de auditorías de ciberseguridad o revisión mensual de la postura de la flota corporativa.
- **Trabajo por realizar:** Asegurar que ningún dispositivo corporativo quede fuera de las políticas de geocercado y verificación de postura, y que no existan reglas "muertas" en el sistema.
- **Fricción actual:** Las herramientas de UEM (Intune, Jamf, Scalefusion) están diseñadas para mostrar lo que SÍ gestionan. Si un dispositivo pierde la comunicación con el agente, no tiene asignada una política de perfil o es dado de alta de forma incompleta, pasa desapercibido en las listas habituales.
- **Impacto:** Puntos ciegos de seguridad por los que se producen filtraciones de datos, incumplimiento involuntario de normativas (ISO 27001 / SOC 2) y desperdicio de licencias o reglas de geocercado mal configuradas.
- **Solución utilizada hoy:** Auditorías manuales periódicas cruzando exportaciones CSV de la consola UEM con listas de empleados del departamento de RRHH.

## 4. Evidencia

- **HECHO:** `lucidfence/core/multiuem.py` normaliza el inventario de múltiples adaptadores UEM (Intune, Jamf, Applivery, Fleet, Workspace ONE) en un modelo unificado `DeviceState`.
- **HECHO:** El backlog de producto en `docs/internal/product/BACKLOG.md` clasifica el Ítem #15 ("Informe de puntos ciegos / coverage gap") con el veredicto explícito **SÍ** y un impacto de 4/5.
- **INFERENCIA:** Ningún panel del mercado enseña la cobertura en negativo ("qué dispositivos no tienen ninguna regla asociada") debido a que las consolas UEM se enfocan en la confirmación de despliegue de sus propios perfiles.
- **HIPÓTESIS:** Ofrecer un informe visual y exportable de puntos ciegos aumentará la confianza del CISO en LucidFence como la "capa de verdad" sobre sus UEMs.
- **DESCONOCIDO:** El porcentaje promedio de dispositivos "huérfanos" sin geocerca asignada en entornos de clientes mid-market (se estima entre un 5% y un 12%).

## 5. Por qué ahora

1. **Capacidad de Normalización Multi-UEM:** LucidFence ya abstrae los inventarios de 7 plataformas UEM diferentes a través de `multiuem.py`.
2. **Exigencia de Cobertura Total en Auditorías:** Los marcos de cumplimiento modernos exigen demostrar el 100% de cobertura de controles en la totalidad del parque informático.
3. **Cero Impacto en Rendimiento:** El cálculo en negativo es una consulta pura en memoria sobre las estructuras de datos ya cargadas en el engine de LucidFence.

## 6. Por qué este producto

Al ser un complemento neutral y no un UEM, LucidFence no sufre el sesgo de autocomplacencia de los proveedores de MDM. Su arquitectura local-first permite cruzar el estado de todas las geocercas y dispositivos en milisegundos sin enviar datos al exterior.

## 7. Experiencia propuesta

1. **Acceso a la Vista:** El administrador selecciona la pestaña **"Puntos Ciegos & Cobertura"** en el Dashboard local de LucidFence (`:8765`).
2. **Análisis Automático en Negativo:** El sistema presenta tres categorías claras:
   - **Dispositivos Huérfanos (*Lost Sheep*):** Dispositivos presentes en el UEM pero que no están vinculados a ninguna geocerca ni regla de postura.
   - **Geocercas Muertas:** Geocercas creadas que no tienen ningún dispositivo ni grupo asignado.
   - **Latidos Caducados:** Dispositivos cuya última señal o reporte tiene más de X horas de antigüedad.
3. **Exploración de Causa:** Un clic sobre cualquier ítem muestra el desglose del motivo (p. ej. *"laptop-dev-04 registrado en Jamf pero sin geocerca asignada desde hace 14 días"*).
4. **Acción Remedial de Un Clic:** Botón para asignar rápidamente el dispositivo a una geocerca predeterminada o exportar el informe de brecha firmado en JSON/PDF para auditoría.

## 8. Momento mágico

«El responsable de seguridad abre el informe de Puntos Ciegos y descubre que 8 portátiles del equipo de ventas internacional, dados de alta en Intune hace tres meses, nunca recibieron las políticas de geocercado corporativo por una etiqueta mal escrita en el UEM. Con un solo clic, corrige la asignación antes de la auditoría SOC 2.»

## 9. Diferenciación y ventaja defensiva

- **Auditoría en Negativo Exclusiva:** Identifica lo que FALTA, en lugar de resumir lo que ya existe.
- **Cruzado Multi-UEM:** Detecta inconsistencias de cobertura incluso si la empresa usa Jamf para Mac e Intune para Windows simultáneamente.
- **Privacidad Preservada:** No requiere geolocalización continua ni rastreo invasivo; evalúa la lógica de asignación de políticas.

## 10. Alcance por etapas

### Experimento
Crear una función pura en `lucidfence/core/coverage_gap.py` que reciba la lista de `DeviceState` y la lista de `Geofence` y retorne las listas de huérfanos, cercas muertas y latidos caducados.

### Primera versión (Thin Slice)
Integrar la función en un nuevo endpoint `/api/v2/reports/coverage-gap` y añadir la tarjeta resumen en el dashboard web local.

### Expansión
Añadir alertas automáticas vía webhook cuando el número de dispositivos huérfanos supere un umbral configurable.

### Visión North Star
Asignación inteligente de geocercas basada en grupos dinámicos para eliminar automáticamente los puntos ciegos en cuanto un dispositivo se registra en cualquier UEM.

## 11. Fuera de alcance

- Reinstalación automática remota del agente UEM en el endpoint (corresponde al admin de TI).
- Modificación directa de etiquetas dentro de la consola propietaria del UEM.

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** `lucidfence/core/multiuem.py`, `lucidfence/core/engine.py`, `lucidfence/core/evidence_export.py`.
- **Integraciones:** Adaptadores UEM existentes.
- **Datos necesarios:** `DeviceState` y `Geofence` en memoria.
- **Dependencias:** Ninguna (estrictamente stdlib Python 3.11+).
- **Incertidumbres técnicas:** Ninguna.

## 13. Seguridad, privacidad y confianza

- **Transparencia Total:** Las reglas de detección de puntos ciegos son deterministicas y auditables.
- **Cero Retención Adicional:** No almacena nuevos datos personales ni coordenadas del usuario.
- **Auditoría Firmada:** Los informes de vacíos de cobertura incluyen firma SHA-256 encadenada.

## 14. Valor para el negocio

- **Alineación con Auditores:** Proporciona la evidencia exacta que exigen los auditores de cumplimiento en normativas de seguridad de la información.
- **Ahorro de Costes de TI:** Detecta geocercas obsoletas y dispositivos inactivos que consumen recursos.

## 15. Métricas

- **Métrica de resultado:** Cobertura del 100% de dispositivos activos bajo políticas de geocercado.
- **Indicador adelantado:** Tiempo medio de resolución de un dispositivo clasificado como "huérfano" (< 24 horas).
- **Métrica de uso:** Frecuencia de consulta del endpoint de puntos ciegos.
- **Guardrails:** Cero consumo adicional de CPU/memoria en el tick del engine (< 1ms).

## 16. Evaluación

- **Problema:** 5/5
- **Alcance:** 4/5
- **Impacto:** 4/5
- **Estrategia:** 5/5
- **Diferenciación:** 5/5
- **Deleite:** 4/5
- **Viabilidad:** 5/5 (cálculo de conjuntos puro sobre datos en memoria)
- **Evidencia:** 5/5
- **Riesgo:** 1/5
- **Efecto compuesto:** 4/5

- **Confianza:** Alta
- **Esfuerzo relativo:** Pequeño (S)
- **Reversibilidad:** Alta
- **Tipo de apuesta:** Núcleo / Usabilidad
- **Horizonte recomendado:** `EXPLORE`

## 17. Riesgos y motivos para no construirla

- **Riesgo de falsos positivos en dispositivos de prueba:** Dispositivos temporales de laboratorio pueden aparecer como huérfanos.
- **Mitigación:** Permitir marcar dispositivos o etiquetas específicas como `ignore_coverage_gap: true`.

## 18. Preguntas abiertas

1. ¿Cuál es el umbral de tiempo idóneo para declarar que un latido está "caducado" (24 horas vs 72 horas)?
2. ¿Debería el informe sugerir automáticamente la geocerca más cercana o predeterminada?

## 19. Próximo experimento recomendado

Escribir una prueba unitaria con 10 dispositivos simulados (3 sin cerca, 2 cercas sin dispositivos) para validar que el algoritmo de intersección de conjuntos retorna con precisión los vacuómetros esperados.

## 20. Recomendación final

**Aprobar para Explore / Implementar prototipo de cálculo.** Esta función aborda una necesidad crítica de auditoría con un esfuerzo técnico mínimo, reforzando la postura de ciberseguridad de los usuarios de LucidFence.
