---
platform: LinkedIn
audience: CISOs / MSPs
status: borrador
needs_owner_approval: true
claims_source: .cto_input_188.md (t_8f3731df, t_d000d423, t_1e921803, t_544e867b — todas done)
repo: https://github.com/adrimg3196/lucidfence
---

# Cómo es diferente LucidFence (y por qué los MDM nativos no lo cubren)

La ubicación de tus dispositivos frontline no debería salir de tu red. Pero el MDM
que ya pagas resuelve el geofencing enviando tus coordenadas a la nube del vendor.
Para un CISO eso es un problema de cumplimiento, no una feature.

LucidFence invierte la premisa: el perímetro es tuyo, la ubicación no se exfiltrra.

Cuatro cosas lo diferencian de "el geofencing de mi MDM":

**1. Soberanía local-first, 100% open-source y gratis para auto-hospedar.**
$0: sin asientos, sin telemetría. Tus coordenadas no abandonan tu infraestructura.
El dashboard corre en 127.0.0.1; para MSPs, cada cliente en su tenant, sus datos en
su disco.

**2. Riesgo que se explica (evidence gate).**
Cada dispositivo recibe un score 0-100 **con la razón exacta** (fuera de geocerca +
CVE crítico + batería baja = 87). Sin señal real que lo respalde, no hay score:
anti-overclaim por diseño, no por promesa. Auditable para tu cliente y para un auditor.

**3. Multi-UEM real, con la matriz honesta (crítico para no incumplir #110).**
Multi-UEM simultáneo por tenant: **Applivery live por defecto**; **Intune/Jamf en
modo live al conectar tu token** (simulación sin token). Cero exfiltración. No somos
"el MDM nº 15": somos el plano de control neutral que se sienta SOBRE el UEM que ya
tienes, vía adapters (MDMAdapter).

**4. SOAR declarativo, ya verificado en runtime.**
4 playbooks frontline — CVE crítico, CVE + fuera de perímetro, no-conforme + fuera,
EPSS alto — con auditoría por dispositivo (`matched_fields`). Y salida hacia tu
Splunk/Cortex XSOAR vía webhook BYO, **firmado HMAC-SHA256 por tenant**
(`X-LucidFence-Signature`), dirigido al SIEM que ya uses.

Ideal para MSPs y CISOs con flotas reguladas (banca, sanidad, defensa, gobierno) o
frontline (logística, retail, field service) que no pueden mandar ubicación a la
nube del vendor. No es una herramienta de pentesting.

Geofencing que no exfiltrra. Riesgo que se explica.

👉 https://github.com/adrimg3196/lucidfence
