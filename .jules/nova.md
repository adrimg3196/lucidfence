# Journal de Product Discovery — NOVA ✨

Este diario registra exclusivamente aprendizajes críticos sobre el producto, sus usuarios, su arquitectura y el mercado de geofencing / UEM local-first.

---

## 2026-09-06 — Límites estructurales del geocercado estático en entornos multi-UEM y transición hacia perímetros adaptativos contextuales

**Aprendizaje:**
Las geocercas estáticas tradicionales (círculos y polígonos con radios fijos dibujados manualmente en un mapa) generan una fricción operativa desproporcionada en organizaciones híbridas y móviles. Los administradores de SecOps sufren de fatiga de alertas por falsos positivos (por ejemplo, empleados en el borde físico de una oficina o transitando corredores) y, al mismo tiempo, pasan por alto riesgos reales cuando el contexto cambia (por ejemplo, un dispositivo conectado a un AP de red no cifrado o con la postura de seguridad degradada dentro del perímetro físico). En un motor local-first y multi-UEM como LucidFence 2.0, el riesgo real no lo determina únicamente la coordenada GPS pura, sino la conjunción del contexto de red (SSID/BSSID/VPN), la jornada laboral (turnos), la integridad de la ubicación y la postura del dispositivo.

**Evidencia:**
- Especificación arquitectónica `docs/superpowers/specs/2026-09-05-lucidfence-2-go-rewrite-design.md` (§4.1 y §5.4): el motor de riesgo ya combina siete señales independientes (`time_of_day`, `shift_match`, `device_health`, `device_posture`, `location_integrity`, `zone_risk`, `route_state`).
- Modelos de dominio `internal/domain/geo`, `internal/domain/fence`, `internal/domain/risk/signals.go`: actualmente `fence` evalúa estrictamente geometría dentro/fuera (`PointInPolygon`, `Haversine`), mientras que la red y el horario se procesan como señales desvinculadas en el veredicto de riesgo.
- Prácticas de mercado UEM (Jamf Pro, Microsoft Intune, VMware Workspace ONE): ofrecen o bien perfiles GPS estáticos o bien filtros IP aislados, sin coordinar el perímetro físico con la confianza de red y postura sin exfiltrar la ubicación a un servidor cloud.

**Implicación estratégica:**
LucidFence está posicionado de forma única para redefinir la categoría pasando de "Geocercado Estático" a "Perímetros Adaptativos Contextuales (LucidPerimeter)". Dado que LucidFence opera 100 % local-first sin telemetría ni envío de datos de ubicación a la nube, puede fusionar señales de física, red y postura en tiempo real en la propia máquina del tenant, ofreciendo un nivel de precisión contextual y privacidad que los competidores de la nube no pueden igualar por restricciones de exfiltración de datos y privacidad de los empleados.

**Acción futura:**
Priorizar en el horizonte `EXPLORE` la oportunidad **LucidPerimeter (Dynamic Contextual Perimeter & Adaptive Geofencing)**. Todas las futuras reglas de geocercado deben diseñarse para aceptar capas de atenuación/amplificación contextual basadas en red y horario, evitando la gestión manual repetitiva de coordenadas estáticas.
