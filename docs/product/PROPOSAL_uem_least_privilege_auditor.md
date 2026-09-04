# ✨ Auditor de Mínimo Privilegio de Credenciales UEM y Análisis de Radio de Impacto (UEM Credential Least-Privilege Auditor & Blast Radius Analyzer)

## 1. Resumen ejecutivo

Cuando las organizaciones conectan herramientas de seguridad o monitorización a sus plataformas UEM (Microsoft Intune, Jamf Pro, Applivery, Fleet), los administradores suelen utilizar tokens de API con privilegios excesivos o globales (p. ej. permisos de escritura o borrado completo `Wipe/EraseDevice`), incluso cuando la herramienta se despliega en modo piloto de solo observación (`enforcement.mode: observe`). Esto crea una superficie de ataque crítica y un radio de impacto catastrófico en caso de compromiso de credenciales. Proponemos el **Auditor de Mínimo Privilegio de Credenciales UEM**: una capacidad local-first que inspecciona automáticamente los tokens de API configurados en cada adaptador de LucidFence, compara sus permisos reales frente al modo de ejecución activo, detecta excesos de privilegios, calcula el radio de impacto potencial y proporciona al administrador una guía interactiva con un clic para recortar las credenciales al scope mínimo estrictamente necesario.

## 2. Propuesta en una frase

«Para el **CISO, Ingeniero de Seguridad Cloud y Admin de TI**, que necesita **eliminar el riesgo de compromiso de credenciales y limitar la superficie de ataque de sus integraciones UEM**, proponemos el **Auditor de Mínimo Privilegio de Credenciales UEM**, que permite **detectar automáticamente tokens sobre-privilegiados, auditar el radio de impacto de la integración y recortar los permisos al mínimo estrictamente necesario según el modo de ejecución (`observe` vs `enforce`)**, a diferencia de **las herramientas del mercado que exigen permisos globales de administrador y nunca auditan la seguridad de sus propias llaves de API**.»

## 3. Problema

- **Persona:** CISO, Lead Security Engineer, Cloud Security Architect y Administrador de TI/MDM.
- **Situación:** Durante el onboarding o configuración de conectores UEM (Intune Graph API, Jamf Pro API, Applivery API Key, Fleet API Token), el administrador debe otorgar permisos API. Por rapidez o falta de documentación granular en las consolas UEM, el admin selecciona permisos por defecto (como `DeviceManagementManagedDevices.ReadWrite.All` en Microsoft Graph o acceso Full Admin en Jamf).
- **Trabajo por realizar:** Garantizar el principio de mínimo privilegio (NIST SP 800-53 AC-6, ISO 27001:2022 A.8.2) en todas las integraciones de seguridad y evitar que un conector de monitorización se convierta en un vector de ataque destructivo.
- **Fricción actual:** LucidFence funciona en modo observador (`enforcement.mode: observe`) durante los pilotos para no realizar escrituras ni modificaciones en la flota real. Sin embargo, la credencial UEM configurada tiene permisos de borrado remoto (`Wipe`), bloqueo (`Lock`) o modificación de políticas. Ninguna consola UEM ni herramienta de terceros alerta al administrador sobre esta inconsistencia de seguridad.
- **Impacto:** Si una credencial UEM con permisos globales es comprometida en el servidor local o en la infraestructura de CI/CD del cliente, un atacante podría ejecutar acciones destructivas (wipe masivo) en toda la flota de la empresa.
- **Solución utilizada hoy:** Ninguna. Las organizaciones confían ciegamente en que las llaves creadas no serán abusadas, o realizan revisiones manuales de permisos en hojas de cálculo una vez al año durante auditorías SOC 2.

## 4. Evidencia

- **HECHO:** El backlog de producto en `docs/internal/product/BACKLOG.md` clasifica el Ítem #16 ("Auditor de mínimo privilegio de credenciales UEM") con veredicto **SÍ** y un impacto de 4/5, destacando: *"nadie del sector audita los privilegios de sus propias integraciones"*.
- **HECHO:** LucidFence cuenta con una arquitectura de adaptadores modular (`lucidfence/core/adapters/`) donde cada adaptador (`IntuneAdapter`, `JamfAdapter`, `AppliveryAdapter`, `FleetAdapter`) interactúa con las APIs del UEM correspondiente y declara sus capacidades explícitamente (`supports_amapi_policy`, `supports_ddm`, etc.).
- **HECHO:** El contrato de seguridad en `docs/operations/ENFORCEMENT.md` y `docs/integrations/` explicita los permisos mínimos por UEM, pero la verificación de esos permisos hoy recae 100% manualmente en el operador.
- **INFERENCIA:** Los administradores de TI tienden a reutilizar tokens API existentes con alcance amplio para evitar errores de autenticación HTTP `403 Forbidden` durante la fase de evaluación de herramientas.
- **HIPÓTESIS:** Proporcionar un diagnóstico claro del radio de impacto de las credenciales UEM aumentará la confianza de los CISOs para desplegar LucidFence en entornos enterprise regulados (banca, salud, gobierno).
- **DESCONOCIDO:** La proporción exacta de endpoints que expone cada UEM para introspección estandarizada de tokens OAuth2/API v3 sin disparar alertas de seguridad internas.

