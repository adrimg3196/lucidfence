# LucidFence UEM Gateway — opcional

Gateway read-only para conectar la PWA pública con un UEM que requiera secreto y/o no permita CORS.

## Propiedades

- Compatible con Cloudflare Workers Free Tier.
- Solo `GET /health`, `GET /v1/fleet` y `GET /v1/cves/enrich`.
- CORS limitado a `ALLOWED_ORIGIN`; nunca `*`.
- Máximo 10.000 dispositivos por respuesta.
- Normaliza únicamente campos operativos; no devuelve tokens ni payloads completos.
- No implementa wipe, lock, delete ni otra mutación UEM. `/v1/soar/incident` (POST) no está implementado a propósito: abriría una mutación saliente hacia un SOAR de terceros sin vendor definido — contradice el diseño read-only de este Worker. Ver tarea t_f952d997.

## Despliegue

```bash
cd apps/uem-gateway
npx wrangler secret put UPSTREAM_TOKEN
npx wrangler secret put NVD_API_KEY  # opcional: sube el limite de NVD de 5 a 50 req/30s
npx wrangler deploy
```

Configura `UPSTREAM_BASE_URL` como variable de Worker o en un `wrangler.toml` privado. No escribas credenciales en el repositorio ni en la PWA.

`/v1/cves/enrich` consulta la API pública de NVD (services.nvd.nist.gov) por `keywordSearch` para un conjunto fijo de plataformas (ios/ipados/macos/android/windows/chromeos) — mismo patrón best-effort que `lucidfence/core/cve_feed_nvd.py`, no CPE exacto. Sin `NVD_API_KEY` puede volver vacío por rate-limit (5 req/30s compartido); el wizard ya tolera respuestas parciales o vacías.

El free tier de Cloudflare tiene cuotas y condiciones que pueden cambiar. El modo demo de LucidFence Web no depende del Worker y permanece operativo sin él.
