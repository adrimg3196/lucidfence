# ✨ Radar de Puntos Ciegos y Dispositivos Huérfanos ("Coverage Gap & Blind Spot Radar")

## 1. Resumen ejecutivo

En flotas corporativas heterogéneas de cientos o miles de dispositivos, uno de los mayores riesgos de seguridad es la falta de cobertura uniforme: dispositivos registrados en el UEM que no están protegidos por ninguna geocerca, geocercas activas que no contienen ningún dispositivo, y dispositivos que han dejado de reportar telemetría sin que nadie lo note ("ovejas perdidas" o *lost sheep*). Proponemos el **Radar de Puntos Ciegos y Dispositivos Huérfanos**: una capacidad de análisis continuo en local que escanea el inventario unificado Multi-UEM y la matriz de geocercas para identificar y visibilizar de inmediato los huecos de protección. La función genera alertas preventivas y propone planes de acción sin instalar agentes adicionales ni enviar datos fuera del entorno soberano del tenant.

## 2. Propuesta en una frase

«Para el **CISO y Administrador de TI**, que necesita **garantizar una cobertura de seguridad del 100% sobre todos los activos corporativos**, proponemos el **Radar de Puntos Ciegos y Dispositivos Huérfanos**, que permite **descubrir instantáneamente dispositivos desprotegidos, geocercas vacías y endpoints desconectados**, a diferencia de **las consolas UEM tradicionales que solo muestran lo que están gestionando activamente y ocultan sus propios huecos de cobertura**.»

## 3. Problema

- **Persona:** Chief Information Security Officer (CISO), IT Asset Manager, Compliance Auditor.
- **Situación:** Preparación para auditorías de seguridad (SOC 2, ISO 27001) o auditoría periódica del inventario de dispositivos corporativos.
- **Trabajo por realizar:** Verificar que el 100% de los portátiles y dispositivos móviles de la compañía están bajo políticas activas de geoperímetro y postura de seguridad.
- **Fricción actual:** Los UEMs muestran paneles con métricas de los dispositivos que *asignan* correctamente, pero no resaltan en negativo los dispositivos que quedaron fuera de las políticas por fallos de etiquetado, grupos dinámicos mal configurados o desatención de agencias externas.
- **Impacto:** Dispositivos corporativos operando en áreas de alto riesgo o redes no seguras sin supervisión alguna, generando un punto ciego crítico explotable por atacantes.
- **Solución utilizada hoy:** Auditorías manuales en hojas de cálculo cruzando el inventario de recursos humanos con las consolas de Intune/Jamf.

## 4. Evidencia

- **HECHO:** LucidFence consolida la información de dispositivos a través de sus conectores Multi-UEM (`multiuem.py`) y mantiene el catálogo de geocercas en `fences.json`.
- **HECHO:** El backlog de producto en `docs/internal/product/BACKLOG.md` clasifica el Ítem #15 ("Informe de puntos ciegos / coverage gap") con el veredicto **SÍ** y una valoración de impacto de 4/5.
- **HECHO:** Plataformas como Kandji/Iru promocionan la detección de "lost sheep", pero requieren reinstalar sus agentes SaaS propietarios.
- **INFERENCIA:** Presentar los vacíos de seguridad "en negativo" (lo que NO está cubierto) otorga un valor inmediato al CISO, revelando vulnerabilidades invisibles en su postura actual.
- **HIPÓTESIS:** Identificar geocercas huérfanas (sin dispositivos) e inventario desatendido reducirá el tiempo de remediación de puntos ciegos de semanas a menos de 5 minutos.

## 5. Por qué ahora

1. **Incompatibilidad de silos de UEM:** Cuando las empresas usan Jamf para Mac e Intune para Windows, ninguna consola ve los puntos ciegos de la otra.
2. **Exigencia de auditoría continua:** Los auditores normativos exigen demostrar no solo que las reglas funcionan, sino que se aplican a la totalidad de la flota sin excepciones.
3. **Barato de implementar en LucidFence:** Toda la información necesaria (lista de dispositivos UEM, geocercas y marcas temporales de último check-in) ya existe en memoria y en el estado del engine (`DeviceState`).

## 6. Por me este producto

LucidFence es la plataforma idónea para esta solución porque:
1. **Es un complemento neutral:** No intenta vender licencias de UEM adicionales; su único objetivo es auditar la cobertura real con total honestidad.
2. **Es Local-First:** El análisis de cobertura se calcula en milisegundos en la máquina del tenant sin exfiltrar la lista de activos a la nube.

## 7. Experiencia propuesta

1. **Vista de Cobertura en el Dashboard:** El usuario abre el Dashboard local y observa la tarjeta **"Radar de Cobertura y Puntos Ciegos"**.
2. **Desglose de Hallazgos:** El panel categoriza los vacíos en tres dimensiones claras:
   - 🔴 **Dispositivos Sin Geocerca Asignada:** 8 portátiles registrados en Intune/Jamf no coinciden con ningún criterio de geoperímetro.
   - 🟡 **Ovejas Perdidas (*Lost Sheep*):** 3 dispositivos llevan más de 72 horas sin reportar telemetría ni check-in al UEM.
   - 🔵 **Geocercas Huérfanas:** 2 geocercas creadas en el sistema no tienen ningún dispositivo asignado o activo.
