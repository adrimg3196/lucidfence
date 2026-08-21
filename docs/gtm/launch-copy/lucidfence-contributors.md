# LucidFence — Programa de Contributors

LucidFence es multi-UEM porque la comunidad lo alimenta. Si manejas un UEM que aún no tiene adapter, o tienes casos de riesgo que el engine debería entender, este es tu lugar.

## Cómo contribuir

- **Adapters (MDMAdapter):** ¿Intune, Jamf, Mosyle, Kandji, Applivery? Abre un adapter. La matriz honesta: Applivery live por defecto; Intune/Jamf en modo live al conectar tu token (simulación sin token). Las primeras son bienvenidas con la etiqueta `good first adapter`.
- **Risk signals:** Propón señales para el evidence gate. Todo hallazgo necesita una señal real; tu caso de uso define cuáles entran.
- **SOAR playbooks:** Los 4 playbooks frontline (CVE crítico, CVE+fuera de perímetro, no-conforme+fuera, EPSS alto) ya corren en runtime con auditoría por dispositivo (matched_fields). Si tu SIEM necesita un formato de webhook distinto, el webhook BYO es firmado HMAC-SHA256 por tenant (X-LucidFence-Signature) — propón el ajuste.
- **Docs y casos:** Comparte cómo geofenceas flotas en tu industria. Ayuda a otros MSPs a adoptar sin fricción.

## Reconocimiento

- Cada adapter mergeado entra al README con crédito y acceso al canal de contributors.
- Bounties para adapters de UEM y para señales de riesgo verificadas por CISOs.
- Los contributors activos reciben acceso anticipado a las capas on-prem (SSO/SOAR/Risk Engine).

Empieza en `CONTRIBUTING.md`. La soberanía se construye en comunidad.
