# ✨ Spatial Twin: Inteligencia Espaciotemporal Autónoma y Análisis de Co-ubicación Física

## 1. Resumen ejecutivo

Spatial Twin transforma a LucidFence de un motor reactivo de geocercas estáticas individuales a un sistema de inteligencia espaciotemporal autónomo que comprende las dinámicas relativas de la flota en tiempo real. Mediante la correlación local de señales GPS/Wi-Fi, densidad de dispositivos y patrones de movimiento, Spatial Twin detecta co-ubicación física no autorizada entre dispositivos sensibles, reuniones físicas anómalas en zonas críticas, escolta no autorizada de activos y dispersión física sospechosa. Todo el cálculo de densidad DBSCAN/H3 y correlación espacial se realiza en el binario local Go sin exfiltrar jamás un solo dato fuera de la red del tenant.

## 2. Propuesta en una frase

«Para CSOs y administradores de SecOps/UEM que necesitan proteger activos físicos críticos y prevenir fuga de información en movilidad, proponemos Spatial Twin, una experiencia de inteligencia espaciotemporal local-first que analiza la co-ubicación física y clusters anómalos de dispositivos en tiempo real, a diferencia de las herramientas MDM/UEM tradicionales que solo evalúan geocercas estáticas e individuales.»

## 3. Problema

- **Persona:** CISO / CPO / Admin de SecOps e IT Infrastructure.
- **Situación:** Organizaciones con ejecutivos, equipos R&D, personal de infraestructura crítica o vehículos operativos que transportan dispositivos gestionados por múltiples UEMs.
- **Trabajo por realizar:** Detectar cuando dos o más dispositivos sensibles están físicamente juntos en un lugar no autorizado (ej. reuniones clandestinas, espionaje corporativo), o cuando un dispositivo crítico abandona una escolta/convoy planificado.
- **Fricción actual:** Las herramientas UEM (Intune, Jamf, Workspace ONE) solo evalúan si un dispositivo $A$ está dentro o fuera de un polígono predefinido. No existe la noción de "relación física relativa entre el dispositivo $A$ y el dispositivo $B$" ni de "concentración anómala de 5 dispositivos corporativos en una ubicación no registrada".
- **Impacto:** Vulnerabilidad ante espionaje, robo coordinado de equipos, incumplimiento de normativas de custodia física y pérdida de visibilidad contextual sobre la flota.
- **Solución utilizada hoy:** Correlación manual a posteriori mediante exportación de logs CSV a hojas de cálculo o consultas SIEM complejas que no pueden ejecutar acciones preventivas inmediatas en el UEM.

## 4. Evidencia

- **HECHO:** El motor actual de LucidFence 2.0 en `internal/domain/geo` implementa Haversine y punto en polígono con máxima precisión, pero evalúa cada dispositivo aisladamente (`internal/domain/device/device.go`).
- **HECHO:** El principio de diseño de LucidFence 2.0 prohíbe explícitamente enviar coordenadas a servidores externos (`ARCHITECTURE.md`).
- **INFERENCIA:** Los administradores de seguridad necesitan automatización frente a riesgos de co-ubicación sin sacrificar la privacidad de la ubicación local-first.
- **HIPÓTESIS:** La detección autónoma de clusters físicos de dispositivos mediante DBSCAN esférico local reducirá en un 80% los incidentes de pérdida de activos en convoys/operaciones de campo.
- **DESCONOCIDO:** La sobrecarga exacta de CPU en el motor Go al calcular matrices de distancia $N \times N$ para flotas superiores a 10.000 dispositivos activos en un solo ciclo de 15 segundos (se mitiga con indexación H3/geohash espacial).

## 5. Por qué ahora

1. **Reescritura a Go (LucidFence 2.0):** El motor Go monobloque con concurrencia nativa permite ejecutar algoritmos de clustering espacial ($N \times N$ optimizados) en milisegundos en la CPU local, algo impensable en el servidor Python 1.x.
2. **Adopción de entornos de trabajo híbridos y móviles:** Aumento exponencial de incidentes de seguridad física en lugares de trabajo temporales y viajes corporativos.
3. **Evolución del modelo de amenazas:** Los atacantes aprovechan la co-ubicación no detectada para intercepción de señales y ataques de ingeniería social presenciales.

## 6. Por qué este producto

LucidFence ya posee las integraciones multi-UEM (Applivery, Intune, Jamf, Fleet, Workspace ONE), el modelo de dispositivo normalizado y el motor de riesgo explicable 0–100. Ningún proveedor UEM del mercado analiza la co-ubicación física ni ofrece clustering espaciotemporal local-first con cero telemetría. LucidFence está en la posición perfecta para redefinir la categoría.

## 7. Experiencia propuesta

1. **Desencadenante:** El motor detecta en un ciclo que tres dispositivos con etiqueta "Executive" y un dispositivo con etiqueta "External-Vendor" están co-ubicados a menos de 15 metros en una ubicación no catalogada como oficina corporativa.
2. **Observación:** La UI de LucidFence muestra un indicador en el mapa en vivo: "Micro-cluster anómalo detectado (#CL-402)".
3. **Decisión:** El motor evalúa la regla de política "Co-ubicación de alto riesgo en zona no confiable".
4. **Automatización:** Se genera automáticamente una señal de riesgo `signal:spatial_twin.colocation = true` que eleva la puntuación de riesgo del dispositivo y dispara una acción guardada de bajo impacto (ej. alerta por webhook signed HMAC + requerir re-autenticación/lock si se sobrepasa el umbral).
5. **Control del usuario:** El operador SecOps puede ver la explicación exacta ("Dispositivos A, B y C co-ubicados durante 25 minutos en Lat/Lng X,Y") y aprobar o descartar la alerta.

