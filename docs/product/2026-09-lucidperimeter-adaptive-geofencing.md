# ✨ LucidPerimeter: Perímetro Adaptativo Contextual y Síntesis Dinámica de Geocercas

## 1. Resumen ejecutivo

LucidPerimeter transforma la protección de geocercas estáticas en un motor de **perímetro adaptativo contextual**. En lugar de requerir que los administradores de SecOps dibujen y ajusten manualmente círculos o polígonos GPS estáticos para cada sede o ruta, LucidPerimeter sintetiza un límite de riesgo dinámico que combina la ubicación física con la confianza de red (SSID/BSSID/VPN), la jornada laboral (turnos) y la postura de seguridad del dispositivo. Cuando un empleado trabaja en el borde físico de una oficina pero se encuentra en la Wi-Fi corporativa segura y en su horario de turno, el perímetro expande automáticamente su tolerancia, eliminando la fatiga de alertas por falsos positivos. Por el contrario, si un dispositivo está dentro del edificio pero se conecta a un punto de acceso no cifrado o presenta la postura degradada (ej. osquery detecta cifrado desactivado), el perímetro se contrae instantáneamente y eleva la severidad. Todo la evaluación se realiza 100 % local-first en el nodo del tenant, preservando la privacidad del empleado sin enviar datos de ubicación a servidores externos.

## 2. Propuesta en una frase

«Para **administradores de SecOps y TI corporativa**, que necesitan **proteger activos corporativos y datos sensibles en movilidad sin abrumarse con falsos positivos ni mantenimiento manual de mapas**, proponemos **LucidPerimeter**, que permite **generar y ajustar automáticamente perímetros de riesgo adaptativos según contexto de red, horario y postura**, a diferencia de **las geocercas GPS estáticas y rígidas de los UEM tradicionales (Intune, Jamf, Workspace ONE)**.»

## 3. Problema

- **Persona:** Responsable de SecOps / Administrador de TI y Movilidad Corporativa.
- **Situación:** Organizaciones con plantilla híbrida o móvil (empleados de campo, directivos con portátiles corporativos, técnicos en ruta) que manejan información regulada o confidencial.
- **Trabajo por realizar:** Garantizar que los dispositivos corporativos solo accedan a datos sensibles o permanezcan operativos cuando estén en ubicaciones y entornos de red seguros, bloqueando o aislando el dispositivo en caso de extravío, robo o salida de zonas autorizadas.
- **Fricción actual:**
  1. *Mantenimiento manual insostenible:* Dibujar decenas de polígonos para oficinas, centros de datos y clientes. Cada cambio de sede o reforma requiere reconfigurar coordenadas.
  2. *Fatiga de alertas por imprecisión física:* Empleados comiendo en la cafetería adyacente o caminando por el parking disparan alertas de "violación de geocerca", generando parálisis operativa y desactivación de políticas.
  3. *Falsa seguridad dentro del perímetro:* Un dispositivo dentro de las coordenadas del edificio conectado a una red Wi-Fi "Rogue AP" no cifrada o con la postura comprometida es tratado como "seguro" por la geocerca tradicional.
- **Impacto:** Horas de trabajo manual en SecOps ajustando radios en metros; cientos de falsas alertas semanales; brechas de seguridad no detectadas por confiar ciegamente en la coordenada GPS.
- **Solución utilizada hoy:** Definición de círculos/polígonos de radio amplio con márgenes exagerados de tolerancia en las consolas de UEM, o scripts personalizados exportados a hojas de cálculo.

## 4. Evidencia

### Hechos
- La arquitectura de LucidFence 2.0 (`docs/superpowers/specs/2026-09-05-lucidfence-2-go-rewrite-design.md`) procesa en cada ciclo de evaluación (`engine`) siete señales puras en `internal/domain/risk/signals.go`: `time_of_day`, `shift_match`, `device_health`, `device_posture`, `location_integrity`, `zone_risk`, `route_state`.
- Las geocercas actuales (`internal/domain/fence`) solo evalúan inclusión geométrica estática (`inside`, `outside`, `unknown`) con un buffer de permanencia (`dwell_seconds`).
- Ningún UEM principal del mercado (Jamf Pro, Microsoft Intune, VMware Workspace ONE, Applivery) ofrece síntesis dinámica de geocercas ponderada por confianza de red local sin exfiltrar la telemetría a la nube del fabricante.

