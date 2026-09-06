# ✨ Compilador Transversal de Políticas Portables Cross-UEM

## 1. Resumen ejecutivo

Cuando las organizaciones operan múltiples plataformas UEM (p. ej. Jamf para Mac, Intune para Windows, Fleet para servidores/Linux), los administradores deben reescribir manualmente cada regla de geocerca y política de postura en el formato nativo de cada consola. Esto genera inconsistencias de criterios, duplicación de esfuerzo y errores humanos. Proponemos el **Compilador Transversal de Políticas Portables**: un motor capaz de tomar las definiciones declarativas de geocercas y postura de LucidFence y **compilarlas automáticamente a los artefactos nativos equivalentes** de cada UEM (Compliance Policy JSON de Microsoft Intune, Smart Group XML/JSON de Jamf Pro, o Policy YAML de Fleet DM). La función opera en modo *export-only*, generando artefactos listos para importar sin asumir el rol de UEM ni forzar una sincronización bidireccional invasiva.

## 2. Propuesta en una frase

«Para el **Admin de TI Multi-UEM y Arquitecto de Seguridad**, que necesita **mantener criterios homogéneos de geocercas y postura en plataformas heterogéneas**, proponemos el **Compilador Transversal de Políticas Portables**, que permite **escribir una política una sola vez y compilarla a los esquemas nativos de Intune, Jamf y Fleet**, a diferencia de **las consolas UEM propietarias que confinan las políticas a sus propios ecosistemas cerrados**.»

## 3. Problema

- **Persona:** Multi-UEM System Administrator, Enterprise Mobility Architect, SecOps Specialist.
- **Situación:** Definir una nueva regla corporativa: *"Todo dispositivo que salga del perímetro autorizado o desactive el cifrado de disco debe clasificarse como No Conforme"*.
- **Trabajo por realizar:** Aplicar esta política exactamente con el mismo criterio estricto en el 100% de los endpoints de la empresa, independientemente del sistema operativo o del UEM que los gestione.
- **Fricción actual:** El administrador debe aprender las sintaxis y esquemas propietarios de 3 consolas distintas (Intune Custom Compliance JSON, Jamf Smart Group criteria, Fleet YAML policy syntax) y traducir la regla manualmente a cada una.
- **Impacto:** Criterios divergentes entre plataformas (p. ej. reglas de geocercas más permisivas en Windows que en macOS), huecos de cumplimiento y duplicación de trabajo administrativo.
- **Solución utilizada hoy:** Redacción de documentos PDF con especificaciones de políticas y traducción manual per-console.

## 4. Evidencia

- **HECHO:** LucidFence cuenta con una sintaxis unificada para geocercas (`fences.json`), reglas de postura (`osquery_posture.py`) y acciones SOAR (`workflows.py`).
- **HECHO:** El backlog canónico de producto en `docs/internal/product/BACKLOG.md` clasifica el Ítem #14 ("Políticas portables: compilar a primitivas nativas del UEM") con el veredicto **SÍ con matiz** y un impacto de 4/5.
- **HECHO:** Las especificaciones de esquemas de Intune Compliance Policies, Jamf Smart Groups y Fleet YAML son públicas y estables.
- **INFERENCIA:** Proporcionar un compilador export-only elimina la barrera de entrada para adoptar políticas estandarizadas en entornos multi-plataforma.
- **HIPÓTESIS:** Los administradores utilizarán el compilador para generar y versionar artefactos de políticas en sus repositorios de infraestructura antes de importarlos a sus consolas UEM.

## 5. Por qué ahora

1. **Heterogeneidad irreversible de la flota corporativa:** El uso conjunto de macOS, Windows y Linux es la realidad predominante en empresas tecnológicas y corporativas.
2. **Adopción de estándares declarativos:** Fleet DM popularizó la gestión de políticas mediante YAML en Git; extender este concepto cross-UEM mediante compilación es el siguiente paso natural.
3. **Alineación con los principios no negociables de LucidFence:** El compilador opera en modo *export-only* (genera el archivo, el administrador decide cuándo y cómo importarlo), respetando estrictamente el principio de "Complemento, No UEM".

## 6. Por qué este producto

LucidFence es el único actor capaz de ofrecer este compilador porque:
1. **Neutralidad Multi-UEM:** Microsoft nunca ofrecerá un exportador a Jamf Smart Groups, ni Jamf compilará a Fleet YAML. Un compilador agnóstico y neutral es la única solución viables.
2. **Motor Local-First:** La compilación de políticas es una transformación AST/JSON pura que se ejecuta en milisegundos en la máquina local del usuario sin depender de servicios en la nube.

## 7. Experiencia propuesta

