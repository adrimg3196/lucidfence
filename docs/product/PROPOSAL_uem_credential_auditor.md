# ✨ Auditor de Mínimo Privilegio para Credenciales Multi-UEM (UEM Token Least-Privilege Auditor)

## 1. Resumen ejecutivo

Cuando una empresa integra un software de seguridad de terceros con sus consolas UEM (Intune, Jamf, Fleet, Applivery, Workspace ONE), suele cometer un error crítico por conveniencia: utilizar tokens de API con privilegios administrativos globales (*Full Admin* o *SuperUser*). Si LucidFence se configura en modo de solo observación (`observe`), mantener un token con permisos de borrado (*wipe*) o bloqueo (*lock*) crea un riesgo de seguridad innecesario. Proponemos el **Auditor de Mínimo Privilegio para Credenciales Multi-UEM**: un módulo de inspección automática que evalúa las API keys, Client Secrets y tokens Bearer configurados en los adaptadores UEM contra el modo de operación activo del tenant (`observe`, `dry_run`, `enforce`). Detecta permisos excesivos (*over-privileging*), alerta al administrador con la lista exacta de scopes/scopes a revocar y garantiza que LucidFence sea la pieza de infraestructura más segura y con el menor vector de ataque de la organización.

## 2. Propuesta en una frase

«Para el **CISO y Lead SecOps**, que necesita **minimizar la superficie de ataque de las integraciones API corporativas**, proponemos el **Auditor de Mínimo Privilegio de Credenciales UEM**, que permite **auditar y recortar proactivamente los permisos de los tokens MDM/UEM conectados al modo estrictamente necesario**, a diferencia de **los proveedores SaaS que solicitan permisos administrativos máximos por defecto y nunca auditan sus propios accesos.**»

## 3. Problema

- **Persona:** CISO, Security Architect, Administrador de TI.
- **Situación:** Conexión de un nuevo adaptador UEM (ej. Microsoft Graph API para Intune o Jamf Pro API) a LucidFence para lectura de inventario y postura.
- **Trabajo por realizar:** Configurar credenciales API seguras que cumplan con el principio de mínimo privilegio (*Least Privilege Principle*).
- **Fricción actual:** Crear un token con scopes ajustados en consolas complejas como Entra ID (Azure AD) o Jamf es laborioso. Los admins suelen asignar el rol `DeviceManagementConfiguration.ReadWrite.All` por prisa. Nadie audita periódicamente si un token configurado hace meses para prueba en modo `observe` conserva capacidades de mutación destructiva que un atacante podría intentar explotar si compromete el entorno.
- **Impacto:** Riesgo de escalada de privilegios, no conformidad en auditorías SOC 2 / ISO 27001 sobre gestión de secretos y exposición indebida ante credenciales filtradas.
- **Solución utilizada hoy:** Ninguna auditoría automática; revisiones manuales esporádicas de registros de Entra ID / Jamf API.

## 4. Evidencia

- **HECHO:** `lucidfence/core/adapters/base.py` define la interfaz unificada de los adaptadores UEM y la especificación de capacidades (`supports_wipe`, `supports_lock`, `supports_ddm`).
- **HECHO:** `lucidfence/core/enforcement.py` gestiona los modos de ejecución (`observe`, `dry_run`, `enforce`).
- **HECHO:** El backlog de producto canónico en `docs/internal/product/BACKLOG.md` clasifica el Ítem #16 ("Auditor de mínimo privilegio de credenciales UEM") con el veredicto **SÍ** y una puntuación de impacto de 4/5.
- **INFERENCIA:** Ningún proveedor del sector audita proactivamente sus propios tokens; ofrecer este nivel de auto-higiene refuerza la propuesta de valor "Trust & Sovereignty" de LucidFence.
- **HIPÓTESIS:** Advertir visualmente al admin sobre el exceso de permisos reducirá el nivel de privilegios de los tokens de producción en más del 70% de los despliegues.

## 5. Por qué ahora

1. **Aumento de ataques a la cadena de suministro API:** Los incidentes cibernéticos recientes explotan tokens de integración de terceros superprivilegiados.
2. **Arquitectura de adaptadores madura:** LucidFence cuenta con 7 adaptadores UEM con especificación explícita de endpoints y requerimientos de permisos (`adapters/ADAPTER.md`).
3. **Cero fricción de red:** La comprobación de permisos utiliza los endpoints de introspección / metadata de token ya disponibles en las APIs de los UEMs.

## 6. Por qué este producto

- **Auto-audición ética:** Es la demostración definitiva de que LucidFence no busca acaparar control, sino ser el componente más seguro y respetuoso de la infraestructura.
- **100% Local y Confidencial:** Las API keys y Client Secrets residen únicamente en `data/cloud_tenants/<tenant>/credentials.json` y nunca se transmiten a ningún servidor externo.

## 7. Experiencia propuesta

