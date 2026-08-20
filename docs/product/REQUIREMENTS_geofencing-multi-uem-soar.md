# Product Requirements — Geofencing Multi-UEM + SOAR (LucidFence)

- **Owner:** Product (`empresa-product`)
- **Status:** Draft v1 — entregado a CTO (impl) y Marketing (mensaje)
- **Fecha:** 2026-08-20
- **Diseño de ingeniería aprobado (fuente):** `docs/superpowers/specs/2026-07-22-multi-uem-geofencing-design.md`
- **Plan de implementación (fuente):** `docs/superpowers/plans/2026-07-22-multi-uem-geofencing.md`
- **Bloquea:** `t_3109be4f` (CTO: adapter geofencing multi-UEM)
- **Alimenta:** Marketing pitch "geofencing multi-UEM + SOAR"

> Este documento es la capa de **requisitos de producto** (el *qué* y el *porqué*).
> No reitera el diseño técnico ya aprobado; lo referencia. El CTO implementa contra
> ambos. Marketing reusa la sección 2–6 para el mensaje, sin inventar capacidades.

---

## 1. Problema y objetivo de producto

Las organizaciones con flotas móviles ya no usan un solo UEM: grandes cuentas corren
**Intune** (Windows/corporativo), **Jamf** (Mac), **Applivery** (Android/kiosk/field) e
incluso **Workspace ONE** en paralelo. Hoy LucidFence soporta cada UEM, pero un tenant
solo puede activar **uno** a la vez. Eso fragmenta la visión de riesgo y obliga al equipo
de seguridad a abrir varias consolas para saber "dónde está cada dispositivo y por qué
está en riesgo".

**Objetivo del producto:** que un mismo tenant de LucidFence controle geofencing y riesgo
sobre **toda su flota consolidada**, venga de donde venga, y responda automáticamente
(**SOAR**) con playbooks declarativos, sin exfiltrar datos y sin ejecución destructiva
implícita.

**Principios innegociables (heredados del diseño aprobado):**
1. Local-first / soberanía: los datos y secretos del tenant nunca salen de su disco.
2. Evidencia antes de geometría: una ubicación dudosa es `unknown`, nunca `outside`.
3. Acciones destructivas (`wipe`, `lock`, `clear_passcode`, `reboot`) siempre human-gated.
4. Proveedor caído = degradación parcial, nunca fallo total ni vaciado de flota.
5. Multitenant real: hosted y local corren el mismo orquestador, misma semántica.

---

## 2. Personas objetivo

| Persona | Necesidad principal | Qué gana con Multi-UEM |
|---|---|---|
| **SOC Analyst / SecOps** | Una sola cola de incidentes de flota, priorizada por riesgo | Ve dispositivos de Intune+Jamf+Applivery en un solo Risk Center; playbooks SOAR disparan desde ahí |
| **IT Admin (MSP)** | Gestionar varios clientes, cada uno con su UEM mixto | Un tenant por cliente, flota consolidada, sin mezclar credenciales |
| **CISO / Auditor** | Trazabilidad: señal → score → playbook → auditoría | Cada decisión SOAR lleva `matched_fields` y procedencia por dispositivo |
| **Field Ops Manager** | Saber si un dispositivo de campo salió del perímetro | Geovallas sobre la flota real de Applivery/Jamf, no sobre un subconjunto |

---

## 3. UEMs soportados (matriz de producto)

La matriz de capacidades es la fuente de verdad para la UX: **el producto no ofrece una
acción que el UEM no soporte**. (Confirmada contra el plan de implementación aprobado.)

| UEM | Inventario | Ubicación | Geovallas nativas | Acciones UEM | Modo live en v1 | Notas de producto |
|---|---|---|---|---|---|---|
| **Applivery** | ✅ | ✅ (tras hardening) | ❌ | ⚠️ pendiente de validar endpoint | ✅ | Conector principal Android/kiosk/field. Acción nativa bloqueada hasta validar endpoint undocumented. |
| **Intune** (Microsoft Graph) | ✅ | ❌ | ❌ | ✅ (Graph) | ✅ | Windows/corporativo. No aporta ubicación → geofencing se basa en evidencia de otros proveedores o simulación. |
| **Jamf** (Jamf Pro API) | ✅ | ❌ | ❌ | ✅ | ✅ (tras validación tenant-host) | Mac. Live solo tras validación de host público; si no, no se simula como live. |
| **Workspace ONE** | ✅ | ❌ | ❌ (export de perfil ≠ geovalla nativa) | ✅ | ✅ (tras validación host) | Solicitado por el mercado. |
| **ChromeOS** | ✅ | ❌ | ❌ | ❌ | ✅ | Report/inventory only. |
| **Windows (conformidad)** | ✅ | ❌ | ❌ | ❌ | ✅ | Report-only; se desactiva si Intune ya aporta el mismo inventario Windows. |
| **Simulation** | ✅ | ✅ | ✅ | dry-run | ✅ (demo local) | Demo 100% local, sin red. |

