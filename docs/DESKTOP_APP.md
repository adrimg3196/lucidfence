# LucidFence Desktop para macOS

LucidFence Desktop es la distribución recomendada para usuarios de Mac que no quieren usar Terminal. El bundle contiene:

- Launcher nativo Swift/AppKit.
- Ventana nativa `WKWebView`.
- Backend local congelado con PyInstaller.
- Python y dependencias embebidos.
- Assets frontend y seeds demo públicos.
- Lifecycle propio: el backend hijo se cierra al salir de la app.

## Requisitos de la build 1.2.0

- Mac Apple Silicon (M1 o posterior).
- macOS 14 o posterior.
- No es compatible todavía con Mac Intel.

## Instalar

1. Descarga el DMG desde [la última release](https://github.com/adrimg3196/lucidfence/releases/latest).
2. Abre el DMG.
3. Arrastra `LucidFence.app` al alias `Applications`.
4. Primera apertura de la build comunitaria: clic derecho → **Abrir**.

No se requiere Homebrew, Python ni una cuenta de LucidFence.

## Datos y logs

- Datos: `~/Library/Application Support/LucidFence`
- Log del backend desktop: `~/Library/Logs/LucidFence/desktop-backend.log`

Eliminar la app no elimina datos. Para borrar también el estado local, cierra LucidFence y elimina manualmente el directorio de Application Support.

## Seguridad

- El backend escucha solo en `127.0.0.1`.
- La app busca un puerto libre entre 8765 y 8775.
- Cada ventana inicia su propio backend en un puerto libre y valida un nonce de instancia antes de cargarlo; nunca adopta procesos existentes.
- Al salir, solo termina el backend iniciado por esa ventana.
- El bundle incluye únicamente `fleet_seed.json`, `fences.json`, `routes.json` y `policies.json`; nunca se empaquetan usuarios, sesiones, trails, secretos o estado de tenants.

## Compilar

Requiere macOS, Command Line Tools y red para instalar las dependencias del entorno builder la primera vez:

```bash
python3 macos/build_desktop.py --version 1.2.0 --allow-adhoc
```

Salidas:

```text
dist/LucidFence.app
dist/LucidFence-1.2.0-arm64.dmg
dist/LucidFence-1.2.0-arm64.json
```

El builder:

1. Recrea un venv aislado en `build/macos-desktop` desde locks con hashes.
2. Congela el backend con PyInstaller.
3. Compila el launcher Swift.
4. Ensambla y firma el bundle.
5. Crea un DMG con alias drag-to-Applications.
6. Verifica plist, firma y DMG; registra SHA-256 y resultado de Gatekeeper en el manifest.

## Firma y notarización

Sin identidad configurada el builder falla de forma segura. `--allow-adhoc` habilita únicamente una build local de QA, marcada como `release_ready: false`; Gatekeeper exigirá clic derecho → Abrir.

Para una distribución de doble clic sin advertencias:

```bash
export LUCIDFENCE_CODESIGN_IDENTITY='Developer ID Application: Example Corp (TEAMID)'
export LUCIDFENCE_NOTARY_PROFILE='LucidFence'
python3 macos/build_desktop.py --version 1.2.0
```

El perfil se crea una vez con `xcrun notarytool store-credentials`. El builder envía el DMG, espera el resultado y aplica el ticket con `stapler`.

## QA de release

Una release desktop solo pasa si:

- `codesign --verify --deep --strict` pasa.
- `hdiutil verify` pasa.
- El DMG contiene `LucidFence.app` y el alias `/Applications`.
- La app instalada inicia su backend dentro de su propio bundle.
- `/api/health`, demo login, seeds y primer ciclo pasan en un directorio de datos vacío.
- La captura WKWebView no está vacía y la consola JavaScript tiene cero errores.
- Al salir de la app desaparece su backend hijo.
