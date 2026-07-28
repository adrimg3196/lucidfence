# LucidFence + DigitalPlat FreeDomain — Whitelabel y Email Soberano

Este documento explica cómo usar **DigitalPlat FreeDomain** (https://github.com/DigitalPlatDev/FreeDomain)
para dar a cada tenant de LucidFence un **dominio propio gratuito** y cerrar el
stack de comunicaciones 100% soberano del SaaS, combinado con **Atomic Mail
Agentic** (el canal de email ya integrado).

> FreeDomain es un servicio gestionado por dashboard (sin API de código en su
> repo). Esta integración es **configurativa**, no de dependencia de código:
> LucidFence genera los registros DNS y valida la delegación, pero el registro
> del dominio se hace en `dash.domain.digitalplat.org`.

## Por qué importa

| Capa | Sin FreeDomain | Con FreeDomain |
|------|----------------|---------------|
| Email saliente | `tenant@atomicmail.ai` | `alertas@acme-fence.dpdns.org` |
| Deliverability | depende de la reputación de atomicmail.ai | SPF/DKIM alineados a TU dominio |
| Branding | subdominio genérico | dominio de la marca del cliente |
| Dashboard | `127.0.0.1:8765` / IP | `acme-fence.dpdns.org` |
| Coste | 0 € | 0 € |

## Qué ofrece FreeDomain

- Dominios gratuitos: `.dpdns.org`, `.us.kg`, `.xx.kg`, `.qzz.io`, `.qd.je`
- **1 dominio por cuenta** (subdominios ilimitados vía tu DNS)
- Compatible con **Cloudflare** (DNS, CDN, SSL) y cualquier DNS estándar
- Delegas NS al panel de DigitalPlat o a tu propio DNS

## Flujo paso a paso

### 1. Registrar el dominio (dashboard)
1. Ve a https://dash.domain.digitalplat.org/ y crea una cuenta.
2. Registra tu dominio, p.ej. `acme-fence.dpdns.org`.
3. En el panel de DigitalPlat, delega el dominio a **Cloudflare** (recomendado)
   cambiando los NS, o usa los NS de DigitalPlat:
   - `ns1.digitalplat.org`
   - `ns2.digitalplat.org`

### 2. Generar los registros DNS (LucidFence)
En la UI de LucidFence (`/whitelabel`) o vía API:
```
POST /api/whitelabel/setup
{ "domain": "acme-fence.dpdns.org", "dkim_selector": "atomicmail",
  "dashboard_target": "lucidfence.example.com", "receive_mail": true }
```
LucidFence devuelve los registros exactos a crear en tu DNS:

| Tipo | Nombre | Valor | Uso |
|------|--------|-------|-----|
| TXT | `acme-fence.dpdns.org` | `v=spf1 include:_spf.atomicmail.ai ~all` | SPF |
| CNAME | `atomicmail._domainkey.acme-fence.dpdns.org` | `atomicmail._domainkey.atomicmail.ai` | DKIM |
| TXT | `_dmarc.acme-fence.dpdns.org` | `v=DMARC1; p=quarantine; …` | DMARC |
| MX | `acme-fence.dpdns.org` | `10 in1.atomicmail.ai` | Recibir respuestas (opcional) |
| CNAME | `acme-fence.dpdns.org` | `lucidfence.example.com` | Dashboard bajo tu dominio |

> El valor DKIM exacto (la clave pública) se copia desde el dashboard de
> Atomic Mail de tu tenant; LucidFence plantilla el *shape* del CNAME que lo
> resuelve.

### 3. Validar la delegación (LucidFence)
```
POST /api/whitelabel/validate
{ "domain": "acme-fence.dpdns.org" }
```
LucidFence consulta DNS-over-HTTPS (sin dependencias externas) y reporta:
```json
{ "domain": "acme-fence.dpdns.org", "ns_delegated": true,
  "spf": true, "dkim": true, "dmarc": true, "overall": "ok" }
```

### 4. Usar el dominio como remitente
Una vez `overall: ok`, LucidFence (vía Atomic Mail) envía las alertas,
incidentes y digest desde `alertas@acme-fence.dpdns.org` con SPF/DKIM válidos,
mejorando la entrega a `soc@tuempresa.com` y evitando la carpeta de spam.

## APIs de LucidFence

| Endpoint | Método | Cuerpo | Descripción |
|----------|--------|--------|-------------|
| `/api/whitelabel/setup` | POST | `{domain, dkim_selector?, dashboard_target?, receive_mail?}` | Guarda el dominio del tenant y devuelve los registros DNS sugeridos |
| `/api/whitelabel/status` | GET | — | Dominio configurado + máscara + último reporte de validación |
| `/api/whitelabel/validate` | POST | `{domain?}` | Valida delegación/SPF/DKIM/DMARC vía DNS-over-HTTPS |

La configuración se persiste en `integration.json` del tenant (campo
`whitelabel`), aislada por organización. El dominio se enmascara en `/status`
para no filtrar información sensible.

## Límites y advertencias

- **1 dominio gratuito por cuenta DigitalPlat.** Para N tenants necesitas N
  cuentas, o usar subdominios (`cliente1.tudominio.dpdns.org`) bajo un dominio
  ya delegado a tu DNS.
- FreeDomain **no tiene API de registro**; el alta es manual en el dashboard.
- El repo de FreeDomain es AGPL-3.0 y solo aporta documentación + un whois
  server; **no se vendoriza nada de él** en LucidFence.
- Aviso de seguridad oficial de DigitalPlat: sus canales de Telegram fueron
  comprometidos; no confíes en mensajes de Telegram sobre el servicio.

## Seguridad

- LucidFence **solo lee** DNS público (DoH a `dns.google`); nunca escribe en
  ningún proveedor.
- Todas las validaciones son best-effort y time-boxed; un fallo de red nunca
  rompe el ciclo del engine.
- El secreto DKIM vive solo en Atomic Mail; LucidFence solo referencia el
  selector vía CNAME.
