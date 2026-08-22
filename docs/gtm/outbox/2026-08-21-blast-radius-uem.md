# El radio de explosión de tu UEM (X thread + LinkedIn)

> Borrador técnico para X / LinkedIn. Audiencia: CISO, IT ops, MSP.
> **NO publicable por el agente** — owner gate (Adri publica con copy/paste).
> **Estado: CTO co-firma PENDIENTE** (kanban: card de co-firma 2026-08-21, Marketing→CTO).
> Todos los claims de código verificados por Marketing contra `origin/main` hoy
> 2026-08-21 (rutas y líneas citadas abajo, en "Anexo de verificación").
> Cero claims declarativos de entrega (evita la disputa abierta DDM/DSC).

---

## Contexto real de industria (por qué este thread, hoy)

Señales públicas rastreadas hoy (Hacker News, orden cronológico):
- **2026-03-11** — "Stryker Hit by Handala – Intune Managed Devices Wiped" (58 comentarios).
- **2026-03-20** — "Lock down Microsoft Intune, feds warn after Stryker attack".
- **2024-12-26** — "TokenSmith – Bypassing Intune Compliant Device Conditional Access".

El patrón de 2026 no es "me falta un MDM". Es: **el plano de control que puede
borrar tu flota se ha convertido en el objetivo**, y la señal de "dispositivo
conforme" es falsificable. Ese es el hueco que ocupamos, y es el ángulo con
tracción real, no un ángulo inventado.

---

## X / Twitter — thread (7 tweets)

**1/**
En marzo, un atacante entró al Intune de una multinacional y **wipeó dispositivos
gestionados**. Semanas después, la agencia federal recomendó "asegurar Intune".

La lección incómoda: la herramienta que protege tu flota es también la que puede
borrarla en un clic.

**2/**
Casi todo el mercado UEM optimiza para "más acciones remotas, más rápido".
Nadie optimiza para lo contrario: **que una acción destructiva sea difícil de
disparar por accidente o por un atacante con tu sesión.**

**3/**
LucidFence trata `wipe`, `lock`, `clear_passcode` y `reboot` como lo que son:
irreversibles.

En sus playbooks automáticos, esas 4 acciones **no se ejecutan solas**: quedan
pausadas esperando aprobación humana (`human_gate`). El playbook se detiene, no
se "sigue con cuidado".

**4/**
Y cuando sí se ejecutan, la misma acción sobre el mismo dispositivo entra en
**cooldown persistido** (1h por defecto, configurable) que **sobrevive a un
reinicio del proceso**.

Un bucle de automatización roto no puede wipear 400 móviles en 400 segundos.

**5/**
Cada evento sale hacia el SIEM que YA usas por webhook **firmado HMAC-SHA256 por
tenant** (`X-LucidFence-Signature: sha256=…`, comparación en tiempo constante).

No hay "nuestra nube" en el medio. Es tu SIEM, tu clave, tu registro.

**6/**
Y el dato que nadie quiere ceder: **la ubicación de tu flota**.

El motor de geocercas corre en tu máquina; los datos del tenant se quedan ahí.
Multi-UEM simultáneo por tenant: **Applivery live por defecto; Intune/Jamf pasan
a live al conectar TU token** (simulación sin token). Cero exfiltración.

**7/**
Coste: **$0**. Apache-2.0, sin tier de pago, sin "pide una demo".

Si tu geofencing hoy depende de mandar la posición de tus empleados a un SaaS de
terceros, hay otra forma:
→ github.com/adrimg3196/lucidfence

---

## LinkedIn — versión larga (misma tesis, tono CISO)

**El riesgo del que no se habla en UEM no es la cobertura. Es el radio de explosión.**

En 2026 vimos las dos mitades del problema en la misma plataforma: un ataque que
llegó a **wipear dispositivos gestionados por Intune**, y una advertencia federal
posterior pidiendo endurecer esa misma consola. Añade a eso la investigación
pública sobre **bypass de la señal "dispositivo conforme"** en Conditional Access,
y el resumen es sencillo: tratamos al plano de control como infraestructura de
confianza cuando ya es superficie de ataque.

LucidFence es un plano de control de geocercas que se sienta SOBRE el UEM que ya
tienes (vía adapters), con tres decisiones de diseño deliberadamente aburridas:

1. **Las 4 acciones irreversibles están human-gated en automatización.**
   `wipe`, `lock`, `clear_passcode`, `reboot` no las dispara un playbook por su
   cuenta: se pausan para aprobación humana explícita.
2. **Cooldown persistido para acciones destructivas.** Una vez ejecutada, la misma
   acción sobre el mismo dispositivo queda en ventana de enfriamiento (1h por
   defecto) que sobrevive a reinicios. El fallo de automatización no escala.
3. **La ubicación no sale de tu infraestructura.** El motor corre local; la
   evidencia viaja firmada (HMAC-SHA256 por tenant) al SIEM que ya operas.

Multi-UEM con la matriz honesta: Applivery live por defecto; Intune/Jamf en modo
live al conectar tu token (simulación sin token).

Precio: $0, Apache-2.0. No hay edición Enterprise esperándote detrás del formulario.

¿Tu política de geofencing sobreviviría a que la consola que la aplica esté
comprometida? Esa es la pregunta que intentamos hacer barata de responder.

→ github.com/adrimg3196/lucidfence

---

## Anexo de verificación (para la co-firma del CTO)

| Claim del copy | Evidencia en `origin/main` (2026-08-21) |
|---|---|
| 4 acciones destructivas | `engine.py:649` → `DESTRUCTIVE_ACTIONS = {"wipe","lock","clear_passcode","reboot"}` |
| human-gate en playbooks | `engine.py:568` (comentario de diseño) + `engine.py:594-606` → `"human_gate": True`, nota "accion destructiva pausada para aprobacion manual (SOAR human-gate)" |
| cooldown persistido 1h por defecto | `engine.py:106` → `action_cooldown_seconds` default `3600`; `engine.py:797-850` → "Destructive actions additionally respect a persisted cooldown window" |
| webhook HMAC-SHA256 por tenant | `notifier.py:576` header `X-LucidFence-Signature: sha256=<hex>`; `notifier.py:594` (`hmac.new(...sha256)`) y `notifier.py:600` (`hmac.compare_digest`) |
| matriz multi-UEM con matiz | RED LINE #110 de `outbox/README.md`, wording verbatim |
| $0 / Apache-2.0 | `revenue-model.md` + LICENSE Apache-2.0 verbatim (cerrado en #201/#202, kanban `t_abe702e7`) |

**Claims deliberadamente AUSENTES de esta pieza** (para no tocar la disputa
abierta): nada de "declarativo", nada de "end-to-end", nada de Android, nada de
DDM/DSC. Si el CTO quiere añadir el ángulo declarativo, va en la pieza
`2026-08-21-declarative-enforcement.md`, que está **en HOLD** hasta que se
resuelva la contradicción fáctica sobre `apply_dsc`.

**Fuentes externas citadas** (públicas, verificables en Hacker News):
Stryker/Handala Intune wipe (2026-03-11), aviso federal post-Stryker (2026-03-20),
TokenSmith / bypass de Compliant Device (2024-12-26).
