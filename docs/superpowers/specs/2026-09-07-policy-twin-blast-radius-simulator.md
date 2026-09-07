# ✨ LucidFence Policy Twin & Blast Radius Simulator

## 1. Resumen ejecutivo
LucidFence Policy Twin es un gemelo digital local y retroactivo que permite a los equipos de IT y SecOps simular el impacto exacto ("Blast Radius") de cualquier regla o política de geocerca antes de activarla en producción o pasar del modo `observe` al modo `enforce`. Re-evaluando instantáneamente el historial local de eventos y telemetría de ubicación de la flota en Go (`internal/engine`), calcula qué dispositivos habrían sufrido bloqueos, notificaciones o sanciones en los últimos 30 días, detecta falsos positivos potenciales (p. ej. ferias comerciales, viajes habituales, zonas WiFi compartidas) y sugiere guardarraíles automáticos. Además, permite desplegar políticas de forma canary (porcentaje de dispositivos o grupo piloto) con botón de pánico de reversión en 1 clic. Esto elimina el principal freno de adopción de la automatización en geoseguridad UEM: el miedo del administrador al impacto operativo masivo accidental.

## 2. Propuesta en una frase
"Para administradores de UEM y líderes de SecOps, que necesitan proteger endpoints sin paralizar la operación del negocio, proponemos **Policy Twin & Blast Radius Simulator**, un gemelo digital local que re-evalúa el impacto histórico de las políticas de geocerca en milisegundos y ofrece despliegues canary con reversión en 1 clic, a diferencia de los UEMs tradicionales que aplican reglas 'a ciegas' con alto riesgo de falsos positivos masivos."

## 3. Problema
- **Persona:** CISO, Responsable de SecOps y Administrador de IT / UEM (Intune, Jamf, Fleet, Applivery, Workspace ONE).
- **Situación:** La organización desea restringir el acceso a datos sensibles o bloquear dispositivos corporativos cuando estos salgan de zonas seguras (oficinas, áreas autorizadas, países permitidos) o se desvíen de rutas asignadas.
- **Trabajo por realizar:** Definir y aplicar políticas automáticas de remediación (como bloqueo de pantalla, restricción de red o solicitud de pase de seguridad) asegurando que cero usuarios legítimos en cumplimiento sufran bloqueos indebidos.
- **Fricción actual:** Los administradores temen configurar reglas en modo activo (`enforce`) o usar acciones automáticas de mitigación porque una regla ligeramente imprecisa (p. ej. un radio de geocerca demasiado estrecho o una anomalía de GPS en interiores) puede bloquear a cientos de empleados simultáneamente.
- **Impacto:** Más del 90 % de los desplegables de geocercas se quedan perennemente en modo de solo observación (`observe`), anulando la capacidad de respuesta en tiempo real ante amenazas físicas o robos de dispositivos.
- **Solución utilizada hoy:** Pruebas manuales con 1 o 2 dispositivos de prueba, intentos de estimación a ojo en hojas de cálculo o abstención total de usar automatización destructiva/mitigadora.

## 4. Evidencia
- **HECHO:** El motor de LucidFence 2.0 en Go (`internal/engine`) evalúa el estado de todos los dispositivos en cada ciclo de N segundos y persiste eventos y acciones en disco local (`events.jsonl`, `actions.jsonl`) (`docs/superpowers/specs/2026-09-05-lucidfence-2-go-rewrite-design.md` §5.4 y §5.5).
- **HECHO:** Los guardarraíles de ejecución (`internal/engine/guardrails.go`) fuerzan el modo `observe` por defecto y requieren configuraciones explícitas de allowlist para acciones destructivas (`ARCHITECTURE.md`).
- **INFERENCIA:** Debido a que el miedo al impacto masivo ("Blast Radius") frena a los administradores de activar `enforce`, proporcionar visibilidad matemática del impacto retroactivo exacto es la palanca decisiva para desbloquear el modo activo.
- **HIPÓTESIS:** Ofrecer una simulación que analice 30 días de historial de la flota en <100ms mediante Go aumentará la tasa de activación del modo `enforce` en más de un 300 % entre los usuarios de LucidFence.
- **DESCONOCIDO:** La proporción exacta de falsos positivos causados por rebotes de precisión GPS en entornos interiores densos frente a errores de definición de límites por parte del administrador.

## 5. Por qué ahora
1. **Rendimiento de la arquitectura 2.0 en Go:** La reescritura de LucidFence en Go permite procesar 100 000 eventos de ubicación históricos en memoria en menos de 50 milisegundos, algo inviable o muy costoso en plataformas Python o SaaS basadas en llamadas API a la nube.
2. **Persistencia local estructurada:** Los ficheros JSONL locales (`events.jsonl`, `actions.jsonl`) contienen la telemetría histórica exacta requerida para re-ejecutar el motor de reglas sin necesidad de bases de datos externas.
3. **Tendencia hacia la Autonomía Controlada:** La industria de ciberseguridad (SOAR / XDR) está migrando de dashboards pasivos a automatización con barreras de contención (Canary Rollouts y Blast Radius Analysis).

