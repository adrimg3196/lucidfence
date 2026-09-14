# ✨ LucidGeo-Attest: Zero-Knowledge Location Compliance Attestation Gateway

## 1. Resumen ejecutivo

LucidGeo-Attest es una pasarela local de atestación criptográfica de cumplimiento geográfico que permite a los proveedores de identidad (Okta, Microsoft Entra ID, Ping Identity) y redes Zero Trust / SASE (Tailscale, Cloudflare Access) verificar si un dispositivo administrado se encuentra dentro de un perímetro geográfico autorizado sin recibir ni almacenar jamás las coordenadas GPS reales del usuario. Al evaluar el estado de la geocerca y la integridad de la ubicación de forma 100 % local en el binario LucidFence, la pasarela emite tokens efímeros firmados criptográficamente (JWT / OCSF) que certifiquen el cumplimiento normativo sin exfiltrar latitud ni longitud. Esto resuelve la contradicción entre las exigencias de seguridad de acceso condicional y las normativas de privacidad (GDPR Art. 88, ITAR, NIS2, convenios laborales).

## 2. Propuesta en una frase

«Para CISOs y responsables de SecOps en empresas reguladas, que necesitan restringir el acceso condicional a aplicaciones críticas según la ubicación física del dispositivo sin violar las leyes de privacidad del empleado, proponemos **LucidGeo-Attest**, una pasarela de atestación criptográfica de ubicación de conocimiento cero que emite evidencias efímeras de cumplimiento firmadas localmente sin exfiltrar coordenadas GPS, a diferencia de los rastreadores UEM tradicionales que exigen supervisión GPS continua y exfiltración de datos a la nube.»

## 3. Problema

- **Persona:** CISO, Lead de Seguridad de la Información, Administrador de Identidad / ZTNA, Comité de Privacidad de Datos.
- **Situación:** Una organización opera bajo normativas estrictas de soberanía de datos (ej. datos financieros en la UE, información militar/defensa bajo ITAR, expedientes de salud bajo HIPAA) y requiere que el acceso a entornos corporativos solo se produzca desde geografías u oficinas autorizadas.
- **Trabajo por realizar:** Garantizar que solo los dispositivos físicamente presentes en zonas autorizadas puedan autenticarse en servicios SaaS o VPNs corporativas.
- **Fricción actual:**
  1. Las soluciones de identidad (Okta, Entra ID) solo verifican la dirección IP pública, la cual es fácilmente eludible mediante VPNs, proxys comerciales o redes móviles CGNAT.
  2. Los sistemas MDM/UEM tradicionales (Intune, Jamf) que ofrecen rastreo GPS exigen la transmisión de coordenadas en vivo hacia servidores en la nube de terceros, lo que viola directamente el Reglamento General de Protección de Datos (GDPR Art. 88), exige acuerdos con comités de empresa y genera un riesgo legal inaceptable.
- **Impacto:** Las empresas se ven obligadas a elegir entre bloquear el trabajo remoto regulado o asumir el riesgo de brechas por acceso desde geografías no autorizadas.
- **Solución utilizada hoy:** Scripts artesanales que consultan las APIs de los UEMs para verificar IPs registradas o formularios manuales de declaración de viaje.

## 4. Evidencia

- **HECHO:** LucidFence 2.0 es un motor local-first con cero telemetría cuya arquitectura procesa las coordenadas GPS exclusivamente en la máquina del tenant (`docs/superpowers/specs/2026-09-05-lucidfence-2-go-rewrite-design.md`, Principio 1).
- **HECHO:** El paquete `internal/domain/risk` evalúa la integridad de la ubicación (velocidad, teletransporte, imprecisión) y el estado de la geocerca (`internal/domain/fence`) de forma puramente matemática sin I/O externa (`ARCHITECTURE.md`).
- **INFERENCIA:** Los proveedores de identidad modernos (Okta, Entra ID) admiten extensiones de autenticación personalizada (Okta Inline Hooks, Entra External Authentication Methods / Custom Claims Providers) que consumen firmas JWT externas para ajustar el nivel de riesgo en la autenticación.
- **HIPÓTESIS:** Las organizaciones preferirán adoptar un estándar de atestación criptográfica local que no guarde ni comparta coordenadas GPS en lugar de habilitar el seguimiento GPS centralizado en sus MDMs.
- **DESCONOCIDO:** La latencia exacta de validación aceptada por cada proveedor de identidad en flujos de autenticación paso a paso bajo volumen extremo.

## 5. Por qué ahora

1. **Endurecimiento normativo (NIS2 y Cyber Resilience Act 2026):** Las nuevas normativas europeas y americanas imponen sanciones severas por el acceso a infraestructuras críticas desde jurisdicciones de alto riesgo.
2. **Maduración de Zero Trust y ZTNA:** La identidad basada únicamente en usuario/contraseña + MFA ha sido superada por ataques de Phishing AITM (Adversary-in-the-Middle); el contexto físico del dispositivo se ha convertido en el vector de validación indispensable.
3. **Rechazo social e institucional a la vigilancia de empleados:** Aumento de sentencias judiciales y bloqueos por parte de sindicatos/comités de empresa ante el rastreo continuo de dispositivos de trabajo.

