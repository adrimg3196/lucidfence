# Geofence UEM — Copy de Lanzamiento (open-source / multi-MDM)

*Generado con skills de marketing (cro + copywriting) sobre `.agents/product-marketing.md` y dictamen del tribunal.*
*Principio del CMO: liderar con RIESGO EXPLICABLE + SOBERANÍA LOCAL, no con "geofencing open-source" (commodity).*

---

## 1. TAGLINE (3 opciones, CMO-friendly)

1. **"Geofencing que no exfiltrra. Riesgo que se explica."** ← recomendada por el tribunal (soberanía + explicable)
2. "El control plane local que une tus MDMs y justifica cada riesgo."
3. "Saber dónde está cada dispositivo y por qué está en riesgo — sin subir nada a la nube."

## 2. ONE-LINER (GitHub / README)

> **Geofence UEM** es un control plane open-core, local-first, que convierte la geolocalización de tu flota móvil en riesgo explicable (0-100) y acciones automáticas — agnóstico a tu MDM vía adapters.

## 3. HERO (homepage / README top)

**H1:** Geofencing y riesgo de flota, explicados — en tu máquina, no en la nube.
**Sub:** Correlaciona geovallas, CVE y SOAR en un Risk Engine que justifica cada decisión. Conecta Intune, Jamf, Applivery o Fleet con un PR. 100% local, multi-tenant, 0 exfiltración.
**Primary CTA:** `git clone` + `./start_all.sh`  (valor: arranca en 1 comando)
**Secondary CTA:** Ver demo en vivo

## 4. POSICIONAMIENTO (cómo hablar de esto sin parecer vaporware)

- ✅ "Local-first UEM Risk & Geofence Control Plane"
- ✅ "Agnóstico a MDM vía framework de adapters"
- ⚠️ NUNCA "para cualquier MDM" hasta tener ≥2 adapters reales. Hoy: **4 adapters incluidos** — simulation, applivery (live), intune + jamf (modo mock, listos para live vía Enterprise on-prem). El claim es "multi-MDM ready por framework de adapters".
- ⚠️ "Open-core": el glue + dashboard es Apache-2.0; el Risk Engine scoring es el moat cerrado (Enterprise).

## 5. COPY POR SECCIÓN (README / landing)

### ¿Por qué no tu MDM nativo?
Tu MDM hace geofencing básico. Pero no correlaciona riesgo, no explica el porqué, y manda la ubicación de tu flota a la nube. Geofence UEM lo hace local y explicable.

### El moat: Risk Engine explicable
Cada dispositivo recibe un score 0-100 con la razón (fuera de geovalla + CVE crítico + batería baja = 87). Auditable para tu cliente y para un auditor.

### Agnóstico a MDM
- Hoy lee Applivery (live). Intune y Jamf ya están incluidos como adapters en **modo mock** (funcionan 100% local sin token); la comunidad o el Enterprise on-prem los llevan a live. La interfaz está congelada; tu MDM es solo fuente y destino de datos.

### Soberanía por diseño
Nada sale de tu máquina. El dashboard corre en 127.0.0.1. Para MSPs: cada cliente en su propio tenant, sus datos en su propio disco.

## 6. CTAs (jerarquía)

| Dónde | CTA primario | CTA secundario |
|-------|-------------|----------------|
| GitHub README | `./start_all.sh` (arranca demo) | "Cómo escribir un adapter" |
| Landing MSP | "Agenda demo MSP" | "Lee la arquitectura" |
| Enterprise | "Habla con ventas" | "Ver Enterprise on-prem" |

## 7. OBJECIONES (FAQ del README, del tribunal)

- **"Intune ya hace geofencing"** → Commodity y cloud; nosotros explicamos el riesgo y no exfiltramos.
- **"¿Mi MDM no está soportado?"** → Framework de adapters: tu equipo o la comunidad lo añade. CI obligatorio + badge verified.
- **"Open-source = inseguro"** → Apache-2.0, auditable, local-first. El Risk Engine (moat) es el código que no abrimos.

## 8. MÉTRICAS DE LANZAMIENTO (Growth, OKR Q1)

- 2.000 stars · 200 forks · 5 adapters MDM contribuidos · 10 demos MSP
- Canal: GitHub-first → Show HN, r/selfhosted, Jamf Nation, foros Intune, LinkedIn MSP.

---
*Siguiente paso sugerido: usar skill `launch` para el plan de GTM y `community-marketing` para el programa de adapters + Hall of Fame.*
