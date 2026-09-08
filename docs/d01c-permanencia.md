# Permanencia y señales pasivas (D01c)

`transition.Evaluate` conserva su firma y mantiene `FenceStateSince` y
`DwellSeconds` en el dispositivo. El origen es el reloj `at` del ciclo, no
`Location.ObservedAt` ni el contador reportado por el dispositivo.

- Misma clave `geocerca:estado`: conserva una copia del origen y calcula segundos
  completos transcurridos, no suma contadores redondeados de ciclos previos.
- Cambio de geocerca o estado: origen nuevo y cero segundos.
- Primer ciclo o estado M1 sin origen (también fecha cero): arranca en `at`.
- Reloj que retrocede: conserva el origen y limita el resultado a cero.
- `unknown` sigue siendo desconocido. Su reloj mide tiempo en ese estado, no
  evidencia de ubicación ni permanencia física. No cambia la semántica M1 de
  transiciones o `LastInsideFence`.

JSON omite `fence_state_since` sin evaluación y siempre emite `dwell_seconds`.
OpenAPI los deja opcionales para lectores compatibles con respuestas M1.
El store JSON existente los conserva al reabrir sin migración de esquema.

`Signals` es solo `map[string]map[string]any`: datos JSON por nombre de señal,
con false, cero y null explícitos preservados. Ausente/vacío se omite; no genera
riesgo ni rellena observaciones desconocidas. El dominio device no importa risk.
El cálculo tipado y la producción de señales pertenecen al trabajo posterior M2.

El llamador existente del motor ya persiste el resultado de Evaluate; no se
modifica engine ni se añade planificación/enforcement de acciones dwell. Un
fallo de proveedor conserva el estado previo según M1: este contador no prueba
observación continua durante la ausencia. Las acciones dwell, riesgo, políticas,
guardarraíles nuevos y restantes entregas M2–M5 no se declaran terminados aquí.

Verificación: tests deterministas de acumulación, cambios de clave, unknown,
reloj ausente/cero/futuro, redondeo, JSON y reapertura; contrato TypeScript y
check runtime contra `/api/v1/devices/dev-001` del binario simulado. `make verify`
es el gate Go/React; no aplica el runner Python legacy.
