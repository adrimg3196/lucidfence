# Empezar con LucidFence

> 📖 ¿Prefieres verlo con capturas? **[Manual de uso](manual/MANUAL_DE_USO.md)** — interactivo en `/static/manual.html` de tu instalación.

Guía de arranque para alguien que **usa** LucidFence por primera vez (no para
contribuir al código — eso está en [CONTRIBUTING](../CONTRIBUTING.md)).
LucidFence es geofencing de flota + motor de riesgo, **local-first** y
**open-source (Apache-2.0)**: tu data vive en tu máquina, tú firmas los tokens
de tu UEM, no hay backend propietario. Es **100% gratis**, sin edición de pago
ni telemetría.

## 1. Qué necesitas

- **Python 3.11+ con `venv`** (el instalador crea `.venv` y no modifica el
  Python del sistema). O bien **Docker** si prefieres no tocar Python.
- `git` para clonar el repositorio. `curl` es opcional: si no existe, el
  instalador verifica la salud con Python o desde el propio contenedor.
- Opcional para datos reales: acceso a tu UEM (Applivery, Intune, Jamf, Fleet…)
  con un token de servicio. Sin él, LucidFence arranca en **modo simulación**
  con una flota de demo — suficiente para evaluarlo.
- No necesitas ninguna cuenta, clave de LucidFence, ni conexión a un servicio
  nuestro. No existe tal servicio: BYOI (Bring Your Own Infrastructure).

## 2. Instalar y arrancar

### Opción A — repositorio (macOS o Linux)

```bash
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence

# Usa Docker si está disponible; si no, arranca con Python 3.11+.
# Solo termina con éxito cuando /api/health responde (timeout: 30 s).
./install.sh
# Alternativa explícita con Docker:
# docker compose up -d --build
```

El script espera de forma acotada a que LucidFence responda y falla si el
servicio no arranca. Ni el script ni Docker instalan un comando `lucidfence`
global en el host. Si tienes Python 3.11+, puedes ejecutar el recorrido
autoverificado desde el checkout:

```bash
python3 -m lucidfence.cli quickstart
```

### Opción B — Homebrew (macOS)

```bash
brew install adrimg3196/lucidfence/lucidfence
lucidfence --version
lucidfence
lucidfence doctor
```

Homebrew sí instala el CLI. No instala `LucidFence.app`: el preview de escritorio
para Apple Silicon es una descarga separada, documentada en
[Desktop para macOS](operations/DESKTOP_APP.md).
El tap puede quedar temporalmente por detrás de la release más reciente:
comprueba `lucidfence --version` y contrástala con
[GitHub Releases](https://github.com/adrimg3196/lucidfence/releases) antes de
usar una función nueva.

## 3. Comprobar que funciona

Deberías poder abrir el dashboard y ver una flota (real o de demo):

```bash
# Comprobación manual opcional; el instalador ya hizo este mismo gate.
curl -fsS http://127.0.0.1:8765/api/health
```

- Dashboard: **http://127.0.0.1:8765** (SPA local que habla con `:8765`).
- Si ves la flota de demo, el modo simulación funciona; conecta tu UEM cuando
  quieras datos reales.
- Suite de humo (opcional, honesta): `python3 tests/run_tests.py`.

Un recorrido guiado sin escribir código está en
[demo-walkthrough](demo-walkthrough.md).

## 4. Primer paso real: conectar tu UEM

1. Registra tu proveedor UEM y su segmento de flota siguiendo
   [integrations/MULTI_UEM](integrations/MULTI_UEM.md).
2. Entiende **qué ubicación te da de verdad cada UEM** antes de dimensionar el
   piloto: [integrations/LOCATION_MATRIX](integrations/LOCATION_MATRIX.md). Para
   portátiles/Windows sin GPS, ver
   [geofencing lógico por red](integrations/NETWORK_LOCATION.md).
3. Da acceso a tu equipo con roles (owner/admin/…):
   [operations/RBAC](operations/RBAC.md).

El índice completo de documentación está en [docs/README](README.md).

## 5. Preguntas frecuentes

**¿LucidFence envía mi ubicación o mis dispositivos a algún sitio?**
No. El estado de la flota vive en tu máquina. Lo único que puede salir es un
snapshot JSON de *demo* si tú activas la vitrina pública; nunca datos reales ni
secretos (garantía de diseño — ver [SECURITY](../SECURITY.md)).

**¿Tiene coste, tier de pago o edición enterprise?**
No. Es Apache-2.0, gratis para usar, modificar y distribuir. No hay funciones de
pago ni telemetría.

**¿Puedo probarlo sin un UEM real?**
Sí, el modo simulación trae una flota de demo. Conecta tu UEM cuando quieras
datos reales.

**¿Necesito una base de datos o un servicio en la nube?**
No. El estado se persiste en ficheros locales; el server HTTP es propio (stdlib).

**¿Mi UEM no está soportado?**
Cada adaptador es un plugin del contrato `MDMAdapter`. Puedes añadir el tuyo
siguiendo [la guía de nuevos adaptadores](contributing/new-adapter-guide.md), o
abrir una petición (ver abajo).

## 6. Reportar un bug o un problema de seguridad

- **Bug o comportamiento raro** → abre un issue en GitHub con la plantilla
  *Reporte de bug* (pasos para reproducir, versión/commit, qué esperabas).
- **Petición de función** → issue con la plantilla *Feature request*.
- **Vulnerabilidad de seguridad** → **no** abras un issue público. Usa el botón
  *"Report a security vulnerability"* del repo (reporte privado) siguiendo
  [SECURITY](../SECURITY.md).

## Relacionado

- [README principal](../README.md) — visión general y stack.
- [CONTRIBUTING](../CONTRIBUTING.md) — si quieres aportar código.
- [demo-walkthrough](demo-walkthrough.md) — recorrido sin código.
