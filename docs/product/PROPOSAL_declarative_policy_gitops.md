# ✨ Geocercas y Políticas como Código con Simulación de Impacto Previo (Declarative Geofence & Policy GitOps with Pre-Flight Blast Radius Replay)

## 1. Resumen ejecutivo

Los administradores de TI y equipos de SecOps temen modificar geocercas y reglas de política de riesgo en producción debido al riesgo de causar bloqueos masivos no deseados o disparar acciones destructivas (aislamiento de red, borrado o bloqueo) sobre dispositivos legítimos. Proponemos potenciar **Geocercas y Políticas como Código (`lucidfence apply`)**: una experiencia declarativa estilo GitOps que permite definir `fences.json` y `policies.json` en repositorios versionables y ejecutarlos mediante la CLI local o el dashboard API-first (`/api/v2/config/apply`). El contrato existente de la CLI ya valida sintácticamente, calcula el diff contra la configuración activa y ejecuta una **simulación de impacto previo (Pre-Flight Blast Radius Replay)** en modo preview por defecto (`policy_replay.py`), aplicando cambios atómicos únicamente al pasar la bandera `--yes`.

## 2. Propuesta en una frase

«Para los **Administradores de TI y Leads de SecOps**, que necesitan **actualizar geocercas y políticas de riesgo de la flota de forma auditable y sin cometer errores destructivos**, proponemos **Geocercas y Políticas como Código con Simulación de Impacto Previo (`lucidfence apply`)**, que permite **ver en tiempo real el diff exacto y la simulación histórica del impacto con contrato de aproximación explícito antes de confirmar cualquier cambio**, a diferencia de **los paneles de UEM convencionales que aplican cambios a ciegas en producción sin previsualizar el alcance del impacto.**»

## 3. Problema

- **Persona:** Admin de TI, Lead Security Engineer, SecOps Lead en organizaciones mid-market y enterprise.
- **Situación:** Una organización debe actualizar las coordenadas de un perímetro corporativo (p. ej. mudanza de sede o redefinición de zona autorizada) o ajustar el umbral de severidad de un playbook SOAR.
- **Trabajo por realizar:** Versionar, auditar y aplicar cambios en las geocercas y políticas de riesgo garantizando que no afecten a usuarios ni portátiles autorizados.
- **Fricción actual:** En la mayoría de consolas UEM (Intune, Jamf, Scalefusion), las reglas se editan manualmente mediante formularios web interactivos. Un error en un radio de geocerca, un polígono invertido o una regla de riesgo mal redactada se aplica de inmediato a la flota viva ("cambio a ciegas"), pudiendo marcar cientos de dispositivos como "no conformes" e iniciar bloqueos de red o de sesión inesperados.
- **Impacto:** Interrupción de la operativa de negocio, llamadas masivas al soporte técnico (Helpdesk), desconfianza en la automatización de seguridad y retraso en el despliegue de políticas actualizadas.
- **Solución utilizada hoy:** Edición manual en consola UI con pruebas limitadas sobre 1-2 dispositivos de prueba (canary manual) o scripts personalizados en CI/CD que llaman a APIs sin evaluar el impacto real previo.

## 4. Evidencia

