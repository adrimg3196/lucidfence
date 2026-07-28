# AI opcional, gateway y MCP local

LucidFence funciona al 100% en modo Demo y con Applivery sin conectar ningún modelo. La IA es una capacidad opt-in: tú eliges el endpoint, el modelo y qué datos se le envían.

## Configurar un proveedor AI

1. Abre `http://127.0.0.1:8765`.
2. Ve a **Ajustes → Proveedor AI opcional**.
3. Activa AI.
4. Elige un preset o `OpenAI-compatible`.
5. Completa Base URL, modelo y API key cuando el proveedor la necesite.
6. Pulsa **Probar modelo** y después **Guardar AI**.

Presets:

| Proveedor | Base URL habitual | API key |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | requerida |
| Ollama | `http://127.0.0.1:11434/v1` | no |
| LM Studio | `http://127.0.0.1:1234/v1` | no |
| Nous Portal u otro gateway | usa `OpenAI-compatible` y la URL documentada por el proveedor | depende del servicio |

LucidFence no fija una URL de Nous Portal en código porque el endpoint comercial puede cambiar. El formulario Custom evita acoplar una release a una URL no estable.

### Almacenamiento

Por organización, dentro del directorio local de datos:

- `ai_provider.json` (modo `0600`): provider, URL y modelo; nunca la key.
- `.env` (modo `0600`): `LUCIDFENCE_AI_API_KEY`.

Los GET devuelven únicamente estado y máscara. La clave no aparece en frontend, logs, MCP ni respuestas de error.

## API autenticada de la app

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/ai/settings` | Estado no secreto y presets |
| POST | `/api/ai/settings` | Guardar provider/model/key; requiere `engine:config` |
| POST | `/api/ai/test` | Validar `/models`; requiere `engine:config` |
| POST | `/api/ai/chat` | Chat tenant-local con el proveedor configurado |

Ejemplo de body:

```json
{
  "messages": [
    {"role": "system", "content": "Eres un analista UEM."},
    {"role": "user", "content": "Resume los dispositivos de riesgo alto."}
  ]
}
```

## Gateway OpenAI-compatible local

Endpoint:

```text
POST http://127.0.0.1:8765/v1/chat/completions
```

Ejemplo sin incluir secretos:

```bash
curl -s http://127.0.0.1:8765/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"lucidfence","messages":[{"role":"user","content":"Hola"}]}'
```

En loopback no exige token adicional. Si LucidFence se enlaza a una interfaz no-loopback, configura antes:

```bash
export LUCIDFENCE_GATEWAY_TOKEN='genera-un-token-largo-en-tu-terminal'
lucidfence serve --host 0.0.0.0
```

Y usa `Authorization: Bearer ...`. No pegues ese token en issues, commits o conversaciones.

En instalaciones con más de una organización, selecciona la organización mediante `X-LucidFence-Org`. Sin esa cabecera se usa la primera organización que tenga AI configurada.

## MCP local

Ejecutar:

```bash
lucidfence mcp
```

Registrar en Hermes:

```bash
echo Y | hermes mcp add lucidfence \
  --command lucidfence --args mcp
hermes mcp list
```

Configuración genérica para clientes MCP stdio:

```json
{
  "mcpServers": {
    "lucidfence": {
      "command": "lucidfence",
      "args": ["mcp"]
    }
  }
}
```

Tools:

- `lucidfence_learn`
- `lucidfence_status`
- `lucidfence_list_devices`
- `lucidfence_list_incidents`
- `lucidfence_get_risk`
- `lucidfence_ask_ai`

La primera versión del MCP es deliberadamente read-only. No expone `wipe`, `lock` ni `reboot`; las acciones de dispositivo siguen protegidas por RBAC y confirmación en la UI.

Variables opcionales:

- `LUCIDFENCE_URL`: instancia local, por defecto `http://127.0.0.1:8765`.
- `LUCIDFENCE_MCP_COOKIE`: sesión explícita para una organización no-demo. Trátala como un secreto temporal y no la guardes en el repositorio.

## Fuentes UEM

- **Demo local:** completa, sin credenciales.
- **Applivery:** integración live disponible; pide Bearer token y organization/workspace ID.
- **Microsoft Intune:** adapter comunitario preview; comandos con token Graph, sin sincronización live de inventario en esta release.
- **Jamf Pro:** adapter comunitario preview; comandos con token, sin sincronización live de inventario en esta release.

La UI muestra Intune/Jamf como preview y no permite activarlos como live hasta completar y verificar su inventario. Esto evita una integración “de escaparate” que aparenta funcionar usando mocks.
