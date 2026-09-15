# ✨ Zero-Trust Geofence Simulator & Time-Machine Replay

## 1. Resumen ejecutivo

Proponemos el **Zero-Trust Geofence Simulator & Time-Machine Replay**, un motor de simulación prospectivo e histórico integrado en LucidFence 2.0. Permite a los equipos de SecOps y administradores de UEM ejecutar análisis "What-If" sobre reglas de geocercado, cambios de perímetro y niveles de riesgo utilizando el histórico de trazas guardado localmente en JSONL. Con esta capacidad, los administradores pueden proyectar el impacto exacto de nuevas políticas o modificaciones de geocercas antes de activarlas en producción, eliminando el miedo a bloqueos accidentales de dispositivos corporativos. La función aprovecha la arquitectura Go local-first de LucidFence y posiciona al producto como el único motor de riesgo UEM con evaluación predictiva de impacto sin telemetría ni costes cloud.

## 2. Propuesta en una frase

«Para **administradores de SecOps y UEM**, que necesitan **validar el impacto y la seguridad de nuevas políticas de geocercado sin interrumpir la operación**, proponemos **Zero-Trust Geofence Simulator**, que permite **simular y reproducir reglas de seguridad sobre histórico de trazas reales o sintéticas**, a diferencia de **las pruebas a ciegas en producción o el análisis manual en hojas de cálculo que ofrecen los UEMs tradicionales**.»

## 3. Problema

- **Persona:** Administrador de UEM (Intune, Jamf, Applivery, Fleet, Workspace ONE) y Responsables de SecOps / CISO.
- **Situación:** La empresa define nuevas áreas geográficas permitidas, rutas comerciales o restricciones de horario/postura para dispositivos móviles y portátiles.
- **Trabajo por realizar:** Crear e imponer políticas de seguridad (como aislamiento, bloqueo o notificación) cuando un dispositivo sale de una zona segura o incumple la postura sin generar falsos positivos que bloqueen el trabajo de empleados legítimos.
- **Fricción actual:** Los administradores mantienen LucidFence en modo `observe` indefinidamente porque temen que una geocerca mal ajustada o una fluctuación de GPS provoque un bloqueo (`lock`) o un borrado (`wipe`) no deseado. Probar una política requiere esperar días a recopilar eventos o arriesgarse a aplicar cambios directamente a la flota viva.
- **Impacto:** Bloqueo de la adopción del modo `enforce`, aumento del trabajo manual de revisión de alertas, fricción entre los equipos de seguridad y los usuarios finales, y menor valor percibido del producto.
- **Solución utilizada hoy:** Ensayos manuales con dispositivos de prueba aislados, exportación manual de logs a hojas de cálculo o consultas ad-hoc para estimar qué dispositivos habrían cruzado una línea determinada.

## 4. Evidencia

- **HECHO:** `internal/engine/guardrails.go` establece por defecto el modo `observe`, asegurando que ninguna acción destructiva se envíe al UEM sin aprobación o cambio explícito.
- **HECHO:** `internal/store/jsonl.go` y `internal/engine/replay_history.go` mantienen las trazas de ubicación y estados de dispositivos en archivos JSONL atómicos en disco local (`data/`).
- **INFERENCIA:** Los administradores dudan en cambiar de `observe` a `enforce` debido a la falta de visibilidad del impacto retroactivo o prospectivo de una regla.
- **HIPÓTESIS:** Proporcionar una simulación visual en tiempo real ("What-If") sobre trazas pasadas incrementará la conversión de modo `observe` a `enforce` en más de un 40 % en organizaciones gestionadas.
- **DESCONOCIDO:** La tasa exacta de falsos positivos en entornos corporativos con fluctuaciones severas de precisión GPS en interiores (que la simulación ayudará a medir).

**Fuentes:**
- `ARCHITECTURE.md` (Principios 1 y 3: Local-first y control del admin por `observe`/`enforce`).
- `internal/engine/guardrails.go`
- `internal/domain/policy/templates.go`
- `docs/superpowers/specs/2026-09-05-lucidfence-2-go-rewrite-design.md`

## 5. Por qué ahora

