# docs/internal/agency/ORG.md — El organigrama de la empresa autónoma

LucidFence se construye y mantiene como una **empresa de software autónoma sin
intervención humana**: los agentes deciden, el propietario solo recibe el digest
semanal y aprueba el outreach (propietario, 2026-08-16). Este fichero es el
organigrama: cada loop es un **departamento**, y cada departamento delega las
decisiones de dominio en un **bench de especialistas** vendido en
`~/lucidfence-agents-tooling/.claude/agents/` (Claude Code native subagents).

El bench adapta la taxonomía y estructura de personas de
[agency-agents](https://github.com/msitarzewski/agency-agents) (msitarzewski) a
las funciones REALES de este proyecto. Decisión honesta de alcance: el repo
fuente trae 230+ agentes, muchos ruido para un producto Python stdlib de
geofencing/UEM local-first (Roblox/Unreal, healthcare clínico, GIS, Drupal,
Solidity…). "Al completo" para ESTA empresa = un bench que cubre cada función
real, no 230 ficheros de game-dev. Cada agente está aterrizado en las
convenciones del repo (`verify.py`, stdlib-first, el contrato de `LOOP.md`), no
copiado literalmente.

## Cómo se usa el bench

Toda sesión de loop clona el repo, así que hereda `~/lucidfence-agents-tooling/.claude/agents/`. Un loop
**delega** invocando al especialista por su `subagent_type` (el slug del
frontmatter, p. ej. `security-penetration-tester`). El loop es el gerente del
departamento; el especialista toma la decisión de dominio y devuelve el
entregable. El humano no está en esta cadena — su único gate es el merge de una
PR `outreach:`.

## Organigrama: departamento (loop) → especialistas → derechos de decisión

| Departamento (loop) | Especialistas del bench | Decide (sin humano) |
|---|---|---|
| **Admin-value** (producto) | `product-manager`, `engineering-senior-developer`, `engineering-backend-architect`, `engineering-iot-fleet-engineer` | Qué mejora entra por ciclo, su diseño e implementación, qué UEM/Fleet se refuerza |
| **Housekeeper** (limpieza) | `engineering-minimal-change-engineer` | Qué se limpia hoy y qué se difiere (nunca borra lo incierto) |
| **Guardián** (salud de main, backlog, watchdog) | `engineering-code-reviewer`, `engineering-git-workflow-master`, `engineering-devops-automator` | Qué PR se rebasa/mergea/cierra, qué rama se borra, cómo se arregla main rojo |
| **Deps-sweeper** (dependencias) | `engineering-devops-automator`, `testing-reality-checker` | Qué pins suben (incl. MAJOR) si el gate QA aguanta |
| **Dirección** (digest, el único que notifica) | `specialized-chief-of-staff` | Qué llega al propietario y en qué orden; qué es incidente |
| **Growth** (adopción) | `marketing-seo-specialist`, `marketing-community-builder`, `support-issue-triage` | Qué experimento SEO corre; redacta el outreach (**merge = aprobación del propietario**) |
| **Centinela** (seguridad ofensiva) | `security-penetration-tester`, `security-architect` | Qué se ataca en localhost, qué fix+regresión entra, qué es crítico-notificable |
| **Lanzamiento** (releases) | `engineering-devops-automator`, `testing-reality-checker` | Si toca lanzar, el bump coherente, disparar `release.yml`, Homebrew |
| **Roadmap** (rumbo de producto) | `product-roadmap-strategist` | Qué entra en el horizonte y con qué prioridad; qué roadmap histórico es canónico; qué sube a la cola de Admin-value |
| **Transversal (todos los loops)** | `project-shepherd` (coordinación), `finance-fpa-analyst` (presupuesto/kill switch), `specialized-fleet-architect` (diseño de la flota), `testing-reality-checker` (DoD), `engineering-privacy-engineer` (local-first) | Contrato de coordinación, techo de tokens, evolución de la flota, veredicto `verify.py`, invariante de privacidad |

## Derechos de decisión (quién decide qué, sin humano)

1. **Producto y código** → los especialistas de ingeniería + `product-manager`
   deciden diseño e implementación. `engineering-code-reviewer` es el veto de
   correctness/seguridad antes del auto-merge.
2. **La definición de "hecho"** → `testing-reality-checker` es la autoridad de
   `verify.py`. Sin `VEREDICTO QA: APTO`, nada mergea.
3. **Seguridad** → `security-architect` fija la postura; `security-penetration-tester`
   la intenta romper por PoC en localhost. Un fix de seguridad sin regresión no
   entra.
4. **Coordinación** → `project-shepherd` hace cumplir propiedad de ramas,
   calendario UTC sin solape y derivación cruzada (`LOOP.md` §Coordinación).
5. **Coste** → `finance-fpa-analyst` custodia `loop-budget.md` (caps + kill
   switch + circuit breaker de 3 intentos).
6. **La flota misma** → `specialized-fleet-architect` evoluciona `LOOP.md`/este
   ORG.md manteniendo el invariante: agentes deciden, humano solo aprueba
   outreach.
7. **El propietario** → recibe UNA notificación (el digest de Dirección) y toma
   UNA decisión recurrente: mergear (o no) las PR `outreach:`. Nada más.

## Invariante (propietario, 2026-08-16)

> "No quiero como humano tomar decisiones; plenamente las toman los agentes."

Todo especialista lleva en su ficha las "Reglas de la casa": el gate QA de
máquina es innegociable, auto-merge total en verde, denylist absoluta,
runtime-first, un solo canal de reporting, estilo i-have-adhd. El único gate
humano que sobrevive es el outreach a terceros.