## 5. Por qué ahora

1. **Aumento de ataques a la cadena de suministro de integraciones:** Incidentes recientes en conectores de CI/CD y plataformas SaaS han demostrado que los tokens de API con exceso de privilegios son el objetivo principal de los atacantes para el movimiento lateral.
2. **Estricto cumplimiento de Mínimo Privilegio (Zero Trust):** Los marcos regulatorios modernos (NIS2 en la UE, EO 14028 en EE. UU.) exigen la auditoría activa de privilegios en todas las APIs e integraciones de seguridad.
3. **Sostenibilidad del modelo "Complement, Not UEM":** Al posicionarse LucidFence como un complemento neutral que **no es un UEM**, debe demostrar que es el componente *menos peligroso y más seguro* de toda la pila de seguridad del cliente.

## 6. Por qué este producto

LucidFence posee tres ventajas estructurales para liderar esta capacidad:
1. **Neutralidad de plataforma:** Al no vender licencias UEM ni competir con Microsoft o Jamf, LucidFence no tiene conflicto de interés para señalar el exceso de permisos otorgado a sus conectores.
2. **Conocimiento del modo de ejecución interno:** LucidFence conoce exactamente en qué modo está funcionando (`observe`, `dry_run`, `enforce`) y qué acciones tiene habilitadas (`wipe`, `lock`, `apply_policy`), permitiendo comparar los permisos *requeridos* vs los permisos *otorgados*.
3. **Procesamiento 100% Local-First y Soberano:** La auditoría del token se ejecuta localmente en el host del tenant. Ninguna credencial ni resultado de auditoría sale a un backend en la nube.

## 7. Experiencia propuesta

1. **Disparador:** El administrador añade o edita una conexión UEM en el Dashboard local (`:8765`), o ejecuta el comando CLI `lucidfence doctor --audit-credentials`.
2. **Inspección de Credenciales (Least-Privilege Scan):** LucidFence realiza una llamada de comprobación de alcance (scope introspection) al adaptador UEM configurado (p. ej. `/me` o `/oauth/token/introspect` en Microsoft Graph o endpoint de permisos en Jamf/Applivery).
3. **Diagnóstico y Análisis de Radio de Impacto:** En el Dashboard aparece la tarjeta **"UEM Credential Safety & Blast Radius"**:
   - *Estado:* ⚠️ **Sobre-privilegiada (Over-privileged)**
   - *Modo activo de LucidFence:* `observe` (Solo lectura)
   - *Permisos detectados en el token:* `DeviceManagementManagedDevices.ReadWrite.All`, `EraseDevice`
   - *Radio de impacto estimado:* **Alta gravedad** — Si este token es comprometido, un atacante podría wipear o modificar 450 dispositivos de la flota.
   - *Permiso recomendado:* `DeviceManagementManagedDevices.Read.All` (Solo lectura)
4. **Guía de Recorte y Remedición de un Clic:** Se genera la guía exacta paso a paso adaptada al UEM correspondiente para ajustar el token en Microsoft Entra ID, Jamf Pro o Applivery.
5. **Verificación y Confirmación:** Al recortar el token, el admin pulsa **"Re-validar Credencial"** y el estado cambia a 🟢 **Mínimo Privilegio Verificado (Zero Risk)**.

## 8. Momento mágico

«El CISO o Admin de TI abre el panel de integraciones durante el despliegue piloto y observa que LucidFence en modo `observe` detectó que la credencial de Intune tenía permisos de borrado remoto (`Wipe`), ofreciéndole en un solo clic el manifiesto JSON de Microsoft Graph para restringir el token a solo lectura antes de pasar a producción.»

## 9. Diferenciación y ventaja defensiva

- **Auto-Gobernanza de Seguridad:** Ninguna otra herramienta de seguridad en el mercado audita sus propios tokens para exigir *menos* permisos.
- **Conciencia Contextual de Ejecución:** Relaciona el modo de enforcement (`observe` vs `enforce`) con los privilegios del token API.
- **Confianza Cero Garantizada:** Facilita la aprobación por parte de los equipos de Risk & Compliance al reducir a cero el riesgo de daño colateral.

## 10. Alcance por etapas

### Experimento
Crear un script de introspección de tokens en Python para los adaptadores de Applivery e Intune que compruebe los permisos devueltos por la API frente a una matriz de permisos mínimos requeridos.

### Primera versión (Thin Slice)
Integrar la prueba de mínimo privilegio en el CLI (`lucidfence doctor`) y en el endpoint de diagnóstico `/api/v2/adapters/audit`, mostrando en el Dashboard local la tarjeta de evaluación de seguridad de la credencial y su radio de impacto.

### Expansión
Añadir soporte de introspección para Jamf Pro, Fleet y Workspace ONE, incluyendo la generación automática de comandos CLI o manifiestos de políticas (p. ej. Terraform / Graph JSON) para crear aplicaciones de mínimo privilegio en cada UEM.

