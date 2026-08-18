# Backlog de producto — ¿merece la pena desarrollarlo? (2026-08-18)

> Mantenido por el loop **Product Manager** (`claude/pm-features`). Cada ítem
> nace de una capacidad real de una herramienta del sector (Intune, Jamf, Fleet,
> Kandji/Iru, Hexnode, Scalefusion, Workspace ONE), se contrasta contra lo que
> LucidFence **ya tiene**, y recibe un veredicto explícito: **SÍ / SÍ con matiz /
> DIFERIR / NO**. Un ítem sin mejora clara sobre el incumbente, o que viole un
> invariante (local-first, $0, sin telemetría, runtime del producto controlado
> por el admin), no merece desarrollo por mucho que lo tenga la competencia.
>
> El loop PM toma su "una función por ciclo" de los SÍ de aquí; el loop Roadmap
> reconcilia contra `docs/roadmap/PRODUCT_ROADMAP.md`.

## Qué tiene ya LucidFence (no reproponer)

Geocercas círculo+polígono, red-fencing sin GPS (`network_location.py`),
señales de postura honestas (osquery, Lockdown Mode, supervisión), detección de
spoofing, simulador what-if (`policy_replay.py`), workflows-plantilla
(`workflows.py`), webhooks multi-canal, export de evidencia con hash encadenado,
enforcement observe/dry_run/enforce con doble llave en wipe, adapters
Applivery/Intune/Jamf/Fleet/Workspace ONE/ChromeOS, SSO OIDC, MCP explain-risk.

## Resumen ejecutivo (scoring)

| # | Ítem | Inspiración | Impacto admin | Esfuerzo | Veredicto |
|---|------|-------------|:---:|:---:|-----------|
| 1 | Políticas y geocercas como código (GitOps + `apply` con diff) | Fleet (YAML/GitOps) | 5 | M | **SÍ** |
| 2 | Grupos dinámicos de dispositivos | Jamf smart groups / Iru Blueprints | 5 | M | **SÍ** |
| 3 | Informe de cumplimiento programado y firmado | Scalefusion Workflows/reports | 4 | S | **SÍ** |
| 4 | Plantillas de baseline verificables (CIS-lite) | Iru compliance templates | 4 | S-M | **SÍ** |
| 5 | Retención y minimización de ubicación (privacidad como feature) | Contra-modelo de Scalefusion/Senturo | 4 | S | **SÍ** |
| 6 | Detección de drift + plan de remediación propuesto | Kandji/Iru auto-remediation | 4 | M | **SÍ con matiz** |
| 7 | Live queries osquery contra la flota | Fleet (sub-30s) | 3 | L | DIFERIR |
| 8 | Lost mode / lock remoto multi-UEM | Jamf/Iru | 3 | M-L | DIFERIR |
| 9 | Conditional access por ubicación (gate de identidad) | Intune + Entra | 2 | L | NO |
| 10 | Kiosk / app / patch management | Scalefusion/Hexnode core | 2 | XL | NO |
| 11 | Tracking continuo con historial granular de ubicación | Scalefusion location tracking | — | — | **NO (invariante)** |

## Los SÍ — qué hacen y cómo mejoramos al incumbente

