# ✨ LucidFence FlightDeck: Engine de Radio de Impacto Espacial y Contención Adaptativa Multi-UEM

## 1. Resumen ejecutivo

**LucidFence FlightDeck** es una consola local-first de inteligencia espacial y contención adaptativa para entornos multi-UEM (Intune, Jamf, Applivery, Fleet, Workspace ONE). Cuando un dispositivo entra en una geocerca de alto riesgo, sufre un cruce de perímetro no autorizado o muestra una discrepancia de postura (por ejemplo, `compliant: true` en el UEM pero osquery detecta un cifrado desactivado o un CVE crítico), FlightDeck no se limita a disparar alertas pasivas ni ordena borrados remotos a ciegas. En su lugar, calcula en tiempo real el **Radio de Impacto Espacial** (dispositivos, redes y credenciales corporativas físicamente o lógicamente expuestos), evalúa la brecha de confianza (*Trust Gap*) entre la afirmación del UEM y la postura real observada, y despliega **playbooks de contención adaptativa, quirúrgica y reversible** (aislamiento por Apple DDM / Windows DSC, restricción de red, revocación temporal de certificados) con simulación previa (*what-if replay*) antes de requerir autorización humana para acciones destructivas.

## 2. Propuesta en una frase

«Para **responsables de SecOps y administradores de flota IT/UEM** que necesitan **contener incidentes de movilidad y pérdida de dispositivos sin causar interrupciones operativas masivas ni confiar a ciegas en consolas UEM potencialmente comprometidas**, proponemos **LucidFence FlightDeck**, un centro de mando local-first de evaluación de radio de impacto espacial y contención adaptativa multi-UEM que **pinta en tiempo real la superficie de ataque geográfica, contrasta el estado declarado frente a la postura real observada y ejecuta playbooks de aislamiento quirúrgico y reversible con simulación previa**, a diferencia de **las alertas estáticas en PDF y las acciones de borrado a ciegas de las consolas UEM tradicionales**.»

## 3. Problema

- **Persona:**
  - **Primaria:** Responsable de SecOps / Incident Responder (SecOps Specialist).
  - **Secundaria:** Administrador de Flota IT / CISO.
- **Situación:**
  - Empleados y directivos se desplazan con ordenadores portátiles corporativos y dispositivos móviles entre sedes corporativas, domicilios, espacios de *coworking*, redes Wi-Fi públicas o países con restricciones de seguridad/privacidad.
- **Trabajo por realizar (*Job to be Done*):**
  - Identificar inmediatamente el riesgo real cuando un endpoint cruza un límite geográfico restringido o muestra una anomalía de postura, y aplicar el nivel mínimo necesario de restricción para mitigar la fuga de datos sin paralizar el trabajo del usuario legítimo.
- **Fricción actual:**
  1. **El dilema binario (Todo o Nada):** Si un dispositivo se marca como no conforme en un perímetro o se pierde en un aeropuerto, las opciones del UEM son binarias: no hacer nada (riesgo de exfiltración) o ejecutar un *remote wipe / remote lock* (pérdida de productividad, fricción ejecutiva, destrucción de evidencias).
  2. **Ceñera Multi-UEM y falta de visión espacial:** Microsoft Intune desconoce los portátiles Mac gestionados por Jamf o los servidores Linux gestionados por Fleet que se encuentran en el mismo segmento de red o ubicación física. Ningún UEM comercial calcula la proximidad espacial ni el radio de impacto entre distintos proveedores.
  3. **Superficie de ataque en el propio UEM:** En incidentes recientes de la industria, las consolas UEM han sido atacadas para borrar flotas enteras o se han falsificado señales de *Conditional Access*. Confiar exclusivamente en el veredicto del propio UEM para autoevaluarse crea un punto único de fallo.
- **Impacto:**
  - Fuga de datos corporativos confidenciales por retraso en la respuesta, o millones de euros perdidos en horas de trabajo destruidas por borrados accidentales o desproporcionados.
- **Solución utilizada hoy:**
  - Hojas de cálculo para mapear qué UEM gestiona qué equipo, reglas estáticas de ubicación por IP en el IdP (Entra ID / Okta), y scripts manuales o alertas por correo que un analista tarda entre 30 minutos y varias horas en revisar.

## 4. Evidencia

