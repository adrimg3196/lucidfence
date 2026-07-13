# Guion de validación — 5 llamadas a CISOs / IT con UEM

Objetivo: matar o confirmar la suposición clave SIN construir nada más.
  "Existen empresas con UEM que pagan por geofencing on-prem (o lo harían)."
Si 4/5 dicen "ya lo cubre mi MDM" → pivotamos a política compuesta + señales
externas (lo que el UEM NO hace). No sigas escribiendo código hasta cerrar esto.

## Antes de llamar
- Lista: 5 contactos en empresas con UEM (LinkedIn, comunidad UEM, clientes
  Applivery/Intune/Jamf). Prioriza banca, defensa, sanidad, logística.
- No vendas. Di: "estoy validando un problema, necesito 15 min de tu dolor real".

## Las 5 preguntas (léelas, no las adornes)
1. ¿Qué UEM usas hoy y quién recibe la alerta cuando un dispositivo sale del
   perímetro?
2. ¿Cuánto tarda hoy responder a esa alerta, y quién decide la acción?
3. ¿Puedes mandar la ubicación de esos dispositivos a la nube del vendor, o hay
   restricción de residencia de datos? (clave del moat on-prem)
4. ¿Combina tu UEM la geolocalización con turno del trabajador, riesgo de la
   zona o señales externas? ¿O solo avisa "está fuera"?
5. ¿Pagas hoy por algo que decida y ejecute automáticamente, o lo haces a mano?
   ¿Cuánto te costaría un incidente de fuga/robo por dispositivo fuera de sitio?

## Señales de "COMPRA" (anota sí/no)
- [ ] Tarda >1h en responder a una salida de perímetro.
- [ ] Hay restricción de residencia de datos (on-prem obligatorio).
- [ ] El UEM solo avisa, no decide ni combina señales.
- [ ] Han tenido un incidente real (robo/fuga) por dispositivo fuera de sitio.
- [ ] Presupuesto de compliance/seguridad aprobado este año.

## Cierre de cada llamada
"Si construyo esto on-prem, corriendo en tu infra, ¿serías mi primer beta gratis
a cambio de un testimonio de 1 párrafo?" → si dice sí, tienes tracción real.

## Qué hacer con los resultados
- 4/5 "sí" en on-prem + "el UEM solo avisa" → construye el GTM, busca el beta.
- 4/5 "ya lo cubre mi MDM" → pivot: políticas compuestas + señales externas que
  el UEM NO modela. Ese es el moat, no la geocerca.
- Empate → llama 5 más antes de decidir. No construyas features a ciegas.
