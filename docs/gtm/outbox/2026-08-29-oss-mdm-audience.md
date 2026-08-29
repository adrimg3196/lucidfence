---
platform: X/Twitter (thread) + LinkedIn (CISO/MSP / open-source MDM operators)
format: thread (7 tweets) + LinkedIn long-form variant
status: draft (owner gate — no agent publish)
positioning_directive: "comparación > marca desnuda" (gate #317 cerrado, t_190e48e9)
new_audience: operadores de MDM open-source (Fleet / NanoMDM / MicroMDM / Headwind / Entgra)
cto_cosign: NO REQUIRED — reusa claims co-firmados (#110, #188, t_389cc434, t_c48380ae);
  el ángulo de copy está APROBADO por Product (esta tarea). Sin claim técnico NUEVO.
claims_source: origin/main verificado (fleet.py, engine.py:297, static/index.html)
repo: https://github.com/adrimg3196/lucidfence
---

# Para quien ya corre un MDM open-source y no puede comprar geofencing en ninguna parte

> Ángulo aprobado (Product, 2026-08-29): **"no somos otro MDM; somos la capa de
> geofencing y riesgo explicable que le falta al tuyo."**
> Regla de posicionamiento: comparación > marca desnuda (Lucid Motors domina "Lucid").

## X/Twitter thread

**1/7** Corres Fleet, NanoMDM o MicroMDM porque querías control sin vendor-lock ni
factura. Pero ninguno de ellos hace geofencing. Ni riesgo que se explique. LucidFence
no es otro MDM: es la capa de geofencing y riesgo explicable que le falta al tuyo.
👉 github.com/adrimg3196/lucidfence

**2/7** El modelo es "sobre lo que ya tienes". LucidFence se enchufa a tu UEM actual
vía adapters en vez de reemplazarlo. Hoy ships un adapter de **Fleet** (live con tu
`FLEET_API_TOKEN`, mock sin él). Intune/Jamf en modo live al conectar tu token
(simulación sin token). Cero exfiltración: el perímetro es tuyo.

**3/7** Geofencing local-first. No mandamos la ubicación de tu flota a la nube del
vendor (ese es el problema de cumplimiento que los MDM nativos resuelven enviando
tus coordenadas a SU nube). LucidFence geofencea donde están tus datos: en tu máquina.

**4/7** El riesgo de un dispositivo no debería ser una caja negra. LucidFence da un
score 0-100 CON la razón de cada alerta cuando hay señal que lo respalda. Sin señal,
el dispositivo queda como "Riesgo desconocido (sin señal)" — nunca un falso verde.
No adivina: explica por qué.

**5/7** Evidence gate (anti-overclaim): un hallazgo solo cuenta si lo respalda una
señal real. Sin señal, no hay score. Por diseño, no por promesa. Para quien ya audita
código: el engine es Apache-2.0 y el sentinel honesto está en `engine.py`.

**6/7** Y no solo alerta: SOAR declarativo ya en runtime. 4 playbooks frontline (CVE
crítico, CVE+fuera de perímetro, no-conforme+fuera, EPSS alto) + auditoría por
dispositivo. Webhook BYO a tu Splunk/Cortex XSOAR, firmado HMAC-SHA256 por tenant.

**7/7** 100% open-source y gratis para auto-hospedar: $0, sin asientos, sin telemetría,
sin cuenta. On-prem por diseño. Si ya corres un MDM open-source, la pieza que te falta
está aquí 👉 github.com/adrimg3196/lucidfence

## LinkedIn (long-form, mismo público)

Título: "Tu MDM open-source hace todo menos geofencing. Aquí está la capa que le falta."

Cuerpo:

Si auto-hospedas Fleet, NanoMDM o MicroMDM, ya resolviste lo caro: controlas el
endpoint, auditas el código, y no pagas por asientos. Lo que esos proyectos NO hacen
es geofencing ni riesgo explicable. No porque no importen — porque no es su alcance.

LucidFence no compite con ellos. Es la capa que se pone *encima* de tu UEM:

• **Geofencing local-first.** Sin enviar la ubicación de tu flota a la nube de un
  vendor. El perímetro es tuyo, los datos se quedan en tu máquina.
• **Riesgo explicable, no caja negra.** Score 0-100 con la razón de cada alerta
  cuando hay señal. Sin señal → "Riesgo desconocido (sin señal)", nunca falso verde.
• **Sobre lo que ya tienes.** Adapter de Fleet ships hoy (live con tu token, mock sin
  él). Intune/Jamf en modo live al conectar tu token (simulación sin token). Multi-UEM,
  agnóstico por adapters.
• **SOAR declarativo + BYO webhook** firmado HMAC-SHA256 por tenant hacia el SIEM que
  ya uses.
• **$0, sin telemetría, sin cuenta, Apache-2.0.** On-prem por diseño.

Si ya corres un MDM open-source, no necesitas migrar a un SaaS de pago para tener
geofencing. La capa que te falta es open-source también.

github.com/adrimg3196/lucidfence

---

## Claims → anclaje (REGLA 0, verificado en origin/main)

| Claim | Anclaje en origin/main (verificado) |
|---|---|
| Adapter de Fleet ships (live con token, mock sin él) | `lucidfence/core/adapters/fleet.py` (clase `FleetAdapter`, `_ensure_token`/`execute` live+mock) |
| Multi-UEM agnóstico por adapters | `lucidfence/core/adapters/` (applivery, intune, jamf, fleet, chromeos, windows_conformidad, workspace_one) + `adapter_marketplace.py` |
| Geofencing local-first / sin exfiltración | `static/index.html` trust-band "Soberano: tus datos no salen de tu máquina" |
| Riesgo explicable 0-100 + "Riesgo desconocido (sin señal)" | `engine.py:297` (sentinel, origin/main 3c6ef66/c8e264c) — co-firmado t_389cc434 |
| Evidence gate | copy co-firmado `2026-08-20-x-thread.md` (t_f250e47e) |
| SOAR 4 playbooks + webhook BYO HMAC-SHA256 por tenant | `.cto_input_188.md` Decisión 1 + 3 (co-firmado t_c48380ae) |
| $0 / sin telemetría / sin cuenta / Apache-2.0 | `LICENSE` (Apache-2.0) + `static/index.html` |

## Guardas (no negociables, #110 / tarea)

- ❌ NO afirmo integración con **NanoMDM/MicroMDM/Headwind/Entgra** (hoy solo el
  adapter de Fleet es real en origin/main; los demás son mencionados como "lo que el
  MDM open-source no hace", no como integraciones LucidFence). La superficie de
  integración existe (contrato `MDMAdapter` congelado, plugin-indexable) pero los
  adapters no están construidos.
- ❌ NO implico que el score esté siempre disponible: puede devolver "desconocido
  (sin señal)" (t_389cc434).
- ❌ NO implico pricing/Enterprise/on-prem cerrada (linter 0 BLOCK).
- ⛔ Outreach a terceros (directorios, listicles, LibHunt, Jamf Marketplace) sigue bajo
  GATE PROPIETARIO humano t_41be699d. Este es solo borrador de contenido; no se publica.

## Linter gate (ejecutar antes de owner gate)

```bash
python3.11 scripts/gtm_claim_linter.py docs/gtm/outbox/2026-08-29-oss-mdm-audience.md --technical
→ esperado: 0 BLOCK
```
