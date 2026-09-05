# Seguridad

Si encuentras una vulnerabilidad, escribe a adrimg3196@gmail.com con asunto
"LucidFence security" o abre un aviso privado en
https://github.com/adrimg3196/lucidfence/security/advisories/new. No abras una
issue pública. Respuesta en 72 h.

Alcance: el binario `lucidfence`, el dashboard embebido y los workflows de este
repositorio. Las releases 1.x (rama `legacy/python`) reciben solo correcciones
críticas hasta la publicación de 2.0.0.

Invariantes que consideramos fallos de seguridad si se rompen: el producto
nunca actúa sobre un dispositivo real sin `enforce` explícito del admin; `wipe`
exige doble llave; las credenciales UEM nunca aparecen en respuestas GET, logs,
MCP ni frontend; ninguna URL de salida se usa sin pasar por la allowlist de egress.