1. **Definición de la Política Portable:** El admin define o selecciona una política en LucidFence (p. ej., `policy_geofence_madrid.json`).
2. **Comando de Compilación:** Ejecuta el comando CLI o selecciona en la interfaz:
   ```bash
   lucidfence compile policy_geofence_madrid.json --target intune,jamf,fleet --out ./artifacts/
   ```
3. **Artefactos Generados:**
   - `./artifacts/intune_compliance_policy.json` (esquema válido para Microsoft Intune Custom Compliance).
   - `./artifacts/jamf_smart_group.xml` (criterio de Smart Group para Jamf Pro API/GUI).
   - `./artifacts/fleet_policy.yaml` (definición de política YAML para Fleet DM).
4. **Importación Controlada:** El administrador revisa e importa los artefactos a sus respectivas consolas UEM mediante sus pipelines habituales.

## 8. Momento mágico

«El administrador define una geocerca compleja con reglas de postura de cifrado y en 3 segundos genera los archivos de política nativos perfectamente formateados para Intune, Jamf y Fleet, ahorrándose 4 horas de configuración manual en 3 consolas distintas.»

## 9. Diferenciación y ventaja defensiva

- **Escribe Una Vez, Compila en Cualquier UEM:** Elimina el lock-in de políticas y unifica los criterios de seguridad de la organización.
- **Transparencia Total Export-Only:** No requiere otorgar permisos de modificación directa sobre la estructura de las consolas UEM si el administrador prefiere la importación manual o vía GitOps.

## 10. Alcance por etapas

### Experimento
Implementar un módulo prototipo `policy_compiler.py` enfocado exclusivamente en exportar reglas de postura a formato Fleet YAML e Intune Compliance JSON.

### Primera versión (Thin Slice)
Soporte de compilación desde el CLI `lucidfence compile` para los 3 targets principales (Intune, Jamf, Fleet) con validación de esquemas de salida.

### Expansión
Soporte para Workspace ONE y Applivery AMAPI policy JSON.

### Visión North Star
Linter y compilador inverso que tome políticas existentes de Intune o Jamf y las normalice al esquema portable de LucidFence.

## 11. Fuera de alcance

- Sincronización bidireccional automática en segundo plano que mutar estados de UEM sin intervención del admin.
- Modificación de la API de UEMs que no expongan endpoints o esquemas públicos para importación de políticas.

## 12. Implicaciones técnicas

- **Nuevos módulos:** `lucidfence/core/policy_compiler.py` (transformador AST/JSON puro).
- **Esquemas:** Mantener los esquemas JSON/YAML de referencia de Intune, Jamf y Fleet en `lucidfence/core/schemas/`.
- **Complejidad:** Media (M). Mapeo de AST de condiciones y operadores lógicos.

## 13. Seguridad, privacidad y confianza

- **Procesamiento 100% Local:** La compilación no realiza solicitudes de red.
- **Verificabilidad:** Los archivos generados son texto plano inspeccionable y versionable en Git.

## 14. Valor para el negocio

- **Interoperabilidad Total:** Convierte a LucidFence en el centro de diseño de políticas de la empresa sin reemplazar los UEMs existentes.
- **Reducción de Errores Humanos:** Elimina las discrepancias causadas por la traducción manual de políticas entre equipos de TI.

## 15. Métricas

- **Métrica de resultado:** 0 inconsistencias de políticas entre plataformas UEM en tenants multi-UEM.
- **Métrica de uso:** Número de compilaciones de políticas ejecutadas por tenant al mes.

## 16. Evaluación

- **Problema:** 4/5
- **Alcance:** 4/5
- **Impacto:** 4/5
- **Viabilidad:** 4/5
- **Riesgo:** 1/5
- **Horizonte recomendado:** `EXPLORE` (prototipar compilador Fleet YAML e Intune JSON)

## 17. Riesgos y motivos para no construirla

- Algunos UEMs no soportan primitivas equivalentes para conceptos específicos (p. ej. geocercas poligonales complejas no expresables en esquemas de compliance nativos de Intune).
- **Mitigación:** Cuando una primitiva no sea soportada nativamente por el UEM destino, el compilador emitirá una advertencia explícita y generará la regla de fallback basada en la señal reportada.

## 18. Preguntas abiertas

1. ¿Deberíamos ofrecer una vista previa en el Dashboard del código JSON/YAML compilado antes de descargarlo?

## 19. Próximo experimento recomendado

Crear un test unitario `tests/test_policy_compiler.py` compilando una regla de geocerca y cifrado a Fleet YAML e Intune Compliance JSON, verificando que los archivos resultantes cumplen con los esquemas de validación.

## 20. Recomendación final

**Aprobar para Explore.** Es una propuesta elegante que refuerza el posicionamiento de LucidFence como el complemento neutral indispensable en entornos multi-UEM.
