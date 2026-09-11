# Strategic Product Roadmap — LucidFence 2.0

**Estado del documento:** Vivo / Gobernado por NOVA ✨
**Última actualización:** 2026-09-06
**Principio rector:** *Local-first, cero telemetría, el admin decide el runtime, gratis y open source.*

---

## Gobernanza del Roadmap

El roadmap de LucidFence no expresa compromisos de fechas fijas ni promesas contractuales. Define la secuencia estratégica de inversión de producto para maximizar el valor entregado a los administradores de TI y seguridad (SecOps), la automatización defensiva y la protección de privacidad.

### Horizontes de Planificación
- **NOW:** Iniciativas validadas, aprobadas, con alcance cerrado y en ejecución activa.
- **NEXT:** Oportunidades prioritarias con evidencia suficiente, pendientes de capacidad o hitos previos.
- **LATER:** Apuestas valiosas a medio/largo plazo dependientes de capacidades anteriores.
- **EXPLORE:** Hipótesis prometedoras en investigación activa de descubrimiento (NOVA), sin compromiso de implementación hasta aprobación explícita.
- **PARKED:** Ideas descartadas, duplicadas o pausadas por falta de evidencia o riesgo excesivo.

---

## Horizontes Actuales

### 🟢 NOW (Reescritura Go 2.0 — Hitos Aprobados)

- **[CORE-2.0] Reescritura Monolito Go + React UI (Hitos M1–M5)**
  - **Objetivo:** Binario único local-first en Go con dashboard React embebido, eliminando runtime Python y clasificando guardarraíles por defecto (`observe`).
  - **Estado:** En desarrollo activo (Spec: `docs/superpowers/specs/2026-09-05-lucidfence-2-go-rewrite-design.md`).
  - **Entregables:** Motor Go, conectores multi-UEM (Applivery, Intune, Jamf, Fleet, Workspace ONE), servidor MCP, SOAR handoffs, suite de informes y evidencia.

---

## 🟡 NEXT (Siguientes Iniciativas en Cola de Capacidad)

- **[INTEG-01] Auditoría de Mínimo Privilegio de Credenciales UEM**
  - **Objetivo:** Detección automática de sobrepermisos en tokens API de conectores UEM frente a las acciones declaradas en políticas.
- **[EVID-01] Cadena de Evidencia Imprimible con Firma Offline**
  - **Objetivo:** Exportación de informes de cumplimiento con hashes criptográficos encadenados verificables sin conexión.

---

## 🔵 LATER (Apuestas a Medio Plazo)

- **[PLAT-01] Marketplace de Plantillas de Políticas y Playbooks Abiertos**
  - **Objetivo:** Catálogo estático local de plantillas de seguridad comunitarias (NIST, CIS Benchmarks) importables en un clic.

---

## 🔍 EXPLORE (Oportunidades en Discovery — NOVA ✨)

- **✨ [EXP-2026-01] LucidPerimeter: Dynamic Contextual Perimeter & Adaptive Geofencing**
  - **Propuesta:** Síntesis autónoma de perímetros de riesgo adaptativos que combinan coordenadas físicas, confianza de red (SSID/BSSID/VPN), horarios de turno y postura del dispositivo.
  - **Firma:** `docs/product/2026-09-lucidperimeter-adaptive-geofencing.md`
  - **Tipo de apuesta:** Moonshot / Apuesta Visionaria
  - **Confianza:** Media | **Esfuerzo relativo:** Grande | **Reversibilidad:** Alta

---

## ⏸️ PARKED (Ideas Descartadas / Pausadas)

- **[PARKED-01] Agente Residente de Telemetría Cloud Continua**
  - **Motivo de descarte:** Viola el principio #1 de LucidFence (Local-first y cero telemetría).
- **[PARKED-02] Chatbot Genérico de Asistencia por IA en Dashboard**
  - **Motivo de descarte:** No elimina trabajo concreto ni mejora decisiones operativas directas; reemplazado por la interfaz estandarizada MCP para LLMs locales.