### HECHO
- **Ataques a consolas UEM (2026):** El incidente Stryker / Handala (marzo 2026) demostró el borrado no autorizado de dispositivos gestionados vía Intune. Agencias federales emitieron advertencias para asegurar el plano de control UEM.
- **Posicionamiento del producto:** Decisión del propietario (2026-08-18): *«Nunca seremos un UEM, somos el complemento»*. LucidFence no enrola ni gestiona parches; lee de adaptadores multi-UEM, correlaciona y actúa sólo con autorización humana.
- **Capacidades existentes en LucidFence:** Motor de geocercas poligonales, osquery postura, simulador `policy_replay.py`, extrapolación de trayectoria `predictive.py`, normalización multi-UEM `multiuem.py`, exportación de auditoría encadenada por hash y *human_gate* / *cooldown* persistido para acciones destructivas (`engine.py`).

### INFERENCIA
- Las empresas no adoptarán otra consola UEM para sustituir a Intune o Jamf, pero pagarán/valorarán una capa de control neutral que audite de forma independiente a sus UEMs y evite que una consola comprometida ordene borrados masivos.
- La evaluación de proximidad física entre endpoints de distintos UEMs solo se puede realizar de forma segura si el procesamiento es 100% local-first (sin enviar coordenadas GPS detalladas a servidores SaaS externos por motivos de privacidad/RGPD).

### HIPÓTESIS
- Un analista de SecOps reducirá el tiempo de triaje de incidentes geográficos de 45 minutos a menos de 30 segundos al disponer de una visualización del Radio de Impacto Espacial junto a una recomendación de playbook de contención reversible.

### DESCONOCIDO
- El porcentaje exacto de organizaciones con más de 500 dispositivos que operan más de 2 UEMs simultáneamente y que tienen habilitada la configuración declarativa (Apple DDM / Windows DSC) en sus clientes.

## 5. Por qué ahora

1. **Maduración de la Gestión Declarativa (Apple DDM / Windows Declared Configuration):**
   Las plataformas modernas ya no requieren lentos sondeos (*polling*) de MDM. Permiten aplicar configuraciones de contención (como deshabilitar AirDrop, restringir redes Wi-Fi o revocar credenciales de Wi-Fi corporativo) de forma casi instantánea y declarativa.
2. **Adopción de Arquitecturas Multi-UEM:**
   La consolidación de plataformas ha fallado: las empresas usan Intune para Windows, Jamf para Apple y Fleet/osquery para servidores/Linux. La fragmentación de la visibilidad de seguridad está en su punto más alto.
3. **Aumento de Ataques al Plano de Control:**
   Las vulnerabilidades en agentes y consolas de gestión han transformado al UEM de una herramienta de defensa en un objetivo prioritario para actores maliciosos.

## 6. Por qué este producto

- **Soberanía y Local-First:** Ningún competidor SaaS puede calcular la proximidad espacial en tiempo real entre múltiples dispositivos sin recolectar y centralizar el rastreo GPS de todos los empleados en la nube (un riesgo inaceptable de privacidad/RGPD). LucidFence lo ejecuta en la máquina local del tenant.
- **Neutralidad Multi-UEM:** Ni Microsoft ni Jamf tienen incentivos para federar el estado de su competidor. LucidFence ya dispone del modelo de datos normalizado `multiuem.py`.
- **Motor de Simulación Integrado:** Gracias a `policy_replay.py`, LucidFence puede predecir e informar del impacto exacto que tendrá una política de contención antes de que el administrador toque un botón.

## 7. Experiencia propuesta

1. **Trigger de Evento:**
   Un portátil con un CVE de alta severidad no corregido o con el cifrado FileVault deshabilitado entra en una geocerca restringida (ej. "Planta de Ensamblaje Competidora" o "País de Alto Riesgo"), o el motor detecta una brecha de confianza (*Trust Gap*) donde Intune reporta `compliant: true` pero osquery reporta `encryption: false`.
2. **Alert en FlightDeck (Radar de Impacto Espacial):**
   El panel de LucidFence resalta la alerta e interactúa con el usuario mostrando el mapa del **Radio de Impacto Espacial**:
   - Muestra el endpoint afectado, su vector de movimiento previsto (`predictive.py`) y los activos corporativos/redes en las inmediaciones.
   - Presenta la tarjeta de **Trust Gap Audit**: comparativa directa «Lo que afirma el UEM» vs «Lo que observa osquery/LucidFence».
3. **Simulación de Playbook de Contención:**
   FlightDeck sugiere un Playbook de Contención Adaptativa en 3 fases:
   - *Fase 1 (Inmediata y Reversible):* Aplicar perfil DDM/DSC de paso descendente (*Step-down Posture*: deshabilitar puertos USB, desactivar AirDrop/Bluetooth, aislar la VPN corporativa).
   - *Fase 2 (Restricción de Red):* Aplicar filtro de red local o solicitar re-autenticación paso a paso.
   - *Fase 3 (Acción Destructiva Pausada):* Si la amenaza persiste y la distancia/velocidad indica exfiltración inminente, se prepara el comando `lock` / `wipe`, retenido automáticamente por `human_gate` y sujeto a la ventana de *cooldown* persistido.
