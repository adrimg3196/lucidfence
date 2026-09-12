# ✨ LucidFence ShadowTwin & Proof-of-Presence (PoP)

## 1. Resumen ejecutivo

LucidFence ShadowTwin & Proof-of-Presence (PoP) transforma la gestión de geocercas en entornos multi-UEM de una disciplina reactiva y temida a una plataforma proactiva de simulación continua y atestación criptográfica de presencia. Mediante la ejecución de un motor en sombra ("ShadowTwin") que simula en tiempo real la aplicación de políticas y geocercas sobre telemetría en vivo o reproducida sin tocar los conectores UEM reales, los administradores de SecOps pueden predecir con exactitud cero el impacto de nuevas reglas. Simultáneamente, el módulo Proof-of-Presence permite emitir tokens firmados localmente que certifican la permanencia de un dispositivo en zonas seguras o corredores sin exponer coordenadas GPS continuas a auditores externos.

## 2. Propuesta en una frase

«Para Administradores de Seguridad TI y Auditores de Cumplimiento que necesitan validar geocercas y probar la presencia de dispositivos sin provocar interrupciones operativas ni violar la privacidad de ubicación, proponemos LucidFence ShadowTwin & Proof-of-Presence, que permite simular políticas en tiempo real con impacto cero en UEMs y generar atestaciones criptográficas locales de cumplimiento espacial, a diferencia de los UEMs tradicionales que aplican políticas a ciegas y requieren exportar historiales de coordenadas crudas.»

## 3. Problema

- **Persona:** CISO, Administrador de SysAdmin / SecOps y Auditor de Cumplimiento Normativo.
- **Situación:** Organizaciones con flotas heterogéneas de dispositivos corporativos (laptops, móviles) que se desplazan entre oficinas, instalaciones clasificadas, rutas logísticas y zonas remotas/no autorizadas.
- **Trabajo por realizar:**
  1. Configurar y ajustar políticas de riesgo por geocercas y corredores sin causar bloqueos accidentales a empleados legítimos.
  2. Demostrar a auditores externos (SOC 2, ISO 27001, NIS2, Esquema Nacional de Seguridad) que los dispositivos que accedieron a datos confidenciales estaban físicamente dentro de perímetros autorizados en ventanas temporales específicas.
- **Fricción actual:**
  - *Temor al modo activo (Enforcement Fear):* Los administradores dejan LucidFence en modo `observe` indefinidamente porque temen que una geocerca mal configurada o un salto repentino de coordenadas GPS active acciones restrictivas (ej. `lock` o `wipe`) en Intune/Jamf.
  - *Falta de atestación respetuosa con la privacidad:* Para verificar si un laptop estuvo dentro de una sede durante una auditoría, hoy se exportan logs completos de latitud/longitud a hojas de cálculo o SIEMs externos, violando la privacidad de los empleados y el principio Local-first.
- **Impacto:** Menor adopción del modo activo de enforcement, sobrecarga manual en auditorías TI y fricción entre equipos de seguridad y usuarios finales.
- **Solución utilizada hoy:** Pruebas manuales con dispositivos de prueba únicos, exportación manual de logs de ubicación CSV y revisión humana caso por caso.

## 4. Evidencia

- **HECHO:** `ARCHITECTURE.md` y `docs/superpowers/specs/2026-09-05-lucidfence-2-go-rewrite-design.md` establecen `observe` como el modo por defecto del motor y exigen confirmación doble llave para acciones de alto impacto como `wipe`.
- **HECHO:** LucidFence 2.0 cuenta con una arquitectura de motor basada en paquetes independientes como `internal/domain/geo`, `internal/domain/risk`, `internal/domain/transition` y un reproductor de ciclos `internal/engine/replay.go`.
- **INFERENCIA:** La separación estricta entre evaluación de riesgo/geocercas y la ejecución de acciones en UEMs (`internal/uem`) permite clonar el estado del motor en memoria para ejecutar simulaciones en sombra sin afectar el entorno de producción.
- **HIPÓTESIS:** Ofrecer una garantía visual del 100% en simulación ("ShadowTwin impact score") aumentará la conversión de tenants del modo `observe` al modo `enforcement` activo en un 40%.
- **DESCONOCIDO:** La tasa exacta de derivas GPS extremas por modelo de hardware en entornos cerrados (in-building drift).

## 5. Por qué ahora

- La arquitectura de LucidFence 2.0 en Go está diseñada desde cero con subsegundos de latencia por ciclo de evaluación y cero bases de datos externas.
- El auge del trabajo híbrido y las normativas de soberanía de datos (NIS2, DORA en la UE) exigen demostrar cumplimiento de localización sin almacenar coordenadas personales en nubes de terceros.
- Las capacidades de simulación en `internal/engine/replay.go` y `internal/uem/simulation` ya están maduras en el motor Go 2.0, requiriendo solo la capa de orquestación en sombra y atestación criptográfica.

