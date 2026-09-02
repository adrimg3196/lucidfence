# ✨ Informe de Puntos Ciegos y Dispositivos Huérfanos ("Coverage Gap & Lost Sheep Detector")

## 1. Resumen ejecutivo

El principal riesgo para un CISO o Administrador de TI no es un dispositivo fuera de perímetro que es detectado, sino el **dispositivo que no está cubierto por ninguna política, el que dejó de reportar sigilosamente o la geocerca vacía que da una falsa sensación de protección**. Proponemos la capacidad **Detector de Puntos Ciegos y Dispositivos Huérfanos ("Coverage Gap & Lost Sheep Detector")**: una función de auditoría pasiva en el dashboard local de LucidFence que realiza consultas cruzadas en tiempo real entre el inventario unificado multi-UEM (`multiuem.py`), el catálogo de geocercas activas (`fences.json`) y las señales de salud de hardware. Identifica al instante 3 vacíos de cobertura críticos: dispositivos no asignados a ningún perímetro, dispositivos "oveja perdida" con check-in caducado y geocercas obsoletas sin asignación de flota, todo ello sin exfiltrar datos ni requerir licencias adicionales.

## 2. Propuesta en una frase

«Para el **CISO y Lead de SecOps**, que necesita **garantizar cobertura total de seguridad sin dejar puntos ciegos en su flota heterogénea**, proponemos el **Detector de Puntos Ciegos ("Coverage Gap & Lost Sheep Detector")**, que permite **descubrir instantáneamente dispositivos huérfanos, check-ins caducados y geocercas vacías en una sola vista local**, a diferencia de **las consolas UEM que solo muestran lo que gestionan activamente y ocultan las brechas de cobertura.**»

## 3. Problema

- **Persona:** CISO, Lead Security Engineer, Auditor de Cumplimiento.
- **Situación:** Preparación de auditorías de seguridad (SOC 2, ISO 27001, NIS2) o revisiones mensuales de salud de la infraestructura de endpoints.
- **Trabajo por realizar:** Identificar cualquier endpoint corporativo que carezca de controles de geocercado, dispositivos desatendidos o perímetros desactualizados.
- **Fricción actual:** Las herramientas MDM/UEM actuales sufren de un sesgo de confirmación: reportan métricas sobre los dispositivos que responden activamente y ocultan los dispositivos desasociados, offline por semanas o sin grupo de políticas asignado. Descubrir un "dispositivo huérfano" requiere cruzar manualmente exportaciones CSV de 3 sistemas diferentes.
- **Impacto:** Falsas métricas de 100% de cumplimiento, incidentes no detectados en portátiles olvidados ("shadow IT" o ex-empleados) y brechas de seguridad no mitigadas.
- **Solución utilizada hoy:** Consultas SQL ad-hoc en SIEMs o filtrado manual en hojas de cálculo Excel.

## 4. Evidencia

- **HECHO:** `lucidfence/core/multiuem.py` normaliza la información de dispositivos proveniente de múltiples adaptadores UEM (Intune, Jamf, Applivery, Fleet, Workspace ONE).
- **HECHO:** `lucidfence/core/state_store.py` almacena los estados de dispositivos, ubicaciones y timestamps de reporte más recientes.
- **HECHO:** El backlog de producto canónico en `docs/internal/product/BACKLOG.md` clasifica el Ítem #15 ("Informe de puntos ciegos: coverage gap & lost sheep") con el veredicto **SÍ** y una puntuación de impacto de 4/5.
- **INFERENCIA:** Mostrar la cobertura en "negativo" (lo que NO está protegido) ofrece un valor de auditoría inmediato que las herramientas tradicionales evitan ofrecer por temor a resaltar sus propias deficiencias.
- **HIPÓTESIS:** Un panel de Puntos Ciegos de un solo vistazo permitirá a los administradores corregir vacíos de cobertura en minutos, incrementando la densidad de políticas activas en la flota.

## 5. Por qué ahora

1. **Crecimiento de la flota remota y BYOD:** La dispersión geográfica aumenta la probabilidad de dispositivos que pierden contacto con la infraestructura corporativa.
2. **Capacidades de agregación listas:** LucidFence ya normaliza flotas multi-UEM y calcula pertenencia a geocercas en runtime sin coste computacional adicional.
3. **Cero costo de licenciamiento:** La función se beneficia de la arquitectura 100% Free Open Source de LucidFence.

## 6. Por qué este producto

- **Diseño centrado en la transparencia:** Mientras los UEMs compiten por mostrar gráficos en verde, LucidFence destaca objetivamente los huecos no cubiertos.
- **Análisis local soberano:** La evaluación de vacíos ocurre en la máquina del tenant sin transmitir el inventario de la empresa a la nube de un tercero.
- **Consola federada:** Funciona a través de todos los UEMs conectados simultáneamente (Jamf + Intune + Fleet).

## 7. Experiencia propuesta

1. **Acceso al Dashboard:** En el Dashboard local de LucidFence, el admin selecciona la pestaña **"Puntos Ciegos & Cobertura"**.
2. **Tarjeta de Cobertura Global:** Muestra la métrica principal:
   > **Cobertura de Flota:** `88% protegida` | `12% con puntos ciegos`
3. **Desglose de Puntos Ciegos (3 categorías):**
   - 🐑 **Dispositivos "Oveja Perdida" (Lost Sheep):** 14 dispositivos con check-in caducado (> 48h sin telemetría).
   - 🛡️ **Sin Geocerca Asignada:** 8 portátiles registrados en Intune que no pertenecen a ningún perímetro ni zona autorizada.
   - 📍 **Geocercas Huérfanas:** 2 geocercas activas en `fences.json` que actualmente tienen 0 dispositivos asignados.