- **HECHO:** `lucidfence/core/policy_replay.py` implementa la función `replay_policy()` que simula la ejecución de reglas sobre trazas históricas de ubicación (`trails.jsonl`). Para reglas puramente espaciales la simulación es exacta; para reglas que incluyen postura de seguridad o compliance, evalúa la postura actual del dispositivo sobre las posiciones históricas declarando explícitamente `approximation.exact = False` (`tests/test_policy_replay.py`).
- **HECHO:** `lucidfence/cli.py` (`cmd_apply`) y `lucidfence/core/config_apply.py` ya implementan el contrato `apply`: validación sintáctica, diff de líneas contra `data_dir` y simulación what-if por defecto. `--dry-run` no existe como argumento CLI (devuelve exit 2 por unrecognized argument); el preview es el comportamiento por defecto y los cambios se escriben solo al suministrar `--yes`.
- **HECHO:** El backlog de producto canónico en `docs/internal/product/BACKLOG.md` clasifica el Ítem #1 ("Políticas y geocercas como código con `apply` y diff") con la máxima puntuación de impacto para el administrador (5/5) y el veredicto **SÍ**.
- **INFERENCIA:** Los administradores prefieren flujos de trabajo basados en infraestructura como código (GitOps) porque permiten revisiones entre pares (PRs), auditoría en Git y reversibilidad instantánea (`git revert`).
- **HIPÓTESIS:** Presentar un informe de impacto previo (*Blast Radius Report*) que cuantifique la flota afectada y declare de forma transparente la aproximación de postura aumentará en un 60% la confianza para automatizar remediaciones SOAR.
- **DESCONOCIDO:** La ventana temporal histórica óptima en `trails.jsonl` (24h, 72h o 7 días) que maximiza la precisión de la simulación sin penalizar el tiempo de respuesta local.

## 5. Por qué ahora

1. **Adopción de GitOps en Seguridad y TI:** Las organizaciones maduras están migrando de configuraciones manuales en UI a flujos declarativos versionados en Git.
2. **Capacidad técnica existente e infrautilizada:** LucidFence ya posee de forma nativa los componentes clave: el rejugador histórico (`policy_replay.py`), el validador de esquemas (`config_validator.py`), el motor de aplicación (`config_apply.py`) y la CLI local (`cli.py`).
3. **Creciente riesgo de automatizaciones destructivas:** A medida que se activan playbooks SOAR automáticos, un cambio de política erróneo tiene consecuencias mucho más graves que una simple alerta visual.

## 6. Por qué este producto

LucidFence cuenta con una posición competitiva única para ofrecer esta experiencia:
1. **Evaluación 100% Local y Desconectada:** La simulación ocurre íntegramente en la máquina o contenedor local del tenant utilizando el historial de estados de dispositivos (`data/cloud_tenants/`), sin necesidad de enviar datos a servidores externos ni pagar por consultas de API cloud.
2. **Motor What-If Nativo:** A diferencia de Fleet (que permite YAML pero lo aplica directamente en el servidor), LucidFence combina validación declarativa con rejugado histórico offline sobre trazas reales, declarando formalmente cuándo el resultado es exacto o aproximado.
3. **Arquitectura API-First y CLI Local:** Funciona mediante CLI local (`lucidfence apply --fences ... --policies ...`, pasando `--yes` para aplicar) o endpoints HTTP versionados (`POST /api/v2/config/apply`).

## 7. Experiencia propuesta

1. **Disparador:** El admin modifica un archivo `fences.json` o `policies.json` en su repositorio Git o en la interfaz del dashboard local.
2. **Pre-flight & Replay (Preview por defecto):** El admin ejecuta `lucidfence apply --fences fences.json --policies policies.json` o presiona "Simular Impacto" en la SPA.
3. **Observación del Informe de Radio de Impacto (Blast Radius Report):**
   - **Diff Declarativo:** Muestra las geocercas/políticas añadidas (`+`), modificadas (`~`) o eliminadas (`-`).
   - **Rejugado Histórico (Simulación What-If):** Evalúa la regla propuesta sobre los datos almacenados de las últimas 48 horas.
   - **Contrato de Aproximación Explicito:** Muestra `approximation.exact: true` para reglas geoespaciales, o `approximation.exact: false` indicando que la postura/compliance evalúa el estado actual sobre las ubicaciones pasadas.
   - **Resultados:** *"Si aplicas este cambio: 124 dispositivos continúan conformes, 3 dispositivos cambian a 'fuera de cerca', 0 dispositivos sufren wipe."*
4. **Decisión y Confirmación:** Si el informe de simulación es aceptable, el admin ejecuta `lucidfence apply --yes --fences fences.json --policies policies.json` o confirma en la UI. Si detecta un impacto no deseado, ajusta los parámetros antes de tocar la flota viva.
5. **Auditoría e Inmutabilidad:** El cambio se aplica de forma atómica y se registra en el log de auditoría con el hash del commit o firma del autor.

