# ✨ Compilador Declarativo Cross-UEM de Políticas Portables («Write Once, Enforce Anywhere»)

## 1. Resumen ejecutivo

Las organizaciones que operan entornos heterogéneos (macOS con Jamf/Applivery, Windows con Intune, Linux con Fleet) deben reescribir y mantener manualmente las mismas reglas de seguridad y geocercado en la sintaxis específica de cada consola UEM. Esta fragmentación genera incongruencias entre plataformas, errores de configuración y silos operativos. Proponemos el **Compilador Declarativo Cross-UEM de Políticas Portables**: un motor local que toma la definición neutral de política de LucidFence (`fences.json`, `policies.json`) y la traduce automáticamente a los artefactos nativos ejecutables por cada UEM objetivo (Fleet GitOps YAML, Intune Compliance Policy JSON, Jamf Extension Attributes/Smart Group criteria, Applivery AMAPI Policy JSON). El administrador define la regla de seguridad o cerca una sola vez en sintaxis declarativa neutral y LucidFence compila el artefacto nativo idóneo para su despliegue directo en el UEM correspondiente.

## 2. Propuesta en una frase

«Para el **Admin de TI y SecOps Multi-UEM**, que necesita **garantizar políticas de seguridad y geofencing homogéneas en flotas mixtas (macOS, Windows, Linux)**, proponemos el **Compilador Declarativo Cross-UEM**, que permite **definir la política una sola vez y compilar artefactos nativos para Intune, Jamf, Fleet y Applivery sin instalar agentes adicionales ni depender de paneles propietarios**, a diferencia de **las consolas MDM tradicionales que fuerzan a duplicar reglas manualmente en sintaxis propietarias e incompatibles**.»

## 3. Problema

- **Persona:** Lead Security Engineer, Admin de TI y SysAdmin responsable de flotas multiplataforma.
- **Situación:** Una empresa define una directiva corporativa de seguridad: "Todo portátil fuera del perímetro de la oficina central debe exigir cifrado activo, firewall habilitado y restringir acceso a red corporativa".
- **Trabajo por realizar:** Traducir esa directiva a configuraciones concretas dentro de Intune para Windows, Jamf para Macs de directivos, Applivery para dispositivos móviles/médicos y Fleet/osquery para servidores Linux de ingeniería.
- **Fricción actual:** Cada UEM exige un formato completamente diferente (JSON de Graph API en Intune, plist/Extension Attributes en Jamf, especificación YAML de Fleet, AMAPI en Android/Applivery). Un cambio en la política requiere modificar 4 consolas distintas, aumentando el riesgo de omisión y desalineación de seguridad.
- **Impacto:** Brechas de seguridad por políticas no sincronizadas entre plataformas, pérdida de tiempo en trabajo manual repetitivo y falta de una fuente única de verdad (Single Source of Truth) para la postura global.
- **Solución utilizada hoy:** Documentación manual en Wikis/Confluence y configuración artesanal pantalla por pantalla en cada consola UEM.

## 4. Evidencia

- **HECHO:** El backlog de producto en `docs/internal/product/BACKLOG.md` clasifica el Ítem #14 ("Políticas portables — compilar a primitivas nativas del UEM") como un **SÍ con matiz** con impacto 4/5.
- **HECHO:** LucidFence ya cuenta con esquemas estructurados y validados para geocercas (`fences.json`), reglas de riesgo (`policies.json`) y acciones SOAR declarativas (`lucidfence/core/actions.py`).
- **HECHO:** Los adaptadores UEM de LucidFence (`lucidfence/core/adapters/`) ya conocen los contratos y capacidades de cada plataforma (`supports_amapi_policy`, `supports_ddm`, `supports_dsc`).
- **INFERENCIA:** Los fabricantes de UEM no tienen incentivo comercial para soportar exportación a consolas competidoras; un motor neutral es la única capa capaz de ofrecer un compilador cross-UEM.
- **HIPÓTESIS:** Ofrecer una CLI y vista de compilación declarativa reducirá a cero el tiempo necesario para replicar políticas entre UEMs y posicionará a LucidFence como el estándar de especificación de políticas portables.

## 5. Por qué ahora

1. **Adopción de infraestructura como código (GitOps):** Equipos de TI exigen cada vez más gestionar configuraciones de seguridad mediante código versionado en repositorios Git.
2. **Arquitectura declarativa madura en UEMs modernos:** Apple (Declarative Device Management DDM), Windows (Desired State Configuration DSC) y Android (AMAPI) han migrado hacia especificaciones declarativas orientadas a estados deseados.
3. **Capacidad existente en LucidFence:** LucidFence ya incluye el motor `policy_replay.py` y validadores de esquemas que permiten simular y validar políticas antes de su emisión.

## 6. Por qué este producto

- **Neutralidad estructural:** Al no estar vinculado a ningún proveedor de UEM, LucidFence puede actuar como el compilador universal.
- **Ejecución Local-First y $0:** El proceso de compilación es una función matemática pura local (sin llamadas externas ni exfiltración de credenciales).
- **Export-Only con Control Humano:** Sigue el principio no negociable "Complement, Not UEM" — el compilador genera los artefactos nativos para que el admin los revise e importe en sus UEMs, sin realizar escrituras no autorizadas en segundo plano.

## 7. Experiencia propuesta

