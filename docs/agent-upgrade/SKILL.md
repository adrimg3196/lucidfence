---
name: agent-upgrade
description: Patrones de referencia para mejorar la calidad del agente.
category: operations
---

# Agent Upgrade — patrones de referencia aplicados a Hermes

Compila los patrones que REALMENTE mejoran a este agente, extraidos de repos
de recon (cron `recon-agent-repos`). No clona monstruos: aplica sus ideas.

## 1. Skills como TDD (obra/superpowers — writing-skills)
- Una skill es "test-driven development applied to process documentation".
- Antes de escribir una skill: corre un escenario de presion (subagent) SIN la
  skill, documenta la rationalizacion que usa el agente para saltarse la regla
  (RED). Escribe la skill que ataca ESE incumplimiento especifico (GREEN).
  Cierra loopholes y revisa (REFACTOR).
- **Aplicar en Hermes:** al crear/editar skills con `skill_manage`, primero
  describe el fallo observado sin la skill, luego el SKILL.md que lo cura.

## 2. Verification before completion (obra/superpowers — iron law)
```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```
- Antes de afirmar "listo/pasa/fix": IDENTIFY comando -> RUN completo ->
  READ exit code + conteo -> VERIFY -> solo entonces CLAIM. Sin evidencia = mentira.
- **Aplicar en Hermes:** nunca digas "funciona" sin haber corrido el comando
  en este turno (ffmpeg -f null, pytest, git status). Ya lo hago; esto lo fija.

## 3. Plan-execute + nested agents + checkpoint (xorbitsai/xagent)
- Patrones: ReAct, DAG plan-execute, agentes padre-hijo (nested), checkpoint
  con pause/resume, tool auto-discovery, memory vectorial.
- **Aplicar en Hermes:**
  - Tareas complejas: desglosa en DAG de subtareas (no lineal ciego).
  - `delegate_task` = nested agent con contexto aislado (ya lo uso).
  - Si una tarea larga puede interrumpirse, guarda estado intermedio para
    reanudar (equivalente a checkpoint).
  - Tools: prefiere auto-descubrimiento (`tool_search`) antes de asumir que
    falta una herramienta.

## 4. Role-play SOP (FoundationAgents/MetaGPT)
- Asignar roles (PM, engineer, reviewer) a agentes para colaborar en tareas
  complejas con un SOP compartido.
- **Aplicar en Hermes:** en workflows multiagente, definir el rol de cada
  subagent explicitamente en el `context` (ya lo hago con `delegate_task`).

## 5. Multi-agent + interoperabilidad (microsoft/autogen -> Microsoft Agent Framework)
- Autogen esta en maintenance; sucesor = Microsoft Agent Framework: orquestacion
  multi-agente enterprise, multi-provider, interoperabilidad cross-runtime via
  **A2A y MCP**.
- **Aplicar en Hermes:** para integrar agentes externos, usar MCP (ya tengo
  servidores MCP) y A2A como contrato de mensajeria, no acoplar prompts.

## 6. Componentes interoperables + memory (langchain-ai/langchain)
- Encadenar componentes interoperables y futuro-proof; tool-use + memory +
  third-party integrations.
- **Aplicar en Hermes:** tools modulares (ya los tengo), memory persistente
  (ya la uso), y elegir integraciones por interfaz estable, no por framework
  de moda.

## Checklist de mejora (usar tras cada recon)
- [ ] ¿La skill nueva tiene un RED (fallo sin ella) documentado?
- [ ] ¿Corri evidencia fresca antes de claim?
- [ ] ¿La tarea compleja tiene DAG y no solo pasos lineales?
- [ ] ¿Los subagents tienen rol + contexto aislado?
- [ ] ¿Hay checkpoint si la tarea puede interrumpirse?

## Referencias (repos de recon)
- obra/superpowers (skill TDD + verification-before-completion (superpowers))
- langchain-ai/langchain (revisar manualmente)
- FoundationAgents/MetaGPT (role-play SOP + nested agents (MetaGPT/xagent))
- microsoft/autogen (revisar manualmente)
- badlogic/lemmy (revisar manualmente)
- zhongyu09/openchatbi (revisar manualmente)
- alexfazio/crewAI-quickstart (role-play SOP + nested agents (MetaGPT/xagent))
- xorbitsai/xagent (DAG plan-execute + checkpoint (xagent))

- obra/superpowers (skills TDD, verification)
- xorbitsai/xagent (plan-execute, nested, checkpoint, memory)
- microsoft/autogen -> Microsoft Agent Framework (A2A/MCP multi-agent)
- FoundationAgents/MetaGPT (role-play SOP)
- langchain-ai/langchain (tool-use, memory, interoperabilidad)
