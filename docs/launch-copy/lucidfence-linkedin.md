# LucidFence — Post de LinkedIn (CISOs / MSPs)

La ubicación de tus dispositivos no debería salir de tu red.

Cada vez más CISOs y MSPs nos hacen la misma pregunta: "¿Cómo geofenceo mi flota MDM sin ceder la soberanía de los datos de ubicación al vendor?"

Los MDM nativos resuelven el geofencing enviando la ubicación a su propia nube. Para un CISO eso es un problema de cumplimiento, no una feature.

Hoy abrimos LucidFence (Apache-2.0): geofencing multi-MDM open-source con un Risk Engine explicable.

Tres cosas lo diferencian:

1. Soberanía local-first. 100% on-prem, 0 exfiltración de datos de ubicación. Tus coordenadas no abandonan tu perímetro.

2. Riesgo que se explica. Cada dispositivo recibe un score 0-100 acompañado de la razón exacta. Nuestro "evidence gate" impide que un hallazgo cuente sin una señal real que lo respalde: sin prueba, sin score.

3. Agnóstico por diseño. Conectas Applivery, Intune o Jamf vía adapters (MDMAdapter) sin reemplazar tu stack actual.

El core es OSS; la capa Enterprise (SOAR, SSO, escala) es on-prem cerrada. El OSS genera inbound; el servicio gestionado es la captura.

Ideal para MSPs y CISOs. No es una herramienta de pentesting.

Geofencing que no exfiltrra. Riesgo que se explica.

👉 https://github.com/adrimg3196/lucidfence
