# Constitución de LucidFence

> Artefacto al estilo [github/spec-kit](https://github.com/github/spec-kit)
> (constitution): los principios **no negociables** del proyecto, consolidados
> desde las decisiones del propietario que vivían desperdigadas en `LOOP.md`,
> `STATE.md` §Overrides, `PRODUCT_ROADMAP.md` y `BACKLOG.md`. Este documento
> es supremo: cualquier spec, plan, PR o loop que lo contradiga está mal por
> definición. El código sirve a la spec; la spec sirve a esta constitución.

## Principios fundamentales

### I. Local-first y soberano
El dato del tenant vive en la máquina del tenant. Cero telemetría, cero
exfiltración de ubicación (el dato geoespacial no sale de la máquina), cero
dependencia de una nube nuestra. La vitrina pública (`data/cloud_state.json`)
es demo-only por diseño y jamás lleva datos reales de tenant.
*(Origen: identidad fundacional; reafirmado 2026-08-15.)*

### II. Complemento, no UEM
LucidFence **nunca será un UEM**: no enrola dispositivos, no empuja perfiles,
no gestiona apps ni parches. Lee del UEM que el admin ya tiene, correlaciona
con señales propias (geocercas, red, osquery, CVE), explica el riesgo y actúa
**solo a través del UEM** cuando el admin decide. La neutralidad es la ventaja:
un UEM no puede federar a sus rivales ni auditarse a sí mismo; el complemento
sí. Una idea que nos convierta en UEM es NO por posicionamiento.
*(Decisión del propietario, 2026-08-18.)*

### III. Gratis y open-source
100% free open-source (Apache-2.0): sin pricing, sin edición enterprise, sin
funciones de pago. Solo free tiers de terceros; cualquier coste siempre-on con
token nuestro exige aprobación explícita del propietario.
*(Decisión del propietario, 2026-08-16.)*

### IV. Runtime-first — honestidad verificable (NO NEGOCIABLE)
Todo claim anunciado se valida en vivo (`scripts/runtime_validation.py`,
batería N/N) además de en la suite honesta (`tests/run_tests.py`, tally real).
Un claim que compila pero no arranca bloquea el merge. Corolarios:
- **Desconocido nunca penaliza**: una señal ausente/None jamás inventa riesgo
  ni cobertura (patrón readback-honesto de todas las señales de postura).
- **Evidencia, no certificación**: el mapeo de compliance declara lo que
  comprueba y lo que no; cero teatro.
- Un umbral de rendimiento es guard de regresión, no SLA.
*(Regla permanente del propietario, 2026-08-15.)*

### V. stdlib-first
El runtime del producto es Python stdlib. Una dependencia nueva es una decisión
de arquitectura que hay que justificar, no un import. Herramientas de
desarrollo (lint, hooks) pueden usar terceros; el producto no. La escalera de
mínimos (¿debe existir? → ¿ya está en el repo? → ¿stdlib? → ¿una línea?) es el
reflejo por defecto al escribir código (skill `ponytail`).

### VI. Frontera de autonomía (INVIOLABLE)
El **desarrollo** del producto es autónomo: la flota de loops idea, implementa,
prueba, versiona y publica sin gate humano (auto-merge total en verde, release
y outreach incluidos). El **runtime** del producto no lo es jamás: el
geofencing y el enforcement sobre dispositivos reales los decide siempre el
administrador — `dry_run` por defecto, `enforce` opt-in explícito por tenant
con allow-list por acción, `wipe` con doble llave (`allow_wipe` **y**
`wipe_allowlist`). Prohibido entregar un cambio que debilite esto.
*(Decisión del propietario, 2026-08-18; detalle en `docs/internal/LOOP.md`.)*

### VII. Fleet de primera clase y mínimo privilegio
Fleet (fleetdm) tiene paridad de primera clase con el resto de UEMs en toda
mejora. Cada integración pide el mínimo privilegio real que su modo necesita
(observe = solo lectura) y cada adapter conserva su camino mock offline: los
tests corren sin credenciales reales.
*(Decisión del propietario, 2026-08-15.)*

## Restricciones adicionales

- **Denylist absoluta** (ni con CI verde): secretos en
  `config.json`/`data/`/`.env`; `adapters/base.py` sin bump MAJOR + mock
  offline; `data/cloud_state.json` con datos reales; wallets/spam; PRs de
  forks/terceros jamás se auto-mergean.
- **Contrato de lint** (`.ruff.toml`): solo clases de error reales (F/E9); el
  estilo compacto de la casa es deliberado y no se lintea. Gate write-time en
  `.claude/hooks/quality_gate.sh`.
- **Integridad del marketplace de adapters**: los adapters publicados se
  verifican por sha256 (`lucidfence/plugins/adapters/index.json`); una edición
  legítima regenera el índice en la misma PR.

## Flujo de desarrollo

1. **Spec antes de código** para toda función nueva (SDD, spec-kit): el loop
   PM escribe la mini-spec (`docs/internal/product/spec-template.md`) con el
   claim runtime que la batería probará. Sin claim verificable no hay feature.
2. **Entrega por el raíl**: push a `claude/**` → `agent-pr.yml` abre PR →
   `agent-automerge.yml` mergea en verde. La CI es el veredicto.
3. **La definición de "hecho" es un comando**: `python3 scripts/verify.py` →
   `VERIFY: APTO (4/4)` (versión coherente + enlaces de docs + batería runtime
   N/N + suite honesta).
4. **La spec se mantiene con el código**: un cambio que deja `SPEC.md`, la
   `openapi.json` o esta constitución desactualizadas no está terminado.

## Gobernanza

Esta constitución prevalece sobre cualquier otra práctica documentada. Las
**enmiendas** son decisiones del propietario: se registran aquí (con fecha),
en la bitácora del roadmap, y llegan por PR del raíl como cualquier cambio.
Los loops y especialistas del bench verifican conformidad constitucional en
cada revisión (las "Reglas de la casa" de `.claude/agents/` son el espejo
operativo de este documento). Ante conflicto entre documentos, gana el más
restrictivo hasta que el propietario resuelva.

**Versión**: 1.0.0 | **Ratificada**: 2026-08-20 | **Última enmienda**: 2026-08-20