## 6. Por qué este producto

LucidFence 2.0 es el único motor de geofencing multi-UEM local-first, de código abierto y sin telemetría de la industria. Dado que LucidFence ya ingiere la ubicación de múltiples UEMs (Applivery, Intune, Jamf, Fleet, Workspace ONE) y ejecuta el motor de riesgo de forma 100 % aislada en la infraestructura del cliente, se encuentra en la posición ideal para convertirse en la autoridad de atestación de confianza local (Trust Authority) para los proveedores de identidad.

## 7. Experiencia propuesta

1. **Desencadenante:** El usuario intenta iniciar sesión en una aplicación corporativa (ej. Salesforce, GitHub, AWS Console) protegida por Okta / Entra ID.
2. **Observación del usuario:** El flujo de autenticación muestra una comprobación rápida de postura de seguridad («Verificando conformidad de ubicación con LucidFence...»).
3. **Evaluación de LucidFence:**
   - El proveedor de identidad realiza una petición HTTP/mTLS segura a la API local de LucidFence (`/api/v1/attest/token` o vía webhook de atestación).
   - LucidFence consulta el veredicto actual del motor de riesgo (`internal/domain/risk` y `internal/domain/fence`).
   - Si el dispositivo está dentro de una geocerca válida y la integridad de ubicación es 100 % verídica, LucidFence genera un token JWT firmado con la clave privada local (Ed25519/RS256).
   - El token contiene: `device_id`, `compliance_status: "PASSED"`, `fence_id: "fence-hq-office"`, `risk_score: 5`, `expires_at: timestamp + 300s`. **Las coordenadas `latitude` y `longitude` se omiten deliberadamente.**
4. **Resultado:** El proveedor de identidad valida la firma usando el endpoint JWKS público de LucidFence (`/api/v1/auth/jwks.json`) y concede acceso. Si el dispositivo está fuera o la ubicación parece falsificada, el token devuelve `compliance_status: "FAILED"` y la regla de acceso condicional exige MFA adicional o deniega el acceso.

## 8. Momento mágico

«El usuario o auditor de seguridad observa cómo el proveedor de identidad (Okta/Entra) aprueba o bloquea instantáneamente el acceso condicional basándose en si la laptop está dentro de la oficina autorizada, comprobando en el inspector de JWT que el token de atestación NO contiene ni un solo dato de latitud o longitud, garantizando la privacidad absoluta del empleado.»

## 9. Diferenciación y ventaja defensiva

- **Zero-Knowledge por diseño:** A diferencia de las soluciones MDM que envían coordenadas GPS en texto plano a servidores remotos, LucidGeo-Attest destruye o aisla el dato geográfico crudo en la memoria del motor local y solo expone la prueba criptográfica de pertenencia.
- **Multi-UEM federado:** Agrupa dispositivos gestionados a través de Intune, Jamf, Applivery y Fleet en una única autoridad de atestación unificada.
- **Independiente del proveedor de red:** No depende de rangos de IP estáticas ni de hardware propietario.

## 10. Alcance por etapas

### Experimento
- Un endpoint HTTP local `/api/v1/attest/verify-device` que tome un `device_id`, consulte el estado actual de la geocerca en memoria y devuelva una firma HMAC-SHA256 simulada demostrando que la respuesta toma < 10 ms sin exponer lat/lng.

### Primera versión (Thin Slice)
- Generador de pares de claves Ed25519 en el store local de LucidFence.
- Endpoint público `/api/v1/auth/jwks.json` para servir la clave pública.
- Endpoint `/api/v1/attest/token` con autenticación por API Key que devuelva un JWT estandarizado OCSF/JWT para integración directa con Okta Custom Auth Hooks o Caddy / Nginx Reverse Proxies.
- Vista de configuración en el dashboard de LucidFence para administrar llaves de atestación y vigencia de tokens.

### Expansión
- Integración oficial con Microsoft Entra ID Custom Claims Providers y Tailscale ACL Extensions.
- Opción de rotación automática de claves de atestación.
- Soporte para atestación de postura extendida (combinando geocerca + estado de cifrado de disco + parches osquery).

### Visión North Star
- Estándar abierto de atestación de ubicación distribuida (W3C Verifiable Credentials / Decentralized Identity) donde el dispositivo lleva su propio pase de atestación criptográfico firmado por LucidFence, permitiendo acceso offline/air-gapped sin necesidad de conectividad directa entre el IdP y el servidor LucidFence.

## 11. Fuera de alcance

