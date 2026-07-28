# LucidFence — SaaS 100% gratis y autónomo

Stack de infraestructura. Cada capa cuelga de un servicio gratis; el
agente maneja todo por CLI (sin consola web de pago).

| Capa | Servicio gratis | Cómo lo maneja el agente |
|------|----------------|-------------------------------|
| Landing + dashboard web | Local + Fly.io static | `flyctl` (deploy) / `start_local.sh` |
| Hosting always-on (VM) | Fly.io free tier (shared-cpu, min 1 siempre on) | `flyctl deploy` |
| Email saliente | Atomic Mail Agentic (`@atomicmail.ai`, JMAP + PoW, sin tarjeta) | vendored en `core/atomicmail/`, facade `core/atomicmail_client.py` |
| Dominio / branding | DigitalPlat FreeDomain (`.dpdns.org` etc.) | `core/freedomain.py` + UI `/static/whitelabel.html` |
| IA (MoA) | Motor local Mixture-of-Agents (free tiers) | `/Users/adri/moa/server.py` en `127.0.0.1:8085`, consumido por `core/ai.py` |
| Geocoding | Nominatim / OpenStreetMap (sin API key) | `core/geocode.py` + cache SQLite |
| Storage de reportes | Volumen local (Fly) + Cloudflare R2 free (10GB, opcional) | `core/storage.py` |
| DB + auth multi-tenant | SQLite local + auth propia | `core/state_store.py`, `saas_server.py` |
| DNS + CDN + SSL | Cloudflare Free | `wrangler` (opcional, para apuntar el dominio FreeDomain) |

Coste total: **$0**. Sin tarjeta de pago en ningún eslabón.

## Ejecutar en local (macOS / Linux)

```bash
cd /Users/adri/geofence-uem
python3.11 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
./start_local.sh
# landing:   http://127.0.0.1:8765/
# dashboard: http://127.0.0.1:8765/app
```
`start_local.sh` arranca MoA (IA, :8085) y LucidFence SaaS (engine + dashboard, :8765) juntos.

## Desplegar always-on (Fly.io free)

```bash
# 1) Tu cuenta, fuera de sesión del agente:
flyctl auth login
flyctl auth whoami

# 2) El agente (o tú) ejecuta:
./deploy_fly.sh
#   → flyctl launch --no-deploy
#   → flyctl deploy   (Dockerfile: MoA + SaaS + SQLite, always-on)
#   → flyctl status
```
La app queda en `https://lucidfence.fly.dev/` 24/7 en free tier.
Para IA real (no solo dry-run) monta las claves de free tiers:
```bash
flyctl secrets set MOA_OPENROUTER_KEY=xxx   # opcional
```

## Whitelabel por tenant (FreeDomain)

1. Registra `tudominio.dpdns.org` en https://dash.domain.digitalplat.org/
2. Abre `/static/whitelabel.html` en el dashboard.
3. Pega el dominio → "Sugerir registros DNS" → crea los TXT/CNAME en
   Cloudflare/DigitalPlat → "Validar DNS" (comprobación live vía DoH).
4. LucidFence envía alertas/incidentes/digest desde `alertas@tudominio.dpdns.org`.

## Geocercas por dirección

`add_fence` acepta `address` (p.ej. "Plaza Mayor, Madrid"); el engine
lo resuelve a coords vía Nominatim y cachea el resultado en SQLite.
Sin red → fallback a coords manuales.

## Secretos

Ningún secreto se commitea. Las API keys de MoA viven en `/app/moa/.env`
(en Fly, montadas con `flyctl secrets set`); las credenciales de Atomic Mail
en `data/tenants/<org>/atomicmail/` (chmod 600, gitignored). `core/storage.py`
lee R2 solo de env vars y nunca las imprime.
