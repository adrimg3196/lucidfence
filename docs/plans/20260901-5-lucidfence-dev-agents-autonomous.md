---
date: "2026-09-01"
status: draft
scope: lucidfence-dev-agents
source: planning-session-2026-09-01-01
---

# Plan: Agentes autónomos para LucidFence — repo work + auto-mejora

**Fecha:** 2026-09-01  
**Propietario:** Hermes Agent (en nombre de Adri, CEO)  
**Repo:** `adrimg3196/lucidfence` (workspace `/Users/adri/lucidfence`)  
**Referencias:** `docs/references/definition-of-done.md`, `docs/references/agent-team-charter.md`, AGENTS.md

---

## 1. Visión

Un sistema de agentes autónomos (Hermes profiles) que trabajan el repo de LucidFence en tres dimensiones simultáneas:

1. **Desarrollo de producto:** implementar bugs, features, tests, docs, abrir y revisar PRs.
2. **Auto-mejora de los agentes:** consumir habilidades/skills/plugins desde @HermesWatcher (única fuente permitida) y aplicarlos para que los agentes sean mejores.
3. **Mantenimiento del repo:** verificar, monitorear CI, actualizar deps, mantener clean el branch.

**Principios de diseño:**
- Sin intervención humana en el loop técnico.
- Fuente única de mejora externa: @HermesWatcher (no GitHub repos).
- Cada agente tiene memoria persistente donde acumula lecciones.
- Toda la mejora pasa por verify.py = puerta de calidad.
- PRs son la interface de entrega, nunca push directo a main.

---

## 2. Agentes del sistema

### 2.1 Dev Agent (implementador)

**Perfil:** `empresa-dev` (o nuevo: `lucidfence-dev`)  
**Herramientas:** terminal, file, gh CLI, test runner  
**Tareas:**
- Escanear issues abiertos en busca de bugs P1/P2 + pequeñas features.
- Para cada issue:
  1. Leer issue completo (title, body, labels, comments).
  2. Localizar código relevante (grep, read_file en engine.py, providers.py, etc.).
  3. Implementar fix/feature en branch `dev/<issue-slug>` desde origin/main.
  4. Escribir tests si es bug (test que fallaba → test que pasa).
  5. Ejecutar `python3 scripts/verify.py --quiet` + `python3 tests/run_tests.py`.
  6. Si verde: git add, git commit (mensaje imperativo + Co-Authored-By), git push.
  7. `gh pr create --title "..." --body "..."` con Closes #<issue>.
  8. Si falla: revertir, documentar en memory, pasar al siguiente.

**Decisiones que toma solo:**
- Qué archivos modificar.
- Qué cambios hacer (basado en issue description + lectura de código).
- Qué tests escribir.
- Decir "no implementable automáticamente" si el issue requiere decisión humana.

**Decisiones que escala a Adri:**
- Issues que requieren decisión de negocio/arquitectura mayor.
- PRs que fallan CI repetidamente.

**Memory:** `docs/internal/dev-agent-memory.md` — lo que implementó, qué falló, lecciones.

### 2.2 Reviewer Agent (revisor de PRs)

**Perfil:** `empresa-qa` (o reutilizar `empresa-test-qa`)  
**Herramientas:** gh CLI, terminal, file  
**Tareas:**
- Escanear PRs abiertas sin reviews.
- Para cada PR:
  1. Leer diff (`gh pr diff <N> --name-only`).
  2. Verificar que incluye: mensaje de commit correcto, body con contexto, Closes #<issue> si aplica.
  3. Verificar que CI está verde (gh pr checks <N>).
  4. Si todo OK: dejar comentario "LGTM" + approve si tiene permisos, o dejar comentario constructivo con sugerencias.
  5. Si hay issues: comentario con puntos específicos.

**Decisiones que toma solo:**
- Qué comentarios de revisión hacer (basado en diff + verify status).
- Decir "faltan cambios" o "aprobado" basado en criterios objetivos.

### 2.3 Docs/SEO Agent

**Perfil:** `empresa-seo-docs` (existente)  
**Herramientas:** terminal, file, web  
**Tareas:**
- Revisar y actualizar landing pages de comparación (static/compare.html).
- Mantener CHANGELOG.md al día con cada merge a main.
- Asegurar que docs/ no tenga links rotos (verify.py gate).
- Añadir documentación para features recién mergeadas.

