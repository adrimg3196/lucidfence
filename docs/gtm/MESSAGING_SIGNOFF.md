# Sign-off de messaging — LucidFence

Proceso vinculante de revisión de **cualquier copy público** (borradores de
Growth/Marketing, posts, README, Pages, one-pagers) antes de que el propietario
lo apruebe y publique. Cierra el riesgo de integridad pública **#110**.

Este doc es la fuente de verdad del *proceso*. El copy aprobado vivo está en
`docs/gtm/outbox/`; el posicionamiento de modelo de negocio está en
`docs/gtm/revenue-model.md` + `docs/internal/STATE.md` (override 2026-08-16).

## Por qué existe (origen)

- Riesgo de integridad **#110**: copy público que contradice la decisión del
  propietario y el código.
- Coordinación **`t_0a1ba0d1`** (kanban) + `docs/internal/self-improvement/
  COORD_TASK_launchcopy-enterprise.md`: Marketing consultó a CTO/PM sobre
  claims **TÉCNICOS** de #188, pero el claim de **MODELO DE NEGOCIO** (tier
  pagado / open-core / "Enterprise on-prem cerrado") NO pasó por ese protocolo
  y reincidió en `launch-copy/`, contradiciendo la decisión del dueño.
- Tarjeta de cierre de proceso: **`t_1def7405`** (CTO) — añadir al sign-off un
  scan de la copia por RE-INTRODUCCIÓN de posicionamiento descartado, no solo
  matiz técnico.

## Gate 0 — Co-firma CTO OBLIGATORIA para copy técnico NUEVO  [t_c120cc9b]

Para cualquier pieza técnica **NUEVA** (blast-radius UEM, no-goals, declarative,
SOAR), además de los Gates 1 y 2 abajo, es **obligatoria la co-firma del CTO**
(perfil `empresa-cto`, vía kanban) **antes** de la aprobación del propietario. El
linter (Gates 1/2) no sustituye esta co-firma: el CTO verifica contra
`origin/main` y da el visto bueno o lo bloquea (riesgo #110).

Proceso y matriz #188 canónica: **`docs/gtm/CTO_CO_SIGN.md`**.

Secuencia (Marketing): escribir borrador en `outbox/` → `gtm_claim_linter.py
--scope outbox --technical` (0 BLOCK) → crear tarjeta de co-firma a `empresa-cto`
con el borrador + salida del linter + claims anclados a #188/#110 → esperar
co-firma → solo entonces owner gate. Sin co-firma del CTO, el agente NO publica.

## Dos gates (ambos obligatorios)

### Gate 1 — Matiz TÉCNICO (#188)  [ya existente]
Verifica que los claims técnicos estén anclados a evidencia de runtime
(`.cto_input_188.md` + `verify.py`). RED LINE en `docs/gtm/outbox/README.md`:
- NO decir "Intune/Jamf live" incondicionalmente (requiere token del cliente).
- Webhook SOAR: firma HMAC-SHA256 por tenant (`X-LucidFence-Signature`), NO
  "egress SSRF-hardened / RFC1918" (eso vive solo en `oidc.py`).

### Gate 2 — Posicionamiento de MODELO DE NEGOCIO descartado  [NUEVO — t_1def7405]
Escanea el borrador por frases de posicionamiento que el dueño descartó y que
están **prohibidas en cualquier superficie pública**.

**Fuente de verdad del posicionamiento:**
- `docs/gtm/revenue-model.md` (2026-07-27, canónica): *"Sustituye al modelo
  open-core anterior (freemium → Pro → Enterprise), descartado por decisión del
  propietario."* + "Coste 0 estricto: solo free tiers."
- `docs/internal/STATE.md` override (2026-08-16): *"100% free open source. Sin
  pricing, sin edición enterprise, sin funciones de pago, sin telemetría."*
- Código: SOAR (`core/soar.py`) + SSO OIDC (`saas/oidc.py`) ya son libres en
  `main`. El producto es **100% free OSS (Apache-2.0)**.

**Frases PROHIBIDAS (posicionamiento descartado) — NUNCA en copy vivo:**

> Recuerda: todas las frases de abajo están prohibidas por decisión del dueño;
> el SOP solo las lista para que el revisor las detecte y bloquee en el gate.

- NUNCA menciones a tier/edición Enterprise pagada ni open-core (sin capas de pago cerradas).
- NUNCA on-prem cerrada, SOAR/SSO/escala solo enterprise, ni acceso anticipado a capas on-prem.
- NUNCA pricing, planes de pago, managed/servicio gestionado como captura, ni que te vendan un UEM gestionado.
- NUNCA el framing Free / Pro / Enterprise.

**Cómo ejecutar el scan (CTO / CEO en el gate de outreach):**

```bash
# copy canónico (outbox/, excluye README.md propio):
python3.11 scripts/gtm_claim_linter.py --scope outbox

# un borrador concreto (o varios):
python3.11 scripts/gtm_claim_linter.py docs/gtm/outbox/2026-08-20-x-thread.md

# incluir también el matiz técnico #188 (Gate 1):
python3.11 scripts/gtm_claim_linter.py --scope outbox --technical
```

- Exit `0` = sin `[BLOCK]` → copy apto para aprobación del propietario.
- Exit `1` = al menos un `[BLOCK]` de posicionamiento → **corregir antes de
  publicar**.
- Las referencias que aparecen en contexto de reconciliación (banners
  RECONCILIADO / SUPERSEDED, "fue eliminado", "descartado") se marcan `[INFO]`
  y no bloquean — pero el revisor debe confirmar que NO son copy vivo.

> Los docs GTM legacy (`marketing-copy.md`, `launch-plan.md`, `PRODUCT_BRIEF.md`,
> `ACQUISITION_NARRATIVE.md`, `VALIDATION_SCRIPT.md`, `launch-copy/*`) siguen
> conteniendo estas frases y están marcados **SUPERSEDED** (pre-2026-07-27). El
> linter las flagga a propósito: son un landmine documentado, no copy canónico.
> Nunca se usan para outreach. El linter sobre `outbox/` (copy limpio) debe dar
> `0 BLOCK`.

## Checklist de sign-off (todo borrador)

- [ ] **Gate 1 (técnico):** claims #188 anclados a evidencia runtime; cumple
      RED LINE de `outbox/README.md`.
- [ ] **Gate 2 (posicionamiento):** `gtm_claim_linter.py` sobre el borrador da
      `0 BLOCK` (o únicamente `[INFO]` de reconciliación revisados).
- [ ] El borrador no reintroduce posicionamiento de pago/open-core/enterprise.
- [ ] Copy vivo solo en `docs/gtm/outbox/`; nada de `launch-copy/` ni docs
      SUPERSEDED.
- [ ] El propietario (Adri) aprueba el PR `outreach:` (o el outbox) → solo
      entonces se publica.

## Referencias cruzadas

- `t_0a1ba0d1` — reconciliación de `launch-copy/` (cierra riesgo #110 para esos
  docs; "100% free OSS", $0, donaciones).
- `t_1def7405` — esta tarjeta: cierre del GAP de PROCESO (scan de
  posicionamiento descartado en el sign-off).
- `docs/internal/self-improvement/COORD_TASK_launchcopy-enterprise.md` — root
  cause y pasos originales (paso 3 = este Gate 2).
- Fuente de verdad de posicionamiento: `docs/gtm/revenue-model.md` +
  `docs/internal/STATE.md` (override 2026-08-16).
- Linter: `scripts/gtm_claim_linter.py`.