### Inferencias
- La causa principal por la que los administradores desactivan el geocercado automático o evitan configurar acciones de cumplimiento estricto (`lock` / `wipe`) es el miedo a bloquear a un empleado legítimo debido al derroche de imprecisión GPS en interiores o bordes de edificios.
- Unificar la señal de red (`Network.SSID`, `Network.BSSID`) con la geometría física permite deducir con más del 95 % de certeza la presencia física legítima en una sede, incluso con señal GPS degradada o ausente.

### Hipótesis
- Añadir atenuación de riesgo por contexto de red reducirá las alertas de falsos positivos de geocerca en más de un 80 %.
- Los administradores estarán dispuestos a activar acciones de cumplimiento automático en modo `enforce` cuando comprueben que la decisión requiere coincidencia multivariable (física + red + postura).

### Desconocidos
- ¿Qué porcentaje exacto de dispositivos gestionados informan BSSID con precisión uniforme según la plataforma (macOS vs Windows vs Android)?

## 5. Por qué ahora

1. **Reescritura de LucidFence 2.0 en Go:** La arquitectura modular 2.0 posee un ciclo de evaluación de alto rendimiento que evalúa dispositivos en milisegundos bajo la stdlib de Go, haciendo viable procesar grafos de contexto sin latencia.
2. **Adopción masiva de osquery y Wi-Fi 6E/7:** Los dispositivos corporativos modernos informan BSSIDs y estados de red ricos a través de osquery y conectores UEM.
3. **Pico histórico de regulaciones de soberanía de datos (NIS2, HIPAA, GDPR):** Las empresas necesitan probar el cumplimiento geográfico sin vulnerar la privacidad de los empleados mediante rastreo GPS invasivo continuo.

## 6. Por qué este producto

1. **Arquitectura Local-First y Cero Telemetría:** LucidFence procesa todos los BSSID, SSIDs y coordenadas localmente en la máquina del tenant. Los competidores SaaS no pueden recopilar BSSIDs detallados de clientes por motivos de privacidad y regulación.
2. **Complemento Multi-UEM Abierto:** LucidFence normaliza la postura de Jamf, Intune, Fleet y Applivery en una sola vista. Ningún UEM individual puede correlacionar redes y geocercas a través de una flota heterogénea.
3. **Motor de Riesgo Explicable (0-100):** La decisión de riesgo ya es 100 % transparente con razones textuales, facilitando la auditoría de por qué un perímetro adaptativo actuó de determinada forma.

## 7. Experiencia propuesta

1. **Configuración de Sede Intencionada:** El administrador crea una geocerca (ej. "Sede Central") y vincula opcionalmente las redes de confianza (SSIDs / BSSIDs / Subredes IP) y los turnos de trabajo.
2. **Evaluación de Perímetro Adaptativo en Tiempo Real:**
   - *Escenario A (Borde Físico + Red Segura):* El empleado está a 15 metros fuera del polígono físico, pero conectado al BSSID corporativo seguro durante su turno. LucidPerimeter aplica un "Atenuador de Perímetro", manteniendo el estado en `inside_contextual` y el riesgo en 0.
   - *Escenario B (Dentro del Polígono + Red No Confiable / Postura Comprometedora):* El empleado está físicamente dentro del edificio, pero conectado a un hotspot móvil no autorizado con el cifrado de disco desactivado. LucidPerimeter activa un "Amplificador de Perímetro", trata la zona como viola e incrementa el `risk_score` a 85 (High).
3. **Visibilidad y Control:** El dashboard muestra la vista en mapa con un doble halo alrededor de la geocerca: el límite geométrico duro y la zona adaptativa contextual activa. Cada decisión de adaptación incluye una explicación clara: *"Perímetro expandido +25m por coincidencia de BSSID corporativo verificada"*.

## 8. Momento mágico

