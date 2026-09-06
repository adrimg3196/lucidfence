# ✨ Auditor de Mínimo Privilegio para Credenciales UEM y API Tokens

## 1. Resumen ejecutivo

Para conectar LucidFence a las plataformas UEM existentes (Microsoft Intune, Jamf Pro, Applivery, Fleet, Workspace ONE), los administradores deben proporcionar tokens de API o credenciales de servicio. En la práctica, por comodidad o prisa, las organizaciones suelen reutilizar tokens con permisos de Administrador Global o permisos destructivos (capacidad de borrar dispositivos / *wipe*, cambiar contraseñas o modificar perfiles) aun cuando LucidFence está configurado en modo puramente observacional (`observe`). Proponemos el **Auditor de Mínimo Privilegio de Credenciales UEM**: una herramienta de auditoría de seguridad integrada que analiza proactivamente los scopes y permisos del token UEM configurado, alertando al usuario sobre el exceso de privilegios y guiándolo para reducir el token a los permisos estrictamente necesarios.

## 2. Propuesta en una frase

«Para el **CISO y Admin de Seguridad de Integraciones**, que necesita **garantizar la máxima seguridad en la cadena de suministro de herramientas de TI**, proponemos el **Auditor de Mínimo Privilegio de Credenciales UEM**, que permite **identificar y corregir inmediatamente tokens de API con permisos excesivos o destructivos**, a diferencia de **las herramientas de mercado que aceptan credenciales de administración total sin auditar ni cuestionar sus privilegios**.»

## 3. Problema

- **Persona:** CISO, Security Architect, IT Compliance Manager.
- **Situación:** Configuración e integración inicial de conectores UEM en LucidFence o auditoría periódica de conectores de API.
- **Trabajo por realizar:** Asegurar que LucidFence opera bajo el principio de mínimo privilegio (Least Privilege Principle), minimizando el radio de impacto en caso de que una credencial sea comprometida.
- **Fricción actual:** Crear un rol personalizado con permisos limitados de lectura en consolas como Microsoft Entra ID o Jamf Pro es complejo. Los administradores tienden a generar tokens con rol de "Full Admin" para evitar errores de conexión.
- **Impacto:** Un token configurado para monitorear geocercas posee en realidad permisos para borrar remotamente miles de dispositivos corporativos. Si ese token es expuesto o mal gestionado, el riesgo es catastrófico.
- **Solución utilizada hoy:** Ninguna auditoría activa. Las empresas asumen el riesgo o realizan revisiones manuales anuales de API tokens.

## 4. Evidencia

- **HECHO:** LucidFence incluye adaptadores para 7 UEMs en `lucidfence/core/adapters/`, los cuales aceptan credenciales de acceso.
- **HECHO:** El backlog canónico en `docs/internal/product/BACKLOG.md` clasifica el Ítem #16 ("Auditor de mínimo privilegio de credenciales UEM") con el veredicto **SÍ** y una puntuación de impacto de 4/5.
- **HECHO:** El documento de arquitectura de adaptadores (`docs/adapters/ADAPTER.md`) estipula que las integraciones deben requerir los menores permisos posibles.
- **INFERENCIA:** Ninguna plataforma UEM del mercado audita los permisos de sus propias integraciones entrantes para avisar al usuario si un token tiene un alcance excesivo.
- **HIPÓTESIS:** Advertir al administrador durante el onboarding o desde el dashboard sobre el exceso de privilegios incrementará la confianza de los equipos de ciberseguridad en LucidFence.

## 5. Por qué ahora

1. **Aumento de ataques a la cadena de suministro (Supply Chain Attacks):** Los atacantes buscan credenciales de integraciones de TI (tokens de API de MDM/UEM) para ejecutar desplazamientos laterales o borrados masivos.
2. **Exigencia de Zero-Trust:** El principio de mínimo privilegio es un requisito obligatorio en marcos de seguridad modernos (NIST 800-207, ISO 27001:2022).
3. **Facilidad de auditoría pasiva:** Muchos UEMs retornan los scopes o permisos asociados al token durante el endpoint de autenticación o verificación (`/me`, `/token/introspect`, `/api/v1/roles`).

## 6. Por qué este producto

LucidFence destaca como el actor ideal para ofrecer este auditor porque:
1. **Compromiso con la seguridad y la transparencia:** Al ser una herramienta neutral y de código abierto, demuestra responsabilidad proactiva velando por la seguridad de la infraestructura del cliente.
2. **Ejecución soberana en local:** La auditoría de la credencial ocurre dentro de la máquina del tenant. El token nunca sale del proceso ni se transmite a servidores de terceros.

## 7. Experiencia propuesta

