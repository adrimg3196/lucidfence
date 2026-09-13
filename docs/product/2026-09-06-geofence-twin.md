# ✨ Geofence Twin — Sintetizador de Geocercas y Simulador de Impacto Espacial

## 1. Resumen ejecutivo

Geofence Twin transforma la creación de geocercas y políticas de riesgo de un proceso manual propenso a errores a una experiencia de síntesis espacial autónoma y simulación de impacto en tiempo real. Utilizando la trazabilidad histórica almacenada localmente en LucidFence (100% privado, cero telemetría), Geofence Twin calcula automáticamente el polígono o corredor óptimo (Convex Hull + Buffer) para cualquier conjunto de dispositivos o instalaciones, y ejecuta una simulación instantánea ("Blast Radius") que predice exactamente cuántos eventos e incidentes se habrían generado en el pasado antes de activar la regla en producción. Esto elimina el riesgo de bloqueos accidentales de dispositivos y reduce el tiempo de configuración inicial en un 80%.

## 2. Propuesta en una frase

Para administradores de IT y SecOps que necesitan definir geocercas y políticas de seguridad sin causar interrupciones ni bloqueos indeseados en la flota, proponemos Geofence Twin, una experiencia que sintetiza de forma autónoma geometrías óptimas desde la trazabilidad local y simula su impacto real antes de desplegarlas, a diferencia del dibujo manual a ciegas en mapas de los UEMs tradicionales.

## 3. Problema

- **Persona:** Administrador de IT, Ingeniero de SecOps, Responsable de Seguridad de Flotas.
- **Situación:** La organización despliega dispositivos móviles o portátiles en nuevas oficinas, polígonos, rutas logísticas o clientes estratégicos y requiere delimitar zonas de seguridad.
- **Trabajo por realizar:** Definir geocercas y asociar políticas de riesgo (`risk_score > X` -> `lock` / `message` / `set_compliance`) para proteger los datos de la empresa cuando los dispositivos abandonen zonas autorizadas.
- **Fricción actual:** Dibujar polígonos o definir radios de círculos manualmente en un mapa es impreciso. Una geocerca circular en un edificio no rectangular abarca zonas externas públicas o ignora áreas operativas adyacentes. Un radio demasiado ajustado provoca bloqueos automáticos en dispositivos de empleados legítimos por fluctuaciones del GPS. Además, el administrador activa la regla "a ciegas", descubriendo los falsos positivos cuando un usuario legítimo sufre un bloqueo.
- **Impacto:** Bloqueos no deseados de dispositivos operativos, fatiga de alertas para el equipo de seguridad y desconfianza en la automatización del UEM, llevando frecuentemente a desactivar las acciones automáticas de respuesta.
- **Solución utilizada hoy:** Ensayo y error manual, consultar coordenadas en Google Maps/OSM, recopilar direcciones por correo electrónico o crear reglas muy laxas que pierden efectividad de seguridad.

## 4. Evidencia

- **HECHO:** LucidFence 2.0 Go implementa en `internal/domain/geo` funciones puras de geometría esférica (Haversine, Ray Casting, Distancia a Polilínea) y en `internal/engine/replay.go` un motor de replay determinista de políticas contra el histórico. (Fuente: `internal/domain/geo/` y `internal/engine/replay.go`).
- **HECHO:** Las observaciones y eventos pasados de la flota se persisten localmente en archivos JSONL (`events.jsonl`) respetando la soberanía local y la privacidad. (Fuente: `internal/store/jsonl.go`).
- **INFERENCIA:** La creación de geocercas en el dashboard actual se realiza mediante formularios de coordenadas manuales o búsqueda directa por dirección vía Nominatim, requiriendo intervención humana para calcular márgenes de error de ubicación.
- **HIPÓTESIS:** Más del 75% de las alertas falsas en geocercas corporativas se deben a geometrías estáticas no adaptadas al comportamiento espacial real de los dispositivos en el terreno.
- **DESCONOCIDO:** El porcentaje exacto de fluctuación de precisión GPS en interiores según la plataforma del dispositivo (iOS vs Android vs Windows) en clientes de LucidFence.

## 5. Por qué ahora

La reescritura en Go (LucidFence 2.0) completó en el hito M2 la separación limpia del dominio esférico puro (`internal/domain/geo`), un motor de evaluación de alto rendimiento (microsegundos por ciclo) y una estructura de persistencia atómica en disco. La ejecución de algoritmos de envolvente espacial y la simulación replay sobre miles de coordenadas históricas se ejecuta ahora en memoria local en milisegundos, sin necesidad de infraestructura GIS compleja ni servicios en la nube de pago.

