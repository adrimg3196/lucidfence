# ✨ Physical Safe-Vault & Zero-Touch Physical Re-Entry Enclave

## 1. Resumen ejecutivo
Proponemos "Physical Safe-Vault & Zero-Touch Re-Entry Enclave", una capacidad de Cero Confianza Físico-Digital que resuelve el dilema clásico entre la paralización operativa por bloqueos destructivos y la desprotección de activos fuera del perímetro corporativo. Cuando un dispositivo corporativo abandona una geocerca de alta seguridad o ingresa en una zona no confiable, LucidFence aplica de forma autónoma políticas de **Vaulting Físico Contextual** (aislamiento preventivo no destructivo: revocación temporal de certificados VPN, bloqueo de puertos USB/biometría y aislamiento osquery). Al regresar al perímetro verificado mediante correlación multi-señal (geocerca física + BSSID de red corporativa + integridad de ubicación sin spoofing + postura osquery limpia), el sistema ejecuta una **restauración física zero-touch**, devolviendo las credenciales y el estado operativo sin requerir la intervención del equipo de soporte ni tickets de IT.

## 2. Propuesta en una frase
«Para el **CISO y los administradores de seguridad e IT**, que necesitan proteger dispositivos móviles y portátiles de alto valor fuera de los perímetros corporativos sin destruir la productividad de los empleados, proponemos **Physical Safe-Vault & Zero-Touch Re-Entry Enclave**, que permite aislar preventivamente el contexto de datos al salir de zonas seguras y restaurar automáticamente el acceso completo al regresar mediante verificación física multi-señal, a diferencia de los bloqueos manuales, los wipes destructivos o la desprotección absoluta que ofrecen los UEMs tradicionales.»

## 3. Problema
- **Persona:** CISO, Director de Operaciones IT/UEM, Analista de SOC y Empleado Móvil/Ejecutivo.
- **Situación:** Dispositivos portátiles y móviles corporativos (laptops con IP/código fuente, tablets de almacén/salud, terminales de alta dirección) entran y salen constantemente de perímetros seguros (oficinas centrales, laboratorios de I+D, centros de datos, zonas francas) hacia entornos no controlados (vuelos, hoteles, sedes de clientes, países de alto riesgo).
- **Trabajo por realizar:** Proteger la información confidencial cuando los dispositivos están físicamente fuera del perímetro seguro, minimizando la ventana de exposición ante robo o extravío, pero garantizando reingreso fluido e inmediato cuando el usuario regresa a su lugar de trabajo.
- **Fricción actual:** Los administradores deben elegir entre dos extremos ineficientes:
  1. *Políticas hiper-agresivas (Wipe / BitLocker Hard-Lock):* Cuando un dispositivo sale de la zona o falla la política, se bloquea por completo. Al regresar, el usuario pierde horas o días esperando a que IT le proporcione una clave de recuperación o reinstale la imagen.
  2. *Políticas pasivas o nulas:* Se envían alertas por correo/slack que nadie atiende a tiempo, dejando los tokens corporativos, claves VPN y puertos accesibles a ataques físicos (cold-boot, extracción por USB, shoulder surfing).
- **Impacto:** Cientos de horas perdidas en tickets de soporte técnico por reseteo de credenciales, o el riesgo catastrófico de fuga de datos en dispositivos robados en tránsito.
- **Solución utilizada hoy:** Scripts artesanales de osquery, revocación manual de sesiones en Entra ID/Okta tras recibir un aviso, o resignarse a mantener perfiles estáticos de UEM sin conciencia geográfica en vivo.

## 4. Evidencia
- **HECHO:** LucidFence 2.0 dispone ya de un motor de integridad de ubicación que detecta teletransporte, velocidad imposible y manipulación de coordenadas (`internal/domain/integrity/`).
- **HECHO:** LucidFence 2.0 evalúa postura mediante osquery y contexto de red (SSID/BSSID) en cada ciclo del motor (`internal/domain/risk/signals.go`).
- **HECHO:** La arquitectura de playbooks SOAR de LucidFence apoya la ejecución directa de acciones no destructivas y el aislamiento mediante handoffs humanos para decisiones críticas (`internal/domain/playbook/`).
- **INFERENCIA:** Los administradores de UEM evitan configurar acciones de bloqueo estricto en geocercas porque el coste de recuperación manual cuando ocurre un falso positivo o un desplazamiento legítimo supera el beneficio percibido de la alerta.
- **HIPÓTESIS:** El 85% de las salidas de geocerca corresponden a desplazamientos de trabajo normales (comidas, visitas a clientes, teletrabajo) donde una restricción contextual temporal (Vaulting) seguida de una restauración transparente (Zero-Touch Re-Entry) eliminaría el 100% de los tickets de soporte por bloqueo.
- **DESCONOCIDO:** La proporción exacta de conectores UEM (Intune, Jamf, Applivery, Fleet, Workspace ONE) que permiten revocación de certificados VPN dinámicos sin requerir re-enrolamiento del dispositivo.

