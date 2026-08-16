# Centinela — loop de seguridad ofensiva (semanal)

Complementa el CI (gitleaks + pip-audit ya corren en cada PR) con testing de
seguridad de aplicación de verdad: arranca el producto y lo ataca, en local,
contra su propio `saas_server.py`. Metodología de
[Strix](https://github.com/usestrix/strix): validar por prueba de concepto,
no por análisis estático. Corre en silencio (regla 7); reporta vía el digest,
salvo vulnerabilidad crítica explotable → rompe el silencio al momento.

## Alcance (autorización)

Strix avisa: "authorized use only, stay within agreed scope". El scope
autorizado de este loop es **exclusivamente el propio LucidFence corriendo en
localhost dentro de la sesión del agente** (`saas_server.py` en `127.0.0.1`,
datos demo, cero credenciales reales). PROHIBIDO apuntar a cualquier host que
no sea ese localhost efímero; jamás a infra de un tenant, a `api.applivery.io`
ni a ningún tercero. Sin ese localhost propio arrancado, el loop no ataca nada.

## Qué prueba (guiado por `docs/architecture/THREAT_MODEL.md`)

Superficie: la API HTTP de `saas_server.py` y el dashboard. Clases OWASP
priorizadas por el modelo de amenazas del repo (autoridad de remediación +
datos de ubicación de tenant + secretos):
- **IDOR / aislamiento entre tenants**: ¿puede un tenant leer/actuar sobre
  dispositivos, incidentes o evidencia de otro? (el invariante nº1 del
  producto).
- **AuthN/AuthZ**: rutas protegidas que respondan sin sesión; el permiso
  `device:action` saltable; escalada de rol.
- **Fuga de secretos**: api_key/client_secret/refresh_token sin enmascarar
  en respuestas; secretos en logs o en `data/cloud_state.json`.
- **Injection / SSRF**: los webhooks configurables y el `generic_http_source`
  como vector de SSRF; inyección en los campos que llegan del adapter.
- **XSS** en el dashboard con datos de dispositivo controlados por el device.

## Ciclo

1. Arranca `saas_server.py` en un puerto local con datos demo (modo
   simulación, dry_run). Crea ≥2 tenants para probar aislamiento.
2. Ejecuta la batería (Strix si está disponible en la sesión como skill/CLI;
   si no, un barrido dirigido con curl/requests contra las clases de arriba).
   Cada hallazgo DEBE llevar prueba de concepto reproducible: la petición
   exacta y la respuesta que demuestra el fallo. Sin PoC no es hallazgo.
3. Trica cada hallazgo confirmado. **Fixes que puede mergear el loop**: solo
   los de bajo riesgo y evidentes (una ruta a la que le falta el check de
   auth, un campo sin enmascarar) con test de regresión nuevo, gate QA
   completo y un check nuevo en `scripts/runtime_validation.py` que pruebe la
   corrección en vivo. **Todo lo que toque `saas_server.py` auth,
   `notifier.py`, el contrato de adapters o el modelo de sesión es GATE
   HUMANO** (loop-constraints.md): PR abierta con el PoC, sin mergear.
4. Registro: hallazgos en `findings.md` (append-only, con estado
   open/fixed/accepted y su PoC); una línea en el run-log común.

## Reglas duras

- Solo el localhost propio del agente. Cero ataques a terceros, cero uso de
  credenciales reales. La PoC vive en `findings.md`, nunca un exploit armado
  ejecutable contra producción.
- Un fix de seguridad nunca se mergea sin test de regresión que falle antes y
  pase después.
- Los hallazgos de severidad alta/crítica se notifican al propietario en el
  acto (excepción de la regla 7), con el PoC y la mitigación propuesta.
- Nada de telemetría ni de exfiltrar los propios hallazgos: `findings.md` es
  interno y se excluye del tarball de cliente como el resto de `docs/internal/`.
