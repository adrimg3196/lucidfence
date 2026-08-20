# ADR-0005 — El runtime lo decide el admin: observe-default, doble llave del wipe

**Estado:** Accepted — 2026-08-18 (decisión del propietario; Constitución §VI, INVIOLABLE).

## Contexto

LucidFence actúa sobre dispositivos reales a través del UEM: en el límite, puede
bloquear o borrar equipos. Un producto autónomo que decida por sí mismo un
`wipe` es inaceptable — el coste de un falso positivo es catastrófico e
irreversible. La autonomía del *desarrollo* (ver ADR-0010) no puede filtrarse al
*runtime* del producto. El administrador humano debe conservar siempre el control
de lo que le pasa a su flota.

## Decisión

El enforcement sobre dispositivos reales lo decide **siempre el admin**, con
defaults seguros escalonados:

- `dry_run` por **defecto**: nada actúa hasta que el admin lo habilita.
- `enforce` es **opt-in** explícito por tenant, con allow-list por acción.
- `wipe` exige **doble llave**: `allow_wipe` **y** `wipe_allowlist`.
- Cada integración pide el mínimo privilegio de su modo (observe = solo lectura).

Está prohibido entregar cualquier cambio que debilite esta frontera.

## Consecuencias

- **A favor:** el peor caso (borrado accidental) requiere dos decisiones
  humanas deliberadas; el default nunca daña; el producto es confiable para un
  admin que no cede el control.
- **En contra:** no hay remediación 100% automática de extremo a extremo — por
  diseño; el admin carga con la decisión final.
- **Frontera inviolable:** ni el gate verde ni la autonomía del desarrollo
  autorizan saltarse esto.

## Dónde vive hoy

`lucidfence/core/engine.py`, `actions.py`, `soar.py` (dry_run primero);
principio en [CONSTITUTION.md §VI](../architecture/CONSTITUTION.md); detalle en
`docs/internal/LOOP.md` §Qué es autónomo y qué NO.
