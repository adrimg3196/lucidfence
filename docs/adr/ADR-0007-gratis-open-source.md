# ADR-0007 — Gratis y open-source (Apache-2.0), sin pricing

**Estado:** Accepted — 2026-08-16 (decisión del propietario; Constitución §III).

## Contexto

Existió una capa de negocio (planes Pro/Enterprise, `/api/plan*`, capability
`org:billing`, vistas de pricing). Añadía superficie, complejidad de RBAC y
código muerto sin alinearse con la misión del proyecto. El propietario decidió
que LucidFence es una herramienta libre para la comunidad UEM, no un SaaS con
tiers.

## Decisión

LucidFence es **100% free open-source bajo Apache-2.0**: sin pricing, sin
edición enterprise, sin funciones de pago. Solo se usan free tiers de terceros;
cualquier coste siempre-on con token nuestro exige aprobación explícita del
propietario. La migración retiró Pro/Enterprise, `/api/plan*`, `org:billing` y
las vistas de billing muertas.

## Consecuencias

- **A favor:** cero complejidad de billing/tiers/paywall; RBAC más simple;
  mensaje de producto sin ambigüedad; adopción sin fricción.
- **En contra:** sin ingresos directos por licencia (sostenibilidad vía
  donaciones/sponsors, p. ej. GitHub Sponsors); toda dependencia con coste
  recurrente es una decisión que hay que aprobar, no un default.
- **Denylist:** wallets/spam prohibidos.

## Dónde vive hoy

`LICENSE` (Apache-2.0); ausencia de rutas `/api/plan*` en `saas_server.py`;
principio en [CONSTITUTION.md §III](../architecture/CONSTITUTION.md) y
[SPEC.md §1](../architecture/SPEC.md).
