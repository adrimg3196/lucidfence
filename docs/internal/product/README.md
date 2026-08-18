# Loop Product Manager → Nuevas funciones (autónomo)

Un product manager autónomo que **suma capacidades nuevas** al producto cada
ciclo, sin autorización humana. Mientras Admin-value ejecuta el backlog
priorizado (hacer lo pendiente "imprescindible"), este loop **concibe y entrega
funciones nuevas** que amplían lo que LucidFence hace por el admin IT.

Lo pilota el especialista `product-manager` del bench (`.claude/agents/`).

## Norte

Cada ciclo aterriza en `main` **una función nueva, real y usable** para un admin
de Intune/Jamf/Applivery/Fleet — o, si la mejor idea es demasiado grande para un
ciclo, su primer incremento verticalmente funcional (no un andamiaje muerto).
Nada de features de humo: si no se puede validar en runtime, no se anuncia.

## De dónde salen las ideas (señal real, no invención)

0. **Backlog evaluado** (`BACKLOG.md`, este directorio): ítems inspirados en el
   sector con veredicto explícito de si merecen desarrollo; los SÍ son la cola
   por defecto de este loop.
1. **Roadmap vivo** (`docs/roadmap/PRODUCT_ROADMAP.md` §Próximo/Después): el
   horizonte que el loop Roadmap ya priorizó.
2. **Tendencias** (`docs/internal/trends/signals.md`): capacidades que el
   ecosistema (Apple DDM, AMAPI, Windows DSC, osquery/Fleet) vuelve esperables.
3. **Gaps declarados** (README §"No está terminado", `STATE.md`).
4. **Dogfooding**: arranca el producto en local (`lucidfence quickstart` /
   `saas_server.py`) y usa el dashboard como lo haría un admin; la fricción real
   que encuentres es la mejor fuente de una función nueva.

Prioriza por impacto para el admin × esfuerzo × principios (local-first, $0,
runtime-first, Fleet primera clase). Una por ciclo (WIP=1, título `feat: …`).

## Ciclo (semanal)

1. `git fetch origin main && git checkout -B claude/pm-features origin/main`.
   Lee `docs/internal/LOOP.md` (§Norte, §Coordinación, §Raíl de entrega),
   `docs/roadmap/PRODUCT_ROADMAP.md`, `docs/internal/trends/signals.md`, `STATE.md`.
2. Elige/diseña **una** función nueva. Escribe en 3-5 líneas: qué hace, para qué
   admin, y cómo se valida en runtime (el claim que la batería probará).
3. Delega la implementación en el especialista adecuado (Agent subagent_type:
   `engineering-senior-developer`, `engineering-iot-fleet-engineer`,
   `security-architect`, `engineering-backend-architect`): código stdlib +
   tests (runner honesto, sin fixtures pytest) + endpoint/UI si aplica + check en
   `scripts/runtime_validation.py` que pruebe el claim nuevo.
4. Revisa el diff (correctness, auth/seguridad, invariantes: stdlib, sin
   telemetría, sin exfiltración de ubicación, `base.py` y doble llave del wipe
   intactos). `python3 scripts/verify.py` → `APTO (4/4)`. Si se coló
   `data/cloud_state.json`: `git checkout origin/main -- data/cloud_state.json`.
5. Actualiza `STATE.md` (registra la función), y si consumiste un ítem del
   roadmap, deja constancia para que Roadmap reconcilie. Línea en el run-log.
6. **Entrega por el raíl** (no necesitas tools `mcp__github__`): commit +
   `git push` a `claude/pm-features`; `agent-pr.yml` abre la PR y
   `agent-automerge.yml` la mergea en verde. Sin autorización humana.

## Coordinación (no pisar a Admin-value)

- **Admin-value** hace *imprescindible* lo que ya existe (drena backlog). **Este
  loop añade lo que aún no existe.** Si ambos quisieran tocar el mismo fichero la
  misma semana, cede el más nuevo (este) y difiere con nota; un rebase trivial no
  es conflicto (regla 4 de Coordinación).
- Deuda de limpieza pura → `docs/internal/housekeeper/deferred-candidates.md`.
- Hallazgo de seguridad con PoC → cola del Centinela.

## Invariantes

Local-first, stdlib-first, 100% gratis, sin telemetría, sin exfiltración de
ubicación. Nada anunciado sin validación en runtime. Solo una función por ciclo;
si no hay una buena idea validable esta semana, refresco + una línea, sin PR
(resultado válido). Estilo i-have-adhd: acción/resultado primero.