3. **Detalle Explicable:** Al hacer clic en un dispositivo desprotegido, el sistema explica el motivo: `"El dispositivo 'MAC-DEV-04' no posee la etiqueta 'oficina-madrid' ni pertenece a ningún grupo dinámico cubierto por las políticas activas"`.
4. **Acción de Remedación Sugerida:** El admin puede descargar un informe de puntos ciegos en PDF/JSON firmado o aplicar un etiquetado de remediación en dry-run.

## 8. Momento mágico

«El CISO ejecuta el Radar de Puntos Ciegos por primera vez y descubre que el portátil de un directivo recién contratado no estaba asignado a ninguna geocerca corporativa debido a una errata en la etiqueta del departamento en Jamf, corrigiéndolo en menos de 60 segundos.»

## 9. Diferenciación y ventaja defensiva

- **Análisis de Cobertura en Negativo:** Muestra lo que falta por proteger, a diferencia de los dashboards de UEM que solo celebran los dispositivos conformes.
- **Detección Cross-UEM:** Evalúa puntos ciegos combinando flotas de macOS (Jamf), Windows (Intune) y Linux (Fleet) en un solo informe.

## 10. Alcance por etapas

### Experimento
Implementar un módulo de consulta puro `coverage_gap.py` en `lucidfence/core/` que analice la colección de `DeviceState` y las geocercas cargadas, retornando un diccionario estructurado de vacíos.

### Primera versión (Thin Slice)
Integrar la tarjeta de resumen y el modal de detalle en `static/dashboard.html`, permitiendo filtrar por tipo de punto ciego y exportar la lista de dispositivos desprotegidos.

### Expansión
Alertas automatizadas vía webhooks (Slack/Teams) cuando el porcentaje de cobertura global de la flota caiga por debajo del 95%.

### Visión North Star
Radar Predictivo de Cobertura que anticipe vacíos al detectar el enrolamiento de nuevos dispositivos en los UEMs antes de que salgan a producción.

## 11. Fuera de alcance

- Instalación automática de agentes en dispositivos huérfanos.
- Eliminación automática de geocercas sin confirmación explícita del administrador.

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** `lucidfence/core/multiuem.py`, `lucidfence/core/engine.py`, `lucidfence/core/state_store.py`.
- **Nuevos módulos:** `lucidfence/core/coverage_gap.py` (módulo puro sin dependencias externas).
- **Complejidad:** Baja (S). Cálculo de conjuntos y marcas temporales en memoria.

## 13. Seguridad, privacidad y confianza

- **Privacidad Soberana:** La lista de dispositivos y los puntos ciegos nunca se envían a servidores externos.
- **Auditabilidad:** Los informes de cobertura generados quedan firmados con hash SHA-256 encadenado localmente.

## 14. Valor para el negocio

- **Generador de Valor Inmediato:** Proporciona un diagnóstico de seguridad útil desde el primer minuto de instalación.
- **Herramienta para Auditores:** Facilita el cumplimiento de normativas de control de inventario de activos de seguridad.

## 15. Métricas

- **Métrica de resultado:** Cobertura de flota objetivo del 100% (0 dispositivos sin política asignada).
- **Indicador de uso:** Porcentaje de administradores que consultan el Radar de Puntos Ciegos semanalmente.

## 16. Evaluación

- **Problema:** 5/5
- **Alcance:** 5/5
- **Impacto:** 4/5
- **Viabilidad:** 5/5 (requiere solo lógica pura sobre datos ya existentes)
- **Riesgo:** 1/5
- **Horizonte recomendado:** `EXPLORE` (preparar prototipo backend `coverage_gap.py`)

## 17. Riesgos y motivos para no construirla

- Riesgo de considerar como "dispositivo huérfano" a equipos en proceso de desincorporación o baja.
- **Mitigación:** Permitir marcar dispositivos específicos como "archivados" o "excluidos de cobertura" con justificación auditable.

## 18. Preguntas abiertas

1. ¿Cuál debería ser el umbral de tiempo por defecto para clasificar un dispositivo como *Lost Sheep* (24h, 48h, 72h)?

## 19. Próximo experimento recomendado

Escribir el test unitario `tests/test_coverage_gap.py` pasando una flota de prueba con 1 dispositivo sin cerca, 1 cerca vacía y 1 dispositivo stale, verificando que la función retorna la estructura exacta de hallazgos.

## 20. Recomendación final

**Aprobar para Explore.** Es una capacidad ligera, de altísimo impacto visual y estratégico, que refuerza la propuesta de valor de LucidFence como auditor neutral de la flota.
