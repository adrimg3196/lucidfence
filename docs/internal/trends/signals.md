# Señales de tendencia → producto (append-only)

Memoria del loop Tendencias (`docs/internal/trends/README.md`). Cada entrada:
fecha, señal, fuente (URL), etiqueta de confianza ([Oficial]/[Prensa]/[Rumor]),
y decisión (implementada con nº de PR, o derivada al backlog de Admin-value, o
descartada con motivo). Nunca se borra; el estado se actualiza en su sitio.

<!-- Formato de entrada:
## AAAA-MM-DD
- **Señal:** <qué cambió en el ecosistema>. Fuente: <URL> [Oficial|Prensa|Rumor].
  **Impacto para LucidFence:** <por qué importa al admin>.
  **Decisión:** implementada (#PR) | backlog Admin-value | descartada (<motivo>).
-->

_(Sembrado 2026-08-18. La primera pasada del loop añadirá las señales reales.)_
