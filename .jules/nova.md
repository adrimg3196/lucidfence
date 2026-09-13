## 2026-09-06 — La desatención de la sintaxis espacial en UEMs y el poder del Local Replay

**Aprendizaje:**
Los administradores de seguridad y operaciones de flotas (SecOps/IT) gastan horas configurando geocercas estáticas (círculos/polígonos) dibujadas a mano en mapas sin visibilidad del impacto real en producción. Esto provoca dos problemas graves: (1) falsos positivos que desencadenan acciones destructivas o de bloqueo sobre dispositivos legítimos, y (2) desactivación de reglas automatizadas por miedo al impacto no simulado. La arquitectura Go 2.0 de LucidFence conserva localmente (`events.jsonl` / `actions.jsonl`) toda la trazabilidad y cuenta con un motor de replay ultra-rápido en memoria, lo que permite sintetizar límites envolventes (Convex Hull + Buffer) y calcular el "Blast Radius" de una geocerca sobre datos históricos reales sin latencia ni fuga de datos.

**Evidencia:**
- `internal/domain/geo/` cuenta con utilidades esféricas puras (Haversine, Ray Casting, Polilíneas) sin I/O ni dependencias externas.
- `internal/engine/replay.go` ejecuta la simulación determinista de políticas sobre eventos pasados.
- `events.jsonl` en `internal/store` conserva el historial de posiciones de la flota con soberanía local completa.

**Implicación estratégica:**
LucidFence no debe competir ofreciendo otro "editor de polígonos manual". La ventaja acumulativa reside en convertir la trazabilidad local histórica en *inteligencia de límites espaciales* y *simulación de riesgo antes del despliegue*, logrando un time-to-value de segundos y eliminando el riesgo de falsos positivos en producción.

**Acción futura:**
Evolucionar el módulo de geocercas y políticas hacia un modelo declarativo asistido por síntesis espacial (Geofence Twin), permitiendo a los usuarios pasar de intenciones operativas ("proteger la flota en la ruta A") a geocercas y reglas verificadas contra el 100% del histórico local.