## 6. Por qué este producto

LucidFence es 100% local-first y cero telemetría. La información de trazabilidad detallada de la flota de una empresa no se envía a servidores cloud de terceros. Esto otorga a LucidFence una ventaja defensiva única: puede analizar años de coordenadas históricas en la propia máquina del cliente para sintetizar polígonos exactos y predecir el impacto de políticas con total privacidad y cumplimiento de normativas de protección de datos (RGPD / CCPA).

## 7. Experiencia propuesta

1. **Iniciación:** En la vista de Geocercas o Políticas, el administrador hace clic en **"✨ Geofence Twin"**.
2. **Selección de Intención:** El admin selecciona el origen de datos:
   - Opción A: "Sintetizar desde dispositivos" (selecciona una etiqueta de flota, ej. `transporte-madrid`, y un periodo, ej. `últimos 14 días`).
   - Opción B: "Sintetizar desde dirección/POI" (introduce el sitio corporativo y el tipo de instalación).
3. **Síntesis Autónoma:** El motor local ejecuta la envolvente convexa ajustada (Convex Hull) y aplica un buffer esférico de tolerancia (ej. 25 m).
4. **Simulación Blast Radius:** La interfaz MapLibre renderiza inmediatamente:
   - El polígono o corredor sintetizado en verde/azul.
   - La nube de puntos de ubicación históricos.
   - Un panel de análisis de impacto: número total de pings analizados, porcentaje de cobertura del histórico (ej. 99.8%), violaciones potenciales detectadas en el pasado y lista de dispositivos que habrían activado la política.
5. **Ajuste Interactivo:** El administrador ajusta un dial de "Margen de Tolerancia (m)" o "Nivel de Rigurosidad". El polígono y las métricas de impacto se recalculan en tiempo real (< 100 ms).
6. **Despliegue Controlado:** Con un clic en **"Guardar y Activar en Modo Observe"**, la geocerca y la política asociada quedan registradas.

## 8. Momento mágico

El usuario se da cuenta del valor de la función cuando selecciona 30 dispositivos de reparto, pulsa "Sintetizar Geocerca Twin" y ve cómo en menos de 200 milisegundos el mapa dibuja el polígono exacto que cubre el 99.9% de los desplazamientos habituales, mostrándole un resumen que confirma: *"0 falsos positivos previstos sobre 14.500 observaciones pasadas. 2 desviaciones anómalas reales identificadas."*

## 9. Diferenciación y ventaja defensiva

- **Cómputo Local Soberano:** Síntesis espacial 100% en la máquina del tenant, sin fuga de trazabilidad GPS.
- **Simulación Blast Radius Determinista:** Ningún UEM del mercado ofrece predecir el impacto de una regla espacial contra datos pasados reales antes de aplicarla.
- **Resistencia a Falsos Positivos:** La geometría se adapta al comportamiento humano y GPS real, no a figuras geométricas teóricas.

## 10. Alcance por etapas

### Experimento
Comando CLI de investigación/herramienta interna `lucidfence geometry twin --org default --device-tag transporte --buffer 30` que lee eventos JSONL, calcula la envolvente con buffer y devuelve el GeoJSON equivalente.

### Primera versión (Thin Slice)
Integración en la API `/api/v1/fences/synthesize` y pestaña "Geofence Twin" en el dashboard React:
- Selección de dispositivos por etiqueta y periodo de tiempo.
- Generación de polígono Convex Hull con buffer de margen.
- Cálculo del reporte de simulación de impacto (Blast Radius).
- Alta directa de la geocerca resultante en estado `observe`.

### Expansión
Detección automática de clústeres de permanencia (DBSCAN local) para sugerir automáticamente al administrador la creación de geocercas corporativas ("Geocercas Sugeridas").

### Visión North Star (Geofencing Autónomo)
Geofencing adaptativo continuo donde las geocercas de seguridad ajustan dinámicamente sus márgenes según patrones estacionales y horarios de la flota con supervisión humana paso a paso.

## 11. Fuera de alcance