### 1. Políticas y geocercas como código (`lucidfence apply`)
- **Qué**: `fences.json`/`policies.json` versionables en git con un comando
  `apply` que valida, muestra el **diff contra el estado vivo** y — clave — pasa
  el cambio por el simulador what-if existente antes de aplicarlo ("esta
  política habría disparado 12 acciones ayer").
- **Incumbente**: Fleet define políticas en YAML y las despliega por CI/CD, pero
  necesita servidor Fleet + infraestructura.
- **Mejora LucidFence**: el mismo flujo GitOps **sin servidor**: validación y
  replay 100% locales con lo que ya existe (`config_validator`, `policy_replay`).
  Nadie del sector enseña el impacto simulado de un cambio de política antes de
  aplicarlo.
- **Validación runtime**: check en `runtime_validation.py`: aplicar un cambio con
  diff no vacío y replay ejecutado deja evidencia en el log de acciones.

### 2. Grupos dinámicos de dispositivos
- **Qué**: grupos calculados por atributos y señales (`platform`, `department`,
  postura, estado de cerca) a los que las políticas apuntan (`group: "portátiles
  sin cifrado"`), recalculados en cada tick del engine.
- **Incumbente**: Jamf smart groups e Iru Blueprints son el estándar de
  organización; hoy LucidFence solo tiene `device_tag` de texto libre.
- **Mejora LucidFence**: los criterios de grupo son las **señales honestas** ya
  existentes (unknown nunca clasifica), y la pertenencia es explicable — cada
  dispositivo lista por qué está en el grupo, como explain-risk.
- **Validación runtime**: un grupo definido sobre la flota simulada resuelve la
  pertenencia esperada N/N en la batería.

### 3. Informe de cumplimiento programado y firmado
- **Qué**: digest diario/semanal por tenant (dispositivos fuera de cerca,
  incumplimientos, acciones), generado en local y **encadenado al hash** del
  export de evidencia existente; entrega por los webhooks ya soportados.
- **Incumbente**: Scalefusion automatiza informes de cumplimiento de geocercas
  vía sus Workflows, pero viven en su nube.
- **Mejora LucidFence**: el informe se genera y queda **en la máquina del
  tenant**, verificable criptográficamente (hash encadenado) — apto como
  evidencia de auditoría sin ceder datos a terceros.
- **Validación runtime**: generar el informe del tenant simulado y verificar la
  cadena de hashes.

### 4. Plantillas de baseline verificables (CIS-lite)
- **Qué**: paquetes de políticas listos ("baseline portátiles", "baseline BYOD",
  "flota supervisada") activables en un click desde el dashboard, construidos
  SOLO con reglas que mapean a señales comprobables en runtime.
- **Incumbente**: Iru vende plantillas CIS/NIST one-click; Hexnode su
  "compliance gating".
- **Mejora LucidFence**: **cero teatro de cumplimiento** — una regla solo entra
  en la plantilla si su señal existe y es readback-honesta (unknown no penaliza).
  La plantilla declara qué NO puede comprobar, cosa que ningún incumbente hace.
- **Validación runtime**: activar una plantilla sobre la flota simulada dispara
  las políticas esperadas y ninguna regla huérfana.

### 5. Retención y minimización de ubicación (privacidad como feature)
- **Qué**: ventana de retención configurable para historial de ubicación con
  purga automática y un panel "qué sabe LucidFence de este dispositivo" (dato,
  antigüedad, cuándo se purga).
- **Incumbente**: el sector (Scalefusion, Senturo sobre Intune) compite por MÁS
  tracking; la retención suele ser opaca o ilimitada.
- **Mejora LucidFence**: competimos por MENOS dato: mínimo necesario para
  aplicar la política, borrado demostrable. Es la feature que convierte el
  invariante local-first en argumento de venta (RGPD-friendly by design).
- **Validación runtime**: inyectar historial viejo, correr la purga, verificar
  que no queda dato fuera de ventana.

### 6. Drift + plan de remediación **propuesto** (SÍ con matiz)
- **Qué**: detectar deriva de postura (cifrado desactivado, dispositivo que sale
  del baseline) y generar un **plan de remediación en dry_run** que el admin
  aplica con un click.
- **Incumbente**: Kandji/Iru remedia en automático ("si el usuario desactiva
  FileVault, Kandji lo reactiva solo").
- **El matiz (invariante)**: en LucidFence **el runtime del producto nunca actúa
  solo** — el desarrollo es autónomo, la flota real no. Mejoramos a Kandji en
  transparencia: el plan explica qué haría y por qué, y no toca nada sin el
  admin. La doble llave del wipe queda intacta.
- **Validación runtime**: una deriva simulada produce un plan en dry_run y
  NINGUNA acción ejecutada sin aprobación.

## DIFERIR (señal insuficiente hoy — revisar con inbound real)

- **7. Live queries osquery**: potente (Fleet responde sub-30s) pero exige flota
  osquery real desplegada; sin demanda inbound es infraestructura muerta. Se
  reabre si Growth trae un usuario con flota osquery. Origen ya registrado en
  `trends/signals.md` (osquery 5.23.1).
- **8. Lost mode / lock remoto multi-UEM**: el valor depende de qué exponga cada
  UEM (Applivery ya tiene lock en el LiveAdapter); generalizarlo a los 5
  adapters es esfuerzo M-L sin usuario que lo pida. Igual que el roadmap #7
  (ampliar adapters "según demanda inbound real").

## NO merece la pena (decisión, no olvido)

- **9. Conditional access por ubicación**: el gate de identidad es terreno del
  IdP (Entra/Okta). Intune lo hace porque ES Microsoft. Duplicarlo sería frágil
  y fuera del norte; ya existe SSO OIDC para autenticar el dashboard.
- **10. Kiosk / apps / parches**: es el core de Scalefusion/Hexnode y un pozo XL
  de esfuerzo. LucidFence gana siendo el mejor en geofencing + postura honesta
  sobre el UEM que ya tengas, no siendo el UEM número 15.
- **11. Tracking continuo granular**: viola frontalmente sin-telemetría y
  minimización. Es además el mayor riesgo reputacional del sector (vigilancia de
  empleados). Nuestro contra-movimiento es el ítem 5.

## Fuentes (sector, consultadas 2026-08-18)

- Scalefusion: [geofencing + Workflows/Eva](https://scalefusion.com/mobile-device-management/), [automatización de alertas](https://blog.scalefusion.com/automate-alerts-for-it-events/)
- Hexnode: [geofencing y compliance gating](https://www.hexnode.com/mobile-device-management/help/geofencing-location-based-mdm-restriction/)
- Fleet: [políticas YAML + automatizaciones](https://fleetdm.com/releases/fleet-4-7-0), [GitOps](https://devopspack.com/fleetdm-open-source-mdm-gitops-device-management/)
- Kandji/Iru: [auto-remediation y plantillas](https://www.goworkwize.com/blog/jamf-vs-kandji), [rebrand Iru](https://www.computerworld.com/article/4077093/kandji-becomes-iru-opens-mdm-for-windows-and-android.html)
- Intune: [Conditional Access + named locations](https://learn.microsoft.com/mem/intune/protect/conditional-access), [geofencing IP-based](https://cloudbymoe.com/f/geo-fencing-access-to-o365-using-conditional-access)