1. **Disparador:** El admin define o modifica una política de geoperímetro y postura en `policies.json` o en la UI local.
2. **Selección de Target:** Ejecuta la CLI `lucidfence compile --policy office-policy.json --target fleet` (o selecciona el objetivo desde la interfaz local de LucidFence).
3. **Compilación y Validación:** El motor `policy_compiler.py` valida la compatibilidad de los parámetros contra el esquema del target y genera el artefacto compilado:
   - Para **Fleet:** `fleet_policy_office.yaml` (consulta osquery + reglas de política YAML).
   - Para **Intune:** `intune_compliance_policy.json` (Custom Compliance JSON para Entra/Intune).
   - Para **Jamf:** `jamf_extension_attribute.xml` y criterios de Smart Group.
   - Para **Applivery:** `applivery_amapi_policy.json` (Declarative Android Management API policy).
4. **Verificación de Cobertura:** El compilador entrega una tabla explicativa de equivalencias: qué reglas se traducen al 100% en primitivas nativas del UEM y qué reglas se evalúan de forma complementaria desde el engine local de LucidFence.
5. **Aprobación y Despliegue:** El admin descarga o copia el artefacto compilado para aplicarlo vía su pipeline GitOps o consola UEM existente.

## 8. Momento mágico

«El usuario define una geocerca y regla de cifrado obligatorio en LucidFence y, con un solo comando, obtiene el archivo YAML listo para Fleet, el JSON de cumplimiento para Intune y la directiva AMAPI para Android, eliminando horas de trabajo manual en tres portales diferentes.»

## 9. Diferenciación y ventaja defensiva

- **"Write Once, Enforce Anywhere":** Ningún UEM del mercado ofrece un formato de política portable que pueda compilarse a consolas rivales.
- **Cero dependencias externas:** Funciona completamente fuera de línea utilizando la biblioteca estándar de Python (stdlib).
- **Simulación previa:** Permite pasar el artefacto por `policy_replay.py` antes de exportar, verificando cuántos dispositivos se verían afectados.

## 10. Alcance por etapas

### Experimento
Crear un script de prototipo en `lucidfence/core/policy_compiler.py` que traduzca una regla simple de geocerca/postura a un YAML válido para Fleet y un JSON de compliance para Intune, validando los esquemas sintácticos.

### Primera versión (Thin Slice)
Integrar la CLI `lucidfence compile` con soporte para exportación a Fleet (YAML) e Intune (JSON), incluyendo pruebas unitarias de contrato y validación de esquemas.

### Expansión
Añadir compiladores target para Jamf (Smart Groups / Extension Attributes) y Applivery (AMAPI JSON), incorporando un botón "Exportar Política Nativa" en la interfaz web de LucidFence.

### Visión North Star
Matriz de alineación automática de políticas que analice los UEMs conectados, detecte desviaciones entre los artefactos desplegados en las consolas y el modelo portable de LucidFence, y sugiera parches de sincronización en un click.

## 11. Fuera de alcance

- Sincronización bidireccional automática no autorizada (el admin siempre mantiene la aprobación final del artefacto exportado).
- Modificación directa de bases de datos internas de UEMs de terceros.
- Sustitución de los agentes MDM nativos del fabricante.

## 12. Implicaciones técnicas

- **Nuevo módulo backend:** `lucidfence/core/policy_compiler.py` (Módulo stdlib puro).
- **Entradas:** `policies.json`, `fences.json`, `DeviceState`.
- **Salidas:** Cadenas de texto estructuradas (YAML, JSON, XML) según el esquema del UEM destino.
- **Capacidades reutilizadas:** `lucidfence/core/config_loader.py`, `lucidfence/core/policy_replay.py`.

## 13. Seguridad, privacidad y confianza

- **Operación puramente determinista y local:** No realiza peticiones HTTP externas ni almacena secretos.
- **Sin elevación de privilegios:** El artefacto resultante es un documento estático generado en la máquina del tenant.
- **Auditoría inmutable:** Cada compilación registra una entrada en el log de auditoría local con el hash SHA-256 de la política de origen y del artefacto compilado.

## 14. Valor para el negocio

- **Aceleración de adopción:** Atrae a organizaciones enterprise con entornos Multi-UEM que buscan estandarizar políticas sin reemplazar sus UEMs actuales.
- **Fidelización:** Convierte a LucidFence en el plano de control declarativo de referencia para la definición de políticas de seguridad espacial y de postura.

## 15. Métricas

- **Métrica de resultado:** Reducción del tiempo de despliegue de políticas cross-platform de horas a < 30 segundos.
- **Métrica de uso:** Número de ejecuciones de `lucidfence compile` y descargas de políticas compiladas desde el dashboard.
- **Métrica de calidad:** 100% de validez sintáctica de los artefactos generados contra los esquemas oficiales de Fleet, Intune, Jamf y Applivery.

## 16. Evaluación

- **Problema:** 5/5
- **Alcance:** 4/5
- **Impacto:** 5/5
- **Estrategia:** 5/5
- **Diferenciación:** 5/5
- **Viabilidad:** 5/5 (Módulo Python stdlib sin dependencias externas)
- **Evidencia:** 4/5
- **Riesgo:** 1/5 (Exportación de archivos locales, sin efectos secundarios en el runtime)

- **Confianza:** Alta
- **Esfuerzo relativo:** Medio (M)
- **Horizonte recomendado:** `EXPLORE`
