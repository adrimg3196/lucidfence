# LucidFence para clientes — Instalación 100% local y soberana

LucidFence es geofencing UEM/MDM que **no depende de nadie**: lo instalas en tu
propia infra (portátil, servidor de la empresa, VM) y corre always-on. Tus datos
y tu base de tenants viven en tu máquina. $0, sin suscripciones.

## Opción A — Homebrew (1 comando, recomendado en macOS/Linux con brew)

```bash
brew install adrimg3196/lucidfence/lucidfence
lucidfence serve
```

Abre `http://localhost:8765`. El dashboard entra en demo local automáticamente;
no hay registro en nuestra nube ni tenant remoto.

Si tu Homebrew no resuelve taps de 3 partes:

```bash
brew tap adrimg3196/lucidfence
brew install lucidfence
lucidfence serve
```

## Opción B — Con Docker (recomendado para servidores)

```bash
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence
docker compose up -d
```

LucidFence queda en `http://localhost:8765`, 24/7, con su propia base de datos
en `./data`.

Para exponerlo a la red de la empresa: poner delante un reverse proxy
(nnginx/caddy) con TLS. Ejemplo mínimo con Caddy:

```
lucidfence.empresa.com {
  reverse_proxy localhost:8765
}
```

## Opción C — Sin Docker (Python directo)

```bash
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence
python3 -m pip install -r requirements.txt
python3 saas_server.py
```

O con el installer de un comando:

```bash
curl -fsSL https://raw.githubusercontent.com/adrimg3196/lucidfence/main/install.sh | bash
```

## Qué obtienes

- **Geocercas** por ubicación y por ruta, con evaluación de conformidad.
- **Motor de riesgo** por dispositivo (rooted, SO desactualizado, batería, cifrado).
- **CVE/SOAR**: escaneo de apps de la flota y playbooks de remediación.
- **Multi-tenant** con whitelabel por cliente.
- **IA local (MoA)**: asistente OpenAI-compatible 100% en tu máquina, sin APIs externas.
- **Email soberano** vía Atomic Mail Agentic (opcional, sin SMTP propio).

## Siempre-on

- Con Docker: `restart: unless-stopped` ya está configurado.
- Sin Docker: `nohup python3 saas_server.py &` o crear un servicio systemd.

## Demo en vivo (vitrina del proveedor)

Antes de instalar, puedes ver el producto funcionando en:
https://adrimg3196.github.io/lucidfence/cloud.html

Es una vitrina generada por el mismo engine, alimentada cada 15 min por GitHub
Actions (gratis). La instalación local es el producto real, soberano y tuyo.
