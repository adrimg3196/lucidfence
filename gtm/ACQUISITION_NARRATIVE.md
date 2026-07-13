# Narrativa de adquisición (pitch para YC / strategic acquirer)

## Hook (una frase)
"Los UEM saben dónde están tus dispositivos frontline. Nosotros decidimos qué
hacer cuando cruzan una frontera — y lo hacemos on-prem, porque en banca y
defensa la nube está prohibida."

## El problema
1. El 80% de las empresas con fuerza frontline ya paga un UEM (Intune/Jamf/
   Applivery). Ese UEM ve la ubicación pero no modela riesgo ni combina señales.
2. Cuando un dispositivo sale del perímetro fuera de turno, el UEM "avisa" y
   el analista decide a mano. Lento, inconsistente, no auditable.
3. Sectores regulados no pueden exfiltrar ubicación a la nube del vendor.

## Nuestra solución
Capa de política de riesgo geoespacial que se despliega on-prem sobre el UEM
existente. Score de riesgo compuesto + políticas declarativas + ejecución de
acciones UEM automatizada. Todo local, auditable, sin exfiltrar datos.

## Por qué ahora
- Adopción masiva de UEM post-COVID (gestión de dispositivos remotos/frontline).
- Leyes de residencia de datos (GDPR, sector bancario, defensa) empujan on-prem.
- Los UEM se están convirtiendo en plataformas; el hueco es la "política
  inteligente", no más telemetría.

## Tamaño de mercado (frame)
No "geofencing" ($X pequeño). Es "capa de política/riesgo sobre UEM" —
adjacente a Samsara ($20B+), MDM enterprise, y la ola de compliance on-prem.
Nos compra un UEM para añadir la capa sin construirla; nos compra un strategic
(defensa/banca) para cumplir regulación.

## Moat (lo que un adquirente valora)
- Integración sobre UEM existente (no hay que cambiar de MDM).
- Datos de señales externas que el UEM no tiene (turnos, riesgo de zona, IoT).
- On-prem + auditoría = cumplimiento regulatorio inmediato.

## Tracción que buscamos (próximos 30 días)
- 5 llamadas de validación con CISOs/IT que ya usan UEM.
- 1 diseño de cohorte beta (un CISO, 50 dispositivos, on-prem gratis).
- 1 testimonio escrito de "reducimos tiempo de respuesta de horas a segundos".

## El ask (si esto fuera YC)
No dinero para construir — el producto existe. Dinero para GTM: las 5 llamadas,
el beta, y la primera integración con un UEM real (Applivery/Intune) en vivo.
