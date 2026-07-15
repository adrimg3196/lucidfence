# LucidFence local app + Homebrew — plan TDD

## Objetivo
Convertir el repositorio en una única app local open source para macOS/Linux. El dashboard debe abrirse desde `lucidfence`, persistir fuera del Cellar/repositorio y poder gestionarse con una CLI estable.

## Tareas y pruebas

1. Directorios portables
- Crear `core/app_paths.py`.
- Test: override `LUCIDFENCE_DATA_DIR` gana.
- Test: macOS usa `~/Library/Application Support/LucidFence`.
- Test: Linux respeta `$XDG_STATE_HOME/lucidfence`.

2. Servidor desacoplado del checkout
- `saas_server.py` usa `LUCIDFENCE_DATA_DIR` para usuarios, sesiones y tenants.
- Los seeds siguen siendo read-only desde el paquete.
- `/` sirve el dashboard local; la landing pasa a `/about`.
- Test contractual de rutas y DATA_ROOT.

3. CLI de producto
- Comandos: `start`, `stop`, `restart`, `status`, `open`, `serve`, `doctor`, `--version`.
- `lucidfence` sin argumentos equivale a `start` y abre el navegador.
- PID/log bajo data dir; health check HTTP real; proceso desacoplado.
- Tests: help/version, data-dir y lifecycle contra puerto libre.

4. App macOS
- Launcher delega en `lucidfence start`, sin pkill global ni kill -9.
- Versión del bundle alineada.
- Test shell/plist.

5. Homebrew
- Fórmula instala el contenido desde la raíz extraída, usa data dir de usuario y prueba HTTP 200 + contenido real.
- Dependencias Python vendorizadas como resources o eliminadas del arranque demo.
- Release tarball limpio, ejecutable y hash verificado.

6. QA final
- Suite completa y syntax checks.
- Instalación local simulada desde tarball.
- `lucidfence start` → HTTP 200 y `/api/status` con datos.
- QA visual en navegador y consola sin errores.
- Revisión independiente de código antes de publicar release/tap.
