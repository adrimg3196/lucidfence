# Hallazgos de seguridad (append-only)

Formato por entrada: fecha | severidad | clase (OWASP) | resumen | PoC (petición→respuesta que lo demuestra) | estado (open/fixed/accepted) | PR.

No se borra ninguna entrada: se cambia su estado y se enlaza el fix. La PoC es descriptiva (cómo reproducir contra el localhost propio), nunca un exploit armado contra producción.

> **Proceso de divulgación (responsible disclosure).** Este fichero es PÚBLICO
> en GitHub (`docs/internal/` no es privado). Por tanto: **las entradas en estado
> `open` NO publican pasos de reproducción** — solo el qué (clase OWASP), el
> dónde (ruta/función) y la severidad. Los pasos exactos de reproducción se
> detallan **únicamente tras pasar la entrada a `fixed`** (con regresión que lo
> cierra) o `accepted` (con justificación). Publicar el mapa de reproducción de
> una vuln viva invertiría la divulgación responsable; redactar la receta hasta
> el fix no es ocultar, es el orden correcto. Toda entrada con PoC descriptiva
> abajo está `fixed`/`accepted`: su receta apunta a un control ya en su sitio y
> respaldado por test.

## Sembrados desde la auditoría Strix previa (PR #45, 2026-07-28)

Ocho hallazgos ya identificados con metodología Strix/OWASP sobre los trust
boundaries del producto. El Centinela debe VERIFICARLOS por PoC contra el
localhost propio (algunos pueden estar ya mitigados desde julio: confirmar
antes de tocar) y, los confirmados de bajo riesgo, arreglarlos con test de
regresión; los que toquen auth/notifier/adapters/sesión son Tier B (PR con
PoC, gate humano). Origen: rutas citadas contra el código de aquella fecha —
reconfirmar líneas actuales.

- 2026-07-28 | alta | A01/A05 Broken Access Control / CSRF | `POST /api/settings/run-once` (y settings) sin auth: una web local cualquiera podía hacer drive-by | PoC: petición POST sin cookie de sesión desde otro origen → 200 | **fixed** (verificado ya mitigado; Centinela 2026-08-16) | gate `require(self)` en `saas_server.py:1268` protege TODO `/api/settings*`; cookie `SameSite=Strict` (`:717`)
- 2026-07-28 | alta | A01 | `settings/test` aceptaba `api_key` en el body y la reenviaba a Applivery (proxy de token) desde un llamador no autenticado | PoC: POST con api_key en body sin sesión → proxied | **fixed** (verificado ya mitigado; Centinela 2026-08-16) | tras el gate + capability `engine:config` (`saas_server.py:1844-1846`); ya no invocable sin sesión
- 2026-07-28 | media | TLS | `urlopen()` en `location_source.py` sin `ssl.create_default_context()` explícito | PoC: revisar que el contexto TLS por defecto valida cadena/host | **accepted** (no explotable; Centinela 2026-08-16) | el default de `urlopen` valida cadena+host (PEP 476); 0 desactivadores en el repo (grep de `CERT_NONE`/`_create_unverified_context`). Hacerlo explícito es cosmético
- 2026-07-28 | alta | A10 SSRF | header `Link` del MDM dictaba la URL re-pedida con Bearer → robo de token hacia IPs internas | PoC: MDM/mock devuelve Link a 169.254.x → LucidFence la sigue con el token | **fixed** (Centinela 2026-08-16) | `location_source._next_from_link` exige mismo origen que `_api_base` (`_same_origin`); regresión en `tests/test_security_findings_strix.py`
- 2026-07-28 | media | A01/A10 | `device_id` sin validar interpolado en URL vía `.format()` | PoC: device_id con `../` o `@host` → URL manipulada | **fixed** (Centinela 2026-08-16) | `quote(device_id, safe="")` en `location_source.py`, `applivery.py`, `jamf.py`, `fleet.py`; regresión con `../@host`
- 2026-07-28 | baja | A03 validación | lat/lng sin acotar ni try/except en `float()` (`fences.py`) | PoC: fence con lat=9999/NaN → comportamiento indefinido | **fixed** (Centinela 2026-08-16) | `geo.valid_coord`/`point_from` acotan rango + rechazan NaN/inf; `fences.py` falla-cerrado (config corrupta no carga); regresión
- 2026-07-28 | baja | A03 | ídem en waypoints de rutas (`routes.py`) | PoC: waypoint malformado → no se omite | **fixed** (Centinela 2026-08-16) | `routes.load_routes` valida cada waypoint con `point_from`; ruta con waypoint corrupto se omite sin abortar el resto; regresión
- 2026-07-28 | baja | A10 SSRF | `webhook_url` de config podía ser `http://` o IP interna (`notifier.py`) | PoC: webhook a 127.0.0.1:port interno → se dispara | **fixed** (parcial, by-design; Centinela 2026-08-16) | `notifier._default_http_post` rechaza esquemas no-http(s) y credential-smuggling (`user:pass@`); IPs internas NO se bloquean a propósito (self-hosted BYOI: el admin puede apuntar a un SIEM interno legítimo); regresión

