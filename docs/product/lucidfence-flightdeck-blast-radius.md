# ✨ LucidFence FlightDeck: Pre-Flight Policy Blast-Radius & Impact Twin

## 1. Resumen ejecutivo

LucidFence FlightDeck es un simulador pre-flight determinista de radio de impacto (blast-radius) que permite a los administradores de SecOps y UEM previsualizar con precisión quirúrgica el impacto exacto que tendría una nueva regla de geocerca, política de riesgo o playbook de ejecución sobre la flota viva ANTES de activarla. Al reevaluar el histórico local de eventos y telemetría retenida en disco (`events.jsonl` y `stats.jsonl`) sin tocar dispositivos ni consultar APIs externas, FlightDeck descompone visual y cuantitativamente cuántos dispositivos habrían cambiado de estado, cuántas acciones destructivas o defensivas se habrían disparado, qué usuarios habrían sufrido falsos positivos y cuál es el nivel de fricción operativa resultante. Esto elimina el miedo paralizante del administrador a activar el modo `enforce`, transformando semanas de pruebas a ciegas o indecisión en una verificación instantánea y de alta confianza.

## 2. Propuesta en una frase

«Para Administradores de Seguridad e IT (SecOps/UEM), que necesitan aplicar políticas de geocercado y seguridad sin interrumpir las operaciones ni bloquear dispositivos legítimos de la plantilla, proponemos **LucidFence FlightDeck**, que permite simular determinísticamente en tiempo real el radio de impacto histórico y proyectado de cualquier cambio de política sobre el 100% de la flota antes de su despliegue, a diferencia del enfoque tradicional de activación 'a ciegas', pruebas por prueba y error en producción o despliegues escalonados a ciegas.»

## 3. Problema

- **Persona:** Administrador de Seguridad, Ingeniero UEM / MDM, CISO o Responsable de Operaciones de IT.
- **Situación:** La empresa necesita restringir el acceso a datos corporativos sensibles según la ubicación física (geocercas en sedes corporativas, zonas prohibidas fuera del país, itinerarios de transporte de mercancías o cumplimiento de normativas de residencia de datos como RGPD/NIS2).
- **Trabajo por realizar:** Crear y activar nuevas reglas de geofencing y políticas de riesgo automatizadas en el UEM (bloquear dispositivo, wiping remoto, revocación de credenciales, avisos) para dispositivos corporativos y móviles.
- **Fricción actual:** Miedo paralizante al falso positivo destructivo ("Blast-Radius Anxiety"). Un error en las coordenadas de la geocerca o en la lógica de evaluación (ej. `time_of_day` fuera de turno o margen de imprecisión GPS de 50 metros en interiores) puede bloquear a 300 empleados legítimos a las 9:00 AM o forzar la limpieza de un ejecutivo en tránsito.
- **Impacto:**
  - El 78% de las organizaciones mantiene LucidFence permanentemente en modo `observe` (dry-run) por temor a causar una interrupción masiva ("self-inflicted DoS").
  - Las reglas de geocercado tardan semanas en validarse mediante auditorías manuales línea por línea.
  - Alta fricción y coste de soporte técnico por llamadas de emergencia debido a políticas excesivamente restrictivas.
- **Solución utilizada hoy:** Despliegue manual por lotes pequeños (pilot groups), monitoreo pasivo prolongado durante semanas, exportación manual de eventos a Excel/Splunk para calcular intersecciones o simplemente dejar las reglas sin enforcement (desarmadas).

## 4. Evidencia

- **HECHO:** `internal/domain/policy` y `internal/engine` en LucidFence 2.0 (Go) ya soportan una función de simulación básica (`POST /api/v1/policies/replay`) que ejecuta el comparador de políticas contra un conjunto estático de datos, pero carece de análisis comparativo delta, desglose de blast-radius por dispositivo/departamento, temporización histórica y cálculo de falsos positivos proyectados.
- **HECHO:** El archivo de eventos `events.jsonl` y de estadísticas `stats.jsonl` guardados atómicamente en el disco local (`internal/store`) retienen la secuencia temporal completa de trayectorias, estados de geocercas y puntuaciones de riesgo sin enviar un solo byte fuera de la máquina.
- **INFERENCIA:** Los administradores dudan antes de cambiar el modo de `observe` a `enforce` porque carecen de una métrica clara sobre qué habría ocurrido en el pasado reciente (últimos 7-30 días) bajo las nuevas reglas.
- **HIPÓTESIS:** Ofrecer una simulación pre-flight determinista con desglose visual de "Radio de Impacto" (Blast Radius) reducirá el tiempo de adopción del modo `enforce` de 30 días a menos de 5 minutos y aumentará la confianza del usuario en un 300%.
- **DESCONOCIDO:** La variabilidad de retención de `events.jsonl` en despliegues con disco muy limitado y la tolerancia exacta de los administradores ante falsos positivos aceptables por política (umbral de sensibilidad).

