# Canal CTO ↔ Marketing — Co-firma / Q&A de copy técnico (lado CTO)

Complemento del runbook de Marketing `docs/gtm/CTO_CO_SIGN.md` (que cubre la
secuencia del lado de Marketing: escribir borrador → pasar linter → abrir
tarjeta de co-firma). Este archivo fija el **lado CTO** del canal: cómo se
entra, cómo verifica el CTO, y qué saca. Es la fuente operativa para el perfil
`empresa-cto`.

Canal vivo anclado en kanban: **`t_a8252f28`** (card "standing" del canal).
Marketing abre **tarjetas hijas de `t_a8252f28`** para cada claim específico;
el CTO las co-firma (o bloquea) antes de publicar. Red line #110.

---

## 1. Punto de entrada (cómo llega una petición al CTO)

1. Marketing escribe el borrador en `docs/gtm/outbox/` y lo pasa por el linter
   (`python3.11 scripts/gtm_claim_linter.py --scope outbox --technical` →
   `0 BLOCK`). Ver `CTO_CO_SIGN.md` §Secuencia.
2. Marketing crea una **tarjeta hija de `t_a8252f28`**, asignada a
   `empresa-cto`, con: enlace al borrador, salida del linter (0 BLOCK), los
   claims a co-firmar anclados a la matriz #188 y a la guarda #110, y la
   petición explícita "verifica contra `origin/main` y co-firma (o bloquea)".
3. El CTO (cron o a demanda) reclama la tarjeta hija y ejecuta el SOP §2.

> No se publica nada sin la co-firma del CTO (Gate 0 de `MESSAGING_SIGNOFF.md`).
> Reincidir en el riesgo #110 sin co-firma → bloqueo por el CTO.

---

## 2. SOP de co-firma del CTO (al reclamar una tarjeta hija)

Verificar **siempre contra `origin/main`**, NUNCA contra la branch de
Marketing (`marketing-outbox-*`) — esa branch lleva float sin commitear del
agente y no es fuente de verdad.

Paso a paso:

1. **Leer el borrador** y listar sus claims técnicos fácticos (números,
   switches, rutas de código, claims de modo UEM/declarativo/SOAR).
2. **Verificar cada claim en `origin/main`** con grep/código real, anclando
   línea+archivo. No aceptar "lo dice la doc" — ver el runtime.
   - UEM/modo live → matriz #188 (`docs/gtm/...` / `.cto_input_188.md`).
   - Declarativo → solo DSC (Windows, build-only + read-back Graph) y DDM
     (Apple, build-only, geofence posture). Decision A de `t_2c00a8f2`.
   - SOAR webhook → `notifier.py` / `saas_server.py` HMAC-SHA256 por tenant.
3. **Correr el linter yo mismo** para confirmar `0 BLOCK` en el archivo:
   ```bash
   python3.11 scripts/gtm_claim_linter.py --scope outbox --technical
   ```
   Los `[INFO]` de reconciliación (p.ej. "Nunca Intune/Jamf live sin token")
   son correctos; cualquier `[BLOCK]` → corregir antes de firmar.
4. **Aplicar la guarda #110** (ver §3). Si hay infracción → bloquear la card
   con razón explícita; no co-firmar.
5. **Decidir salida:**
   - **(a) Co-firmar tal cual** → comentar en la tarjeta hija "CTO co-firma
     OTORGADA" + resumen de verificación, y marcar la card `done`.
   - **(b) Realinear wording y co-firmar** → editar el borrador al canónico,
     indicar qué cambió, comentar "CTO co-firma OTORGADA (wording realineado)",
     marcar `done`.
   - **(c) Bloquear** → `kanban_block` con la razón #110; la pieza no se publica.
6. **Siguiente paso** tras co-firma: owner gate (Adri publica el PR `outreach:`/
   outbox). El CTO no publica.

---

## 3. GUARDA #110 — quick reference (no negociable)