### Visión North Star
Monitoreo continuo de deriva de permisos de credenciales (Credential Scope Drift) con alertas automáticas por webhook en caso de que un administrador modifique los permisos del token en la consola del UEM sin previo aviso.

## 11. Fuera de alcance

- Modificación automática de permisos en consolas UEM de terceros (requeriría credenciales de Administrador Global del IdP del cliente, violando el propio principio de mínimo privilegio).
- Rotación de secretos o gestión de certificados Vault/KMS de terceros.

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** `lucidfence/core/adapters/` (contrato `MDMAdapter`), `saas_server.py` (`/api/v2/`), `lucidfence/cli.py` (`lucidfence doctor`).
- **Integraciones:** Adaptadores UEM existentes (Applivery, Intune, Jamf, Fleet, Workspace ONE).
- **Datos necesarios:** Configuración activa de conectores en `data/cloud_tenants/<tenant>/` y modo de enforcement en `enforcement.mode`.
- **Dependencias:** Ninguna librería externa adicional (stdlib Python 3.11+).
- **Incertidumbres técnicas:** Diferencias en la API de cada UEM para consultar los scopes asociados a una API key o Bearer token sin requerir permisos elevados adicionales.

## 13. Seguridad, privacidad y confianza

- **Mínimo Privilegio Extremo:** El proceso de auditoría no almacena ni imprime en logs los secretos o tokens API en texto claro.
- **Aislamiento Local-First:** Toda la evaluación de scopes se calcula en la memoria local del servidor `:8765`.
- **Transparencia Explicable:** El algoritmo de cálculo de radio de impacto es 100% determinista y documentado.

## 14. Valor para el negocio

- **Desbloqueo de Ventas Enterprise:** Elimina el principal freno de seguridad en evaluaciones del CISO ("¿Por qué necesita este conector permisos de escritura si solo están probando el geofencing?").
- **Posicionamiento de Marca:** Refuerza la identidad de LucidFence como software soberano, transparente y de confianza cero.
- **Reducción del Coste de Soporte:** Previene errores catastróficos causados por ejecuciones accidentales de acciones de remediación con tokens sobre-privilegiados.

## 15. Métricas

- **Métrica de resultado:** Porcentaje de conectores UEM en producción con certificación de **Mínimo Privilegio Verificado**.
- **Indicador adelantado:** Número de ejecuciones de la auditoría de credenciales en `lucidfence doctor` durante la primera hora de onboarding.
- **Métrica de uso:** Ratio de conectores que reducen sus permisos tras visualizar la advertencia de sobre-privilegio.
- **Métrica de calidad:** 0 falsos positivos en la detección de exceso de permisos (100% de precisión entre permisos declarados por la API y matriz de necesidades).
- **Guardrails:** Cero fallos de autenticación o bloqueos de API provocados por las llamadas de introspección de tokens.

## 16. Evaluación

- **Problema:** 5/5
- **Alcance:** 4/5
- **Impacto:** 5/5
- **Estrategia:** 5/5
- **Diferenciación:** 5/5
- **Deleite:** 4/5
- **Viabilidad:** 5/5
- **Evidencia:** 5/5
- **Riesgo:** 1/5 (riesgo mínimo, operación puramente de lectura y diagnóstico)
- **Efecto compuesto:** 4/5

- **Confianza:** Alta
- **Esfuerzo relativo:** Pequeño-Medio (S-M)
- **Reversibilidad:** Alta (funcionalidad de lectura/diagnóstico)
- **Tipo de apuesta:** Adyacente / Seguridad Integrada
- **Horizonte recomendado:** `EXPLORE`

## 17. Riesgos y motivos para no construirla

- **Riesgo de APIs UEM no estandarizadas:** Algunos UEMs heredados o locales no exponen endpoints de introspección de tokens, requiriendo llamadas de prueba heurísticas (ej. intentar leer una lista de dispositivos y verificar si responde HTTP 200 o 403).
- **Mitigación:** Implementar una matriz de introspección por adaptador con fallback gracioso ("Auditoría no soportada por el UEM de origen; verificar manualmente").

## 18. Preguntas abiertas

1. ¿Debería la advertencia de sobre-privilegio bloquear preventivamente la ejecución de acciones en modo `enforce` hasta que el administrador confirme explícitamente el riesgo?
2. ¿Qué formato de exportación de guía de recortado (Markdown, JSON de Terraform, script PowerShell/Bash) resulta más útil para los ingenieros de SecOps?

## 19. Próximo experimento recomendado

Implementar un prototipo de prueba en `lucidfence/core/adapters/` para Intune y Applivery que verifique si las credenciales de prueba devuelven sus scopes activos y compare contra los requeridos por el modo `observe`, midiendo la latencia de respuesta (< 200ms).

## 20. Recomendación final

**Promover a Discovery / Mantener en Explore.** La propuesta ataca una brecha crítica de seguridad de las integraciones UEM del sector, reforzando la propuesta de valor única de LucidFence como complemento neutral y soberano. Permanece en `EXPLORE` hasta la aprobación explícita del responsable de producto.