1. **Configuración de Adapter:** El admin registra las credenciales de Intune o Jamf en la interfaz o CLI de LucidFence.
2. **Auditoría Automática de Credenciales:** El módulo realiza un test de scopes de solo lectura sin realizar mutaciones.
3. **Reporte de Mínimo Privilegio (en la UI y CLI):**
   > ⚠️ **Advertencia de Mínimo Privilegio (Intune Adapter):**
   > - **Modo Activo de LucidFence:** `observe` (Solo lectura).
   > - **Permisos Detectados en Token:** `DeviceManagementManagedDevices.ReadWrite.All` (Escritura detectada).
   > - **Riesgo:** El token tiene capacidad de wipe/lock, pero LucidFence está configurado en modo observe.
   > - **Acción Recomendada:** Recorte el scope en Azure Entra ID a `DeviceManagementManagedDevices.Read.All`.
4. **Guía de Recorte en 1-Clic:** Se incluye la lista exacta de scopes mínimos requeridos para el modo actual según `adapters/ADAPTER.md`.
5. **Estado Verde de Mínimo Privilegio:** Una vez ajustado el token, el indicador de seguridad del adaptador cambia a **"Mínimo Privilegio Confirmado ✅"**.

## 8. Momento mágico

«El CISO revisa la pantalla de integración de adaptadores y ve que el sistema le felicita porque todas las credenciales conectadas están recortadas al estricto mínimo privilegio necesario para el modo de operación actual. Al presentar esta pantalla a un auditor de ISO 27001, la evidencia es aceptada de inmediato sin objeciones.»

## 9. Diferenciación y ventaja defensiva

- **Seguridad Proactiva By Design:** Auto-auditoría que previene la acumulación de deuda de seguridad.
- **Documentación Dinámica Integrada:** Mapeo automático de scopes exigidos por cada versión de API de los UEMs soportados (Intune Graph, Jamf Classic/Pro, Fleet API, Applivery REST).

## 10. Alcance por etapas

### Experimento
Prototipar en `tests/test_least_privilege.py` una función de verificación que compare el diccionario de permisos declarados de un token sintético contra la matriz de capacidades requeridas por el modo activo.

### Primera versión (Thin Slice)
Implementar la rutina de verificación en `lucidfence/core/least_privilege.py` e integrarla en la respuesta del endpoint `/api/v2/adapters/health`.

### Expansión
Añadir soporte para alertas por webhook cuando un token configurado cambie de permisos en el lado del proveedor UEM.

### Visión North Star
Generación de plantillas Terraform/JSON de políticas de Entra ID y roles de Jamf recortadas a medida con 1 clic.

## 11. Fuera de alcance

- Revocación o modificación automática de permisos dentro del IdP/Entra ID del cliente (debe realizarla el admin en su proveedor de identidad).

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** Adaptadores UEM (`lucidfence/core/adapters/`), `least_privilege.py` (existente en tests).
- **Archivos de configuración:** `credentials.json` en el estado local del tenant.
- **Sin dependencias externas:** Parsing de JWTs y respuestas JSON mediante bibliotecas estándar.

## 13. Seguridad, privacidad y confianza

- **Almacenamiento seguro:** Las credenciales nunca se exponen en logs ni se retornan completas en respuestas API (máscara de clave).
- **Cero telemetría:** El veredicto de privilegio se calcula e imprime únicamente en la máquina del tenant.

## 14. Valor para el negocio

- **Diferenciador Enterprise:** Atrae a CISOs de grandes empresas con políticas rigurosas de gobierno de APIs.
- **Reducción de responsabilidad:** Elimina el riesgo de acusaciones de sobre-acceso en caso de incidentes en el proveedor UEM.

## 15. Métricas

- **Métrica de resultado:** 100% de los adaptadores en producción operando con tokens de mínimo privilegio ajustados a su modo.
- **Métrica de calidad:** 0 falsos positivos al detectar permisos requeridos para la operación del adaptador.

## 16. Evaluación

- **Problema:** 4/5
- **Alcance:** 5/5
- **Impacto:** 4/5
- **Estrategia:** 5/5
- **Diferenciación:** 5/5
- **Deleite:** 4/5
- **Viabilidad:** 5/5
- **Evidencia:** 5/5
- **Riesgo:** 1/5
- **Efecto compuesto:** 4/5

- **Confianza:** Muy Alta
- **Esfuerzo relativo:** Pequeño-Medio (S-M)
- **Reversibilidad:** Alta
- **Tipo de apuesta:** Plataforma / Seguridad
- **Horizonte recomendado:** `EXPLORE` (para refinamiento de trazado de scopes)

## 17. Riesgos y motivos para no construirla

- **Riesgo de falsas alertas si el UEM no expone introspección de scopes:** Algunos UEMs secundarios no retornan la lista de scopes en sus tokens.
- **Mitigación:** Tratar la ausencia de metadatos de scopes como "No Verificable" neutro en lugar de alarma destructiva.

## 18. Preguntas abiertas

1. ¿Deberíamos incluir un enlace directo a la documentación oficial del proveedor (ej. Microsoft Learn) para configurar la aplicación App Registration con scopes restringidos?

## 19. Próximo experimento recomendado

Añadir una prueba unitaria que valide que `least_privilege.py` detecta correctamente la presencia del permiso `DeviceManagementManagedDevices.ReadWrite.All` cuando el tenant opera en modo `observe`.

## 20. Recomendación final

**Aprobar para horizonte EXPLORE / Implementación en siguiente ciclo.** Refuerza la credibilidad de seguridad del proyecto sin alterar el comportamiento de producción existente.
