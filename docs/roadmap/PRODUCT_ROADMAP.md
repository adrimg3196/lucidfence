# Roadmap de Producto LucidFence

Este documento define la visión estratégica y la priorización de oportunidades de producto de LucidFence 2.0. Se organiza según horizontes de descubrimiento y gobernanza de producto (NOVA).

---

## 🟢 NOW (Comprometido & En Desarrollo)

*Iniciativas validadas, con alcance cerrado y capacidad asignada.*

- **M2: Motor de Riesgo Explicable y Ejecución Protegida de Acciones UEM**
  - Score determinista de riesgo 0–100 (`internal/domain/risk`).
  - Handoffs con gate humano para acciones destructivas (`wipe`, `lock`).
  - Cooldowns, allowlists y guardarraíles por defecto en `observe`.
  - Integración completa con API v1 y interfaz web embebida.

---

## 🟡 NEXT (Prioridad Estratégica Próxima)

*Oportunidades con alta evidencia pendientes de finalización de diseño o capacidad.*

- **Integración de Telemetría OCSF & Conectores SIEM/SOAR**
  - Exportación estandarizada OCSF v1.1 para eventos de riesgo y cambio de geocerca.
  - Webhooks firmados con reintentos y tolerancia a fallos.

---

## 🔵 LATER (Apuestas a Medio/Largo Plazo)

*Ideas valiosas a largo plazo dependientes de capacidades anteriores.*

- **Políticas Declarativas Multi-Tenant Completeras**
  - Soporte ampliado para Android Management API (AMAPI) y Apple DDM directo en conectores Jamf/Intune.

---

## 💜 EXPLORE (Hipótesis & Discovery)

*Oportunidades prometedoras en fase de investigación y validación de hipótesis.*

- ✨ **Simulador de Geocercas Zero-Trust y Replay Temporal ("What-If Policy Engine")**
  - **Estado:** EXPLORE
  - **Documento:** [`docs/product/2026-09-15-zero-trust-geofence-simulator.md`](../product/2026-09-15-zero-trust-geofence-simulator.md)
  - **Apuesta:** Núcleo / Adyacente | **Confianza:** Alta | **Esfuerzo:** Medio
  - **Descripción:** Motor de simulación prospectivo e histórico ("What-If") sobre trazas JSONL locales que permite a SecOps evaluar el impacto exacto de nuevas reglas y cambios de perímetro sin arriesgar falsos positivos ni bloqueos accidentales de dispositivos corporativos en producción.

---

## ⏸️ PARKED (Ideas Aparcadas o Descartadas)

*Ideas duplicadas, poco alineadas o que no superan el estándar mínimo de producto.*

- *(Ninguna propuesta aparcada en este ciclo)*