> Nota: PR #45 solo anotó estos hallazgos como comentarios; no cambió
> comportamiento. El Centinela cierra el ciclo: verificar por PoC → arreglar
> (Tier A) o escalar (Tier B) → estado a fixed/accepted con enlace a la PR.

## Nuevos (ciclos del Centinela)

- **2026-08-16 (ciclo 1, pasada manual)** — verificados los 8 hallazgos Strix
  sembrados contra el código actual. Resultado: 5 vivos arreglados con
  regresión (C header Link SSRF/robo de token · F device_id sin escapar en 4
  sitios · G lat/lng de geocercas · H waypoints de rutas · D esquema de
  webhook), 2 ya mitigados desde julio (A/B auth de settings), 1 aceptado sin
  riesgo (E TLS, el default ya valida). Ningún hallazgo crítico nuevo. Batería
  runtime 28/28; suite 485 pass. Regresiones en
  `tests/test_security_findings_strix.py` (8 tests, uno por finding vivo).

- **2026-08-20 (Privacy Engineer, revisión de divulgación)** — segunda
  verificación independiente de los 8 findings Strix contra el código HOY (no
  contra el run-log): **8/8 confirmados como `fixed`/`accepted` en el código
  vivo**, ninguno queda `open`. Evidencia contrastada línea a línea:
  - **A** (settings/run-once authz+CSRF) → `fixed`: gate `require(self)` en
    `saas_server.py:1268` cubre todo el bloque de settings; cada ruta exige
    `AuthStore.can(..., "engine:config")` (p.ej. `:1924-1925`); cookie de sesión
    `SameSite=Strict; HttpOnly` (`saas_server.py:701`).
  - **B** (settings/test proxy de token) → `fixed`: `POST /api/settings/test`
    exige `engine:config` (`saas_server.py:1957-1958`); no invocable sin sesión.
  - **C** (Link header SSRF / robo de token) → `fixed`: `_next_from_link`
    (`location_source.py:230`) solo sigue el `Link` si `_same_origin` (scheme+
    host+port) contra `_api_base` (`location_source.py:49-70`, `:240`). Test
    `test_link_pagination_refuses_foreign_host`.
  - **D** (webhook SSRF) → `fixed (parcial, by-design)`: `_default_http_post`
    (`notifier.py:48`) rechaza esquema ≠ http/https, host vacío y
    credential-smuggling `user:pass@` (`:59`); HTTPS con
    `ssl.create_default_context()` (`:76`). IPs internas NO se bloquean a
    propósito (BYOI self-hosted: SIEM interno legítimo) — riesgo aceptado y
    documentado en el propio código. Test `test_webhook_rejects_dangerous_url`.
  - **E** (TLS explícito en `location_source`) → `accepted`: el default de
    `urlopen` valida cadena+host (PEP 476); 0 desactivadores en el repo. Además
    el POST HTTPS del notifier usa contexto por defecto explícito. Cosmético.
  - **F** (device_id sin escapar) → `fixed`: `quote(str(device_id), safe="")` en
    los 4 sitios: `location_source.py:376`, `applivery.py:117`, `jamf.py:371`,
    `fleet.py:124`. Tests `test_location_source_quotes_device_id`,
    `test_fleet_adapter_quotes_device_id`.
  - **G** (lat/lng geocercas) → `fixed`: `geo.valid_coord` rechaza NaN/inf y
    acota rango (`geo.py:16-33`); `fences.py` falla-cerrado vía `point_from`.
    Tests `test_fence_rejects_out_of_range_and_nan`, `..._accepts_valid...`.
  - **H** (waypoints de rutas) → `fixed`: `routes.load_routes` valida cada
    waypoint con `point_from` y omite la ruta corrupta sin abortar el resto
    (`routes.py:76-82`). Test `test_route_with_malformed_waypoint_is_skipped_others_load`.
  Regresión `tests/test_security_findings_strix.py` 8/8 pass (ejecutada hoy).
  Como las 8 están `fixed`/`accepted`, sus PoC descriptivas quedan publicadas
  conforme al proceso de arriba; no hubo ninguna `open` que redactar.

(el primer ciclo corre el jueves)
