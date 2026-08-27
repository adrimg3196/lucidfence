# CTO Co-Signatura OBLIGATORIA — copy técnico nuevo

Proceso vinculante del canal CTO (tarjeta kanban `t_c120cc9b`, 2026-08-21).

> **Regla:** Toda pieza técnica **NUEVA** que toque cualquiera de estos ejes
> debe pasar por **co-firma del CTO** (perfil `empresa-cto`, vía kanban) **antes**
> de que el propietario (Adri) la publique:
>
> - **Blast-radius UEM** (acciones destructivas, human-gate, cooldown, multi-UEM).
> - **No-goals / honesty** (qué NO hace el producto, incl. matiz multi-UEM y Android).
> - **Declarative enforcement** (DDM/DSC/AMAPI). ← resuelto por arbitraje `t_2c00a8f2` (decisión A): DSC build-only + read-back Graph (NO end-to-end); pieza co-firmada y apta para owner gate.
> - **SOAR** (webhook BYO, playbooks, matched_fields).
>
> Esto es **adicional** a los Gates 1 y 2 de `MESSAGING_SIGNOFF.md`. El linter no
> sustituye la co-firma: el CTO verifica contra el código/runtime y da el visto
> bueno (o lo bloquea). Reincidir en el riesgo #110 sin co-firma es motivo de
> bloqueo por el CTO.

---

## REGLA 0 — no se redacta un claim sin anclaje (añadida 2026-08-25)

**Un claim técnico sin evidencia de código NO se redacta, ni siquiera marcado.**

Origen: el 2026-08-25 Marketing autodetectó un claim **falso** en su propio borrador del
día anterior (`docs/internal/gtm/SOCIAL_2026-08-24.md`): un *"double-key wipe"* que no
existe en el código (0 coincidencias de `double.?key|dual.?key|two.?person` en
`lucidfence/`), y que implicaba resistencia a un admin comprometido que el producto no
tiene. Riesgo #110. Post-mortem: `docs/internal/gtm/CORRECTION_2026-08-25-double-key-wipe.md`.

Causa raíz: el borrador se autoetiquetó `⚠️CTO (co-sign)` y siguió adelante redactando el
claim **como si fuera cierto**, dejando la verificación para después. El marcador se usó
como **pagaré**, no como freno — y el mismo borrador declaraba que no tenía acceso a
kanban, así que el pagaré nunca se iba a cobrar.

Reglas que se derivan:

1. `⚠️CTO` sirve para **matizar un claim ya anclado** (fichero+línea), **nunca para
   sostener uno inventado**. Si no hay anclaje, se escribe el hueco:
   `[claim de guardarraíl de wipe — pendiente de anclaje del CTO]` + la tarjeta hija.
2. Todo borrador técnico lleva un **inventario de claims → anclaje** (tabla claim /
   fichero:línea). Sin inventario no se pide co-firma. Plantilla de referencia:
   `docs/gtm/outbox/2026-08-25-network-location-geofencing.md` §3.
3. **Sin shell no hay excusa.** Un runtime de cron sin terminal (no puede correr
   `gtm_claim_linter.py` ni `verify.py`) **sí** puede grepear el paquete con herramientas
   de fichero. La verificación del 2026-08-25 se hizo así. Falta de shell ⇒ se declara
   "linter NO ejecutado" y el borrador queda pre-co-firma; **no** ⇒ licencia para escribir
   de memoria.
4. Solo se reclaman UEMs de la **matriz #188** (Applivery / Intune / Jamf). `fleet.py`,
   `chromeos.py` y `workspace_one.py` existen en disco pero **sin estado live/mock
   co-firmado** → no reclamables.
5. El **matiz RED LINE #110 es obligatorio y verbatim** en toda pieza que mencione
   multi-UEM. No es opcional ni parafraseable.
6. Copy vivo **solo** en `docs/gtm/outbox/`. Nada de copy destinado a publicación en
   `docs/internal/`.

---

## Secuencia obligatoria (Marketing)

1. **Escribir el borrador** en `docs/gtm/outbox/` (NO en `launch-copy/`, NO en docs
   SUPERSEDED). Header del borrador: marca `Estado: CTO co-firma PENDIENTE`.