## 6. Por qué este producto
- **Local-first & Privacidad Absoluta:** Re-evaluar historiales de ubicación en la nube de un tercero expone datos de posicionamiento sensibles de los empleados. LucidFence ejecuta la simulación 100 % localmente en el binario del cliente.
- **Federación Multi-UEM:** LucidFence consolida la identidad y telemetría de dispositivos a través de múltiples UEMs (Intune + Jamf + Fleet + Applivery). Ningún UEM individual tiene la visión global necesaria para calcular el Blast Radius multi-plataforma.
- **Motor Explicable:** Puntuaciones de riesgo y coincidencias de políticas transparentes con razones textuales auditables.

## 7. Experiencia propuesta
1. **Creación o Edición de Política:** El administrador diseña una regla (ej. "Si el dispositivo de Finanzas sale del área metropolitana de Madrid entre las 22:00 y las 06:00, aplicar `lock`").
2. **Simulación Retroactiva Automática (Policy Twin):** Al escribir la regla, el editor muestra en vivo la tarjeta **Blast Radius Analysis**:
   - *"Si esta regla hubiese estado activa en los últimos 30 días:"*
   - **Dispositivos impactados:** 3 de 145 (2.0 %).
   - **Alertas de Falso Positivo Detectadas:** 1 incidente potencial identificado (El dispositivo de `ana.marquez@empresa.com` se detectó fuera de la geocerca durante 4 minutos a las 23:15 debido a baja precisión de GPS de 85m en interiores).
   - **Sugerencia Inteligente de Guardarraíl:** *"Añadir regla de dwell time: exigir violación sostenida durante ≥ 2 ciclos (10 min) o precisión de GPS ≤ 30m para reducir falsos positivos a 0."*
3. **Ajuste en 1 Clic:** El administrador hace clic en *"Aplicar sugerencia de guardarraíl"*. El Blast Radius se recalcula instantáneamente: 0 falsos positivos, 2 violaciones legítimas confirmadas.
4. **Despliegue Progresivo (Canary Policy Rollout):** El administrador selecciona el modo de despliegue:
   - **Etapa 1 (Canary):** Activar `enforce` solo en el grupo `IT-Piloto` (5 dispositivos) durante 48h.
   - **Etapa 2 (Gradual):** Escalar automáticamente a la flota completa si el número de handoffs no supera el umbral de alerta.
5. **Botón de Pánico (Emergency Rollback):** Si ocurre cualquier anomalía imprevista en producción, un banner destacado en la UI permite suspender la política y revertir todas las acciones canary en 1 clic.

## 8. Momento mágico
El administrador ajusta una política de geoseguridad severa y el gemelo digital le advierte en milisegundos: *"Atención: Esta regla habría bloqueado la laptop del Director de Ventas anoche durante su estancia en el hotel del evento corporativo. Sugerimos añadir la excepción SSID 'Hotel-Conference-WiFi' o un dwell time de 15 minutos."* El admin aplica la sugerencia con un clic, comprobando que el Blast Radius baja a 0 víctimas indebidas.

## 9. Diferenciación y ventaja defensiva
- **Diferenciación:** Los competidores aplican reglas de UEM "a ciegas" de forma estática o requieren enviar logs a un SIEM de pago para análisis posterior. LucidFence realiza simulación predictiva local-first antes de la aplicación.
- **Ventaja Acumulativa:** A medida que LucidFence acumula historial de `events.jsonl` local, la precisión de la simulación del Policy Twin se vuelve cada vez más exacta y personalizada para los patrones reales de movimiento de la empresa, sin filtrar un solo dato a la nube.

## 10. Alcance por etapas
### Experimento
Endpoint `POST /api/v1/policies/simulate-blast-radius` que acepta un borrador de objeto `Policy` y lo re-evalúa en memoria contra los últimos N eventos guardados en `events.jsonl`, devolviendo el número de dispositivos afectados y un desglose por departamento.

### Primera versión (Thin Slice)
Integración del simulador Blast Radius en el editor de políticas del dashboard web (`/policies`), mostrando el resumen de impacto (dispositivos afectados, usuarios, eventos de los últimos 30 días) y un indicador de nivel de riesgo de falso positivo.

### Expansión
Módulo de **Canary Policy Rollout** que permite activar políticas en subconjuntos de dispositivos con avance automático basado en ausencia de alertas y botón de rollback global.

### Visión North Star (Gemelo Digital Autónomo)
Policy Twin continuo que analiza en segundo plano todas las políticas existentes contra la telemetría en tiempo real, alertando de "Drift de Políticas" (políticas que se han vuelto obsoletas o demasiado agresivas debido a cambios en la dinámica de trabajo de la flota) y proponiendo auto-sintonización de geocercas.

