# CONTRIBUTING

Gracias por querer contribuir a LucidFence. Estas notas te ahorran tiempo y evitan trabajo duplicado.

## Cómo contribuir

1. **Busca primero.** Revisa issues existentes y el README antes de abrir algo nuevo.
2. **Habla antes de escribir mucho.** Si quieres cambiar algo grande, abre un issue describiendo qué, por qué, y cómo lo piensas hacer. Si no hay issue y es pequeño, directo a PR.
3. **PRs pequeños, PRs frecuentes.** Un PR que hace una cosa bien es más fácil de revisar que uno que hace cinco.
4. **Mantén el commit histórico limpio.** Commits atómicos, mensaje que explica el *por qué* en el primer párrafo, el *qué* es el diff.
5. **Sigue el stack del proyecto.** Python 3.11, stdlib-first. Nothing web frameworks in the engine. El HTTP propio está en `saas_server.py`.
6. **No hackee el runner de tests.** `tests/run_tests.py` es honesto; un `test_*.py` que hace `raise SystemExit` en el import mata la discovery de todos los siguientes archivos.

## Desarrollo local

```bash
# 1 — clonar
git clone https://github.com/<owner>/lucidfence.git
cd lucidfence

# 2 — correr tests (honestos, 105 = verde)
python3 tests/run_tests.py

# 3 — servidor local
python3 saas_server.py          # :8765
```

Dashboard: `http://localhost:8765` → `static/dashboard.html`.

## Setup del repo (merge de fricción-cero)

El `.gitattributes` declara drivers de merge que eliminan conflictos crónicos
del merge train (ver tarea t_e207227e / issue #118). Para que funcionen en tu
máquina, registra el driver custom **una sola vez** tras clonar:

```bash
# Driver que regenera el índice de adapters desde los .py mergeados.
# Evita conflictos en lucidfence/plugins/adapters/index.json (JSON con sha256
# verificados por tests/test_annual_roadmap.py: regenerar, no unir a mano).
git config --local merge.regen-adapter-index.name  "regenerate adapter index"
git config --local merge.regen-adapter-index.driver \
  'python3 scripts/build_adapter_index.py || true'
```

Los `merge=union` (logs append-only de los loops: `loop-run-log.md`,
`release/history.md`, `trends/signals.md`, `security/findings.md`,
`growth/experiments.md`, `growth/mentions.md`) son drivers **integrados** de git
no necesitan registro. `data/*.jsonl` es append-only pero está gitignored, así
que no entra en merges.

> Nota: `STATE.md` es **reescrito** por los loops, no append → no lleva
> `merge=union` a propósito (un union dejaría basura duplicada).

### Alcance de los drivers (importante)

- `merge=union` es un driver **integrado de git** y GitHub sí lo aplica en el
  merge server-side → los 6 logs append-only no generan conflictos ni en local
  ni en el merge train de GitHub (#118).
- `merge=regen-adapter-index` es un driver **custom** (`cmd`): git lo ejecuta en
  merge **local**, pero **GitHub NO lo corre en el merge server-side**. Por tanto,
  en el merge train de GitHub el `index.json` puede seguir dando conflicto si dos
  PRs lo tocan a la vez (igual que antes). El driver custom solo alivia merges
  locales; no es la solución para el tren de GitHub.
- **Solución duradera para el merge train (#118):** un job CI *post-merge* que
  regenere `lucidfence/plugins/adapters/index.json` sobre `main` tras cada merge
  (o que falle el merge si el índice quedó obsoleto). Así el hash verificado por
  `tests/test_annual_roadmap.py` siempre coincide. Ver tarea de seguimiento
  pendiente de crear.

## Adapter UEM nuevo

TODO: completar la guía de plugin con el contrato de adapter (qué methodos/estructuras espera el engine, cómo se registra, qué data retorna, cómo se verifica). Mientras tanto, mira `lucidfence/core/adapters/` existentes como referencia.

## Releases

Los tags y releases se hacen desde el mantenedor. El README externo declara la versión actual.

## Código de conducta

TODO: agregar el código de conducta del proyecto (Contributor Covenant o equivalente) cuando el proyecto esté listo para recibir contribuciones externas.

## Language policy / Política de idioma

**English-first for new technical material.** New code, code comments, commit
messages and technical reference docs are written in **English**. This keeps the
codebase legible to any contributor and stops the language from drifting file to
file.

Two deliberate exceptions:

1. **Existing Spanish stays.** We do not do repo-wide rewrites. Where a file is
   already in Spanish, keep editing it in Spanish until it is rewritten for
   another reason. New code converges to English; old code is not churned just
   to translate it.
2. **The user manual is bilingual.** The end-user manual
   (`docs/manual/`, client-facing READMEs) is intentionally bilingual
   ES/EN, because our users are.

The goal is convergence, not a flag day: touch a file, leave it a little more
English than you found it (for code) — and leave the user manual bilingual.

---

**English-first para material técnico nuevo.** El código nuevo, los comentarios,
los mensajes de commit y los docs de referencia técnica se escriben en
**inglés**. Así el código queda legible para cualquiera y el idioma deja de
variar de fichero en fichero.

Dos excepciones deliberadas:

1. **El español existente se mantiene.** No reescribimos el repo entero. Donde
   un fichero ya está en español, se sigue editando en español hasta que se
   reescriba por otro motivo. El código nuevo converge a inglés; el viejo no se
   remueve solo para traducirlo.
2. **El manual de usuario es bilingüe.** El manual para el usuario final
   (`docs/manual/`, READMEs de cliente) es bilingüe ES/EN a propósito, porque
   nuestros usuarios lo son.

El objetivo es convergencia, no un corte seco: al tocar un fichero, déjalo algo
más en inglés de como estaba (para código) — y deja el manual de usuario
bilingüe.

## Código de conducta

TODO: agregar el código de conducta del proyecto (Contributor Covenant o equivalente) cuando el proyecto esté listo para recibir contribuciones externas.

## Contacto

TODO: agregar canal de contacto del mantenedor cuando esté listo.
