# LucidFence

> Geofencing y riesgo explicable para flotas UEM/MDM. Open source, gratuito y 100% web.

[![Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![PWA](https://img.shields.io/badge/app-PWA-5e6ad5.svg)](static/web.html)
[![Browser-first](https://img.shields.io/badge/data-IndexedDB-4cc38a.svg)](docs/AUTONOMOUS_GEOFENCING_COMPANY.md)

LucidFence convierte ubicaciones y postura de dispositivos en geovallas, rutas, riesgo explicable y acciones UEM. Su modo principal funciona directamente en el navegador: no exige instalación, cuenta de LucidFence, nube propia ni suscripción.

## Consumir LucidFence Web — infraestructura del usuario

LucidFence no necesita ni presupone un hosting operado por el autor. Cada organización genera el bundle y lo publica en su propia cuenta, dominio, nube o intranet:

```bash
python3 scripts/build_web_bundle.py
```

Artefactos:

```text
dist/lucidfence-web/       # directorio estático
dist/lucidfence-web.zip    # paquete redistribuible
dist/lucidfence-web/SHA256SUMS
```

Consulta [`deploy/web/SELF_HOST.md`](deploy/web/SELF_HOST.md) para desplegarlo en GitHub Pages, Cloudflare Pages, Nginx, Caddy, S3 o un contenedor del cliente.

- Sin signup, tarjeta, Python, Docker o Homebrew.
- Objetivos, flota, geovallas y ciclos se ejecutan en JavaScript/Web Worker.
- El workspace se guarda en IndexedDB y puede exportarse/importarse.
- El Service Worker permite reutilizarla offline después de la primera carga.
- Las simulaciones no tienen efectos externos y no usan APIs de pago.
- Los secretos UEM se rechazan en las importaciones y nunca se guardan en GitHub Pages.

La app de escritorio, Homebrew y el backend Python siguen disponibles como opciones avanzadas para conectores live y despliegues soberanos; ya no son obligatorios para probar ni operar el modo de simulación.

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
- Fleet Intelligence descriptiva: recencia, continuidad, interrupciones, cobertura GPS,
  tendencia de conformidad y transiciones de geovalla con fórmula explicable.
- Alertas, export CSV/HTML y digest.
- RBAC local y aislamiento por organización.
- Compañía autónoma de geofencing gobernada: objetivos medibles, squads
  especializados, evidencia, simulación, policy gates y handoff humano sin
  ejecución implícita de comandos UEM. Ver
  [`docs/AUTONOMOUS_GEOFENCING_COMPANY.md`](docs/AUTONOMOUS_GEOFENCING_COMPANY.md).
- Dashboard local sin CDN, telemetría ni frontend cloud.
- Adapters MDM (interfaz `MDMAdapter` congelada): `simulation` (demo local),
  `applivery` (live), `intune` (live vía Microsoft Graph, Bounty #1) y
  `jamf` (live vía Jamf Pro API, Bounty #2). Ver `core/adapters/ADAPTER.md`.
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
├── analysis/               # notebooks reproducibles con outputs verificados
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

## Operación y monitoreo always-on

```bash
# Arrancar servicio en segundo plano managed
python3 scripts/health_monitor.py

# Salida JSON con estado del check y, en caso de fallo, apertura/cierre
# automática de issue de infraestructura en GitHub con severidad y alertas.
```

Documentación operativa:

- [`docs/operations/health-monitor.md`](docs/operations/health-monitor.md)
- `scripts/health_monitor.py`

## Diseño

- Tema dark por defecto, light opcional.
- Tokens CSS en variables `:root` para colores, radios, sombras y fonts.
- Densidad compacta y jerarquía clara; los KPIs y chips priorizan legibilidad.
- Contraste AA para texto normal; UI components usan bordes suaves y paneles diferenciados.
- Navegación consistente: sidebar, topbar y vistas principales con mismo vocabulario.
- Comportamiento responsivo en `1100px`, `700px` y `430px`.

Referencia canónica: `static/dashboard.html` y `static/cloud.html`.

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

## Adapter Hall of Fame

Programa de adapters de la comunidad (issue #3). El producto es agnóstico al
MDM vía la interfaz `MDMAdapter` (`core/adapters/base.py`). Quien entregue el
primer PR **verificado** de un MDM entra al Hall of Fame y se vuelve
*Adapter Maintainer*.

| Adapter | Estado | Contribuidor | Notas |
|---------|--------|--------------|-------|
| `intune` (Microsoft Graph live) | ✅ live (Bounty #1) | [@jdjioe5-cpu](https://github.com/jdjioe5-cpu) | PR #13 mergeado — respeta el contrato congelado, tests 7/7, sin secretos |
| `jamf` (Jamf Pro API live) | ✅ live (Bounty #2) | mantenedor | reimplementado siguiendo el patrón #13 — tests 7/7 |
| `applivery` | ✅ live | mantenedor | conector principal |
| `simulation` | ✅ mock | mantenedor | demo 100% local |

**Siguientes MDMs pedidos:** SOTI, Workspace ONE, Mosyle, Kandji, Fleet.

**Política anti-spam:** los PRs/comments que incluyan direcciones de wallet
(Solana, BTC, USDT, ETH, XMR…), promoción de repos externos o pago de bounty
en cripto serán cerrados sin merge. El código debe respetar `base.py` (no
cambiar la interfaz), usar solo placeholders en `.env.example` y pasar la suite
sin credenciales reales. Ver `core/adapters/ADAPTER.md`.