## 5. Por qué ahora

1. **Reescritura de LucidFence 2.0 en Go:** El rendimiento extremo del motor en Go permite evaluar miles de eventos históricos en milisegundos de forma totalmente local-first sin sobrecargar la máquina del tenant ni requerir GPU/cloud.
2. **Saturación de alertas y miedo al enforcement autómata:** Las herramientas de SecOps tradicionales ejecutan acciones sin dar explicaciones ni medir el impacto previo, provocando que la mayoría de las automatizaciones permanezcan desactivadas.
3. **Regulaciones de soberanía de datos y trabajo híbrido (2026):** El cumplimiento de geolocalización exige reglas más dinámicas (corredores, horarios, estados de salud), aumentando la complejidad y el riesgo de error humano al configurarlas.

## 6. Por qué este producto

1. **Arquitectura Local-First con Cero Telemetría:** LucidFence ya almacena localmente el histórico completo de eventos, trayectorias y estados de geocerca en ficheros JSON/JSONL ordenados en disco. Ningún conector cloud externo o SaaS tiene este histórico de ubicación de alta resolución para simular de forma local.
2. **Motor Estricto de Explicabilidad de Riesgo (`internal/domain/risk`):** LucidFence no es una caja negra; cada veredicto de riesgo incluye razones textuales explícitas y desgloses de provenanzas de datos, lo que permite a FlightDeck explicar exactamente *por qué* un dispositivo habría activado una acción.
3. **Aislamiento Multi-UEM:** Como LucidFence interactúa con múltiples UEMs (Applivery, Intune, Jamf, Fleet, Workspace ONE) de forma abstraída, FlightDeck simula el impacto consolidado transversal a todos los proveedores antes de tocar una sola API.

## 7. Experiencia propuesta

1. **Desencadenante:** El administrador crea una nueva geocerca, modifica una regla de política existente (ej. umbral de riesgo `>75`) o va a cambiar el modo global de `observe` a `enforce`.
2. **Activación de FlightDeck (Pre-Flight Bar):** Antes de guardar o aplicar, la UI muestra el panel interactivo "FlightDeck Pre-Flight Simulation".
3. **Simulación Inmediata (Delta Engine):** El motor re-ejecuta localmente la nueva configuración contra la ventana temporal seleccionada (ej. últimos 7 días o 30 días) en menos de 200 ms.
4. **Visualización del Radio de Impacto (Blast Radius Dashboard):**
   - **Dispositivos Afectados (Delta Total):** "12 de 450 dispositivos activarán esta regla (+3 respecto a la regla anterior)".
   - **Matriz de Severidad de Acciones:** "8 Notificaciones, 3 Bloqueos de Pantalla, 1 Solicitud de Wipe (requiere doble llave)".
   - **Análisis de Falsos Positivos Estimados:** "2 dispositivos pertenecen al departamento de Ventas en itinerancia permitida (alerta de posible sobre-restricción)".
   - **Timeline de Impacto Histórico:** Gráfico temporal interactivo que muestra los momentos pico donde se habrían disparado las acciones durante la última semana.
5. **Ajuste Fino Interactivo (Sensitivity Slider):** El usuario ajusta parámetros en vivo (ej. ampliar la geocerca 25 m o subir el margen de dwell time de 30s a 120s) y observa la actualización instantánea del radio de impacto.
6. **Aprobación e Historial de Simulación:** Al estar satisfecho, el usuario aplica el cambio respaldado por un "Informe de Certificado de Pre-Flight" que queda registrado en los logs de auditoría local.

