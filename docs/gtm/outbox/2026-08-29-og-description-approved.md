---
platform: meta (og:description de static/index.html)
status: draft (owner gate — no agent publish)
positioning_directive: "comparación > marca desnuda" (gate #317 cerrado, t_190e48e9)
cto_cosign: APROBADO por Product en standup 2026-08-29 (t_f94d1aed) — #110-safe, 0 BLOCK
copy_is_canonical: true (copy literal aprobado en el body, úsalo tal cual)
repo: https://github.com/adrimg3196/lucidfence
---

# og:description — LucidFence (copy aprobado, comparación > marca desnuda)

> Copy literal APROBADO por Product (standup 2026-08-29, t_f94d1aed). Es #110-safe
> (0 BLOCK en linter) y encarna el posicionamiento firmado "comparación > marca desnuda":
> menciona a los competidores EN CONTEXTO de comparación ("vs Kandji, Intune & Jamf"),
> no como marca desnuda. Es usable tal cual en `static/index.html`.

## Copy aprobado (og:description meta)

> LucidFence vs Kandji, Intune & Jamf — a free, local-first geofencing and
> explainable-risk layer that runs on top of the UEM you already use. Not another
> UEM. No telemetry, no accounts. Apache-2.0.

## Por qué este copy (anclaje a la decisión)

- **"vs Kandji, Intune & Jamf"** → comparación explícita, no SEO de marca desnuda.
  Lucid Motors domina "Lucid" (NASDAQ); renunciamos a marca desnuda a corto plazo (#317/#326).
- **"runs on top of the UEM you already use" / "Not another UEM"** → el ángulo de
  producto firmado: LucidFence es la capa que le falta a tu UEM, no un reemplazo.
- **"free, local-first … No telemetry, no accounts. Apache-2.0"** → posicionamiento
  100% free OSS, sin edición de pago ni capas cerradas (RED LINE #110 respetada).

## Guardas

- NO afirma integración con NanoMDM/MicroMDM (solo Fleet adapter real en origin/main).
- NO implica score siempre disponible (puede ser "desconocido (sin señal)").
- NO afirma "Enterprise on-prem cerrada" / open-core / pricing.

## Linter gate

```bash
python3.11 scripts/gtm_claim_linter.py docs/gtm/outbox/2026-08-29-og-description-approved.md --technical
→ esperado: 0 BLOCK
```
