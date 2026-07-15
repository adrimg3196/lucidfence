# LucidFence — Guía de arranque para macOS

Centro de mando local de geofencing, riesgo y acciones para flotas UEM/MDM.

## 1. Descargar e instalar

1. Abre [la última release](https://github.com/adrimg3196/lucidfence/releases/latest).
2. Descarga `LucidFence-1.2.0-arm64.dmg` (Mac Apple Silicon M1 o posterior, macOS 14 o posterior).
3. Abre el DMG y arrastra **LucidFence** a **Applications**.
4. Primera apertura: clic derecho sobre LucidFence → **Abrir**.

Después puedes abrir LucidFence normalmente desde Launchpad, Spotlight o Finder. No necesitas Terminal, Homebrew, Python ni una cuenta cloud.

La aplicación inicia su motor local, muestra el Command Center en una ventana nativa y carga una flota demo automáticamente.

## 2. Qué puedes hacer

| Vista | Para qué |
|-------|----------|
| **Resumen** | KPIs: dispositivos, dentro/fuera, incumplimientos y CVE |
| **Mapa** | Posición de dispositivos frente a geovallas |
| **Dispositivos** | Estado operativo y de conformidad |
| **Inventario** | SO, modelo, serial, batería, almacenamiento, usuario y departamento |
| **Riesgo** | Riesgo explicable y evidencia por dispositivo |
| **AI opcional** | Conecta tu propio proveedor compatible si lo necesitas |
| **Eventos / Incidentes** | Trazabilidad y lifecycle de incidencias |
| **SOAR · CVE** | Vulnerabilidades y playbooks de remediación |
| **Acciones** | Auditoría de lock, wipe, locate, reboot y mensajes |
| **Geovallas / Rutas** | Perímetros y rutas operativas |
| **Workflows / Objetivos** | Automatización y KPIs |
| **Ajustes** | Integraciones UEM y configuración local |

## 3. Conectar Applivery u otro UEM

Abre **Ajustes**, selecciona el adapter y añade sus credenciales. Los secretos permanecen en el directorio local del tenant; no se envían a una nube de LucidFence.

## 4. Cerrar, actualizar y desinstalar

- **Cerrar:** `LucidFence → Salir de LucidFence` o `⌘Q`. La app termina su backend local.
- **Actualizar:** descarga la nueva release y reemplaza la app en Applications. Tus datos se conservan.
- **Desinstalar:** mueve `LucidFence.app` a la Papelera.
- **Borrar también los datos:** elimina `~/Library/Application Support/LucidFence` después de cerrar la app.

## 5. Privacidad

- Backend solo en `127.0.0.1`.
- Sin telemetría.
- Sin cuenta remota obligatoria.
- Datos en `~/Library/Application Support/LucidFence`.
- Logs en `~/Library/Logs/LucidFence`.

## 6. Alternativa técnica

Para servidores, Linux o automatización:

```bash
brew tap adrimg3196/lucidfence
brew install lucidfence
lucidfence
```

Consulta [README.md](README.md) y [docs/DESKTOP_APP.md](docs/DESKTOP_APP.md) para CLI, build, firma y QA.