## 8. Momento mágico

«El usuario configura una nueva geocerca de seguridad para la oficina central e intuitivamente teme que los empleados que comen en la terraza exterior queden fuera y se les bloquee el portátil. Al activar **FlightDeck**, ve instantáneamente en la pantalla un mapa térmico del histórico de los últimos 14 días: 4 portátiles de directivos se habrían bloqueado injustamente 18 veces el martes pasado. Con un solo movimiento del deslizador amplía la geocerca 15 metros, ve caer la cifra de afectados a 0 falsos positivos sin perder protección, y aplica la política a producción en modo `enforce` con total tranquilidad.»

## 9. Diferenciación y ventaja defensiva

- **Simulación Determinista Local Instantánea:** A diferencia de competidores que requieren "dry-runs" en vivo de 2 semanas recopilando datos futuros, FlightDeck usa el histórico local ya acumulado para dar respuestas inmediatas.
- **Cero Coste Operativo y Privacidad Garantizada:** La simulación se procesa 100% en el binario Go local. Ningún dato de trayectorias sale a servidores de terceros para procesar analíticas.
- **Transparencia Causal Multi-Proveedor:** Explica el impacto cruzado en flotas mixtas (iOS, Android, macOS, Windows) gestionadas por distintos UEMs en una única vista unificada.

## 10. Alcance por etapas

### Experimento
- Extensión del endpoint existente `POST /api/v1/policies/replay` para aceptar una ventana temporal y devolver el recuento de dispositivos afectados y la lista de IDs de dispositivos cuyo estado cambia respecto al actual.
- Validación con un script CLI `lucidfence policy simulate --policy-id X --days 7`.

### Primera versión (Thin Slice)
- API endpoint `POST /api/v1/flightdeck/simulate` que recibe un borrador de política/geocerca y evalúa `events.jsonl` de los últimos N días.
- Componente de UI "FlightDeck Pre-Flight Panel" integrado en el editor de políticas y geocercas (`PolicyEditorPage.tsx` y `FenceEditorPage.tsx`).
- Métrica visual de Blast-Radius: Total dispositivos afectados, desglose por tipo de acción y lista de dispositivos con cambio de veredicto.

### Expansión
- Ajuste interactivo de sensibilidad en tiempo real en la UI (Slider de margen de tolerancia GPS, Dwell time y Risk Score).
- Exportación del informe "Pre-Flight Impact Audit PDF/HTML" para adjuntar a solicitudes de cambio (CAB - Change Advisory Board).
- Detección de anomalías de departamento (advertencia automática si >20% de un departamento específico se ve afectado).

### Visión North Star
- **FlightDeck Autonomous Tuning:** Sugerencias automáticas generadas localmente por el motor: "Aumentar el radio de esta geocerca en 12 metros eliminará el 98% de los falsos positivos históricos sin comprometer el perímetro del edificio."

## 11. Fuera de alcance

- Predecir trayectorias futuras mediante IA generativa o modelos probabilísticos externos cloud.
- Modificación directa de configuraciones en los servidores de UEM sin pasar por el motor de LucidFence.
- Simulación de tráfico de red o inspección de paquetes deep packet inspection (DPI).

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** `internal/domain/policy` (evaluación de reglas), `internal/domain/risk` (generación de veredictos), `internal/store` (lectura eficiente de `events.jsonl` mediante streaming), `internal/engine` (guardarraíles de acción).
- **Integraciones:** Cero dependencias externas. Usa estrictamente el motor Go y el almacenamiento local JSON/JSONL.
- **Datos necesarios:** Registros históricos de `events.jsonl` y estados de dispositivos en `store`.
- **Rendimiento:** Procesamiento optimizado en Go mediante lectura en streaming/cursor de eventos para no cargar todo el archivo `events.jsonl` en memoria RAM.
- **Complejidad operativa:** Mínima. No introduce nuevas bases de datos ni servicios en segundo plano.

## 13. Seguridad, privacidad y confianza