- Servidores o bases de datos GIS externas (PostGIS, GDAL). Todo el cómputo utiliza algoritmos puros en Go stdlib.
- Modificación directa de reglas activas en modo `enforce` sin aprobación del administrador.
- Fusión con conectores UEM externos para alterar mapas del fabricante (la geocerca vive y se evalúa en el motor de LucidFence).

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** `internal/domain/geo` (Haversine, Ray Casting), `internal/engine/replay.go` (motor de simulación), `internal/store` (persistencia JSONL).
- **Nuevos componentes:** Módulo de síntesis de geometría pura en `internal/domain/geo` (algoritmo Monotone Chain o Graham Scan para Convex Hull sobre plano tangencial esférico + expansión de buffer).
- **Integraciones:** Ninguna dependencia externa adicional requerida.
- **Rendimiento:** Complejidad O(N log N) para la síntesis de N puntos. Para 10.000 puntos ejecuta en < 20 ms en Go.

## 13. Seguridad, privacidad y confianza

- **Minimización y Privacidad:** La síntesis procesa únicamente los eventos persistidos localmente. Ningún punto de ubicación sale de la máquina.
- **Control Humano:** Toda geocerca sintetizada se guarda por defecto con las acciones asociadas en modo `observe`.
- **Explicabilidad:** El informe Blast Radius justifica visual y numéricamente por qué cada punto histórico queda dentro o fuera del polígono.

## 14. Valor para el negocio

- **Adopción y Retención:** Transforma el producto de una herramienta reactiva de mapas a un motor de inteligencia espacial predictiva.
- **Reducción de Costes de Soporte:** Disminuye drásticamente las incidencias por bloqueos accidentales y falsos positivos de la flota.
- **Diferenciación Competitiva:** Posiciona a LucidFence como el único complemento UEM local-first capaz de realizar simulación de riesgo espacial.

## 15. Métricas

- **Métrica de resultado:** Reducción del 80% en el tiempo transcurrido desde la identificación de una zona hasta la activación de la política sin falsos positivos.
- **Indicador adelantado:** Porcentaje de geocercas creadas utilizando "Geofence Twin" frente a las creadas manualmente.
- **Métrica de uso:** Número de simulaciones Blast Radius ejecutadas por los administradores antes de guardar.
- **Métrica de calidad:** Tasa de falsos positivos en producción de geocercas creadas vía Twin (< 0.2%).
- **Guardrails:** El tiempo de cálculo de la síntesis no debe superar los 500 ms ni consumir más de 32 MB de RAM adicional en el ciclo del servidor.

## 16. Evaluación

- **Problema:** 4.5/5
- **Alcance:** 4.0/5
- **Impacto:** 4.5/5
- **Estrategia:** 5.0/5
- **Diferenciación:** 5.0/5
- **Deleite:** 5.0/5
- **Viabilidad:** 4.5/5
- **Evidencia:** 4.0/5
- **Riesgo:** 1.5/5 (Bajo riesgo, módulo puramente local)
- **Efecto compuesto:** 4.5/5

**Atributos adicionales:**
- **Confianza:** Alta
- **Esfuerzo relativo:** Medio
- **Reversibilidad:** Alta
- **Tipo de apuesta:** Núcleo (Core Evolution)
- **Horizonte recomendado:** EXPLORE

## 17. Riesgos y motivos para no construirla

- *Riesgo de densidad insuficiente:* Si un grupo de dispositivos tiene muy pocos registros de ubicación (menos de 5 pings en el periodo), el polígono generado puede resultar demasiado pequeño o distorsionado.
- *Mitigación:* Exigir un umbral mínimo de datos (ej. N ≥ 10 puntos) y mostrar un indicador claro de "Calidad de Trazabilidad (Baja / Media / Alta)" en la interfaz antes de permitir la síntesis.

## 18. Preguntas abiertas

1. ¿Cuál es la distancia de buffer predeterminada más adecuada para la mayoría de entornos corporativos (15m, 25m o 50m)?
2. ¿Conviene permitir la exportación de la geocerca sintetizada en formato estándar GeoJSON para su reutilización en otras herramientas de GIS?

## 19. Próximo experimento recomendado

Diseñar un test unitario en Go que utilice el conjunto de datos de la flota simulada de Madrid (`internal/engine/demo.go`) para ejecutar la síntesis de envolvente convexa y buffer, evaluando la velocidad de cálculo y verificando que el 100% de los waypoints de la ruta demo quedan contenidos en la geocerca resultante.

## 20. Recomendación final

Promover a **discovery** (estado en roadmap: **EXPLORE**).
