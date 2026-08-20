# ADR-0010 — Auto-merge total en verde: los agentes deciden el desarrollo

**Estado:** Accepted — 2026-08-18 (decisión del propietario; Constitución §VI).

## Contexto

El desarrollo de LucidFence lo lleva una flota de loops/agentes que idean,
implementan, prueban, versionan y publican. Un gate humano de revisión en cada
PR sería el cuello de botella que anula esa autonomía. La confianza se pone en el
**gate automatizado** (`scripts/verify.py` + CI), no en un revisor humano: si la
CI está verde, la definición de "hecho" se cumplió.

## Decisión

**Auto-merge total en verde**, release y outreach incluidos: no queda ningún gate
humano en el desarrollo. El raíl es la entrega: push a `claude/**` →
`agent-pr.yml` abre la PR → `agent-automerge.yml` la mergea en verde. La CI es el
veredicto (`VEREDICTO QA: APTO`). Esta autonomía cubre **solo el desarrollo** —
el runtime del producto sigue bajo control del admin (ADR-0005), frontera
inviolable.

## Consecuencias

- **A favor:** velocidad de entrega sin cuello de botella humano; la calidad la
  garantiza un gate reproducible, no la disponibilidad de un revisor; el proceso
  es auditable (todo pasa por PR y CI).
- **En contra:** un gate débil dejaría pasar defectos — por eso el gate es
  estricto (runtime-first, ADR-0009) y la denylist es absoluta; toda la presión
  de calidad recae en `verify.py` y en la CI.
- **Denylist:** PRs de forks/terceros **jamás** se auto-mergean; la denylist
  absoluta aplica ni con gate verde.

## Dónde vive hoy

`.github/workflows/agent-pr.yml`, `.github/workflows/agent-automerge.yml`,
`.github/workflows/ci.yml`, `scripts/verify.py`; principio en
[CONSTITUTION.md §VI y §Flujo de desarrollo](../architecture/CONSTITUTION.md);
detalle en `docs/internal/LOOP.md` §Raíl.
