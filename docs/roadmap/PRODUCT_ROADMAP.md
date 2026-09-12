# Strategic Product Roadmap — LucidFence 2.0

Este documento refleja el estado actual de discovery y priorización estratégica del producto LucidFence 2.0. Las propuestas en los horizontes `EXPLORE`, `LATER` y `NEXT` son hipótesis de producto y requieren aprobación explícita del responsable de producto para pasar a implementación (`NOW`).

---

## 🚀 NOW (Committed & In Build)
*Iniciativas validadas y en desarrollo activo para la versión 2.0.0 Go binary & React UI.*

- **M0: Binario único Go + React UI Embed:** Reescritura completa del motor en Go 1.27+ con persistencia JSON/JSONL atómica local.
- **M1: Geofencing Núcleo & Multi-UEM:** Conectores UEM (Applivery, Intune, Jamf, Fleet, Workspace ONE), geocercas poligonales/circulares, corredores y evaluación determinista de riesgo 0–100.
- **M2: Motor de Riesgo, Acciones & Guardarraíles:** Hand-offs SOAR, modo `observe` por defecto, guardarraíles de enfriamiento y doble autorización para borrado (`wipe`).

---

## 🎯 NEXT (Prioritized Discovery)
*Oportunidades con alta evidencia estratégica pendientes de capacidad final.*

- **Visualizador What-If interactivo de políticas:** Previsualización gráfica en `web/` de impactos de políticas en masa antes de guardarlas.

---

## 🔮 EXPLORE (Product Discovery Horizon)
*Propuestas de valor examinadas por NOVA ✨ pendientes de validación con usuarios.*

- **✨ LucidFence ShadowTwin & Proof-of-Presence (PoP)**
  - *Estado:* Proposal (`docs/product/GEOFENCING_SHADOW_TWIN_AND_PROOF_OF_PRESENCE.md`)
  - *Tipo de apuesta:* Plataforma / Apuesta estratégica
  - *Confianza:* Alta | *Esfuerzo:* Medio
  - *Resumen:* Ejecución en sombra paralela del motor de geofencing sobre telemetría en vivo para predecir impactos de políticas con cero falsos positivos en producción + atestación criptográfica local de presencia (Proof-of-Presence) firmada sin exponer coordenadas lat/long a auditores.

---

## ⏸️ PARKED / REJECTED
*Propuestas archivadas o descartadas por duplicidad o desalineación estratégica.*

- *(Ninguna en este ciclo)*
