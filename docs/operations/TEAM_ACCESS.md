# Acceso en equipo: reverse proxy + SSO OIDC

Por diseño LucidFence binda a `127.0.0.1`: en una máquina personal eso es
una feature. Para que lo use el equipo de IT sin regalar el dashboard a la
red, el patrón soportado es **reverse proxy con TLS delante + OIDC dentro**.

## 1. Reverse proxy

**Caddy** (TLS automático, config mínima):

```
lucidfence.interna.tu-org.com {
    reverse_proxy 127.0.0.1:8765
}
```

**nginx:**

```nginx
server {
    listen 443 ssl;
    server_name lucidfence.interna.tu-org.com;
    ssl_certificate     /etc/ssl/private/lucidfence.crt;
    ssl_certificate_key /etc/ssl/private/lucidfence.key;
    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

El server sigue escuchando solo en loopback: el proxy es el único camino de
entrada y quien termina TLS.

## 2. SSO OIDC (Google Workspace / Entra ID / cualquier IdP)

El SSO se configura **solo por entorno del despliegue** (nunca desde la UI
ni desde requests — decisión de seguridad deliberada). Google como caso
rápido:

```bash
export LUCIDFENCE_GOOGLE_CLIENT_ID="....apps.googleusercontent.com"
export LUCIDFENCE_GOOGLE_CLIENT_SECRET="..."
export LUCIDFENCE_GOOGLE_REDIRECT_URI="https://lucidfence.interna.tu-org.com/api/auth/sso/google/callback"
export LUCIDFENCE_GOOGLE_ALLOWED_DOMAINS="tu-org.com"   # corta cuentas ajenas
```

Cualquier otro IdP (Entra ID, Okta, Keycloak…) entra por JSON:

```bash
export LUCIDFENCE_OIDC_PROVIDERS_JSON='[{
  "name": "entra", "label": "Microsoft Entra", "enabled": true,
  "issuer": "https://login.microsoftonline.com/<tenant>/v2.0",
  "client_id": "...", "client_secret": "...",
  "redirect_uri": "https://lucidfence.interna.tu-org.com/api/auth/sso/entra/callback"
}]'
```

Notas del implementación que te protegen:

- El id_token se valida (firma, claims, nonce) y **se descarta**: la
  identidad durable es solo `(issuer, sub)`.
- `allowed_domains` restringe quién puede entrar aunque el IdP autentique.
- Dependencias de OIDC (`PyJWT`/`cryptography`) son opcionales: sin ellas el
  producto funciona y el SSO simplemente no se ofrece.

## 3. Roles dentro del producto

Los comandos a dispositivos pasan por permisos por rol de org
(`device:action`): un usuario sin ese permiso puede mirar el dashboard pero
no ejecutar acciones, y cada comando manual queda en el action log con el
email del operador (`operator`). Combínalo con el rollout de
[ENFORCEMENT.md](ENFORCEMENT.md): rol + fase de enforcement + credencial
UEM de mínimo privilegio son tres líneas de defensa independientes.

## Anti-patrones

- Exponer `0.0.0.0:8765` "un momento" — no hay TLS ni razón para ello.
- Compartir una cuenta de operador — pierdes la atribución del action log.
- Configurar OIDC con secrets en el YAML del tenant — va por entorno del
  despliegue, con permisos 600, como el resto de credenciales.