1. **Conexión del Adapter:** El administrador ingresa el token API o credencial de su UEM (p. ej. Intune o Jamf) en el dashboard de LucidFence.
2. **Ejecución del Auditor:** El conector realiza una prueba de salud (`test_connection`) y el **Auditor de Mínimo Privilegio** analiza los scopes devueltos por el proveedor.
3. **Diagnóstico Claro:**
   - 🟢 **Mínimo Privilegio Confirmado:** `"Token configurado con permisos estrictos de lectura ('DeviceManagementManagedDevices.Read.All'). Sin capacidades de borrado."`
   - ⚠️ **Alerta de Exceso de Privilegios:**
     ```text
     [ALERTA DE SEGURIDAD: EXCESO DE PRIVILEGIOS]
     El token ingresado posee permisos de borrado remoto ('DeviceManagementManagedDevices.Wipe').
     LucidFence está configurado en modo OBSERVE y no requiere permisos de escritura.
     RECOMENDACIÓN: Recorte los scopes del token a lectura para cumplir con el principio de Mínimo Privilegio.
     ```
4. **Guía de Recorte:** Un enlace directo a la documentación paso a paso explica cómo reducir los permisos en la consola de origen del proveedor.

## 8. Momento mágico

«El administrador de seguridad conecta Intune usando un token generado por el equipo de TI y el Auditor de Mínimo Privilegio le advierte inmediatamente que el token tiene permisos de Administrador Global de Entra ID, evitando desplegar una credencial de alto riesgo en el entorno de monitoreo.»

## 9. Diferenciación y ventaja defensiva

- **Auditoría Auto-Aplicada de Seguridad:** Ninguna herramienta de monitoreo del mercado audita los permisos que se le otorgan a ella misma.
- **Refuerzo de la Filosofía Neutral:** Demuestra que LucidFence prioriza la seguridad del tenant por encima de la comodidad o la recolección de permisos.

## 10. Alcance por etapas

### Experimento
Crear un método `audit_credentials_least_privilege()` en los adaptadores clave (Jamf, Intune, Applivery) que inspeccione los campos de roles/scopes del perfil de API.

### Primera versión (Thin Slice)
Integrar la verificación en la pantalla de configuración de integraciones UEM y en los diagnósticos del comando `lucidfence check`.

### Expansión
Soporte para la detección de caducidad cercana de certificados de cliente y tokens Bearer (p. ej. alerta 14 días antes de expirar).

### Visión North Star
Generador automático de definiciones de roles mínimos (p. ej. exportar un archivo JSON de Custom Role para Intune/Jamf con los permisos exactos requeridos por LucidFence).

## 11. Fuera de alcance

- Revocación o mutación automática de permisos en el IdP/UEM de origen (debe ser ejecutada por el admin del UEM).

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** Adaptadores en `lucidfence/core/adapters/`.
- **Estructura:** Añadir la interfaz `CredentialAuditResult` en la clase base de adaptadores.
- **Complejidad:** Pequeña-Media (S-M). Parsing de scopes estándar JWT / OAuth2 / API responses.

## 13. Seguridad, privacidad y confianza

- **Tratamiento Seguro de Secretos:** Las credenciales y tokens permanecen cifrados en reposo en la base de datos local del tenant.
- **Cero Exfiltración:** Los diagnósticos de auditoría de credenciales nunca se envían a ningún servidor externo.

## 14. Valor para el negocio

- **Aprobación Acelerada de Ciberseguridad:** Facilita la aprobación del software por parte de los departamentos de Infosec y Riesgo Corporativo.
- **Prevención de Desastres:** Previene que credenciales comprometidas en la red del cliente puedan ser usadas para ataques destructivos masivos.

## 15. Métricas

- **Métrica de resultado:** 100% de los conectores UEM activos en clientes operando con tokens de mínimo privilegio (0 tokens Full Admin en producción).
- **Métrica de calidad:** 0 falsas alertas de exceso de privilegios sobre tokens correctamente configurados.

## 16. Evaluación

- **Problema:** 5/5
- **Alcance:** 5/5
- **Impacto:** 4/5
- **Viabilidad:** 5/5
- **Riesgo:** 1/5
- **Horizonte recomendado:** `EXPLORE` (preparar especificación de scopes mínimos por conector)

## 17. Riesgos y motivos para no construirla

- Algunos conectores de UEM legados o APIs propietarias no retornan la lista de scopes en sus respuestas de token.
- **Mitigación:** Para estos adaptadores, realizar una verificación heurística mediante llamadas de prueba a endpoints de solo lectura o indicar "Scopes no inspeccionables por la API del proveedor".

## 18. Preguntas abiertas

1. ¿Deberíamos bloquear la activación de acciones de enforcement en vivo (como `enforce` / `wipe`) si el token configurado no cuenta con firma HMAC requerida?

## 19. Próximo experimento recomendado

Escribir el test `tests/test_least_privilege_auditor.py` simular las respuestas de API de Intune y Jamf con scopes completos vs scopes mínimos, comprobando que el auditor emite el diagnóstico correcto en cada caso.

## 20. Recomendación final

**Aprobar para Explore.** Es una característica diferencial de ciberseguridad que eleva la reputación de LucidFence como el estándar de oro en software respetuoso y seguro.