## 8. Momento mágico

«El usuario se da cuenta del valor de la función cuando, al intentar reducir el radio de una geocerca de oficina de 500m a 50m, la simulación de impacto le advierte antes de guardar: *'⚠️ Atención: Esta modificación habría clasificado como NO CONFORME al 42% de la plantilla comercial que trabaja en las salas de reuniones del ala oeste durante los últimos 3 días.'* Evitando así un incidente masivo de falso positivo antes de que ocurra.»

## 9. Diferenciación y ventaja defensiva

- **Simulación Blast Radius Offline:** Ningún UEM del mercado (Intune, Jamf, Scalefusion, Fleet) ofrece simulación histórica previa sobre la propia telemetría del cliente sin servidores externos.
- **Transparencia en el Contrato de Aproximación:** A diferencia de sistemas opacos, LucidFence declara explícitamente en el informe si el rejugado es exacto (señales espaciales) o aproximado (postura actual sobre posiciones pasadas).
- **Inmunidad a Fallos en Cascada:** Al validar y simular localmente, se eliminan los errores de sintaxis y las inconsistencias lógicas antes de que alcancen los conectores UEM.
- **Soberanía y Portabilidad de Políticas:** Las políticas se expresan en formato JSON/YAML estándar y portable, libre de lock-in de proveedor.

## 10. Alcance por etapas

### Contrato Existente (Línea Base)
Comando CLI `lucidfence apply --fences <path> --policies <path>` que valida, calcula diff, simula por defecto (preview) y requiere `--yes` para aplicar atómicamente a disco (`lucidfence/cli.py` + `config_apply.py`).

### Experimento (Discovery)
Validar mediante pruebas de integración el comportamiento de `POST /api/v2/config/apply` consumiendo el resultado de `policy_replay.py` y verificando que devuelva la estructura de diff y `approximation` esperada.

### Primera versión (Thin Slice v2.0 API-First)
Exponer la capacidad declarativa en la API v2 (`POST /api/v2/config/apply` y `GET /api/v2/config/diff`), permitiendo a clientes externos y scripts de CI/CD obtener el informe de radio de impacto en JSON estructurado.

### Expansión UI
Incorporar en la SPA local (`static/dashboard.html`) un editor visual de geocercas/políticas con panel split-screen: "Configuración Actual vs Propuesta" con mapa de impacto de dispositivos simulados.

### Visión North Star
Integración con pipelines CI/CD (GitHub Actions / GitLab CI) que comente automáticamente en las Pull Requests el informe gráfico de simulación de impacto previa (*GitOps Policy Bot*) antes de fusionar cambios a la rama principal.

## 11. Fuera de alcance

- Agentes de compilación remota o servicios SaaS centralizados para procesar configuraciones.
- Reescritura directa de archivos de configuración de otros UEMs propietarios (Intune/Jamf) sin pasar por sus APIs oficiales.
- Modificación automática de repositorios Git remotos sin autorización previa del usuario.

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** `lucidfence/core/policy_replay.py`, `lucidfence/core/config_apply.py`, `lucidfence/core/config_validator.py`, `lucidfence/core/fences.py`, `lucidfence/core/policies.py`, `lucidfence/cli.py`.
- **Integraciones:** Mantenimiento de compatibilidad con la arquitectura API-first y esquemas OpenAPI en `/api/v2/`.
- **Datos necesarios:** Trazas históricas de `DeviceState` registradas en el almacén local del tenant (`data/cloud_tenants/`).
- **Dependencias:** Exclusivamente biblioteca estándar de Python 3.11+.
- **Incertidumbres técnicas:** Garantizar que el cálculo de simulación `policy_replay.py` ejecute en < 200 ms para flotas de hasta 5,000 dispositivos.

