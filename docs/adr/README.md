# Architecture Decision Records (ADR)

Registro de las decisiones de arquitectura **ya tomadas** en LucidFence. Cada
ADR captura una decisión estructural real, el contexto que la forzó y las
consecuencias que arrastra, para que un ingeniero nuevo no re-litigue "¿por qué
no Flask?" cada seis meses.

Estos ADRs **documentan lo existente**, no deciden nada nuevo. La autoridad
normativa vive en la [Constitución](../architecture/CONSTITUTION.md) (suprema) y
en la [SPEC as-built](../architecture/SPEC.md). Un ADR describe *cómo se llegó*
a lo que la Constitución declara; ante conflicto, gana la Constitución.

## Formato

Cada ADR es de **una página** y sigue el formato estándar:

- **Estado** — `Accepted` / `Superseded` / `Deprecated`, con fecha.
- **Contexto** — la fuerza o restricción que obligó a decidir.
- **Decisión** — qué se decidió, en una frase accionable.
- **Consecuencias** — lo que ganamos y lo que aceptamos a cambio.
- **Dónde vive hoy** — el fichero o gate que materializa la decisión (trazabilidad).

Numeración `ADR-NNNN`, monotónica, sin reutilizar números. Una decisión que
revierta a otra no la borra: crea un ADR nuevo y marca el viejo `Superseded by
ADR-NNNN`.

## Índice

| ADR | Decisión | Estado |
|---|---|---|
| [ADR-0001](ADR-0001-http-server-stdlib.md) | Servidor HTTP stdlib, sin Flask/FastAPI | Accepted |
| [ADR-0002](ADR-0002-runner-tests-propio.md) | Runner de tests propio, sin pytest/fixtures | Accepted |
| [ADR-0003](ADR-0003-almacenamiento-json-en-disco.md) | Estado en JSON en disco, sin base de datos | Accepted |
| [ADR-0004](ADR-0004-adapters-base-congelado.md) | `adapters/base.py` como contrato congelado | Accepted |
| [ADR-0005](ADR-0005-frontera-runtime-admin.md) | El runtime lo decide el admin: observe-default, doble llave del wipe | Accepted |
| [ADR-0006](ADR-0006-local-first-cero-telemetria.md) | Local-first: cero telemetría, cero exfiltración de ubicación | Accepted |
| [ADR-0007](ADR-0007-gratis-open-source.md) | Gratis y open-source (Apache-2.0), sin pricing | Accepted |
| [ADR-0008](ADR-0008-complemento-no-uem.md) | Complemento del UEM, nunca un UEM | Accepted |
| [ADR-0009](ADR-0009-validacion-runtime-gate.md) | Validación runtime como gate de merge, no solo unit tests | Accepted |
| [ADR-0010](ADR-0010-auto-merge-agentes-deciden.md) | Auto-merge total en verde: los agentes deciden el desarrollo | Accepted |
