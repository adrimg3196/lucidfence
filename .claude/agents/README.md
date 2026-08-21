# .claude/agents — Bench de especialistas de LucidFence

Subagentes nativos de Claude Code que la flota de loops usa para delegar
decisiones de dominio. Cada `*.md` es un especialista (frontmatter
`name`/`description`/`color`) invocable por su slug como `subagent_type`.

- **Origen:** taxonomía y estructura de personas de
  [agency-agents](https://github.com/msitarzewski/agency-agents) (msitarzewski),
  **adaptadas** a las funciones reales de este repo (Python stdlib, geofencing/
  UEM local-first). No es una copia literal de los 230+ agentes del origen: es
  el bench que ESTA empresa necesita. Ver `docs/internal/agency/ORG.md`.
- **Cómo se usa:** cada loop (departamento) delega en sus especialistas. El
  mapa loop → especialistas → derechos de decisión está en
  `docs/internal/agency/ORG.md`. El contrato de la flota, en
  `docs/internal/LOOP.md`.
- **Regla común:** todos llevan las "Reglas de la casa" (gate QA `verify.py`
  innegociable, auto-merge total en verde, denylist absoluta, runtime-first, un
  solo canal de reporting, estilo i-have-adhd). Los agentes deciden; no queda
  gate humano en el desarrollo (release y outreach incluidos, propietario
  2026-08-18). El RUNTIME del producto lo controla siempre el admin, y
  LucidFence es complemento del UEM, nunca UEM.

## Bench actual (por división)

| División | Especialistas |
|---|---|
| engineering | backend-architect, senior-developer, code-reviewer, minimal-change-engineer, devops-automator, git-workflow-master, iot-fleet-engineer, privacy-engineer |
| security | penetration-tester, architect |
| testing | reality-checker |
| product | manager, roadmap-strategist |
| marketing | seo-specialist, community-builder |
| project-management | project-shepherd |
| finance | fpa-analyst |
| support | issue-triage |
| specialized | chief-of-staff, fleet-architect |

Añadir un especialista: crea `<division>-<slug>.md` con el mismo frontmatter,
aterrízalo en las convenciones del repo y mapéalo a su loop en `ORG.md`.
