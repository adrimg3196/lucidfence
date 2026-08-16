# Hallazgos de seguridad (append-only)

Formato por entrada: fecha | severidad | clase (OWASP) | resumen | PoC (petición→respuesta que lo demuestra) | estado (open/fixed/accepted) | PR.

No se borra ninguna entrada: se cambia su estado y se enlaza el fix. La PoC es descriptiva (cómo reproducir contra el localhost propio), nunca un exploit armado contra producción.

## Sembrados desde la auditoría Strix previa (PR #45, 2026-07-28)

Ocho hallazgos ya identificados con metodología Strix/OWASP sobre los trust
boundaries del producto. El Centinela debe VERIFICARLOS por PoC contra el
localhost propio (algunos pueden estar ya mitigados desde julio: confirmar
antes de tocar) y, los confirmados de bajo riesgo, arreglarlos con test de
regresión; los que toquen auth/notifier/adapters/sesión son Tier B (PR con
PoC, gate humano). Origen: rutas citadas contra el código de aquella fecha —
reconfirmar líneas actuales.

- 2026-07-28 | alta | A01/A05 Broken Access Control / CSRF | `POST /api/settings/run-once` (y settings) sin auth: una web local cualquiera podía hacer drive-by | PoC: petición POST sin cookie de sesión desde otro origen → 200 | open (verificar) | —
- 2026-07-28 | alta | A01 | `settings/test` aceptaba `api_key` en el body y la reenviaba a Applivery (proxy de token) desde un llamador no autenticado | PoC: POST con api_key en body sin sesión → proxied | open (verificar) | —
- 2026-07-28 | media | TLS | `urlopen()` en `location_source.py` sin `ssl.create_default_context()` explícito | PoC: revisar que el contexto TLS por defecto valida cadena/host | open (verificar) | —
- 2026-07-28 | alta | A10 SSRF | header `Link` del MDM dictaba la URL re-pedida con Bearer → robo de token hacia IPs internas | PoC: MDM/mock devuelve Link a 169.254.x → LucidFence la sigue con el token | open (verificar) | —
- 2026-07-28 | media | A01/A10 | `device_id` sin validar interpolado en URL vía `.format()` | PoC: device_id con `../` o `@host` → URL manipulada | open (verificar) | —
- 2026-07-28 | baja | A03 validación | lat/lng sin acotar ni try/except en `float()` (`fences.py`) | PoC: fence con lat=9999/NaN → comportamiento indefinido | open (verificar) | —
- 2026-07-28 | baja | A03 | ídem en waypoints de rutas (`routes.py`) | PoC: waypoint malformado → no se omite | open (verificar) | —
- 2026-07-28 | baja | A10 SSRF | `webhook_url` de config podía ser `http://` o IP interna (`notifier.py`) | PoC: webhook a 127.0.0.1:port interno → se dispara | open (verificar) | —

> Nota: PR #45 solo anotó estos hallazgos como comentarios; no cambió
> comportamiento. El Centinela cierra el ciclo: verificar por PoC → arreglar
> (Tier A) o escalar (Tier B) → estado a fixed/accepted con enlace a la PR.

## Nuevos (ciclos del Centinela)

(el primer ciclo corre el jueves)