4. **Drill-down y Explicación:** Al hacer clic en un dispositivo "Lost Sheep", se despliega el historial del último check-in conocido, la IP de origen y el UEM responsable.
5. **Acción de Remediación:**
   - Botón *"Re-sincronizar con UEM"* para solicitar actualización de inventario.
   - Botón *"Asignar a Geocerca Predeterminada"* para aplicar protección inmediata.
   - Exportación de reporte de vacíos de cobertura en PDF/JSON para la dirección o auditores.

## 8. Momento mágico

«El administrador abre por primera vez la pestaña de Puntos Ciegos y descubre que 5 portátiles pertenecientes al departamento de dirección contratados hace 3 meses en otra delegación nunca fueron añadidos a la geocerca corporativa ni han reportado estado en las últimas 3 semanas. Con un clic en el reporte, notifica al equipo de soporte de TI antes de que ocurra una pérdida de datos.»

## 9. Diferenciación y ventaja defensiva

- **Enfoque en Seguridad Negativa:** Visualización de lagunas de cobertura en lugar de métricas vanidosas.
- **Compatibilidad Cross-Platform:** Audita vacíos en macOS, Windows, Android y Linux por igual.
- **Generación Criptográfica de Evidencia de Cobertura:** Permite probar ante auditores de ISO 27001 que el 100% de los endpoints activos han sido auditados en busca de puntos ciegos.

## 10. Alcance por etapas

### Experimento
Crear un endpoint interno `/api/v2/blindspots` que retorne la lista filtrada de dispositivos sin cerca y dispositivos offline > 48h desde `state_store.py`.

### Primera versión (Thin Slice)
Añadir la tarjeta de resumen de Puntos Ciegos en `static/dashboard.html` mostrando contadores y la lista de dispositivos "Lost Sheep".

### Expansión
Permitir la creación automática de reglas SOAR de notificación cuando un dispositivo pase a estado "Oveja Perdida" (> N horas sin reportar).

### Visión North Star
Asignación Dinámica Inteligente: Recomendar automáticamente la geocerca más adecuada para un dispositivo huérfano basándose en sus patrones de ubicación pasados.

## 11. Fuera de alcance

- Reinstalación remota forzada de agentes UEM desde LucidFence.
- Modificación de grupos organizativos en el IdP/UEM de origen.

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** `lucidfence/core/multiuem.py`, `lucidfence/core/state_store.py`, `lucidfence/core/engine.py`.
- **APIs afectadas:** `/api/v2/stats`, `/api/v2/devices`.
- **Rendimiento:** Evaluación en memoria durante el tick del engine (< 2ms adicionales).

## 13. Seguridad, privacidad y confianza

- **Soberanía:** Evaluación 100% local sin envío de inventarios a servidores de terceros.
- **Acceso por Roles (RBAC):** Restringido a usuarios con rol `admin` u `owner`.

## 14. Valor para el negocio

- **Valor para el CISO:** Elimina el pánico pre-auditoría al ofrecer una métrica clara de brechas no cubiertas.
- **Retención:** Convierte a LucidFence en el panel de salud diario para el equipo de SecOps.

## 15. Métricas

- **Métrica de resultado:** Reducción del porcentaje de dispositivos huérfanos a < 1% en organizaciones que usan LucidFence.
- **Métrica de uso:** Frecuencia de consulta del panel de Puntos Ciegos.
- **Guardrails:** Cero impacto en el rendimiento de respuesta de las APIs principales.

## 16. Evaluación

- **Problema:** 5/5
- **Alcance:** 5/5
- **Impacto:** 4/5
- **Estrategia:** 5/5
- **Diferenciación:** 5/5
- **Deleite:** 4/5
- **Viabilidad:** 5/5 (los datos requeridos ya están calculados en `engine.py`)
- **Evidencia:** 5/5
- **Riesgo:** 1/5
- **Efecto compuesto:** 4/5

- **Confianza:** Alta
- **Esfuerzo relativo:** Pequeño (S)
- **Reversibilidad:** Alta
- **Tipo de apuesta:** Plataforma / Visibilidad
- **Horizonte recomendado:** `EXPLORE` (para refinamiento de la tarjeta UI)

## 17. Riesgos y motivos para no construirla

- **Riesgo de falsas alarmas en dispositivos en vacaciones:** Un dispositivo apagado por vacaciones prolongadas figurará como "Lost Sheep".
- **Mitigación:** Permitir marcar un dispositivo temporalmente como "En Mantenimiento / Vacaciones" o ajustar el umbral de horas en la configuración.

## 18. Preguntas abiertas

1. ¿Cuál debe ser el umbral de tiempo por defecto para considerar a un dispositivo como "Lost Sheep" (24h, 48h o 72h)?
2. ¿Deberíamos enviar una alerta por webhook/email cuando la cobertura de la flota caiga por debajo del 90%?

## 19. Próximo experimento recomendado

Añadir una consulta en `tests/test_ui_posture_visibility.py` que valide el filtrado de dispositivos huérfanos sobre datos simulados y diseñar el boceto UI de la tarjeta de Puntos Ciegos.

## 20. Recomendación final

**Aprobar para horizonte EXPLORE / Implementación rápida.** Es una función de bajísimo esfuerzo (S) y alto valor de visibilidad que complementa perfectamente la propuesta de neutralidad de LucidFence.