2. **Pasar el Gate del linter** (POSITIONING + técnico #188):
   ```bash
   python3.11 scripts/gtm_claim_linter.py --scope outbox --technical
   ```
   Debe dar `0 BLOCK`. Solo se permiten `[INFO]` de reconciliación (p.ej. el
   matiz honesto "Nunca Intune/Jamf live sin token"). Cualquier `[BLOCK]` → corregir.
   Evidencia verificada 2026-08-21 (outbox limpio): `0 BLOCK, 3 INFO`, exit 0.
   Test negativo de control: un borrador con "webhook SSRF-hardened RFC1918" →
   `[BLOCK] TEC-WEBHOOK-SSRF`, exit 1. El gate funciona.
3. **Crear tarjeta de co-firma** en kanban, asignada a `empresa-cto`, con:
   - enlace al borrador (`docs/gtm/outbox/<archivo>.md`),
   - salida del linter (`0 BLOCK`),
   - los claims a co-firmar, anclados a la matriz #188 y a la guarda #110,
   - petición explícita: "verifica contra `origin/main` y co-firma (o bloquea)".
   Patrón previo validado: `t_5471f0a3` → hijo `t_1a407df5`; `t_5e8c5bfe`.
4. **Esperar co-firma del CTO.** El CTO puede: (a) co-firmar tal cual, (b) realinear
   el wording al canónico y co-firmar, o (c) bloquear por riesgo #110.
5. **Solo tras co-firma → owner gate.** Adri aprueba el PR `outreach:` / outbox y
   publica. Sin co-firma del CTO, el agente NO publica.

---

## Matriz UEM verificada (#188) — fuente de verdad

De `.cto_input_188.md` (Decisión 4), verificada en runtime por el CTO:

| UEM | Modo en el código | Claim honesto |
|---|---|---|
| **Applivery** | LIVE por defecto (Bearer key, sin rama mock) | live por defecto |
| **Intune** (Graph) | adapter LIVE implementado, requiere token del cliente | live **al conectar tu token** |
| **Jamf** (Pro API) | adapter LIVE implementado, requiere token del cliente | live **al conectar tu token** |
| (sin token) | caen a **simulación** (mock) | "simulación sin token" |

**Claim canónico (usar verbatim, no inventar):**
> Multi-UEM simultáneo por tenant: **Applivery live por defecto**; **Intune/Jamf en
> modo live al conectar tu token** (simulación sin token). Cero exfiltración.

**Webhook SOAR:** BYO endpoint firmado **HMAC-SHA256 por tenant**
(`X-LucidFence-Signature: sha256=…`), dirigido al SIEM que ya uses. El hardening
real es la firma por tenant (`notifier.py` / `saas_server.py`). El egress RFC1918 /
DNS-rebinding (`PublicEgressPolicy`) **SOLO** existe en `oidc.py` (fetch IdP OIDC),
no en el webhook de salida. El webhook permite SIEMs internos por diseño.

---

## GUARDA #110 — no negociable (red line)

1. **NUNCA** afirmar "Intune/Jamf live" **incondicionalmente**. Toda afirmación
   "live" se ancla a la matriz: live solo al conectar el token del cliente.
2. **NUNCA** decir que el webhook SOAR es "SSRF-hardened / egress RFC1918". El
   hardening real es firma HMAC-SHA256 por tenant.
3. **Declarative:** solo Windows DSC (config) y Apple DDM (geofence posture,
   build-only). "lock" declarativo = postura de geocerca, NO comando de bloqueo.
   Android AMAPI: **cero** "declarativo" en público hasta builder #42 + tests verdes.
4. **Posicionamiento de negocio:** 100% free OSS (Apache-2.0), $0, sin edición
   Enterprise pagada, sin open-core, sin on-prem cerrada (Gate 2 del sign-off).

---

## Estado actual del outbox (2026-08-21)

| Pieza | Eje | Linter | Co-firma CTO |
|---|---|---|---|
| `2026-08-21-blast-radius-uem.md` | blast-radius UEM | 0 BLOCK / 1 INFO | **enrutada** (ver tarjeta co-firma) |
| `2026-08-21-no-goals.md` | no-goals (multi-UEM + Android #42) | 0 BLOCK / 1 INFO | **CO-FIRMADA** (`t_7b575db8`; pts 4-5 confirmados por arbitraje `t_2c00a8f2` decisión A) |
| `2026-08-21-declarative-enforcement.md` | declarative | 0 BLOCK / 1 INFO | ⛔ **HOLD ENGINE-LEVEL (t_0d04cdd0, 2026-08-23)**: co-firma CTO previa (`t_1a407df5`) supersededida para el claim de engine; en la rama de publicación `engine.run_command` es imperativo (engine.py sin gate declarativo). Solo el orquestador multi-UEM enruta declarativamente. Re-co-firmar tras #89. El claim de orquestador multi-UEM declarativo sigue válido. |
| `2026-08-20-x-thread.md` (**P2**, technical thread) | SOAR + multi-UEM | 0 BLOCK / 0 INFO (P2 limpia) | **CO-FIRMADA** (`t_f250e47e`, 2026-08-22; claims 1-6 verificados vs `origin/main`; matiz #110 respetado: live solo al conectar token + webhook HMAC-SHA256 por tenant) → owner gate |

---

## Referencias

- `docs/gtm/CTO_CHANNEL.md` — **lado CTO del canal**: cómo entran las peticiones
  (tarjetas hijas de `t_a8252f28`), SOP de co-firma del CTO y guarda #110.
- `docs/gtm/MESSAGING_SIGNOFF.md` — Gates 1 (técnico #188) y 2 (posicionamiento).
- `docs/gtm/outbox/README.md` — RED LINE #110 + §HOLD declarativo.
- Card del canal (standing): **`t_a8252f28`** — Marketing abre hijas aquí para
  cada claim; el CTO co-firma antes de publicar.
- `.cto_input_188.md` — matriz UEM verificada y decisiones CTO.
- Patrón de co-firma: `t_5471f0a3` (matriz declarativa) → `t_1a407df5`; `t_5e8c5bfe`.
- Infra de gate: `scripts/gtm_claim_linter.py`.
- Linter (negativo de control): `TEC-WEBHOOK-SSRF` bloquea "SSRF-hardened/RFC1918";
  `TEC-INTUNE-LIVE` bloquea "Intune/Jamf live" incondicional (salvo contexto de
  negación → INFO).