### 2.4 Release Agent

**Perfil:** `empresa-devops-release` (existente)  
**Herramientas:** terminal, gh CLI  
**Tareas:**
- Revisar main periódicamente: si hay commits nuevos que cierran issues.
- Actualizar CHANGELOG.md con cambios significativos.
- Si hay milestone cumplida: preparar release (version bump en pyproject.toml).
- Ejecutar verify.py antes de cualquier release.

### 2.5 Auto-mejora Agent (skill discovery)

**Perfil:** `empresa-selfimprove` (existente, 4 agentes con batch_processing + memory + subagent)  
**Herramientas:** web, terminal, file, memory, delegate_task  
**Tareas:**
- Revisar @HermesWatcher feed regularmente por nuevas habilidades/skills/plugins.
- Para cada habilidad encontrada:
  1. Evaluar si aplica a LucidFence dev agents.
  2. Si sí: crear skill en `~/.hermes/profiles/<perfil>/skills/<skill-name>/SKILL.md`.
  3. Si no es installable pero es útil: documentar en memory como lección.
- Registrar en loop-run-log.md qué se aplicó y qué resultado tuvo.

**Fuente única:** @HermesWatcher (X posts) — ningún GitHub repo discovery (eliminado tras decisión del usuario).

---

## 3. Infraestructura

### 3.1 Memory de agentes

Cada agente tiene un archivo de memory persistente en `docs/internal/`:
- `dev-agent-memory.md` — lecciones del dev agent.
- `reviewer-memory.md` — lecciones del reviewer.
- `loop-run-log.md` — registro de cada ejecución del loop.

Format: markdown con secciones de "Lo que funcionó", "Lo que falló", "Lecciones aprendidas".

Los agentes leen su memory al inicio de cada sesión y la actualizan al final.

### 3.2 Daily Loop Script

**Archivo:** `scripts/lucidfence-dev-loop.py` (o similar)

El loop ejecuta en tres fases:
1. **Plan:** lectura de issues, triaje, asignación a agentes.
2. **Ejecución:** agentes trabajan en paralelo (delegate_task) — dev agent implementa, reviewer revisa.
3. **Auto-mejora:** skill discovery desde @HermesWatcher, actualización de memory.

**Schedule:** una vez al día (ej. 9:00 AM) via cron job de Hermes.

### 3.3 Cron Jobs necesarios

Nuevos jobs de cron (en perfil `empresa-dev` o similar):

| Job | Schedule | Descripción |
|-----|----------|-------------|
| `lucidfence-dev-daily` | 0 9 * * * | Ejecuta loop completo (plan + ejecución + auto-mejora) |
| `lucidfence-dev-weekly` | 0 9 * * 1 | Resumen semanal + revisión de lecciones |

Cada job tiene acceso a: terminal, file, gh, web (para @HermesWatcher), memory, delegate_task.

---

## 4. Pipeline de work

### 4.1 Ciclo típico de un dev agent

```
1. Leer issues abiertos (gh issue list --state open --limit 20)
2. Filtrar: bugs P1/P2, issues sin asignar
3. Para cada issue candidato:
   a. Investigar: leer issue + buscar código relevante
   b. Si no es implementable automáticamente: skip (documentar)
   c. Si es implementable:
      - Crear branch dev/<issue-slug> desde origin/main
      - Implementar cambio
      - Escribir tests (si bug)
      - Ejecutar verify.py + tests
      - Si verde: commit, push, crear PR
      - Si rojo: revert, documentar, skip
4. PRs creados → entrar en cola de reviewer
5. Reviewer agent revisa PRs en cola
6. PRs aprobadas → esperar merge (manual o auto-merge si está habilitado)
```

### 4.2 Ciclo de auto-mejora

```
1. Revisar @HermesWatcher por nuevos posts
2. Extraer habilidades/skills/plugins mencionados
3. Para cada uno:
   a. Evaluar relevancia para LucidFence dev agents
   b. Si relevante: instalar skill en perfil apropiado
   c. Si no es installable: documentar como lección
4. Registrar en loop-run-log.md
5. Próximo día: los agentes ya tienen las nuevas habilidades cargadas
```

---

## 5. Quality gates

### 5.1 Antes de push

- `python3 scripts/verify.py --quiet` → APTO 4/4 o 6/6 (dependiendo versión).
- `python3 tests/run_tests.py` → 0 failures (o failures aceptados documentados).