4. **Ejecución en 1-Clic & Trazabilidad:**
   El analista hace clic en «Simular y Aplicar Fase 1». El simulador `policy_replay` confirma: *«Impacto: 1 dispositivo restringido, 0 usuarios bloqueados en red adyacente»*. Se aplica la contención vía los adaptadores UEM correspondientes y se emite un evento firmado con HMAC-SHA256 y hash encadenado al SIEM.

## 8. Momento mágico

«El analista de SecOps observa cómo un portátil perdido en un aeropuerto extranjero se ilumina en el radar de FlightDeck con una discrepancia de cifrado, presiona **Simular Contención** y ve en 2 segundos cómo el dispositivo queda aislado de la VPN y sus puertos bloqueados vía Apple DDM sin haber tenido que destruir los datos del disco ni llamar por teléfono al usuario.»

## 9. Diferenciación y ventaja defensiva

- **Independencia del Vendedor:** No dependemos de que un único UEM sea perfecto; verificamos de forma cruzada la información de todos los proveedores.
- **Simulación Previa (*What-If* Replay):** Ninguna herramienta de mercado muestra el resultado exacto de aplicar un playbook de contención sobre el historial reciente antes de ejecutarlo.
- **Privacidad Demostrable:** Los datos de ubicación y las trayectorias de los empleados nunca salen de la máquina del cliente ($0 exfiltración, cumplimiento RGPD por diseño).

## 10. Alcance por etapas

### Experimento (Validación de Hipótesis)
- Un script de evaluación que toma el inventario simulado multi-UEM de `data/cloud_tenants/` y calcula el *Trust Gap* (discrepancia entre UEM y osquery) junto a un cálculo de proximidad euclidiana entre dispositivos en el motor local.

### Primera versión (Thin Slice — MVP Útil)
- Extensión de la SPA local (`dashboard.html` / `app.js`) con la vista **FlightDeck**:
  - Panel de auditoría *Trust Gap Multi-UEM*.
  - Indicador visual del Radio de Impacto Espacial (dispositivos y geocercas en riesgo dentro de un radio $R$).
  - Botón de recomendación de Playbook de Contención Adaptativa en modo `observe` / `dry_run`.
  - Integración nativa con `human_gate` y generación de logs firmados HMAC para SIEM.

### Expansión
- Soporte para políticas de contención declarativas automatizadas (compilación de reglas LucidFence a perfiles de paso descendente en Apple DDM y Windows DSC).
- Generación de pasaportes temporales de viaje (*Travel Safe-Pass*) aprobados por el admin para excepciones geográficas controladas.

### Visión North Star
- Sistema de orquestación espacial totalmente autónomo que detecta anomalías complejas de desplazamiento (ej. viajero imposible o spoofing GPS), aísla el vector de ataque en sub-segundos a través de múltiples UEMs simultáneos, y genera atestaciones criptográficas soberanas para auditores de ciberseguridad e aseguradoras de riesgo.

## 11. Fuera de alcance

- Enrolamiento directo de dispositivos o sustitución de agentes MDM (nos mantenemos fieles al principio no negociable: *«Nunca seremos un UEM»*).
- Gestión de parches de software, distribución de aplicaciones o venta de almacenamiento en la nube.
- Monitoreo o espionaje continuo e intrusivo de empleados fuera de las geocercas corporativas definidas.

## 12. Implicaciones técnicas

- **Capacidades reutilizables:**
  - `lucidfence/core/multiuem.py` para la normalización de la flota.
  - `lucidfence/core/policy_replay.py` para la ejecución de simulaciones *what-if*.
  - `lucidfence/core/predictive.py` para la extrapolación de movimientos.
  - `lucidfence/core/engine.py` para los controles de *human_gate* y *cooldown* persistido.
  - `lucidfence/core/notifier.py` para la emisión de eventos firmados HMAC-SHA256.
- **Integraciones necesarias:**
  - Adapters existentes: Applivery, Intune, Jamf, Fleet, Workspace ONE.
- **Incertidumbres técnicas:**
  - Latencia en la recepción de respuestas de estado desde las APIs de UEM de terceros cuando se solicita un cambio de postura en vivo.

## 13. Seguridad, privacidad y confianza

- **Controles de Acceso:**
  - Aplicación estricta de RBAC (roles `owner`, `operator`, `viewer`) para acceder a la vista FlightDeck.
