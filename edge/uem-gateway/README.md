# LucidFence UEM Gateway — opcional

Gateway read-only para conectar la PWA pública con un UEM que requiera secreto y/o no permita CORS.

## Propiedades

- Compatible con Cloudflare Workers Free Tier.
- Solo `GET /health` y `GET /v1/fleet`.
- CORS limitado a `ALLOWED_ORIGIN`; nunca `*`.
- Máximo 10.000 dispositivos por respuesta.
- Normaliza únicamente campos operativos; no devuelve tokens ni payloads completos.
- No implementa wipe, lock, delete ni otra mutación UEM.

## Despliegue

```bash
cd edge/uem-gateway
npx wrangler secret put UPSTREAM_TOKEN
npx wrangler deploy
```

Configura `UPSTREAM_BASE_URL` como variable de Worker o en un `wrangler.toml` privado. No escribas credenciales en el repositorio ni en la PWA.

El free tier de Cloudflare tiene cuotas y condiciones que pueden cambiar. El modo demo de LucidFence Web no depende del Worker y permanece operativo sin él.
