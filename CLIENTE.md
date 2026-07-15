# LucidFence para clientes — Instalación 100% local y soberana

LucidFence es geofencing UEM/MDM local-first: se instala en tu propia infra
(portátil, servidor de la empresa o VM) y mantiene tenants y datos en tu máquina.
La Demo funciona sin nube obligatoria; UEM live, IA y email son conectores opcionales
que dependen de la configuración y disponibilidad de sus proveedores. $0, sin suscripción de LucidFence.

## Opción A — App de escritorio macOS (recomendada para usuarios)

1. En un Mac Apple Silicon (M1 o posterior) con macOS 14 o posterior, descarga `LucidFence-1.2.0-arm64.dmg` desde [LucidFence Desktop Preview 1](https://github.com/adrimg3196/lucidfence/releases/tag/v1.2.0-desktop-preview.1).
2. Abre el DMG y arrastra LucidFence a Applications.
3. Primera apertura: clic derecho → **Abrir**.

La app incluye backend, Python y dependencias; no requiere Terminal ni Homebrew. Abre el Command Center en una ventana nativa y mantiene los datos en `~/Library/Application Support/LucidFence`.

## Opción B — Homebrew (macOS/Linux técnico)

```bash
brew install adrimg3196/lucidfence/lucidfence
lucidfence
```

## Opción C — Con Docker (servidores)

```bash
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence
docker compose up -d
```

LucidFence queda en `http://localhost:8765`, 24/7, con su propia base de datos
en `./data`.

Para exponerlo a la red de la empresa: poner delante un reverse proxy
(nginx/Caddy) con TLS. Ejemplo mínimo con Caddy:

```
lucidfence.empresa.com {
  reverse_proxy localhost:8765
}
```

## Opción D — Sin Docker (Python directo)

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
- **IA opcional**: proveedor OpenAI-compatible configurado por el usuario; puede apuntar a un modelo local como MoA o a una API externa.
- **Email soberano** vía Atomic Mail Agentic (opcional, sin SMTP propio).

## Siempre-on

- Con Docker: `restart: unless-stopped` ya está configurado.
- Sin Docker: `nohup python3 saas_server.py &` o crear un servicio systemd.

## Demo en vivo (vitrina del proveedor)

Antes de instalar, puedes ver el producto funcionando en:
https://adrimg3196.github.io/lucidfence/cloud.html

Es una vitrina generada por el mismo engine, alimentada cada 15 min por GitHub
Actions (gratis). La instalación local es el producto real, soberano y tuyo.
