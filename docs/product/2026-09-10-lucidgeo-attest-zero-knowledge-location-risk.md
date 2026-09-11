# ✨ LucidGeo-Attest: Bóveda de Atestación de Ubicación Cero-Conocimiento para Zero Trust

## 1. Resumen ejecutivo

LucidGeo-Attest transforma a LucidFence de una consola de monitorización local en la primera Autoridad de Atestación de Riesgo de Ubicación Cero-Conocimiento (Zero-Knowledge Location Risk Attestation Authority) para arquitecturas Zero Trust (ZTNA). Al integrar emisores de claims JWT/OIDC firmados criptográficamente desde el motor local de LucidFence, las organizaciones pueden condicionar el acceso a aplicaciones SaaS y recursos corporativos (Okta, Microsoft Entra ID, Cloudflare Access) según el nivel de riesgo de ubicación e integridad del dispositivo, **sin enviar jamás latitudes, longitudes ni historiales de movimiento a ningún servidor externo o nube**. Esta capacidad resuelve la tensión histórica entre la seguridad física Zero Trust y el cumplimiento estricto de privacidad (RGPD / ePrivacy / convenios laborales).

## 2. Propuesta en una frase

Para **CISOs y Administradores de SecOps** que necesitan incorporar el contexto de riesgo físico en las decisiones de acceso Zero Trust sin violar la privacidad de los empleados, proponemos **LucidGeo-Attest**, un motor de atestación local que emite tokens criptográficos de riesgo de ubicación sin coordenadas, a diferencia de los agentes UEM/ZTNA en la nube que rastrean y exfiltran la ubicación GPS continua a servidores de terceros.

## 3. Problema

- **Persona:** CISO, Administrador de SecOps, Ingeniero de Identidad y Zero Trust, Delegado de Protección de Datos (DPO).
- **Situación:** Una empresa exige restringir el acceso a datos críticos (repositorios de código, ERP, BD de clientes) según el riesgo del entorno físico del dispositivo (p. ej. prohibir acceso desde países no autorizados, zonas de alto riesgo o dispositivos con ubicación suplantada/VPN destructiva).
- **Trabajo por realizar:** Validar en tiempo de autenticación (y en evaluación continua CAE) si el entorno físico del dispositivo es seguro antes de conceder la sesión.
- **Fricción actual:** Los motores de acceso condicional de los IdP (Okta, Entra ID) solo verifican direcciones IP (fácilmente eludibles mediante proxies/VPNs) o exigen instalar agentes SaaS que suben coordenadas GPS continuas a nubes de terceros. Esto genera rechazo sindical, inspecciones del DPO por violaciones del RGPD/ePrivacy y riesgos reputacionales de vigilancia.
- **Impacto:** Las organizaciones terminan desactivando las políticas de ubicación física o aceptando el riesgo de fuga de datos cuando un portátil corporativo es operado desde ubicaciones no autorizadas.
- **Solución utilizada hoy:** Control por IP estática (ineficaz), reglas de geofencing en la nube con pérdida de privacidad, o inacción operativa.

## 4. Evidencia

- **HECHO:** LucidFence 2.0 procesa toda la ubicación, geocercas e integridad en un binario local sin telemetría ni exfiltración (`docs/superpowers/specs/2026-09-05-lucidfence-2-go-rewrite-design.md`, Sección 3).
- **HECHO:** El motor de riesgo (`internal/domain/risk`) genera un veredicto explicable 0–100 (`risk_score`, `severity`, `reasons`) e `internal/domain/integrity` detecta anomalías de velocidad y teletransporte.
- **INFERENCIA:** Los IdPs modernos admiten proveedores de atestación externos o comprobaciones de Risk Claims mediante OIDC Custom Claims o webhooks de evaluación continua antes de emitir tokens de sesión.
- **HIPÓTESIS:** Los equipos de seguridad empresarial adoptarán masivamente la atestación de ubicación si se garantiza mediante firmas criptográficas locales que las coordenadas geográficas reales permanecen confinadas dentro de la infraestructura local del cliente.
- **DESCONOCIDO:** Latencia exacta de integración en tiempo de autenticación interactiva cuando el IdP consulta al endpoint local a través de un túnel/egress seguro.

## 5. Por qué ahora

1. **Evolución de Zero Trust (CAE / Continuous Access Evaluation):** Las arquitecturas ZTNA han migrado de autenticación puntual a evaluación continua de postura de seguridad.
2. **Endurecimiento Regulatorio (RGPD / NIS2 / EU AI Act):** La supervisión de empleados y el procesamiento de geolocalización continua por proveedores SaaS está sufriendo sanciones severas por parte de agencias de protección de datos en Europa.
3. **Reescritura de LucidFence en Go (2.0):** La arquitectura modular de un solo binario con submódulos puros (`domain/risk`, `domain/integrity`, `auth`) permite firmar tokens JWT/OIDC en microsegundos sin sobrecarga de runtime.

## 6. Por qué este producto