## 6. Por qué este producto

LucidFence es el único motor geofencing multi-UEM local-first y open source del mercado. A diferencia de las plataformas UEM propietarias (Microsoft Intune, VMware Workspace ONE, Jamf Pro) que tratan la ubicación como un atributo estático o dependiente de su propia nube, LucidFence procesa el riesgo de ubicación localmente en la infraestructura del cliente. Esto le otorga la posición única para emitir atestaciones de presencia locales y ejecutar simulaciones gemelas en sombra sin costos por API externa ni fuga de telemetría.

## 7. Experiencia propuesta

1. **Activación de ShadowTwin:** El administrador navega a la sección de Políticas o Geocercas y activa la casilla **«Modo ShadowTwin»** al crear o editar una política/geocerca.
2. **Evaluación Proactiva en Sombra:** El motor de LucidFence procesa los reportes de ubicación entrantes de la flota real a través del pipeline `ShadowEngine`. Registra veredictos, incidencias hipotéticas y acciones desencadenadas en un registro de auditoría en sombra (`shadow_events.jsonl`), sin enviar comandos al adaptador UEM real.
3. **Panel de Impacto Proyectado:** En el dashboard de LucidFence, una tarjeta muestra: *«En las últimas 24 horas, esta política en modo ShadowTwin habría desencadenado 3 bloqueos (2 por deriva GPS en Sede Central)»*. El admin ajusta el radio de tolerancia sin haber afectado a ningún usuario.
4. **Generación de Token Proof-of-Presence (PoP):** Para solicitudes de cumplimiento/auditoría, el admin o una API autorizada solicita una atestación para `device_id` en `fence_id` durante `[t_start, t_end]`.
5. **Atestación Criptográfica:** LucidFence valida las permanencias (`dwell_marks`) almacenadas localmente y emite un token JWT/Ed25519 firmado por la clave local de la organización. El token certifica: `"El dispositivo X permaneció dentro de la Geocerca Y con un nivel de confianza del 98% entre T1 y T2"`, eliminando las coordenadas GPS del token final.

## 8. Momento mágico

«El administrador activa una política restrictiva en modo ShadowTwin, observa en el panel cómo el sistema detecta correctamente 15 dispositivos fuera de ruta pero identifica un falso positivo en 1 laptop con GPS inestable, ajusta la geocerca con un clic y convierte la política a Modo Activo con total tranquilidad en menos de 2 minutos.»

## 9. Diferenciación y ventaja defensiva

- **Cero telemetría externa + Cero Falsos Positivos Operativos:** Ningún competidor UEM ofrece simulación gemela previa a la aplicación de cambios de geocerca.
- **Prueba de Presencia Privada (Privacy-Preserving Proof-of-Presence):** Permite pasar auditorías de seguridad física/lógica proporcionando pruebas matemáticas firmadas en lugar de rastros de GPS crudos que violan el RGPD/LOPD.
- **Efecto acumulativo:** Las simulaciones históricas mejoran los modelos locales de tolerancia por geocerca y dispositivo sin enviar datos fuera de la red local.

## 10. Alcance por etapas

### Experimento
- Extender `internal/engine/replay.go` y `cmd/lucidfence` con una marca `--shadow` que evalúe eventos pasados contra un borrador de política en memoria e imprima una tabla de impactos hipotéticos en consola.

### Primera versión (Thin Slice MVP)
- API endpoint `/api/v1/policies/shadow-test` y UI en `web/src/features/policies/WhatIfPanel.tsx` para previsualizar eventos simulados en tiempo real durante 1 hora.
- Generación de atestación PoP en formato JSON firmado por la clave local de la org en `internal/store/secrets.go`.

### Expansión
- Ejecución persistente de políticas ShadowTwin en segundo plano paralelas al ciclo principal de `internal/engine`.
- Visualización de diferencias entre trazado real vs trazado en sombra en el mapa de React (`FleetMap.tsx`).

### Visión North Star
- Sistema de Auto-Tuning Autónomo: El ShadowTwin recomienda automáticamente ajustes de radio y corredores de geocerca basados en densidad de señales y patrones reales de movimiento de la flota sin intervención manual.

## 11. Fuera de alcance

- Modificaciones en las APIs públicas de los UEMs de terceros.
- Aplicaciones de agentes nativos en el dispositivo cliente (LucidFence sigue operando a nivel de servidor local / API de UEM).
- Almacenamiento en la nube de tokens PoP (los tokens son gestionados exclusivamente por la instancia local de LucidFence).

