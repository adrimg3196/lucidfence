# Alojar LucidFence Web en infraestructura del usuario

Este directorio es una aplicación estática autocontenida. No llama a servidores de LucidFence, no requiere backend y no contiene credenciales.

## Opción 1 — servidor estático existente

Publica el contenido completo del directorio conservando las rutas. El punto de entrada es `web.html#company`.

Requisitos del servidor:

- HTTPS en producción (Service Worker e IndexedDB);
- servir `.js` como `text/javascript`;
- servir `.webmanifest` como `application/manifest+json`;
- no reescribir archivos JavaScript inexistentes a HTML;
- permitir `worker-src 'self'`;
- no inyectar scripts de analítica.

## Opción 2 — GitHub Pages del cliente

1. Crea un repositorio en la organización del cliente.
2. Copia este bundle en la raíz.
3. Copia `deploy/github-pages.yml` a `.github/workflows/pages.yml`.
4. En Settings → Pages selecciona **GitHub Actions**.
5. Haz push a `main`.

La cuenta, dominio, logs y disponibilidad pertenecen al cliente.

## Opción 3 — Cloudflare Pages del cliente

Desde este directorio:

```bash
npx wrangler pages deploy . --project-name lucidfence-web
```

El proyecto se crea en la cuenta Cloudflare del cliente. No requiere el gateway UEM para demo/simulación.

## Opción 4 — Nginx o contenedor del cliente

```bash
docker build -f deploy/Dockerfile -t lucidfence-web:local .
docker run --rm -p 8080:8080 lucidfence-web:local
```

O copia los archivos a cualquier Nginx/Caddy/S3 compatible con hosting estático. Los ejemplos están en `deploy/`.

## UEM live

Las API keys no deben entrar en este bundle. Para datos live, el cliente despliega `edge/uem-gateway` en su propia cuenta y configura `ALLOWED_ORIGIN`, `UPSTREAM_BASE_URL` y el secreto `UPSTREAM_TOKEN`. El gateway es read-only.

## Actualizaciones y salida

No hay actualización forzada. El cliente puede fijar una versión, verificar `SHA256SUMS`, mantener un fork y actualizar cuando decida. Exportar el workspace desde la UI evita lock-in del almacenamiento del navegador.