- **Aislamiento Local-First:** Ningún competidor SaaS (Jamf, Microsoft Intune, CrowdStrike) puede ofrecer atestación cero-conocimiento porque sus modelos de negocio e infraestructura dependen de la ingesta centralizada de datos de ubicación en sus nubes.
- **Motor de Riesgo Explicable Existente:** LucidFence ya calcula de forma determinista la integridad de ubicación, violaciones de geocerca/ruta y postura de dispositivo (`internal/domain/risk`).
- **Arquitectura de Un Binario:** Facilita el despliegue de la clave de firma de atestación dentro del perímetro seguro del cliente sin dependencias externas.

## 7. Experiencia propuesta

1. **Desencadenante:** Un usuario abre una aplicación corporativa protegida por el IdP (Okta / Entra ID / ZTNA Gateway).
2. **Evaluación Transparente:** El IdP solicita un Claim de Atestación de Ubicación al endpoint local `/api/v1/auth/attest/location-risk` de LucidFence enviando el ID de dispositivo normalizado.
3. **Procesamiento Local:** LucidFence evalúa la última posición recibida del UEM, verifica la integridad de ubicación (velocidad, VPN, suplantación) y el veredicto de riesgo de geocerca/ruta.
4. **Emisión Cero-Conocimiento:** LucidFence firma localmente un token JWT de atestación de corta duración (p. ej., TTL 60 s) conteniendo:
   - `sub`: ID del dispositivo
   - `location_risk_score`: 12
   - `zone_tier`: "trusted_perimeter"
   - `integrity_status`: "verified"
   - `attestation_valid`: true
   *(Cero latitudes, cero longitudes, cero direcciones físicas).*
5. **Decisión del IdP:** El IdP recibe el token, verifica la firma criptográfica con la clave pública de LucidFence y autoriza la sesión sin haber conocido jamás dónde se encuentra físicamente el empleado.
6. **Respuesta ante Anomalías:** Si el dispositivo entra en una zona prohibida o detecta teletransporte/suplantación, `location_risk_score` escala a 85 e `integrity_status` pasa a "degraded". En el siguiente ciclo de evaluación CAE, el IdP revoca automáticamente la sesión.

## 8. Momento mágico

El **Momento Mágico** ocurre cuando el CISO y el Delegado de Protección de Datos (DPO) observan juntos el log de auditoría del IdP: el motor de acceso bloquea instantáneamente una autenticación sospechosa desde una zona no autorizada mostrando la evidencia `"location_risk_score: 88 (integrity_degraded)"`, mientras confirman que en la base de datos del IdP y en los logs de la nube **no existe ni una sola coordenada GPS registrada**, preservando la privacidad del empleado y la conformidad RGPD al 100%.

## 9. Diferenciación y ventaja defensiva

- **Propiedad Cero-Conocimiento:** Imposible de imitar por plataformas UEM/ZTNA basadas en SaaS sin rediseñar por completo su arquitectura cloud.
- **Firma Criptográfica Local:** Las claves de atestación residen exclusivamente en el almacén de datos local (`<data>/auth/attest_keys`), garantizando soberanía total sobre las evidencias.
- **Sinergia Multi-UEM:** Consolida datos de ubicación provenientes de múltiples UEMs (Intune, Jamf, Fleet) en una única afirmación de riesgo coherente.

## 10. Alcance por etapas

### Experimento
- Un endpoint mock `/api/v1/auth/attest/location-risk` que acepte un `device_id`, consulte el veredicto del motor de riesgo local y firme un token JWT de prueba utilizando una clave RSA/Ed25519 generada en memoria.
- Validación manual mediante `jwt.io` o script curl demostrando la ausencia de coordenadas.

### Primera versión (Thin Slice)
- Emisión de JWT de atestación firmado localmente con claves guardadas en `<data>/auth/attest_keys.json` (0600).
- Exposición del JWKS (JSON Web Key Set) público en `/api/v1/auth/attest/jwks.json` para validación automática de firmas por parte de IdPs/Gateways.
- Configuración de políticas de umbral de atestación en la interfaz web de LucidFence.

### Expansión
- Soporte para webhooks de Evaluación Continua de Acceso (CAE - Continuous Access Evaluation) que notifiquen activamente al IdP ante cambios abruptos de nivel de riesgo.
- Conector preconfigurado para Okta Custom Identity Claims y Microsoft Entra ID Custom Authentication Extensions.

### Visión North Star
- Estándar abierto de Atestación de Ubicación Cero-Conocimiento (ZK-Location Spec) adoptado por el ecosistema de seguridad open source, convirtiendo a LucidFence en el estándar de facto para atestación física de dispositivos en arquitecturas Zero Trust.

## 11. Fuera de alcance

