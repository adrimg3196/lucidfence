## 2026-09-15 — Geofence Policy Drift & Simulation Blind Spot in Local-First UEM Environments

**Aprendizaje:**
Los administradores de SecOps y UEM se resisten a activar políticas de geocercado automático (enforcement mode) por temor a falsos positivos e interrupciones operativas (como bloqueos de dispositivos o borrados accidentales en zonas limítrofes). Aunque el motor de LucidFence soporta un modo `observe` seguro por defecto, la falta de una herramienta de simulación "What-If" que proyecte el impacto de nuevas políticas sobre trazas históricas de ubicación y riesgo congela la adopción de automatización autónoma.

**Evidencia:**
- `internal/engine/guardrails.go`: El motor fuerza el modo `observe` por defecto para evitar acciones UEM destructivas no intencionadas.
- `internal/domain/policy/templates.go` y `internal/engine/replay.go`: Existen semillas de motor y mecanismos de simulación/replay de ciclo en memoria, pero no están expuestos como una capacidad prospectiva o predictiva de evaluación de políticas sobre escenarios sintéticos o históricos.
- `ARCHITECTURE.md` y `docs/superpowers/specs/2026-09-05-lucidfence-2-go-rewrite-design.md`: LucidFence 2.0 es local-first con almacenamiento local en JSONL, lo que proporciona una ventaja competitiva única: el histórico completo de eventos de ubicación reside localmente sin problemas de privacidad ni costes de ingestión en la nube.

**Implicación estratégica:**
La simulación de políticas y el replay contextual (Zero-Trust Geofence Simulator) aprovecha los datos históricos guardados localmente para transformar LucidFence de un motor de riesgo reactivo a una plataforma de simulación predictiva y confianza cero, permitiendo a los administradores probar políticas sin riesgo antes de pasar de `observe` a `enforce`.

**Acción futura:**
Priorizar en la fase EXPLORE del roadmap la propuesta del Simulador de Geocercas y Replay Temporal ("What-If Policy Engine"), utilizando la arquitectura Go local-first existente sin requerir infraestructura cloud adicional ni APIs de terceros costosas.