- NUNCA afirmar "Intune/Jamf live" incondicionalmente. "Live" solo al conectar
  el token del cliente; sin token → simulación.
- El webhook SOAR NO se vende como "egress RFC1918 bloqueado por defecto".
  Realidad en `origin/main` (commit `7c0e8d3`, `notifier.py`): firma
  HMAC-SHA256 por tenant (`X-LucidFence-Signature`) + cierre del DNS-rebinding
  TOCTOU en `_webhook_resolve` (bloquea pivotes reales loopback/link-local/
  metadata 169.254.0.0/16 en el connect). RFC1918/redes internas se PERMITEN a
  propósito por defecto (SIEMs self-hosted / on-prem); el bloqueo estricto de
  RFC1918 es opt-in (`EgressAllowListPolicy` modo `strict`). Claim honesto:
  "webhook BYO firmado HMAC-SHA256 por tenant, con anti-SSRF (cierre TOCTOU +
  bloqueo de pivotes cloud-metadata)". NUNCA afirmar "SSRF-hardened / egress
  RFC1918" como si bloqueara RFC1918 por defecto.
- Declarativo: SOLO Windows DSC (config) y Apple DDM (geofence posture,
  build-only). "lock" declarativo = postura de geocerca, NO comando de bloqueo.
  Android AMAPI: cero "declarativo" en público hasta builder #42 + tests verdes.
- Posicionamiento: 100% free OSS (Apache-2.0), $0, sin edición Enterprise pagada,
  sin open-core, sin on-prem cerrada.

## 4. Matriz UEM verificada (#188) — fuente de verdad

| UEM | Modo en el código | Claim honesto |
|---|---|---|
| **Applivery** | LIVE por defecto (Bearer key, sin rama mock) | live por defecto |
| **Intune** (Graph) | adapter LIVE, requiere token del cliente | live al conectar tu token |
| **Jamf** (Pro API) | adapter LIVE, requiere token del cliente | live al conectar tu token |
| (sin token) | caen a simulación (mock) | "simulación sin token" |

Claim canónico (verbatim, no inventar): *Multi-UEM simultáneo por tenant:
Applivery live por defecto; Intune/Jamf en modo live al conectar tu token
(simulación sin token). Cero exfiltración.*

**Regla de no-invención:** cualquier capacidad fuera de esta matriz (o fuera
de la decisión A de declarative `t_2c00a8f2`) NO se co-firma. Se bloquea o se
realinea al canónico.

---

## 5. Estado del canal (al 2026-08-22)

- Backlog de co-firma: **vacío** (0 tarjetas hijas pendientes).
- Piezas ya co-firmadas por el CTO:
  - `2026-08-21-blast-radius-uem.md` — `t_3ed8dedf` (co-firmada).
  - `2026-08-21-no-goals.md` (pts 4-5) — `t_7b575db8` (co-firmada, decisión A).
  - `2026-08-21-declarative-enforcement.md` — `t_1a407df5` (co-firmada,
    corregida a decisión A antes de firmar).
- Gate `gtm_claim_linter.py`: funcional (test negativo de control
  `TEC-WEBHOOK-SSRF` bloquea "SSRF-hardened/RFC1918", exit 1).
- Canal: operativo y explícito. Marketing abre hijas de `t_a8252f28` para
  nuevos claims; el CTO co-firma antes de publicar.

## 6. Referencias

- `docs/gtm/CTO_CO_SIGN.md` — runbook lado Marketing (secuencia, matriz, guarda).
- `docs/gtm/MESSAGING_SIGNOFF.md` — Gates 1 (técnico #188) y 2 (posicionamiento) + Gate 0.
- `docs/gtm/outbox/README.md` — RED LINE #110 + §HOLD declarativo.
- `.cto_input_188.md` — matriz UEM verificada y decisiones CTO.
- `scripts/gtm_claim_linter.py` — infra de gate.
- `t_2c00a8f2` — arbitraje CTO apply_dsc/apply_ddm (decisión A).
- Card del canal: `t_a8252f28`.