## 5. Por qué ahora
1. **Consolidación de LucidFence 2.0 (Go Rewrite):** El motor en Go alcanza latencias de evaluación en milisegundos y dispone de un modelo unificado de integridad de ubicación, BSSID de red, permanencia (`dwell_seconds`) y postura osquery (`internal/domain/...`).
2. **Adopción de Arquitecturas Zero-Trust y NIS2/SOC2:** Las normativas internacionales exigen probar que los endpoints que contienen PII o datos críticos están aislados criptográfica o funcionalmente cuando operan fuera de límites físicos auditados.
3. **Evolución del Trabajo Híbrido:** La frontera de la oficina física ha desaparecido; la seguridad debe adaptarse al movimiento físico dinámico del empleado sin ser un obstáculo.

## 6. Por qué este producto
- **Arquitectura Local-First y Cero Telemetría:** LucidFence procesa las coordenadas y redes del dispositivo dentro de la red del tenant. Ningún servicio cloud de terceros conoce la ubicación física de los ejecutivos ni los patrones de movimiento de la flota.
- **Visión Multi-UEM Federada:** A diferencia de Intune o Jamf (que operan en silos y carecen de motor de integridad geográfica multi-señal), LucidFence correlaciona la presencia física con postura cruzada entre proveedores.
- **Infraestructura Existente:** Se reutilizan los dominios de geometría (`geo`), geocercas (`fence`), integridad (`integrity`), riesgo (`risk`), políticas (`policy`), playbooks SOAR (`playbook`) y trazabilidad criptográfica de evidencias (`reports/evidence`).

## 7. Experiencia propuesta
1. **Desencadenante:** Un dispositivo corporativo configurado en el playbook "Safe-Vault Enclave" cruza el límite exterior de una geocerca de alta seguridad (ej. Centro de I+D).
2. **Vaulting Físico Contextual (Salida):**
   - El motor detecta la transición `on_exit`.
   - LucidFence envía comandos al UEM/osquery para activar el estado *Vaulted*: deshabilitación de interfaces USB no esenciales, suspensión de certificados VPN corporativos y forzado de bloqueo de pantalla con timeout reducido.
   - Se crea un incidente de severidad `medium` con estado `vaulted`.
3. **Fase de Movilidad / Tránsito:** El dispositivo permanece funcional para uso personal/básico, pero el acceso a la red interna y los datos sensibles queda congelado.
4. **Verificación Multi-Señal de Reingreso:** El usuario regresa a las instalaciones corporativas. En el siguiente ciclo del motor (cada 15 s):
   - **Señal 1 (Geocerca):** El dispositivo está dentro del perímetro `HQ-Fence`.
   - **Señal 2 (Integridad de Ubicación):** `speed_kmh` es coherente (sin teletransporte ni spoofing GPS).
   - **Señal 3 (Contextual de Red):** El BSSID de la red Wi-Fi reportado coincide con la allowlist de puntos de acceso físicos de la sede.
   - **Señal 4 (Postura):** osquery confirma que el agente de seguridad está intacto y no hay procesos maliciosos.
5. **Restauración Zero-Touch (Reingreso):**
   - Al cumplirse las 4 señales simultáneas, LucidFence ejecuta automáticamente la acción `restore_vault_access`.
   - Se restablecen las credenciales VPN, se desbloquean los perfiles corporativos y se cierra el incidente de forma auditada.
   - El usuario vuelve a trabajar de inmediato sin ingresar claves BitLocker ni contactar con el Helpdesk.

