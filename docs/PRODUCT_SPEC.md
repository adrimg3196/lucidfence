# LucidFence 1.1 — Spec: configuración local, AI opcional y MCP

Fecha: 2026-07-15
Estado: LOCKED para implementación TDD
Referencia de proceso: grill → spec → tareas pequeñas → revisión independiente → QA → ship.

## 1. Principios

1. LucidFence funciona sin cuenta cloud y sin modelo AI.
2. Toda credencial la introduce el operador en la UI local; nunca aparece en GET, logs, MCP ni frontend.
3. Demo es el primer arranque y no pide claves.
4. Live exige elegir y validar un conector UEM.
5. AI es BYO endpoint/model/key y se puede desactivar.
6. Todo endpoint administrativo conserva RBAC `engine:config`.
7. El gateway OpenAI-compatible solo es anónimo en loopback; exposición remota exige bearer token explícito.
8. MCP corre por stdio y usa la instancia local; herramientas destructivas no se incluyen en 1.1.

## 2. Onboarding único

Paso 1 — Modo:
- Demo local, recomendado para probar.
- Conectar UEM.

Paso 2 — Fuente UEM:
- Applivery: API key + organization/workspace ID.
- Microsoft Intune: tenant ID + client ID + client secret.
- Jamf Pro: base URL + client ID + client secret.
- Los campos dependen del provider; no se muestran formularios irrelevantes.
- Botón “Probar conexión” antes de activar Live.

Paso 3 — AI opcional:
- Desactivada.
- OpenAI-compatible: base URL + model + API key opcional.
- Presets de UX: OpenAI, Ollama local, LM Studio local, Custom.
- Nous Portal y cualquier gateway compatible se configuran mediante Custom mientras no haya endpoint estable documentado en el producto.
- Botón “Probar modelo”.

Paso 4 — Resumen:
- Modo, conector, dry-run, AI, rutas de datos.
- Confirmar sin exponer secretos.

## 3. Backend AI

Configuración tenant-local:
- `ai_provider.json` 0600: enabled/provider/base_url/model (no key).
- `.env` 0600: `LUCIDFENCE_AI_API_KEY` (key).

Endpoints autenticados:
- `GET /api/ai/settings`: estado no secreto y presets.
- `POST /api/ai/settings`: guarda configuración; permiso `engine:config`.
- `POST /api/ai/test`: prueba `/models`; permiso `engine:config`.
- `POST /api/ai/chat`: chat con contexto opcional de flota.

Gateway local:
- `POST /v1/chat/completions`: contrato OpenAI-compatible; reenvía al provider configurado.
- Loopback: disponible sin token.
- Bind no-loopback: exige `Authorization: Bearer $LUCIDFENCE_GATEWAY_TOKEN`.
- Si AI está desactivada: 503 honesto, sin respuesta simulada disfrazada de modelo.

## 4. MCP local

`mcp/lucidfence_mcp.py`, stdio JSON-RPC, cero dependencias extra.

Tools read-only:
- `lucidfence_status`
- `lucidfence_list_devices`
- `lucidfence_list_incidents`
- `lucidfence_get_risk`
- `lucidfence_ask_ai` (error explícito si AI no configurada)
- `lucidfence_learn` (contrato y setup)

No se exponen wipe/lock/reboot en 1.1. El MCP no acepta API keys UEM en argumentos.

## 5. Criterios de aceptación

- Tests unitarios de guardado/enmascarado/config 0600.
- Fake OpenAI server: test models + completion normalizada.
- Key nunca aparece en `status()` ni errores.
- UI no contiene `/Users/adri/moa` ni afirma MoA local incorporado.
- AI desactivada muestra CTA “Configurar proveedor”, no error técnico.
- MCP responde initialize, tools/list y tools/call por stdin/stdout.
- UEM settings renderiza catálogo Applivery/Intune/Jamf y Demo.
- Suite completa verde.
- Homebrew incluye `mcp/lucidfence_mcp.py` y muestra comando de registro.
- Documentación `docs/AI_AND_MCP.md` con ejemplos sin secretos reales.