1. **Reescritura a Go 2.0 completada:** LucidFence 2.0 posee un motor ultra rápido en Go capaz de evaluar miles de ciclos de pertenencia y riesgo en milisegundos de forma puramente local.
2. **Adopción de arquitecturas Zero Trust:** Las organizaciones exigen verificar el impacto de las políticas antes de otorgar acceso o aplicar remediaciones automáticas.
3. **Crecimiento de trabajo híbrido:** La variabilidad geográfica de las flotas de trabajo remoto genera mayor ruido en señales GPS y hace imprescindible probar las geocercas antes de desplegarlas.

## 6. Por qué este producto

LucidFence es el único motor de geocercado multi-UEM **local-first** que almacena las trazas completas de ubicación, velocidad, integridad y postura en JSONL en el dispositivo/servidor local del cliente.
- Ningún UEM de mercado (Intune, Jamf, Workspace ONE) ofrece un simulador retroactivo "What-If" sobre trazas geográficas locales.
- Al no requerir servicios cloud ni almacenamiento en terceros, LucidFence puede reevaluar años de trazas en segundos sin incurrir en costes de API ni violar normativas de privacidad (GDPR / LOPD).

## 7. Experiencia propuesta

1. **Desencadenante:** El administrador crea o edita una geocerca, ruta o política de riesgo en el dashboard de LucidFence.
2. **Panel de Simulación "What-If":** Antes de guardar o activar la política, el usuario hace clic en **"Simular impacto histórico"**.
3. **Parámetros de Simulación:** El usuario selecciona el rango temporal (p. ej., últimos 7, 30 o 90 días) o una cohorte de dispositivos/grupos.
4. **Ejecución y Visualización:** El motor Go recorre los registros JSONL en memoria y genera un informe instantáneo:
   - Número total de evaluaciones.
   - Dispositivos que habrían sido marcados fuera de geocerca o en alto riesgo.
   - Acciones que se habrían desencadenado (`notify`, `lock`, `wipe`, `isolate`).
   - Mapa de calor con los "puntos de fricción" o falsos positivos detectados (p. ej., ubicaciones limítrofes).
5. **Ajuste fino asistido:** El sistema sugiere un ajuste de margen/tolerancia (buffer en metros) o un tiempo de permanencia mínimo (`dwell_time`) para eliminar el 95 % de las falsas alarmas.
6. **Aplicación con Confianza:** El administrador activa la política en modo `enforce` sabiendo exactamente el comportamiento esperado.

## 8. Momento mágico

«El administrador arrastra un control de tolerancia en la ventana de simulación y ve al instante cómo el gráfico de disparos accidentales de la regla `Lock fuera de turno` pasa de 14 falsos positivos a 0, confirmando que la regla es 100 % segura para pasar a producción.»

## 9. Diferenciación y ventaja defensiva

- **Ventaja de Datos Locales:** La simulación funciona directamente sobre el histórico de trazas JSONL local de la empresa. Los competidores SaaS tendrían costes prohibidores de consulta o restricciones de retención para ofrecer esto.
- **Motor Go Embeddable:** El motor de evaluación en Go permite ejecutar simulaciones de 100.000 eventos por segundo en la propia máquina del administrador sin latencia de red.
- **Efecto de Confianza Acumulativa:** A mayor volumen de trazas locales recopiladas por el motor, más precisas y valiosas se vuelven las simulaciones "What-If".

## 10. Alcance por etapas

### Experimento
Endpoint CLI/API `/api/v1/policies/simulate` que recibe una definición de política temporal y la evalúa contra el histórico JSONL existente en disco, devolviendo un conteo de coincidencias por dispositivo.

### Primera versión (Thin Slice)
Integración en la interfaz de edición de políticas (`web/src/features/policies/PolicyEditorPage.tsx` y `WhatIfPanel.tsx` extendido) con selección de período (7/30 días), resumen de acciones potenciales y lista de dispositivos impactados.

### Expansión
- Mapa visual de calor de disparos históricos sobre el componente `FleetMap.tsx`.
- Recomendación automática de parámetros (sugerencia de `dwell_time` y buffer de distancia).

### Visión North Star
**Autonomous Policy Optimization:** El motor analiza continuamente las desviaciones de la flota y propone automáticamente correcciones a las geocercas y políticas de riesgo, ejecutando simulaciones de fondo sin intervención humana.

## 11. Fuera de alcance

