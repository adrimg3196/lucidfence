# LucidFence — Modelo de sostenibilidad: gratis + donaciones

*Especificación canónica (2026-07-27). Sustituye al modelo open-core anterior
(freemium → Pro → Enterprise), descartado por decisión del propietario.*

## Decisión

**LucidFence es gratis para siempre.** Todas las funciones, para todo el mundo,
sin límites artificiales, sin planes de pago y sin pasarela de cobro.

La única vía de ingresos son las **donaciones voluntarias**:

- `.github/FUNDING.yml` → botón "Sponsor" en GitHub (`github: adrimg3196`).
- El plan único vive en `saas/tenant.py` → `FREE_PLAN` (etiqueta, precio 0 €,
  enlace de donaciones). No hay catálogo de planes ni enforcement de límites.

## Implicaciones operativas

- **Coste 0 estricto:** solo free tiers de Vercel, Supabase y GitHub.
  Prohibido dar de alta servicios de pago.
- No existe `/api/plan` ni `/api/plan/upgrade`; `/api/org` devuelve `FREE_PLAN`
  como información, no como restricción.
- Los tenants legacy con plan `pro`/`enterprise` se migran a `free`
  automáticamente al cargar (`TenantStore._load`).

## Qué NO hacer

- No añadir paywalls, límites por plan ni telemetría de upsell.
- No reintroducir catálogos de precios en docs o UI: si un texto de marketing
  menciona planes de pago, es legacy y debe corregirse.