- **Protección contra Acciones Destructivas:**
  - Mantenimiento obligatorio del mecanismo `human_gate` para acciones irreversibles (`wipe`, `lock`, `clear_passcode`, `reboot`).
  - Límite de frecuencia (*cooldown*) de 1 hora persistido en disco para evitar bucles infinitos de automatización.
- **Privacidad y Minimización:**
  - Minimización de datos de ubicación: retención configurable con purga automática. Las coordenadas exactas no se transmiten fuera del servidor local `:8765`.

## 14. Valor para el negocio

- **Adopción y Retención:** Transforma el producto de una simple herramienta de geocercas en una consola estratégica de respuesta a incidentes para SecOps.
- **Diferenciación Competitiva:** Posiciona a LucidFence como el único "árbitro neutral" en el mercado de seguridad de endpoints y UEM.
- **Ecosistema:** Amplía el valor de los UEMs existentes que la empresa ya ha comprado, evitando el coste de migración de plataformas.

## 15. Métricas

- **Métrica de resultado:** Reducción del tiempo medio de respuesta (*MTTR*) ante incidentes de movilidad de 45 minutos a < 1 minuto.
- **Indicador adelantado:** Porcentaje de alertas geográficas donde el analista ejecuta una simulación *what-if* antes de aplicar una acción.
- **Métrica de uso:** Número de análisis de *Trust Gap* y ejecuciones de Playbooks de Contención Adaptativa por semana en el tenant.
- **Métrica de calidad:** 0 borrados accidentales o no autorizados reportados.
- **Guardrail:** Cero impacto en el rendimiento del CPU local del engine de geocercas (< 5% uso de CPU durante cálculos de radio espacial).

## 16. Evaluación

- **Problema:** 5/5 (Dolor real de la industria confirmado por incidentes de seguridad reales).
- **Alcance:** 4/5 (Afecta a todas las empresas medianas/grandes con trabajo híbrido y múltiples UEMs).
- **Impacto:** 5/5 (Elimina interrupciones operativas masivas y previene fugas de datos).
- **Estrategia:** 5/5 (Alineación total con el principio «Nunca seremos un UEM, somos el complemento»).
- **Diferenciación:** 5/5 (Casi imposible de copiar para competidores SaaS monomarca).
- **Deleite:** 5/5 (Experiencia visual e interactiva con simulación instantánea).
- **Viabilidad:** 4/5 (Reutiliza el 80% de la infraestructura de código existente en `core/`).
- **Evidencia:** 4/5 (Basada en hechos comprobables de mercado y arquitectura de código).
- **Riesgo:** 2/5 (Bajo riesgo gracias a *human_gate*, *cooldown* persistido y ejecución local).
- **Efecto compuesto:** 5/5 (Aumenta de valor a medida que se conectan más adaptadores UEM).

### Resumen de Priorización:
- **Confianza:** Alta.
- **Esfuerzo relativo:** Medio (gracias al reuso masivo de motores existentes).
- **Reversibilidad:** Alta (los playbooks de contención son paso a paso y reversibles).
- **Tipo de apuesta:** Adyacente / Plataforma.
- **Horizonte recomendado:** EXPLORE (candidato prioritario para discovery y prototipado).

## 17. Riesgos y motivos para no construirla

- *Argumento en contra:* Las organizaciones pequeñas con una flota homogénea de un solo UEM y sin requisitos de movilidad estricta podrían encontrar la evaluación de radio espacial innecesaria si solo buscan alertas básicas en PDF.
- *Mitigación:* FlightDeck se presenta como un módulo avanzado activable en la interfaz, manteniendo la simplicidad del dashboard básico para usuarios con necesidades simples.

## 18. Preguntas abiertas

1. ¿Qué nivel de precisión espacial (radio en metros) prefieren los analistas de SecOps al evaluar proximidad en oficinas corporativas frente a áreas metropolitanas?
2. ¿Qué porcentaje de eventos de *Trust Gap* se deben a retrasos de sincronización de la API del UEM frente a deshabilitaciones reales de seguridad por parte del usuario final?

## 19. Próximo experimento recomendado

Crear una maqueta/prototipo funcional en `docs/product/flightdeck-prototype-spec.md` o simular un escenario de evaluación de *Trust Gap* + Radio de Impacto utilizando los datos de test de `tests/test_multiuem.py` para demostrar el cálculo de discrepancias y la simulación del playbook en < 100 ms.

## 20. Recomendación final

**Promover a EXPLORE.**
La propuesta cumple con todos los estándares exigidos por NOVA ✨: resuelve un problema real y urgente de la industria, aprovecha las capacidades únicas y soberanas de LucidFence, respeta de forma estricta los principios no negociables del producto y ofrece una diferenciación 10x frente a cualquier competidor de mercado.
