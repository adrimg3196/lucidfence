# Jules & Hermes — NOVA Discovery Manifesto & Learnings

- **Fecha:** 2026-09-06
- **Agente Creador (Soñador de Roadmap):** Jules
- **Agente Constructor:** Hermes
- **Ámbito:** Reescritura Go de LucidFence 2.0 (Horizonte EXPLORE / NOVA)

---

## Directrices Fundamentales para Hermes

1. **Local-First Sin Excepciones:**
   Cualquier nueva característica propuesta en el horizonte NOVA (ZK-Geofencing, Anti-Spoofing, Evidencia Post-Cuántica, Federación Aislada) **debe operar 100% en la máquina local o red local del tenant**. No se permite enviar telemetría ni coordenadas a servidores externos.

2. **Agnóstico de Base de Datos:**
   LucidFence utiliza archivos JSON/JSONL atómicos en disco (`internal/store`). Ninguna propuesta NOVA debe introducir dependencias de bases de datos externas (SQL, NoSQL, Redis).

3. **Verificación Runtime Obligatoria (Battery Checks):**
   Para cada funcionalidad NOVA que Hermes implemente, se debe añadir un check de claim correspondiente en `internal/battery/` para garantizar que la CI valida el funcionamiento en vivo contra el binario real compilado (`RUNTIME: N/N`).

4. **Guardarraíles del Motor de Riesgo:**
   Los guardarraíles definidos en `internal/engine/guardrails.go` son inviolables. Incluso la acción de SOAR más avanzada de auto-recuperación debe respetar el modo `observe` por defecto y la doble llave para acciones destructivas (`allow_wipe` y `wipe_allowlist`).

5. **Límites Físicos del Código:**
   - Archivos Go $\le 400$ líneas.
   - Componentes React TSX $\le 300$ líneas.
   - Funciones Go $\le 60$ líneas y complejidad ciclomática $\le 15$.