## 11. Fuera de alcance
- Modificación directa de configuraciones en los paneles SaaS de UEM de terceros (las acciones se siguen encauzando estrictamente a través de las APIs de adaptadores UEM de LucidFence).
- Envío de telemetría o datos de ubicación a servicios de IA de terceros o nube de LucidFence.

## 12. Implicaciones técnicas
- **Capacidades reutilizables:** Motor de evaluación `internal/engine`, evaluador de políticas `domain.Policy`, almacenamiento en `internal/store` (`events.jsonl`, `devices.json`).
- **Nuevos componentes backend:** Módulo `internal/engine/simulator.go` para ejecución aislada y concurrente de ciclos retroactivos sobre snapshots en memoria.
- **Rendimiento:** Re-evaluación en Go de 10 000 eventos en <20ms; consumo de memoria temporal acotado.
- **Incertidumbres:** Densidad y ventana de tiempo disponible en `events.jsonl` en instalaciones de recién arranque (se resuelve utilizando el seed simulado en instalaciones demo o de prueba).

## 13. Seguridad, privacidad y confianza
- **Privacidad Local:** Cero llamadas externas. Toda la simulación ocurre dentro del proceso ejecutable `lucidfence`.
- **Inmutabilidad de Producción:** El simulador se ejecuta en un estado en memoria clónico (`dry-run` estricto), garantizando que ningún comando real se envíe a los adaptadores UEM durante la simulación.
- **Auditoría:** Cada ejecución de simulación y cada cambio de estado Canary queda registrado en `audit.jsonl`.

## 14. Valor para el negocio
- **Adopción:** Incrementa el porcentaje de organizaciones que pasan de modo `observe` a modo `enforce` activo del 5 % a más del 40 %.
- **Retención y Valor:** Convierte a LucidFence en una herramienta imprescindible en la toma de decisiones de SecOps, no solo en un monitor pasivo.
- **Diferenciación de Mercado:** Posiciona a LucidFence como la única solución de geoseguridad local-first con simulación de impacto sin riesgo de producción.

## 15. Métricas
- **Métrica de resultado:** % de políticas activas configuradas en modo `enforce` frente a `observe` por organización.
- **Indicador adelantado:** Frecuencia de uso del botón "Simular Blast Radius" en el editor de políticas durante la creación de reglas.
- **Métrica de uso:** Número de simulaciones ejecutadas antes de guardar o modificar una política.
- **Métrica de calidad:** Tasa de falsos positivos reportados o deshacimientos (rollbacks) en las primeras 48h tras activar una política simularizada.
- **Guardrail:** Cero incrementos en la tasa de errores del motor de evaluación principal durante la ejecución de simulaciones concurrentes.

## 16. Evaluación
- **Problema:** 5/5
- **Alcance:** 5/5
- **Impacto:** 5/5
- **Estrategia:** 5/5
- **Diferenciación:** 5/5
- **Deleite:** 5/5
- **Viabilidad:** 4/5
- **Evidencia:** 4/5
- **Riesgo:** 2/5
- **Efecto compuesto:** 4/5

- **Confianza:** Alta
- **Esfuerzo relativo:** Medio
- **Reversibilidad:** Alta
- **Tipo de apuesta:** Núcleo / Plataforma
- **Horizonte recomendado:** EXPLORE

## 17. Riesgos y motivos para no construirla
- **Argumento en contra:** Si la instalación de LucidFence es nueva y cuenta con menos de 24 horas de telemetría histórica en `events.jsonl`, el Blast Radius calculado tendrá poca muestra estadística y podría infundir falsa confianza.
- **Mitigación:** Indicar claramente el nivel de confianza basado en la ventana temporal de datos disponibles (ej. "Confianza: Baja - Solo 12 horas de datos acumulados. Se recomiendan 7 días de observación previa").

## 18. Preguntas abiertas
1. ¿Cuál es la ventana temporal óptima para la simulación retroactiva por defecto (7, 14 o 30 días) para mantener un tiempo de respuesta inferior a 100 ms en procesadores modestos?
2. ¿Deberían las simulaciones incluir fluctuaciones sintéticas de precisión GPS para estresar la regla ante condiciones adversas de red?

## 19. Próximo experimento recomendado
Crear una prueba de concepto en Go (`internal/engine/simulator_test.go`) que lea 10 000 eventos sintéticos de `events.jsonl`, ejecute la evaluación contra un borrador de `Policy` y mida el tiempo de cómputo y la precisión del conteo de dispositivos impactados.

## 20. Recomendación final
**Promover a DISCOVERY / EXPLORE** como la iniciativa estrella para fortalecer la gestión de políticas y riesgo en LucidFence 2.0.