## 13. Seguridad, privacidad y confianza

- **Aplicación Atómica:** Si la simulación o validación de un paquete de políticas falla, el estado del engine permanece inalterado (rollback automático).
- **Mínimo Privilegio y Doble Llave:** Las acciones de alto impacto (como `wipe`) identificadas durante la simulación requieren la bandera explícita `allow_wipe=true` en el entorno.
- **Trazabilidad Total:** Cada archivo aplicado genera un digest SHA-256 almacenado en el registro de auditoría local.

## 14. Valor para el negocio

- **Adopción en Enterprise / SecOps:** Posiciona a LucidFence como la única solución de geofencing compatible con flujos modernos de Infraestructura como Código (IaC / GitOps).
- **Reducción de Costes Operativos:** Elimina las horas de soporte dedicadas a solucionar incidentes provocados por malas configuraciones accidentales de geocercas.
- **Retención de Usuarios:** Incrementa la confianza de los administradores al eliminar el miedo a la automatización de la seguridad.

## 15. Métricas

- **Métrica de resultado:** 0 incidentes de falsos positivos masivos causados por reconfiguración de geocercas en tenants que utilizan `lucidfence apply`.
- **Indicador adelantado:** Porcentaje de cambios de política precedidos por una simulación en vista previa (sin `--yes`).
- **Métrica de uso:** Número de ejecuciones de `lucidfence apply` / simulaciones what-if por tenant al mes.
- **Métrica de calidad:** Latencia media de la simulación de impacto previa (< 100ms para 1,000 dispositivos).
- **Guardrails:** Cero corrupción de la configuración activa en caso de cancelación o fallo durante la simulación.

## 16. Evaluación

- **Problema:** 5/5
- **Alcance:** 5/5
- **Impacto:** 5/5
- **Estrategia:** 5/5
- **Diferenciación:** 5/5
- **Deleite:** 5/5
- **Viabilidad:** 5/5 (los componentes backend `config_apply.py`, `config_validator.py`, `cli.py` y `policy_replay.py` ya forman parte del núcleo)
- **Evidencia:** 5/5
- **Riesgo:** 1/5 (operación puramente previa y atómica sin efectos colaterales no deseados)
- **Efecto compuesto:** 5/5

- **Confianza:** Alta
- **Esfuerzo relativo:** Pequeño-Medio (S-M)
- **Reversibilidad:** Alta (los cambios son declarativos y revertibles vía versión o Git)
- **Tipo de apuesta:** Núcleo / Plataforma
- **Horizonte recomendado:** `EXPLORE` (para refinamiento de la experiencia API v2 y especificación de la UI)

## 17. Riesgos y motivos para no construirla

- **Riesgo de desalineación si los datos históricos son escasos:** En una instalación completamente nueva con pocas horas de telemetría, la simulación histórica podría mostrar un impacto artificialmente bajo.
- **Mitigación:** Incluir una advertencia explícita en el informe de simulación cuando la ventana histórica almacenada sea menor a 24 horas ("*Nota: Simulación basada en 2 horas de telemetría acumulada*").

## 18. Preguntas abiertas

1. ¿Deberíamos permitir exportar el informe de simulación en formato SARIF / JSON para ser consumido por linters de CI/CD como GitHub Actions Code Scanning?
2. ¿Cuál debe ser el límite por defecto de días históricos rejugados en la simulación para equilibrar velocidad y exhaustividad?

## 19. Próximo experimento recomendado

Diseñar y verificar el contrato JSON del nuevo endpoint `/api/v2/config/apply` que exponga la salida estructurada del diff y del objeto `approximation` de `policy_replay.py` para consumo desde la SPA.

## 20. Recomendación final

**Promover a Discovery / Horizon Explore.** La oportunidad satisface holgadamente todos los criterios de valor, diferenciación y apalancamiento arquitectónico de LucidFence. Se recomienda incluir la propuesta en el mapa de producto bajo el horizonte `EXPLORE` e iniciar la definición de la especificación API.