### 5.2 Antes de merge

- PR tiene CI verde (gh pr checks <N>).
- PR tiene al menos 1 review (del reviewer agent o de Adri si es manual).
- verify.py pasa en el branch del PR.

### 5.3 Auto-mejora

- Nueva skill añadida a profile → agente recarga perfil → skill disponible en próximos runs.
- Lección documentada → leída por agente en próximos runs → mejora comportamiento.

---

## 6. Manejo de lo indecidible

**No implementable automáticamente:**
- Issues que requieren decisión de negocio (ej. "qué feature priorizar").
- Issues que requieren acceso a sistemas externos sin credenciales automatizadas.
- Features grandes que necesitan diseño arquitectónico.

**Acción:** agente documenta en memory + deja comentario en issue indicando que requiere decisión humana.

**Escalación a Adri:**
- PRs que fallan CI repetidamente.
- Issues que ningún agente puede implementar.
- Divergencias entre agentes (ej. reviewer dice que PR está mal, dev agent dice que está bien).

---

## 7. Primeros pasos (próximas 24h)

### 7.1 Ya disponible (polished)

- **PR #377:** mergeado a main, cierra #310 + #302. Gate declarativo + honest sentinel.
- **PR #379:** mergeado a main, cierra #317 + #326. SEO infraestructura.
- **Agentes de monotorización:** CTO audit, Security SOC, DevOps CI, TestQA (4 agentes con batch_processing + memory + subagent).

### 7.2 Hitos inmediatos

1. **Crear dev-agent.py standalone** que implemente un issue real de principio a fin.
2. **Ejecutar dev-agent contra un issue simple** (ej. #302 ya resuelto en #377 — para demostrar el ciclo, o un issue nuevo pequeño).
3. **Integrar hugo_skill_discovery.py** en el loop diario (ya existente, solo conectar).
4. **Configurar cron job** para ejecutar el loop diariamente.
5. **Crear agent-lessons.md** inicial con lecciones de las iteraciones anteriores.

### 7.3 Hitos a medio plazo

- Dev agent implementando bugs reales de forma recurrente.
- Reviewer agent dando feedback constructivo en PRs.
- Auto-mejora agent integrando skills de @HermesWatcher en los perfiles.
- Loop ejecutándose diariamente sin intervención humana.
- Tantos PRs mergeados a main como agentes puedan producir de forma honesta.

---

## 8. Lo que NO se hace (para mantener realismo)

- **No se prometen features grandes** que requieran decisión arquitectónica.
- **No se usa GitHub repo discovery** para skill discovery (eliminado).
- **No se hace push directo a main** — siempre PRs.
- **No se automatiza lo que no se puede verificar** con verify.py.
- **No se crean agentes infinitos** — 4-5 agentes bien definidos es suficiente.

---

## 9. Éxito

El sistema está funcionando cuando:

- Hay agentes ejecutándose de forma autónoma cada día.
- PRs están siendo creados sin intervención humana (bugs pequeños, docs, tests).
- PRs están siendo revisados sin intervención humana.
- Nuevas habilidades de @HermesWatcher se aplican regularmente.
- verify.py sigue siendo el gate de calidad, respetado por todos los agentes.
- El repo avanza como software open-source gestionado por una empresa real.

**Métricas de éxito:**
- PRs abiertos por agentes en los últimos 30 días.
- PRs mergeados a main en los últimos 30 días.
- Skills aplicados desde @HermesWatcher en los últimos 30 días.
- Issues cerrados por agentes en los últimos 30 días.
- verify.py verde en main tras cada merge.

---

## 10. Riesgos

- **Agentes perdiendo contexto:** si un agente es reiniciado, su memoria persiste en files, pero la sesión en memoria se pierde. Solución: leer memory file al inicio.
- **CI fallando por diferencias ambientales:** lo que pasa localmente puede fallar en CI. Solución: ejecutar exactamente lo mismo que CI hace (`tests/run_tests.py`).
- **Bloat de PRs:** si los agentes crean muchos PRs pequeños, el repo puede saturarse. Solución: triaje inteligente — cada agente enfoca un tipo de trabajo.
- **Dependencia en @HermesWatcher:** si el feed está down o no tiene nuevo contenido, el auto-mejora agent no tiene nada que hacer. Solución: aceptable, no es crítico.