## 8. Momento mágico
Un directivo sale de la sede central hacia el aeropuerto. Al cruzar la puerta, su laptop suspende automáticamente el túnel corporativo y bloquea el acceso USB a datos confidenciales. Tres días después, al atravesar los tornos de entrada de la empresa, el portátil detecta la geocerca, valida los BSSID corporativos e instruye a LucidFence para restaurar el entorno seguro en menos de 15 segundos, registrando la evidencia criptográfica de la cadena de custodia sin que el equipo de IT haya tenido que mover un solo dedo.

## 9. Diferenciación y ventaja defensiva
- **Validación Cero-Falso-Positivo mediante Correlación Triangulada:** A diferencia de una geocerca GPS simple (fácilmente suplantable por software de mock location), la re-autorización exige la confluencia de ubicación física + BSSID verificado + firmas de postura osquery + evaluación de integridad de velocidad.
- **Efecto Compuesto de Datos Locales:** La huella de BSSIDs y tiempos de permanencia (`dwell_seconds`) aprende los patrones de acceso físicos legítimos de la organización sin enviar un solo byte a la nube.
- **Reversibilidad Garantizada y Auditada:** Cadena de custodia criptográfica exportable en JSON/HTML (`reports/evidence`) que certifica exactamente cuánto tiempo permaneció el activo en estado aislante y bajo qué señales verificadas se autorizó el reingreso.

## 10. Alcance por etapas

### Experimento
Creación de una plantilla de política SOAR "Safe-Vault Simulation" que evalúa las 4 señales (Geocerca + BSSID + Integridad + Postura) en modo `observe`, registrando en los logs (`actions.jsonl`) los momentos en que se habría activado el aislamiento y la restauración sin ejecutar cambios en el dispositivo.

### Primera versión (Thin Slice)
- Plantilla oficial de Playbook `safe_vault_reentry` en `internal/domain/playbook`.
- Condición de regla compuesta para verificar `signal:network.bssid_matched` + `signal:location.integrity_ok` + `fence_state:inside`.
- Acción normalizada `vault_isolate` y `vault_restore` mapeada a acciones de UEM existentes (`lock` / `message` / `set_compliance`).
- Notificación al usuario en pantalla informando del aislamiento contextual y la restauración automática.

### Expansión
- Soporte para perfiles de aislamiento fino por conector (Intune Conditional Access Compliance state, Jamf Restriction Profile, Fleet osquery extension).
- Inclusión de umbrales de permanencia mínima (`dwell_seconds > 300`) antes de ejecutar la restauración para evitar fluctuaciones en los bordes del perímetro.

### Visión North Star
Enclave de Aislamiento Autónomo Cero-Confianza capaz de coordinar la seguridad física (integración con sistemas de control de acceso PACS vía webhooks) con la seguridad del endpoint, permitiendo que la apertura física de una puerta de alta seguridad desbloquee la clave de cifrado local en el dispositivo de forma efímera.

## 11. Fuera de alcance
- Desarrollo de agentes propietarios en los dispositivos finales (LucidFence utiliza los agentes UEM y osquery ya existentes).
- Instalación de hardware físico de GPS o beacons Bluetooth en las sedes.
- Modificación del firmware o BIOS del dispositivo.

## 12. Implicaciones técnicas
- **Capacidades reutilizables:** `internal/domain/integrity` (verificación de spoofing/velocidad), `internal/domain/risk` (generación de señales), `internal/domain/playbook` (motor de reglas SOAR), `internal/domain/fence` (pertenencia y dwell).
- **Integraciones necesarias:** Extensión de conectores UEM (`internal/uem`) para soportar marcado de estado de conformidad (`set_compliance`) o envío de perfiles de restricción no destructivos.
- **Datos necesarios:** BSSID de red en el modelo de inventario de dispositivos (`Device.Network.BSSID`), ya presente en el modelo normalizado de LucidFence 2.0.
- **Dependencias:** Ninguna dependencia externa adicional; se mantiene 100% Go stdlib + dependencias autorizadas.

