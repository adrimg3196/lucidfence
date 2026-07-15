# LucidFence

> Geofencing y riesgo explicable para flotas UEM/MDM. Open source, gratuito y local-first.

[![Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![macOS + Linux](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-blue.svg)](bin/lucidfence)
[![Local-first](https://img.shields.io/badge/data-local--first-5e6ad5.svg)](docs/LOCAL_APP.md)

LucidFence convierte ubicaciones y postura de dispositivos en geovallas, rutas, riesgo explicable y acciones UEM. Se ejecuta en tu Mac o servidor Linux; no exige una cuenta de LucidFence, una nube propia ni una suscripción.

## Descargar la app de escritorio — Preview comunitaria

Para un Mac con Apple Silicon (M1 o posterior) y macOS 14 o posterior:

1. Abre **[LucidFence Desktop Preview 1](https://github.com/adrimg3196/lucidfence/releases/tag/v1.2.0-desktop-preview.1)**.
2. Descarga `LucidFence-1.2.0-arm64.dmg`.
3. Abre el DMG y arrastra **LucidFence** a **Applications**.
4. En el primer inicio, haz clic derecho sobre LucidFence → **Abrir**. Después se abre normalmente desde Launchpad o Finder.

La app es autónoma: incluye su backend y abre LucidFence en una ventana nativa de macOS. No requiere Terminal, Homebrew, Python, cuenta cloud ni suscripción. Sus datos permanecen en `~/Library/Application Support/LucidFence`.

> La build comunitaria actual usa firma ad-hoc. El clic derecho del primer inicio es necesario hasta que el proyecto disponga de certificado Apple Developer ID y notarización.

El primer arranque carga una flota de demostración local. No necesitas credenciales para evaluar las funciones incluidas en Demo; UEM live, IA y email son conectores opcionales y requieren su propia configuración.

## Homebrew y Linux (alternativa técnica)

Para automatización, servidores o usuarios de CLI:

```bash
brew tap adrimg3196/lucidfence
brew install lucidfence
lucidfence
```

`lucidfence` inicia el servicio local en `http://127.0.0.1:8765` y abre el navegador.

## CLI

```bash
lucidfence                 # iniciar y abrir la interfaz
lucidfence start           # iniciar en segundo plano
lucidfence open            # abrir; inicia si hace falta
lucidfence status          # salud, PID, datos y log
lucidfence restart         # reiniciar limpiamente
lucidfence stop            # detener solo la instancia gestionada
lucidfence serve           # primer plano; ideal para servidores/systemd
lucidfence doctor          # diagnóstico de instalación
lucidfence mcp             # MCP local read-only por stdio
lucidfence --version
```

Puerto personalizado:

```bash
lucidfence start --port 9000
```

Servidor Linux accesible en la red — hazlo solo detrás de tu firewall/reverse proxy:

```bash
lucidfence serve --host 0.0.0.0 --port 8765
```

## Dónde están los datos

LucidFence nunca escribe datos mutables dentro del repositorio ni del Cellar de Homebrew:

- macOS: `~/Library/Application Support/LucidFence`
- Linux: `${XDG_STATE_HOME:-~/.local/state}/lucidfence`
- Override: `LUCIDFENCE_DATA_DIR=/ruta/propia`

Ahí viven usuarios locales, sesiones, tenants, configuración, eventos, trails, logs y PID. Los permisos del directorio se restringen al usuario.

## Qué incluye

- Geovallas circulares y poligonales.
- Rutas y detección de desvíos.
- Inventario y postura de dispositivos.
- Risk Engine 0–100 con `reasons`, `provenance` y evidence gate.
- Incidentes, lifecycle y auditoría.
- Workflows y acciones UEM con cooldown para acciones destructivas.
- CVE + EPSS y playbooks SOAR declarativos.
- Alertas, export CSV/HTML y digest.
- RBAC local y aislamiento por organización.
- Dashboard local sin CDN, telemetría ni frontend cloud.
- Adapters: simulación, Applivery live y bases extensibles para Intune/Jamf.
- IA opcional BYO API/modelo (OpenAI, Ollama, LM Studio, Nous Portal o compatible).
- Gateway local OpenAI-compatible y MCP read-only incluidos.

## Arquitectura

```text
lucidfence/
├── bin/lucidfence          # lifecycle portable macOS/Linux
├── saas_server.py          # servidor HTTP local
├── core/                   # geofencing, riesgo, CVE, SOAR, adapters
├── mcp/lucidfence_mcp.py   # MCP local read-only
├── saas/                   # auth local, RBAC y aislamiento
├── static/                 # interfaz local, assets vendorizados
├── data/                   # seeds públicos read-only del paquete
├── macos/                   # app Swift/WebKit + builder PyInstaller/DMG
├── Formula/lucidfence.rb   # Homebrew
└── tests/                  # suite stdlib
```

La capa histórica se sigue llamando `saas/` internamente por compatibilidad, pero no implica un servicio cloud: es la capa local de usuarios, organizaciones y RBAC.

## Integrar un MDM

Desde la interfaz, abre **Ajustes** y configura el adapter y sus credenciales. Los secretos se almacenan en el directorio local de la organización, nunca en el frontend ni en Git.

Para contribuir un adapter, implementa `MDMAdapter` siguiendo [`core/adapters/ADAPTER.md`](core/adapters/ADAPTER.md) y añade pruebas offline.

## AI opcional y MCP

La aplicación funciona sin modelo. En **Ajustes → Proveedor AI opcional** puedes conectar cualquier endpoint OpenAI-compatible y probarlo antes de guardar. La clave queda en el directorio tenant-local con modo `0600`.

- Gateway: `POST http://127.0.0.1:8765/v1/chat/completions`
- MCP: `lucidfence mcp`
- Guía completa: [`docs/AI_AND_MCP.md`](docs/AI_AND_MCP.md)

## Desarrollo

```bash
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence
python3 -m pip install -r requirements.txt
python3 tests/run_tests.py
python3 bin/lucidfence start --no-open
```

La suite debe terminar con un resumen explícito y cero fallos. El proyecto usa Python 3.9+ y evita frameworks web.

## Seguridad y privacidad

- Escucha en `127.0.0.1` por defecto.
- Sin telemetría ni cuenta remota.
- Secretos y sesiones locales con permisos restringidos.
- RBAC capability-based y aislamiento de tenants.
- Path traversal bloqueado en estáticos.
- Acciones UEM validadas contra allowlist y cooldown persistente.
- Un riesgo positivo sin evidencia se marca `verified: false`.

Consulta [`SECURITY.md`](SECURITY.md) si está disponible o abre un security advisory privado en GitHub para reportar una vulnerabilidad.

## Licencia

Todo el producto distribuido en este repositorio se publica bajo **Apache License 2.0**. Uso personal, comercial, modificación y redistribución permitidos conforme a la licencia.
