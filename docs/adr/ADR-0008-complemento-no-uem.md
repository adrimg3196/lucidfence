# ADR-0008 — Complemento del UEM, nunca un UEM

**Estado:** Accepted — 2026-08-18 (decisión del propietario; Constitución §II).

## Contexto

Existe una tentación recurrente de crecer hacia "hacerlo todo": enrolar
dispositivos, empujar perfiles, gestionar apps y parches — es decir, convertirse
en un UEM más. Eso destruiría la ventaja del producto y lo pondría a competir de
frente con los UEM que son su ecosistema. Un UEM no puede federar a sus rivales
ni auditarse a sí mismo con neutralidad; un complemento sí.

## Decisión

LucidFence es el **complemento neutral del UEM que el admin ya tiene, y nunca un
UEM**: no enrola dispositivos, no empuja perfiles, no gestiona apps ni parches.
Lee de la flota del UEM existente, la correlaciona con señales propias
(geocercas, red, osquery, CVE), **explica** el riesgo y actúa **solo a través del
UEM** cuando el admin decide. Cualquier idea que nos convierta en UEM es NO por
posicionamiento.

## Consecuencias

- **A favor:** neutralidad como ventaja competitiva; integra en lugar de
  competir; alcance acotado y defendible; encaja con local-first (ADR-0006) y
  con la frontera de runtime (ADR-0005).
- **En contra:** dependemos de que exista un UEM y de lo que su API exponga
  (huecos declarados, no inventados: p. ej. subir declarations DDM propias no
  existe por API en Jamf y se deja offline); no capturamos el caso "sin UEM".
- **Guardarraíl:** una feature que enrole/empuje/gestione se rechaza en revisión.

## Dónde vive hoy

`lucidfence/core/adapters/*` (solo lectura + acción vía UEM), `actions.py`,
`soar.py`; principio en [CONSTITUTION.md §II](../architecture/CONSTITUTION.md) y
[SPEC.md §1](../architecture/SPEC.md); posicionamiento en
`docs/internal/product/BACKLOG.md`.