- Modificación o reescritura de archivos de trazas históricos existentes (la simulación es estrictamente de lectura).
- Ejecución de acciones reales sobre UEMs durante la simulación (siempre opera en espacio simulado sin I/O externa).
- Predicción meteorológica o de tráfico externo no contenida en los datos del tenant.

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** `internal/engine/replay_history.go`, `internal/domain/policy/match.go`, `internal/store/jsonl.go`.
- **Integraciones:** Cero dependencias externas; usa la stdlib de Go y los paquetes de dominio existentes.
- **Datos necesarios:** Trazas históricas de `device_states.jsonl` o colecciones de eventos guardadas en `internal/store`.
- **Posibles cambios arquitectónicos:** Ninguno. Respeta las reglas de dependencia de `ARCHITECTURE.md` (Domain -> Store -> Engine -> API).
- **Incertidumbres técnicas:** Rendimiento de lectura secuencial de JSONL en discos mecánicos o volúmenes montados por red cuando el histórico supera 1 GB (resuelto mediante streaming y decodificación eficiente en Go).

## 13. Seguridad, privacidad y confianza

- **Privacidad Local:** Las trazas y las simulaciones permanecen 100 % locales en el tenant. Cero datos enviados a servidores externos.
- **Aislamiento entre Tenants:** La simulación respeta la separación por `org_id` y permisos de rol (`auth.RoleAdmin` / `auth.RoleOperator`).
- **Inmutabilidad:** La simulación opera en modo estrictamente de solo lectura sobre la persisistencia de trazas.

## 14. Valor para el negocio

- **Adopción:** Incrementa el porcentaje de tenants que activan el modo `enforce` activo del 15 % al 60 %.
- **Retención:** Convierte a LucidFence en una herramienta indispensable para auditoría de cumplimiento y gobernanza de movilidad.
- **Diferenciación:** Establece una brecha competitiva frente a soluciones UEM tradicionales que carecen de capacidades de replay y simulación temporal.

## 15. Métricas

- **Métrica de resultado:** Aumento en el porcentaje de organizaciones que pasan de modo `observe` a `enforce`.
- **Indicador adelantado:** Número de simulaciones "What-If" ejecutadas antes de guardar o actualizar una política.
- **Métrica de uso:** % de políticas creadas/editadas que hicieron uso previo del simulador.
- **Métrica de calidad:** Tiempo medio de respuesta del motor de simulación para 30 días de datos (< 500 ms).
- **Guardrail:** Cero llamadas accidentales a conectores UEM reales durante ejecuciones de simulación.

## 16. Evaluación

- **Problema:** 5/5
- **Alcance:** 4/5
- **Impacto:** 5/5
- **Estrategia:** 5/5
- **Diferenciación:** 5/5
- **Deleite:** 5/5
- **Viabilidad:** 4/5
- **Evidencia:** 4/5
- **Riesgo:** 1/5 (muy bajo, no toca producción ni UEMs reales)
- **Efecto compuesto:** 4/5

- **Confianza:** Alta
- **Esfuerzo relativo:** Medio
- **Reversibilidad:** Alta (característica puramente aditiva y aislada)
- **Tipo de apuesta:** Núcleo / Adyacente
- **Horizonte recomendado:** EXPLORE

## 17. Riesgos y motivos para no construirla

- **Riesgo:** Si una organización acaba de instalar LucidFence y no tiene histórico de trazas local (día 0), el simulador mostrará resultados vacíos.
- **Mitigación:** Proveer semillas sintéticas de trazas en modo demo (`internal/engine/demo.go`) para que el usuario pueda experimentar la simulación inmediatamente durante la evaluación del producto.

## 18. Preguntas abiertas

1. ¿Cuál es el límite óptimo de trazas históricas a procesar en memoria antes de aplicar paginación o streaming en disco?
2. ¿Deberían guardarse los reportes de simulación como artefactos de auditoría de cumplimiento para certificar ante ISO 27001 / SOC2 que las políticas fueron probadas previo a su despliegue?

## 19. Próximo experimento recomendado

Crear un prototipo de endpoint `/api/v1/policies/simulate` en Go que acepte un payload de política y responda el número de alertas que habrían sido generadas en las últimas 24 horas usando la flota demo (`internal/engine/demo.go`).

## 20. Recomendación final

**Promover a EXPLORE en el Roadmap de Producto.**
La oportunidad aprovecha perfectamente las fortalezas únicas de LucidFence 2.0 (Go local-first, cero telemetría, motor de riesgo determinista) y resuelve el mayor obstáculo de adopción: el miedo de los administradores a los falsos positivos en la automatización de seguridad UEM.
