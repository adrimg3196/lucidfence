# LucidFence — Marketing copy (canon público)

Fuente única del copy público aprobado por Producto (issue #188). Cualquier
superficie pública (`static/index.html`, `README.md`, vitrina) debe coincidir
con este documento. No editar el copy suelto en otras páginas sin actualizar
este archivo primero.

## Regla de integridad pública (#110)
Toda afirmación «live» debe anclarse a la matriz de UEMs. No afirmar
«Intune/Jamf live» incondicionalmente: se ancla al token del tenant.

Anclas de verificación (fuentes):
- Credenciales UEM actuales: `docs/architecture/PRODUCT_SPEC.md` (líneas 25-27:
  Applivery / Intune / Jamf).
- Matriz de capacidades por UEM: `docs/integrations/MULTI_UEM.md` (registro del
  provider por tenant + «Probar conexión» antes de activar Live).
- La matriz de código `lucidfence/core/adapters/capabilities.py` AÚN NO está en
  `main` (vive en `cto/multiuem-adapters-soar`). Mientras tanto, anclar a
  `MULTI_UEM.md` / `PRODUCT_SPEC.md`.

## Copy aprobado (usar tal cual — verificado por PM)

### Claim 1 — Multi-UEM simultáneo (Decisión 4) — PUBLICABLE YA
ES: «Multi-UEM simultáneo por tenant: Applivery live por defecto; Intune
(Microsoft Graph) y Jamf Pro en modo live al conectar tu token del tenant
(caen a simulación sin token). Cero exfiltración de datos.»
EN: «Simultaneous multi-UEM per tenant: Applivery live by default; Intune
(Microsoft Graph) and Jamf Pro go live when you connect your tenant token
(they fall back to simulation without one). Zero data exfiltration.»

### Claim 2 — SOAR declarativo v1 (Decisiones 2/3) — PUBLICABLE YA
ES: «SOAR declarativo con 4 playbooks frontline (CVE crítico, CVE + fuera de
perímetro, no conforme + fuera, EPSS alto) y auditoría por dispositivo
(matched_fields).»
EN: «Declarative SOAR with 4 frontline playbooks (critical CVE, CVE + outside
perimeter, non-compliant + outside, high EPSS) and per-device audit
(matched_fields).»

### Claim 3 — Webhook SOAR BYO (Decisión 1) — PENDIENTE (NO publicar)
Bloqueado por #110: el hardening SSRF (allow/deny-list por tenant) NO está en
`origin/main`. Vive en `cto/webhook-egress-allowlist` /
`cto/webhook-pinned-ip-egress` y no está contenido en `cto/multiuem-adapters-soar`.
ES: «SOAR con webhook BYO hacia tu Splunk/Cortex XSOAR (o cualquier endpoint),
con salida SSRF-hardened y allow/deny-list por tenant.»
EN: «SOAR with a BYO webhook to your Splunk/Cortex XSOAR (or any endpoint),
with SSRF-hardened egress and per-tenant allow/deny-list.»
→ Publicar SOLO tras fusionar `cto/webhook-egress-allowlist` en main (ver tarea
  CTO t_51849f2c). No incluir en vitrina hasta entonces.

## Matriz de publicación (estado del copy)
| Claim | Estado | Superficie | Ancla a fuente |
|-------|--------|-----------|----------------|
| 1 Multi-UEM | ✅ publicado | index.html, README.md | MULTI_UEM.md / PRODUCT_SPEC.md |
| 2 SOAR v1 | ✅ publicado | index.html, README.md | soar.py:253 (DEFAULT_PLAYBOOKS) en main |
| 3 Webhook BYO | ⛔ pendiente CTO | — | cto/webhook-egress-allowlist |

## Notas de estilo
- NO usar «BYO vendor fijo»: el webhook es trae-tu-propio-endpoint
  (Splunk/Cortex XSOAR son ejemplos, no socios nombrados).
- Mantener «Cero exfiltración de datos» junto al claim multi-UEM: el dato
  geoespacial se correlaciona en local, los secretos no salen de la máquina.