**Regla de producto para v1:** al menos **dos** de {Intune, Jamf, Applivery} deben poder
activarse **simultáneamente** en un mismo ciclo de un tenant (criterio de aceptación del
diseño). El resto quedan como live opt-in tras validación.

**Compatibilidad legacy:** un tenant con un solo proveedor configurado (o sin
`uem.providers`) conserva el comportamiento actual, sin nuevos campos visibles.

---

## 4. Features clave (nivel producto)

1. **Consolidación de flota con procedencia.** El mismo dispositivo que aparece en dos
   UEM (mismo serial/IMEI válido) se muestra **una vez**, con `provider_refs` y
   procedencia por campo. Ambigüedad = registros separados + flag de conflicto visible.
2. **Selección determinista de mejor ubicación.** Entre varias fuentes, se elige por
   frescura → precisión → prioridad declarada. Stale/imprecisa/futura → `unknown`.
3. **Salud Multi-UEM por proveedor.** Vista tenant-authenticated: proveedores activos,
   última sync, nº de dispositivos, capacidades, errores sanitizados, cobertura de
   ubicación apta/no apta. Una flota parcialmente sincronizada **nunca** se presenta como
   completa.
4. **Enrutado de acción al dueño.** Toda acción UEM se ejecuta contra el `provider_device_id`
   correcto, vía el adapter de ese UEM. No se deduce la acción desde el `canonical_id`.
5. **Risk Engine sobre flota consolidada.** Score 0–100 con `reasons` + `provenance`, ya
   explicable, ahora alimentado por la flota multi-UEM.
6. **SOAR declarativo** (ver sección 5).
7. **Modo hosted (login + SSO OIDC) y modo local (loopback, sin cuenta)** con el mismo
   orquestador. Google SSO preset; Entra ID/Okta vía OIDC genérico.

---

## 5. Flujos SOAR (catálogo de producto)

El motor SOAR (`lucidfence/core/soar.py`) ya existe con condiciones declarativas
(`eq`, `gt`, `in`, `contains`, `glob`, `regex`, `exists`, combinadores `all`/`any`/`not`)
y validación al carranque. **Requisito de producto: todo playbook se define en datos
(JSON/YAML), no en código.** Los playbooks por defecto a entregar en v1 (ya en `DEFAULT_PLAYBOOKS`,
confirmar que se exponen en UI):

| Playbook | Disparador (condición) | Acciones | Severidad mín. |
|---|---|---|---|
| `soar-cve-critical` | app con CVE `critical` | `notify` (SOC, high) + `flag_app` | high |
| `soar-cve-outside` | CVE `critical`/`high` **Y** `fence_state=outside` | `locate` + `lock` (human-gated) + `notify` | high |
| `soar-rooted-outside` | `compliant=false` **Y** `outside` | `lock` (human-gated) + `notify` | high |
| `soar-cve-epss-high` | `epss_max > 0.5` | `notify` (SOC, critical) | critical |

**Requisitos de producto SOAR (v1):**
- **Editor de playbooks en la consola** (mínimo: crear/editar/activar desde UI, con
  validación en caliente). El diseño técnico prioriza ejecución correcta y observable; el
  editor puede ser progresivo, pero el usuario debe poder añadir un playbook propio sin
  tocar código.
- **Auditoría por playbook:** cada ejecución registra `playbook_id`, `matched_fields` y
  severidad, trazable desde señal → score → playbook → auditoría (criterio de éxito de piloto).
- **Human-gate explícito:** `lock`/`wipe`/`clear_passcode`/`reboot` generan un handoff
  (dry-run/aprobación), nunca ejecución autónoma. Un playbook roto se salta (auditado), no
  rompe el ciclo.
- **Webhook de salida opcional** (BYO endpoint, hardening SSRF) para escalar a un SOAR de
  terceros (p.ej. Splunk SOAR, Cortex XSOAR). *Decisión de producto pendiente: BYO endpoint
  vs vendor fijo* — ver sección 10.

---

## 6. Casos de uso prioritarios

### P0 — Debe funcionar en v1 (bloquea el lanzamiento del mensaje)
1. **Flota mixta Intune + Applivery en un tenant.** El SOC ve Windows (Intune) y Android
   de campo (Applivery) en el mismo Risk Center; un dispositivo Android fuera de geovalla
   con CVE alto dispara `soar-cve-outside` → `locate` + handoff de `lock`.