## 13. Seguridad, privacidad y confianza
- **Riesgo:** Un atacante intenta suplantar el BSSID y las coordenadas GPS dentro de un vehículo cerca de la oficina para forzar la restauración del dispositivo robado.
- **Control:** El protocolo exige la coincidencia simultánea de 4 factores: geocerca física + BSSID verificado + evaluación de postura osquery local no alterada + velocidad cero/coherente. Si osquery detecta un agente detenido o un sistema manipulado (`rooted/tampered`), la restauración automática se bloquea y requiere autorización humana explícita (`handoff:approve`).
- **Principio de Mínimo Privilegio:** Las acciones de Vaulting son estrictamente no destructivas (`lock`/`restrict`), garantizando que jamás se ejecute un `wipe` por error en un flujo de reingreso.

## 14. Valor para el negocio
- **Adopción:** Desbloquea el caso de uso de geocercas en empresas altamente reguladas (banca, defensa, farmacéuticas, infraestructuras críticas) que descartaban la geofencing por miedo a bloqueos accidentales.
- **Reducción de Costes:** Elimina hasta un 80% de los tickets de soporte de IT relacionados con bloqueo de dispositivos en desplazamientos de empleados.
- **Diferenciación:** Convierte a LucidFence en el único motor de geocercas multi-UEM con capacidad de **restauración física autónoma Zero-Touch**.

## 15. Métricas
- **Métrica de resultado:** Reducción del 90% en tiempo de inactividad de empleados al reingresar a instalaciones corporativas tras viajes o desplazamientos.
- **Indicador adelantado:** Porcentaje de transiciones `on_exit` gestionadas mediante el flujo `vaulted` frente a cierres manuales.
- **Métrica de uso:** Número de restauraciones automáticas `vault_restore` completadas con éxito por semana.
- **Métrica de calidad:** Tasa de falsos positivos en la restauración (meta: 0%).
- **Guardrail:** Cero incrementos en la ejecución accidental de comandos `wipe` o bloqueos irreversibles.

## 16. Evaluación
- **Problema:** 5/5 (Dolor real, frecuente y costoso en empresas)
- **Alcance:** 4/5 (Afecta a cualquier organización con empleados móviles o sedes seguras)
- **Impacto:** 5/5 (Transforma una herramienta de alerta en un sistema autónomo)
- **Estrategia:** 5/5 (Alineación perfecta con los principios de LucidFence 2.0 Go)
- **Diferenciación:** 5/5 (Ningún UEM ni competidor ofrece reingreso autónomo multi-señal)
- **Deleite:** 5/5 (Experiencia totalmente invisible para el usuario final y el admin)
- **Viabilidad:** 4/5 (Aprovecha en un 80% componentes ya construidos en M1 y M2)
- **Evidencia:** 4/5 (Basado en la arquitectura Go probada y los modelos de trazas)
- **Riesgo:** 2/5 (Bajo, al utilizar únicamente acciones no destructivas)
- **Efecto compuesto:** 5/5 (Mejora a medida que se registran más BSSIDs y perfiles de postura)

- **Confianza:** Alta
- **Esfuerzo relativo:** Medio (1-2 semanas de diseño de reglas y plantillas)
- **Reversibilidad:** Alta (Acciones 100% no destructivas)
- **Tipo de apuesta:** Adyacente / Núcleo
- **Horizonte recomendado:** `EXPLORE`

## 17. Riesgos y motivos para no construirla
- **El argumento en contra:** Algunos administradores de IT ultraconservadores prefieren mantener el control manual absoluto de cualquier cambio de estado de seguridad y podrían desconfiar de un reingreso 100% automático.
- **Mitigación:** Ofrecer un modo híbrido donde la restauración genere un `handoff` de un solo clic en la interfaz antes de automatizarlo por completo.

## 18. Preguntas abiertas
1. ¿Qué nivel de precisión de BSSID proporcionan los conectores UEM live (Intune/Jamf/Applivery) en comparación con el agente simulado de LucidFence?
2. ¿Conviene incluir la biometría local como un quinto factor de verificación en plataformas macOS/Windows?

## 19. Próximo experimento recomendado
Diseñar un test de integración en `internal/engine` que simule la salida de un dispositivo (`on_exit`), verifique la emisión de la orden de aislamiento no destructivo y simule el reingreso con las 4 señales activas para validar que la restauración se completa en un solo ciclo sin intervención.

## 20. Recomendación final
**Promover a `EXPLORE`**. La propuesta resuelve un problema de negocio de alto valor, aprovecha las capacidades centrales de LucidFence 2.0 y posiciona al producto como líder pionero en la convergencia entre seguridad física y Zero-Trust.