- Rastrear o almacenar coordenadas geográficas en el token de atestación.
- Actuar como un proveedor de identidad primario (IdP); LucidFence emite claims de atestación complementarios, no gestiona identidades de usuarios humanos.
- Reemplazar las comprobaciones de postura de software del UEM (antivirus, versión de SO).

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** `internal/domain/risk` (veredicto de riesgo), `internal/domain/integrity` (verificación de anomalías), `internal/auth` (infraestructura JWT/tokens).
- **Integraciones:** Publicación de clave pública mediante endpoint JWKS (`/api/v1/auth/attest/jwks.json`).
- **Datos necesarios:** Veredicto del dispositivo, firma criptográfica local (Ed25519 o RSA-256).
- **Dependencias:** stdlib de Go (`crypto/ed25519`, `crypto/rsa`, `encoding/json`). Cero dependencias externas adicionales.
- **Incertidumbres técnicas:** Formato óptimo de integraciones con extensiones personalizadas de Microsoft Entra ID y Okta Inline Hooks.

## 13. Seguridad, privacidad y confianza

- **Privacidad por diseño:** Estricta exclusión de campos de coordenadas (`lat`, `lng`, `alt`, `address`) en los payloads de los tokens de atestación.
- **Seguridad de claves:** Las claves privadas de firma se generan localmente con permisos 0600 en el directorio de secretos de la organización y jamás se exponen vía API ni logs.
- **Protección contra Replay:** Inclusión obligatoria de timestamp (`iat`), expiración corta (`exp`, máx 60-120 s) y nonce opcional en los tokens JWT.

## 14. Valor para el negocio

- **Desbloqueo de Nuevos Segmentos:** Permite la adopción de LucidFence en organizaciones altamente reguladas (banca, defensa, administraciones públicas, empresas europeas sujetas a convenios laborales estrictos) que previamente rechazaban herramientas de geofencing por riesgo de privacidad.
- **Diferenciación Única:** Posiciona a LucidFence como un complemento de seguridad esencial para las inversiones existentes en Okta, Microsoft Entra ID y Cloudflare Access.
- **Adopción y Retención:** Incrementa de forma dramática la frecuencia de uso del producto, pasando de ser una consola de consulta ocasional a un servicio crítico ejecutado en cada solicitud de acceso corporativo.

## 15. Métricas

- **Métrica de resultado:** 0% de coordenadas GPS exfiltradas a servicios externos manteniendo un 100% de precisión en el bloqueo de accesos desde zonas no autorizadas.
- **Indicador adelantado:** Número de tokens de atestación solicitados y validados con éxito por IdPs integrados.
- **Métrica de uso:** Porcentaje de dispositivos activos con atestación Zero Trust habilitada.
- **Métrica de calidad:** Latencia de generación del token de atestación (< 5 milisegundos en el P99).
- **Guardrail:** La latencia del motor de atestación no debe degradar el ciclo de evaluación periódico del motor principal ni superar el timeout de autenticación del IdP (1000 ms).

## 16. Evaluación

- **Problema:** 5/5
- **Alcance:** 4/5
- **Impacto:** 5/5
- **Estrategia:** 5/5
- **Diferenciación:** 5/5
- **Deleite:** 5/5
- **Viabilidad:** 4/5
- **Evidencia:** 4/5
- **Riesgo:** 2/5
- **Efecto compuesto:** 5/5

**Puntuación global de alineación:** 4.4 / 5.0

- **Confianza:** Alta
- **Esfuerzo relativo:** Medio
- **Reversibilidad:** Alta (funcionalidad opt-in modular)
- **Tipo de apuesta:** Plataforma / Adyacente
- **Horizonte recomendado:** EXPLORE

## 17. Riesgos y motivos para no construirla

- **Argumento en contra:** Los clientes podrían encontrar compleja la configuración inicial de los webhooks de autenticación condicional en sus proveedores de identidad (Okta/Entra ID). Si el IdP requiere un proceso de configuración farragoso, la adopción de la función podría verse frenada.
- **Mitigación:** Proveer plantillas de configuración listas para usar (Okta Inline Hook templates y Entra ID Custom Authentication Extension JSONs) en la interfaz del dashboard de LucidFence.

## 18. Preguntas abiertas

1. ¿Qué estándar de claim de riesgo (OIDC Identity Risk Claims vs. CAEP/SSF Shared Signals Framework) tiene mayor tracción inmediata entre los clientes objetivo para el primer experimento?
2. ¿Debemos ofrecer soporte de rotación automática de claves de firma de atestación en la primera versión o relegarlo a la fase de expansión?

## 19. Próximo experimento recomendado

Crear una prueba de concepto interna que genere un token JWT firmado localmente desde `internal/domain/risk` y consumirlo desde un ejemplo simple de Okta Inline Hook o cURL, midiendo la latencia de generación del JWT y verificando la validez del esquema público JWKS en `/api/v1/auth/attest/jwks.json`.

## 20. Recomendación final

**Promover a EXPLORE.**
LucidGeo-Attest representa una oportunidad estratégica excepcional para convertir la arquitectura local-first de LucidFence en un elemento diferenciador imbatible en el mercado de Zero Trust y Privacidad.