## 12. Implicaciones técnicas

- **Capacidades reutilizables:** `internal/engine/replay.go`, `internal/domain/transition`, `internal/domain/risk`, `internal/store/dwell_marks.go`, `internal/auth` (firmado Ed25519 / HMAC).
- **Integraciones:** Egress vía Webhook/OCSF existente para emitir eventos de atestación PoP.
- **Datos necesarios:** `dwell_marks` históricos y trazas guardadas localmente en `internal/store`.
- **Incertidumbres técnicas:** Impacto en CPU/Memoria de ejecutar 2x ciclos de evaluación en paralelo para flotas de >10.000 dispositivos en hardware modesto.

## 13. Seguridad, privacidad y confianza

- **Privacidad por diseño:** El token PoP contiene hashes unidireccionales del identificador del dispositivo y la geocerca, junto con la ventana temporal y el veredicto de presencia. Las coordenadas latitud/longitud no se empaquetan en el token.
- **Trazabilidad & Auditoría:** Cada atestación PoP emitida queda registrada atómicamente en `pop_attestations.jsonl` bajo permisos `0600`.
- **Kill switch:** Las simulaciones ShadowTwin corren en hilos desacoplados y pueden ser pausadas inmediatamente sin afectar el loop principal de evaluación de `internal/engine`.

## 14. Valor para el negocio

- **Aumento del uso del modo activo (Enforcement Adoption):** Desbloquea la transición de clientes de `observe` a `active`, aumentando el valor percibido del producto.
- **Apertura de caso de uso de auditoría y cumplimiento:** Permite a empresas en sectores altamente regulados (defensa, banca, salud) usar LucidFence como motor de evidencia para compliance.
- **Diferenciación competitiva:** Consolida a LucidFence como el estándar de geofencing de código abierto indispensable sobre cualquier UEM comercial.

## 15. Métricas

- **Métrica de resultado:** % de tenants que convierten al menos 1 política de modo `observe` a `enforcement active` tras usar ShadowTwin (Objetivo: +35%).
- **Indicador adelantado:** Número de simulaciones ShadowTwin ejecutadas por usuario a la semana.
- **Métrica de uso:** Número de tokens Proof-of-Presence emitidos para auditoría.
- **Métrica de calidad:** 0 falsos positivos en verificaciones PoP respecto al estado real de `dwell_marks`.
- **Guardrails:** El consumo de CPU/Memoria del motor no debe incrementarse en más de un 15% durante las simulaciones en sombra.

## 16. Evaluación

- Problema: 4.8/5
- Alcance: 4.5/5
- Impacto: 4.7/5
- Estrategia: 5.0/5
- Diferenciación: 5.0/5
- Deleite: 4.6/5
- Viabilidad: 4.5/5
- Evidencia: 4.2/5
- Riesgo: 1.8/5 (Bajo riesgo por ser aislado en memoria / local-first)
- Efecto compuesto: 4.8/5

- **Confianza:** Alta
- **Esfuerzo relativo:** Medio
- **Reversibilidad:** Alta
- **Tipo de apuesta:** Plataforma / Apuesta estratégica
- **Horizonte recomendado:** EXPLORE -> NEXT

## 17. Riesgos y motivos para no construirla

- **Argumento en contra:** Si los administradores están satisfechos manteniendo LucidFence exclusivamente como un dashboard pasivo de visualización de mapas y alertas por correo, la complejidad de mantener un motor en sombra y firma de tokens criptográficos podría no ser aprovechada por organizaciones pequeñas sin requisitos de auditoría.
- **Mitigación:** Diseñar la función como un componente modular opt-in que reutilice las estructuras existentes en `internal/engine/replay.go` sin agregar peso al runtime básico.

## 18. Preguntas abiertas

1. ¿Es preferible utilizar claves Ed25519 por organización o JWT firmados con RSA/HMAC para la atestación PoP para máxima compatibilidad con validadores externos de SIEM?
2. ¿Cuál es el límite razonable de días de retención histórica de trazas para simulaciones en sombra sin impactar el almacenamiento en disco local?

## 19. Próximo experimento recomendado

Crear un subcomando CLI experimental en `cmd/lucidfence` (`lucidfence shadow test --policy-file draft.json`) que lea las trazas locales existentes de la org y genere un informe comparativo entre las acciones que se hubieran ejecutado y las que se ejecutaron realmente en producción.

## 20. Recomendación final

**Promover a EXPLORE.**
Esta propuesta aborda directamente la mayor barrera de adopción del modo activo de geofencing en LucidFence 2.0, apalanca las fortalezas únicas del motor Go local-first y crea un diferenciador categórico imposible de replicar por competidores SaaS tradicionales.
