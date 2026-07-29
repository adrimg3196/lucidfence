# Servidor MCP Oficial de LucidFence

El Servidor MCP (Model Context Protocol) oficial de LucidFence permite a agentes de Inteligencia Artificial (como Claude, GPTs y asistentes agénticos compatibles con el estándar de integración de Anthropic) interactuar de forma segura y directa con la API pública de tu instancia LucidFence para gestionar geocercas, consultar el estado de dispositivos, visualizar incidentes activos y auditar eventos.

Este servidor se ejecuta 100% localmente mediante entrada/salida estándar (stdio), garantizando soberanía de datos y costo cero.

## Arquitectura y Seguridad

- **Cero dependencias externas:** Implementado usando únicamente librerías estándar de Python.
- **Sin atajos privados:** Cada herramienta (tool) realiza peticiones HTTP directas a la API REST pública de LucidFence (por defecto en `http://127.0.0.1:8765`), respetando el modelo RBAC de `lucidfence/saas/auth.py`. Un agente con rol de `viewer` no podrá ejecutar operaciones de escritura como `create_fence` o `delete_fence`.
- **Autenticación flexible:** Soporta autenticación mediante tokens de API (`api_key` con prefijo `lf_`) o cookies de sesión (`session_cookie` con prefijo `gf_session`). Si no se suministran explícitamente, el servidor intentará autenticarse mediante la sesión demo por defecto si la instancia local lo permite.

---

## Configuración

### Claude Desktop

Para integrar LucidFence con Claude Desktop, añade el siguiente bloque de configuración a tu archivo `claude_desktop_config.json`:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "lucidfence-official": {
      "command": "poetry",
      "args": [
        "run",
        "python3",
        "-m",
        "lucidfence.mcp.server"
      ],
      "env": {
        "LUCIDFENCE_URL": "http://127.0.0.1:8765",
        "LUCIDFENCE_API_KEY": "tu_token_api_aqui_lf_..."
      }
    }
  }
}
```

> **Nota:** Si no usas Poetry, puedes configurar el comando directo usando el path a tu intérprete de Python global o de entorno virtual:
> ```json
> "command": "/ruta/a/tu/venv/bin/python3",
> "args": ["-m", "lucidfence.mcp.server"]
> ```

### mcporter

Si prefieres usar `mcporter` para gestionar y exponer servidores MCP, añade el siguiente bloque a tu archivo de configuración de `mcporter`:

```yaml
servers:
  lucidfence:
    command: "python3"
    args:
      - "-m"
      - "lucidfence.mcp.server"
    env:
      LUCIDFENCE_URL: "http://127.0.0.1:8765"
      LUCIDFENCE_API_KEY: "lf_..."
```

---

## Herramientas Expuestas (Tools)

El servidor MCP oficial expone las siguientes herramientas:

### 1. Gestión de Geocercas (Geofences)

- `list_fences`: Obtiene el listado de todas las geocercas configuradas en la organización.
- `get_fence`: Recupera la información detallada de una geocerca específica pasándole su `id`.
- `create_fence`: Crea una nueva geocerca.
  - **Parámetros:**
    - `name` (Requerido): Nombre de la geocerca.
    - `type` (Opcional, por defecto `circle`): Tipo de geocerca (`circle` o `polygon`).
    - `lat`, `lng`: Coordenadas geográficas.
    - `radius_m`: Radio en metros para geocercas circulares.
    - `address` (Opcional): Dirección física que será geocodificada automáticamente.
    - `coordinates` (Opcional): Lista de puntos `{lat, lng}` para tipo polígono.
    - `actions` (Opcional): Lista de acciones de transición (e.g., lanzar alertas o bloquear dispositivos al entrar/salir).
- `delete_fence`: Elimina una geocerca pasando su `id`.

### 2. Dispositivos (Devices)

- `list_devices`: Obtiene la lista de todos los dispositivos de la flota. Permite filtrar opcionalmente por estado geográfico (`inside`, `outside`, `unknown`) usando el argumento `state`.
- `get_device_state`: Obtiene el estado detallado en tiempo real, el histórico de trails, incidentes y acciones ejecutadas de un dispositivo mediante su `id`.

### 3. Incidentes y Eventos (Incidents & Events)

- `list_incidents`: Obtiene la lista de alertas e incidentes de riesgo activos y recientes en LucidFence.
- `list_events`: Lista el historial de eventos del sistema generados por el motor de evaluación.