2. **Mac (Jamf) no conforme sale del perímetro.** Dispara `soar-rooted-outside` → handoff
   de `lock`.
3. **Degradación segura.** Si Applivery cae, Intune/Jamf siguen evaluando; la flota no se
   vacía y la salud lo refleja.
4. **Cero exfiltrración demostrable.** Instalación a primera flota < 5 min (demo), cero
   datos del tenant fuera de su infraestructura, cero errores de consola.

### P1 — Diferenciadores de mensaje (v1 si cabe, P2 si no)
5. **Workspace ONE en la misma consola** (tras validación de host).
6. **Playbook propio del cliente** definido desde UI (no solo los 4 por defecto).
7. **SSO Enterprise** (Entra ID/Okta) para el modo hosted.

### P2 — Evolutivos (fuera de v1)
8. Sincronización concurrente de proveedores (solo con evidencia de necesidad de rendimiento).
9. Webhook SOAR a vendor fijo (si se decide en sección 10).
10. Billing/whitelabel por UEM (hoy whitelabel por tenant ya existe).

---

## 7. Requisitos de UX

- Ficha de dispositivo muestra **procedencia** (`provider_refs`) y **calidad de ubicación**
  (`location_quality`, `location_rejection_reason`).
- Vista de salud Multi-UEM expone: proveedores activos, última sync, nº de dispositivos,
  capacidades, errores sanitizados, cobertura apta/no apta.
- Botones de acción derivados de `capabilities` del proveedor; mantienen dry-run/aprobación.
- No presentar flota parcialmente sincronizada como completa.
- Editor de playbooks (P1): crear/editar/activar con validación en caliente y vista de
  `matched_fields` en el histórico.

---

## 8. Métricas de éxito (producto)

- **Adopción:** nº de tenants con ≥2 UEM activos simultáneos.
- **Cobertura:** % de flota consolidada con ubicación apta (no `unknown`).
- **Falsos positivos:** tasa de `outside` incorrectos (debe ser ~0 por el evidence gate).
- **MTTR:** tiempo de remediación desde señal → handoff de acción (playbook trazable).
- **Auditoría:** 100% de acciones SOAR con `matched_fields` + procedencia.

---

## 9. Fuera de alcance (non-goals v1)

- Microservicios / message bus.
- Ejecución destructiva autónoma (siempre human-gated).
- Validación live con credenciales reales que el usuario no haya configurado.
- Concurrencia de proveedores (secuencial en v1).
- Billing / adquisición / campañas (ya gratis y sin planes).
- Reescritura de `saas_server.py` / `engine.py` no necesaria para este objetivo.

---

## 10. Decisiones de producto abiertas (necesito input de CTO / Marketing)

1. **Webhook SOAR de salida:** ¿BYO endpoint con hardening SSRF (flexible, recomendado)
   o nombrar un vendor fijo (Splunk/Cortex)? Afecta el mensaje de "integración SOAR".
2. **Acción nativa de Applivery:** el endpoint undocumented de acción no está validado.
   ¿Lanzamos v1 con Applivery como inventory+location y acciones vía handoff manual, o
   bloqueamos hasta validar? Recomiendo lanzar inventory+location y dejar acción como
   dry-run hasta validar.
3. **Editor de playbooks en v1 vs P1:** el diseño prioriza ejecución observable; ¿el
   editor UI entra en v1 o es P1? Marketing necesita saber si "playbooks editables" es
   claim de v1.
4. **Claim de marketing:** el copy actual dice "4 adapters incluidos (Intune/Jamf mock,
   Applivery live)". Con Multi-UEM, el claim correcto es "**multi-UEM simultáneo por
   tenant**" (Intune+Jamf+Applivery live). Marketing debe actualizar el posicionamiento.

---

## 11. Handoff

- **CTO (`t_3109be4f`):** implementa contra el diseño aprobado + este doc. UEMs live v1 =
  Intune + Jamf + Applivery; SOAR = 4 playbooks por defecto + validación en caliente;
  salud Multi-UEM en API/UX. Resuelve las decisiones de sección 10 (1–3).
- **Marketing:** reusa secciones 2–6 para el pitch "geofencing multi-UEM + SOAR". Claim
  sugerido: *"Una sola consola de riesgo y geofencing para toda tu flota Intune + Jamf +
  Applivery, SOAR declarativo y cero exfiltrración."* No inventar capacidades fuera de
  esta matriz. Actualizar posicionamiento (sección 10.4).
- **CEO:** este doc desbloquea la impl del CTO y el mensaje de Marketing; canal coordinado
  Product → CTO + Marketing confirmado.