«El administrador activa LucidPerimeter en una sede con un historial de 50 falsas alertas diarias por imprecisión GPS. En el mapa en vivo, observa cómo 12 dispositivos que estaban marcados como "violación fuera de zona" en el límite del edificio pasan instantáneamente a estado verde verificado gracias a la coincidencia del BSSID corporativo local, reduciendo las alertas a cero sin haber tenido que ajustar una sola coordenada manual.»

## 9. Diferenciación y ventaja defensiva

- **Ventaja de Privacidad Acumulativa (Privacy-First Geofencing):** Al apoyarse en huellas de red locales (BSSID) y turnos, LucidPerimeter logra mayor precisión que la localización GPS continua sin almacenar ni rastrear el historial de coordenadas detallado del trabajador.
- **Inmunidad al Spoofing GPS:** Un atacante que falsifique las coordenadas GPS para aparentar estar dentro de la oficina será detectado inmediatamente porque su BSSID de red y subred IP no coincidirán con la firma local del sitio.
- **Dificultad de Copia por UEMs Tradicionales:** Los UEMs de mercado están diseñados como silos en la nube y no tienen acceso a la red de área local del tenant para realizar correlación en tiempo real sin agentes pesados propietarios.

## 10. Alcance por etapas

### Experimento
- Un script de validación en Go (`internal/domain/fence/adaptive_test.go`) que tome muestras de ubicaciones y BSSIDs simulados para demostrar matemáticamente que la tasa de falsos positivos cae en más del 80 % frente a la geometría pura.

### Primera versión (Thin Slice / MVP)
- Añadir al modelo `Fence` el campo opcional `AdaptiveRules{TrustedBSSIDs []string, ShiftIDs []string, ToleranceExtensionMeters float64}`.
- Extender `fence.Evaluate` para calcular el estado contextual (`inside_contextual`).
- Añadir la razón de atenuación/amplificación a las razones textuales del veredicto de riesgo (`Verdict.Reasons`).
- Mostrar en el detalle del dispositivo del dashboard el indicador de adaptación contextual.

### Expansión
- Aprendizaje automático local (auto-discovery) de BSSIDs corporativos: sugerir al admin vincular redes observadas con frecuencia dentro de una geocerca.
- Integración de la señal de red en el simulador What-If de políticas.

### Visión North Star
- **Perímetro Autónomo Auto-Regulado (Self-Healing Perimeter):** El sistema analiza patrones de movimiento y red de la organización para proponer y actualizar automáticamente los límites geométricos y de red sin intervención humana, garantizando un modelo Zero-Trust continuo y sin fricción.

## 11. Fuera de alcance

- Triangulación Wi-Fi basada en fuerza de señal (RSSI) en interiores (requiere hardware de infraestructura dedicado).
- Rastreo continuo de empleados fuera de horario laboral o fuera de geocercas configuradas.
- Agentes residentes propietarios en los endpoints (LucidFence utiliza la información obtenida a través de los UEMs y osquery).

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** Reutiliza `internal/domain/geo` (distancias haversine), `internal/domain/fence` (evaluación de polígonos), `internal/domain/risk` (generación de razones y veredicto 0-100) y `internal/store` (persistencia JSON atómica).
- **Integraciones:** Consume `Device.Network` (SSID, BSSID, IP) proporcionado por los conectores existentes (Applivery, Intune, Jamf, Fleet, osquery).
- **Datos necesarios:** Extensión menor del esquema JSON de `fences.json` (retrocompatible con `schema_version`).
- **Posibles cambios arquitectónicos:** Ninguno. Sigue la regla de oro de `domain`: tipos puros sin I/O.
- **Complejidad operativa:** Cero. No añade bases de datos ni servicios externos.

## 13. Seguridad, privacidad y confianza

- **Principio de Mínimo Privilegio y Privacidad:** No se almacena la ruta de movimientos del usuario. La atenuación se calcula en memoria durante el ciclo de evaluación y se descarta.
- **Controles de Abuso:** Los BSSIDs configurados como seguros se almacenan en ficheros locales del tenant (`fences.json`, permisos 0600).
- **Guardarraíles:** LucidPerimeter opera bajo el modo predeterminado `observe`. No se ejecutan acciones destructivas (`wipe`/`lock`) sin pasar por los guardarraíles existentes (cooldowns, allowlists y handoffs con aprobación humana).