- No se construirá un IdP o proveedor de identidad propio.
- No se enviarán notificaciones push directamente a teléfonos móviles del usuario final fuera de las integraciones UEM existentes.
- No se guardará un historial de coordenadas pasadas en las evidencias de atestación.

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** `internal/domain/risk` (veredicto de riesgo), `internal/domain/fence` (pertenencia a geocerca), `internal/auth` (almacenamiento de claves y RBAC), `internal/api` (rutas HTTP).
- **Nuevos componentes:** Módulo de firma JWT con algoritmo Ed25519 en stdlib (`crypto/ed25519`), servidor JWKS en `internal/api`.
- **Datos necesarios:** Configuración de vigencia de token (default 300 segundos), par de claves Ed25519 de la organización.
- **Sin cambios arquitectónicos:** Mantiene el modelo de un solo binario en Go sin dependencias de bases de datos ni servicios externos.

## 13. Seguridad, privacidad y confianza

- **Minimización estricta de datos:** El token JWT generado prohíbe explícitamente incluir campos de coordenadas GPS (`lat`, `lng`, `accuracy`, `altitude`).
- **Aislamiento de claves:** La clave privada Ed25519 se almacena en `<data>/secrets/<org>/attestation_key.json` con permisos `0600`, accesible solo por el proceso del servidor.
- **Trazabilidad y Auditoría:** Cada emisión de atestación genera un registro de auditoría en `audit.jsonl` indicando `device_id`, `attest_result` (PASSED/FAILED) y `timestamp`, sin almacenar datos geográficos.
- **Mitigación de Replay Attacks:** Tokens con tiempo de expiración corto (máximo 5 minutos) y `nonce` único.

## 14. Valor para el negocio

- **Desbloqueo de mercado B2B altamente regulado:** Permite a LucidFence vender e implantarse en instituciones financieras, gubernamentales, de defensa y salud donde el rastreo GPS tradicional está prohibido por los comités de empresa.
- **Aumento de la retención:** Transforma a LucidFence de una herramienta pasiva de monitoreo UEM a un componente crítico en la cadena de autenticación diaria (Zero Trust Gateway).
- **Posicionamiento defensivo:** Ningún competidor UEM comercial (Intune, Jamf) ofrece atestación de ubicación de conocimiento cero local-first.

## 15. Métricas

- **Métrica de resultado:** 0 % de coordenadas GPS exfiltradas a servicios de identidad externos durante autenticaciones condicionales.
- **Indicador adelantado:** Número de integraciones con IdP (Okta / Entra / Tailscale) configuradas activamente por los usuarios.
- **Métrica de uso:** Volumen diario de tokens de atestación emitidos con éxito (`/api/v1/attest/token`).
- **Métrica de calidad:** Latencia P99 de generación de atestación < 15 ms.
- **Guardrails:** Latencia en la evaluación del motor de riesgo por debajo de 20 ms para no ralentizar el inicio de sesión del usuario.

## 16. Evaluación

- Problema: 5/5
- Alcance: 5/5
- Impacto: 5/5
- Estrategia: 5/5
- Diferenciación: 5/5
- Deleite: 5/5
- Viabilidad: 4/5
- Evidencia: 4/5
- Riesgo: 4/5
- Efecto compuesto: 5/5

**Atributos de apuesta:**
- Confianza: Alta
- Esfuerzo relativo: Medio
- Reversibilidad: Alta
- Tipo de apuesta: Plataforma / Adyacente
- Horizonte recomendado: EXPLORE

## 17. Riesgos y motivos para no construirla

- **Argumento en contra:** Si la mayoría de las pequeñas y medianas empresas no utilizan reglas de acceso condicional complejas basándose en la ubicación física, esta función podría resultar superflua para clientes no regulados.
- **Mitigación:** La pasarela se diseña como un módulo opcional y ligero. La configuración inicial toma menos de 2 minutos y reutiliza 100 % las geocercas y políticas de riesgo ya existentes en el producto.

## 18. Preguntas abiertas

1. ¿Se debe estandarizar la estructura de los claims del JWT de atestación bajo la especificación OCSF (Open Cybersecurity Schema Framework) o usar una estructura JSON llana simplificada para integraciones sin fricción?
2. ¿Qué intervalo de caducidad por defecto (ej. 60s vs 300s vs 900s) ofrece el mejor equilibrio entre seguridad y carga de procesamiento para los conectores de identidad?

## 19. Próximo experimento recomendado

Diseñar un prototipo del generador de tokens firmado Ed25519 en un benchmark Go y simular un Hook de Okta Custom Authentication validándolo en menos de 10 ms en un entorno local.

## 20. Recomendación final

**Promover a discovery** bajo el horizonte **EXPLORE** en `docs/roadmap/PRODUCT_ROADMAP.md` y documentarla como la propuesta prioritaria para el ecosistema de integración de identidad local de LucidFence 2.0.