## 8. Momento mágico

«El usuario se da cuenta del valor de la función cuando, sin haber dibujado manualmente cientos de geocercas, LucidFence destaca automáticamente en el mapa una reunión no planificada de 4 laptops confidenciales en un hotel no autorizado y aplica una política de protección en el UEM.»

## 9. Diferenciación y ventaja defensiva

- **Procesamiento de densidad espacial local-first:** Algoritmos DBSCAN/H3 ejecutados en el binario Go local sin depender de servicios Cloud como Google Maps API o AWS Location Service.
- **Ventaja acumulativa:** La matriz de co-ubicación histórica entrena un modelo de grafo espacial local que aprende cuáles son los pares/grupos de dispositivos habitualmente juntos (ej. equipo de guardia) reduciendo falsos positivos con el uso.

## 10. Alcance por etapas

### Experimento
Crear un prototipo de paquete `internal/domain/spatial` en Go que reciba un slice de `device.Device` y calcule pares de co-ubicación a distancia $D < X$ metros usando Haversine, midiendo el consumo de memoria y CPU.

### Primera versión (Thin Slice)
Incorporar la señal `signal:spatial_twin.colocation` en el motor de riesgo (`internal/domain/risk/signals.go`) para detectar pares de dispositivos sensibles co-ubicados fuera de geocercas conocidas.

### Expansión
Detección de clusters dinámicos ($N$ dispositivos), análisis de acompañamiento/convoy (dispositivos moviéndose juntos en el tiempo) y alertas de dispersión de flota.

### Visión North Star
Gemelo espaciotemporal autónomo con predicción de trayectoria colectiva y remediación SOAR autorregulada sin intervención humana para flotas de alta seguridad.

## 11. Fuera de alcance

- Rastreio continuo de dispositivos personales de empleados no inscritos en el UEM (BYOD sin gestión).
- Uso de APIs de mapas externas de pago para triangulación GSM/torres celulares.

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** `internal/domain/geo` (Haversine, Point), `internal/domain/risk` (Signals, Verdict), `internal/domain/device` (Device).
- **Integraciones:** Cero dependencias externas adicionales.
- **Riesgo arquitectónico:** Complejidad algorítmica $O(N^2)$ amortiguada mediante indexación por cuadrícula espacial/geohash en memoria Go.

## 13. Seguridad, privacidad y confianza

- **Privacidad:** Cero coordenadas salen de la memoria RAM / disco local de la máquina del tenant.
- **Control:** Las acciones preventivas respetan la matriz de guardarraíles (`observe` por defecto, doble llave de wipe).

## 14. Valor para el negocio

- **Aumento de adopción:** Desbloquea casos de uso en sectores altamente regulados (Defensa, Gobierno, Banca, Logística de alto valor).
- **Diferenciación:** Convierte a LucidFence en el único motor de seguridad espaciotemporal multi-UEM del mercado.

## 15. Métricas

- **Métrica de resultado:** Reducción del 90% en el tiempo de detección de incidentes de co-ubicación física sospechosa.
- **Indicador adelantado:** Número de micro-clusters anómalos detectados y revisados por los operadores.
- **Métrica de uso:** % de políticas activas que utilizan la señal `spatial_twin.colocation`.
- **Métrica de calidad:** < 1% de falsos positivos en la detección de parejas de co-ubicación habituales.
- **Guardrail:** El tiempo de ejecución del ciclo del motor en Go no debe incrementarse en más de 50 ms para 1.000 dispositivos.

## 16. Evaluación

- Problema: 4/5
- Alcance: 4/5
- Impacto: 5/5
- Estrategia: 5/5
- Diferenciación: 5/5
- Deleite: 5/5
- Viabilidad: 4/5
- Evidencia: 3/5
- Riesgo: 2/5
- Efecto compuesto: 4/5

- **Confianza:** Media
- **Esfuerzo relativo:** Medio
- **Reversibilidad:** Alta
- **Tipo de apuesta:** Visionaria / Moonshot accesible
- **Horizonte recomendado:** EXPLORE

## 17. Riesgos y motivos para no construirla

- **Argumento en contra:** Si la densidad de la flota es muy baja o los dispositivos están ampliamente dispersos geográficamente, el análisis de co-ubicación no aportará valor diario constante a PYMEs pequeñas.
- **Mitigación:** La función debe activarse como un módulo de inteligencia opcional o auto-desactivarse si la flota cuenta con menos de $N$ dispositivos.

## 18. Preguntas abiertas

1. ¿Cuál es el umbral de distancia óptimo en metros para considerar dos dispositivos corporativos como "co-ubicados" (ej. 10m, 25m, 50m)?
2. ¿Cómo estructurar la exención de parejas legítimas (ej. portátil y teléfono del mismo usuario) sin saturar la configuración del administrador?

## 19. Próximo experimento recomendado

Implementar una prueba de rendimiento en `internal/domain/geo` calculando matrices de distancia relativas sobre un dataset sintético de 5.000 dispositivos para verificar que el impacto en la CPU sea inferior a 10 ms.

## 20. Recomendación final

Promover a **EXPLORE** en el roadmap de producto `docs/roadmap/PRODUCT_ROADMAP.md`.
