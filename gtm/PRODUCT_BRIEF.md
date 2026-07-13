# Geofence UEM — Product Brief (one-pager)

## Categoría (reframe para adquisición)
**Geospatial Risk & Policy Engine para dispositivos frontline gestionados.**
No es "geofencing". Es la capa de política de riesgo geoespacial que se sienta
SOBRE cualquier UEM/MDM (Intune, Jamf, Applivery, Fleet) y decide, en tiempo
real, qué hacer cuando un dispositivo cruza una frontera física, de turno o de
riesgo. Los UEM saben dónde está el dispositivo; nosotros modelamos el RIESGO
como función compuesta y ejecutamos política. Eso no lo copian en una sprint.

## Dolor real (pagado hoy)
- Dispositivo frontline (logística, retail, field service, sanidad) fuera de su
  perímetro permitido fuera de turno = fuga de datos / robo / incumplimiento.
- Sector regulado (banca, defensa, sanidad, gobierno) NO puede mandar ubicación
  a la nube del UEM por ley de residencia de datos → necesita on-prem.
- El UEM alerta; no decide ni combina señales externas (turno, riesgo de zona).

## Producto (lo que construimos, 100% local, grado producto)
- Motor de riesgo compuesto: score 0-100 por dispositivo = geocerca + salud del
  dispositivo + señales externas (turno, hora, riesgo de zona) + historial.
- Políticas compuestas: "fuera de geocerca AND fuera de turno AND zona de
  riesgo → aislar dispositivo". Explicable (cada decisión trae sus señales).
- Multi-tenant, auth (scrypt), RBAC (owner/admin/operator/viewer), dashboard
  SaaS local: mapa, dispositivos, Risk Center, políticas, compliance, analytics,
  billing mock, usuarios, settings.
- Auditoría local completa (events, actions, trails) — listo para ISO/NIST.

## Por qué es adquirible (moat)
1. El UEM ya tiene la ubicación pero NO el motor de política compuesta →
   integración, no competencia. Nos compran para no construirlo.
2. On-prem + residencia de datos = franja regulada que SaaS puro no toca.
3. Señales externas pluggable (turnos, IoT, datasets de riesgo) = datos que el
   UEM no tiene. El moat crece con los datos, no con el código.

## Modelo (mock hoy, real mañana)
Free / Pro / Enterprise por dispositivos, geocercas y retención. El on-prem es
el despliegue; la marca/vitrina es SaaS. El secreto es el despliegue, no el GTM.

## Primer hito de tracción (lo que falta validar)
5 llamadas a CISOs/IT con UEM desplegado. Pregunta única:
"¿Pagas hoy por geofencing on-prem, o lo harías corriendo tú el server?"
Si 4/5 dicen "ya lo cubre mi MDM" → pivot a lo que el UEM NO hace (política
compuesta + señales externas). Un CISO beta gratis a cambio de testimonio.