## 14. Valor para el negocio

- **Adopción:** Elimina el principal freno de adopción de LucidFence en clientes empresariales: el miedo a bloqueos accidentales por imprecisión GPS.
- **Diferenciación de Producto:** Posiciona a LucidFence como la única solución Zero-Trust Geo-Contextual local-first del mercado.
- **Eficiencia Operativa:** Reduce hasta un 90 % el tiempo dedicado por los equipos de SecOps a dibujar y reajustar geocercas manualmente.

## 15. Métricas

- **Métrica de resultado:** Reducción > 80 % en la tasa de alertas de violaciones de geocerca falsas positivas.
- **Indicador adelantado:** Porcentaje de geocercas creadas que incluyen al menos un BSSID o regla de turno vinculada.
- **Métrica de uso:** Número de evaluaciones del motor donde el perímetro adaptativo evitó una alerta falsa (`inside_contextual`).
- **Métrica de calidad:** Precisión en la clasificación de red y ausencia de pánico/errores en el ciclo del motor.
- **Guardrails:** La latencia del ciclo de evaluación del motor (`engine.runOnce`) no debe incrementarse en más de 2 milisegundos por cada 1 000 dispositivos.

## 16. Evaluación

- Problema: 5/5
- Alcance: 5/5
- Impacto: 5/5
- Estrategia: 5/5
- Diferenciación: 5/5
- Deleite: 5/5
- Viabilidad: 4/5
- Evidencia: 4/5
- Riesgo: 2/5
- Efecto compuesto: 5/5

**Resumen de priorización:**
- **Confianza:** Media (requiere validación con muestras de BSSID reales de flotas heterogéneas).
- **Esfuerzo relativo:** Grande (afecta dominio fence, risk y frontend dashboard).
- **Reversibilidad:** Alta (activable/desactivable por geocerca sin alterar datos subyacentes).
- **Tipo de apuesta:** Apuesta visionaria / Moonshot.
- **Horizonte recomendado:** `EXPLORE` (Descubrimiento activo en LucidFence 2.0).

## 17. Riesgos y motivos para no construirla

- **Argumento en contra:** Algunos conectores UEM en ciertas plataformas (por ejemplo, iOS sin perfil de ubicación precisa) pueden omitir el campo BSSID de la red Wi-Fi debido a restricciones del sistema operativo, limitando la atenuación de red principalmente a macOS, Windows y Android.
- **Mitigación:** LucidPerimeter se degrada de forma segura: si el BSSID no está disponible, el sistema utiliza el SSID o la subred IP corporativa, y si ninguna señal de red está presente, se recurre a la evaluación geométrica estática tradicional sin interrumpir el ciclo.

## 18. Preguntas abiertas

1. ¿Debería la atenuación contextual reducir el `risk_score` a 0 o mantener una pequeña penalización informativa (ej. risk_score = 10) para reflejar que el dispositivo se halla físicamente fuera de las coordenadas teóricas?
2. ¿Con qué frecuencia cambian los BSSIDs de los puntos de acceso Wi-Fi en grandes sedes corporativas y cómo debería gestionar el sistema la rotación de hardware de red?

## 19. Próximo experimento recomendado

Diseñar una prueba de concepto en Go en `internal/domain/fence` con un conjunto de datos sintéticos de 100 dispositivos simulados en el borde de una geocerca con señales BSSID/Shift variables, midiendo la variación del `risk_score` y la tasa de falsos positivos.

## 20. Recomendación final

**PROMOVER A DISCOVERY (`EXPLORE`).**
LucidPerimeter aborda la fricción más profunda del geocercado corporativo tradicional mediante una solución elegante, alineada con los valores local-first y la arquitectura de LucidFence 2.0. Debe permanecer en el horizonte `EXPLORE` de `docs/roadmap/PRODUCT_ROADMAP.md` mientras se consolida la fase de desarrollo del núcleo M1-M3.