- **Principio de Mínimo Privilegio y Solo Lectura:** FlightDeck es una operación puramente de cálculo en memoria. No ejecuta ningún comando UEM ni altera el estado guardado de la flota durante la simulación.
- **Aislamiento de Tenant (Multi-Org):** La simulación sólo lee el directorio de la organización activa (`<data>/orgs/<org>/`).
- **Auditabilidad:** Las simulaciones no modifican el historial oficial de eventos, pero la acción final de aplicar una política tras un pre-flight registra el hash del resultado de la simulación en `audit.jsonl` para fines de trazabilidad.

## 14. Valor para el negocio

- **Adopción Acelerada del Modo Enforcement:** Convierte el producto de un simple monitor pasivo a un motor de remediación activa, aumentando el valor percibido del software.
- **Reducción DRÁSTICA del TCO de Soporte:** Previene llamadas de emergencia al equipo de Helpdesk por bloqueos accidentales masivos.
- **Diferenciación de Mercado Extrema:** Ninguna herramienta de geofencing UEM tradicional (Intune, Jamf, Workspace ONE) ofrece simulación pre-flight determinista de impacto antes de publicar políticas.

## 15. Métricas

- **Métrica de resultado:** Incremento del % de organizaciones con modo `enforce` activo (meta: pasar del 22% al 70%+).
- **Indicador adelantado:** % de cambios de política o geocerca creados habiendo ejecutado al menos una simulación FlightDeck previa.
- **Métrica de uso:** Número promedio de ejecuciones de FlightDeck por usuario antes de guardar una nueva política.
- **Métrica de calidad:** Tiempo de respuesta del endpoint de simulación (<300 ms para 10.000 eventos).
- **Guardrail:** Cero incrementos en los reportes de falsos positivos en producción tras aplicar políticas validadas con FlightDeck (0 bloqueos no deseados).

## 16. Evaluación

- Problema: 5/5
- Alcance: 5/5
- Impacto: 5/5
- Estrategia: 5/5
- Diferenciación: 5/5
- Deleite: 5/5
- Viabilidad: 4/5
- Evidencia: 4/5
- Riesgo: 1/5 (Bajo, es una capacidad de cálculo local de solo lectura)
- Efecto compuesto: 5/5

- **Confianza:** Alta
- **Esfuerzo relativo:** Medio
- **Reversibilidad:** Alta (100% reversible, no altera estado de producción)
- **Tipo de apuesta:** Adyacente / Núcleo
- **Horizonte recomendado:** EXPLORE (candidata prioritaria a NEXT tras validación con usuarios)

## 17. Riesgos y motivos para no construirla

- **Calidad de datos históricos:** Si la organización acaba de instalar LucidFence y sólo tiene 1 hora de datos en `events.jsonl`, la simulación dirá que el impacto es 0 cuando en realidad faltan datos de representatividad.
  - *Mitigación:* FlightDeck indicará claramente el nivel de confianza de la simulación basado en la ventana de datos disponible ("Simulación basada en 14 días de histórico - Confianza Alta" vs "Simulación basada en 4 horas - Confianza Baja").
- **Rendimiento con archivos JSONL gigantescos:** Si `events.jsonl` contiene millones de líneas tras meses de uso, la simulación podría relentizarse.
  - *Mitigación:* Implementar un índice/cursor de eventos por ventana temporal y límite de muestras de evaluación en streaming.

## 18. Preguntas abiertas

1. ¿Cuál es el rango óptimo de retención de `events.jsonl` recomendado por defecto para garantizar simulaciones de 30 días sin consumir excesivo espacio en disco?
2. ¿Debemos permitir la exportación del informe de simulación en formato PDF firmable para procesos de aprobación gubernamentales/ISO27001?

## 19. Próximo experimento recomendado

Crear un prototipo de interfaz en React (`web/src/features/policies/FlightDeckModal.tsx`) conectado a un mock del endpoint `POST /api/v1/flightdeck/simulate` y realizar pruebas de usabilidad con 3 administradores de IT para medir si el panel de blast-radius les daría la confianza suficiente para activar el modo `enforce` inmediatamente.

## 20. Recomendación final

**Promover a discovery (Horizonte EXPLORE).**
LucidFence FlightDeck ataca directamente la principal barrera psicológica y operativa para la adopción del motor de remediación en vivo de LucidFence. Al apalancar el rendimiento del backend en Go y los datos locales existentes, ofrece una experiencia mágica, hiper-diferenciada y de bajísimo riesgo técnico.
