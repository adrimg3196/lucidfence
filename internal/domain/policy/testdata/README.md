# Políticas puras D04 — contrato y procedencia

Referencia de comportamiento, solo leída: commit legacy
`eea09c56c67996d4086f8d11771bf57cec3cfd9b`,
`lucidfence/core/policies.py:266–329,488–559` y
`lucidfence/core/workflows.py:77–162`. No se importa ni ejecuta Python.

- `compatibility.json`: casos manualmente transcritos de la semántica de `_cmp`
  (ocho operadores, bordes positivos/negativos). Son goldens derivados de lectura,
  no una ejecución acreditada del runtime legacy ni prueba de paridad universal.
- `divergences.json`: goldens separados con resultado histórico esperado y 2.0.
  Booleano/número separados incluso en eq; ne entre familias incompatibles no
  acredita desigualdad; no coerción textual/bool en umbrales; in exige lista.
  `legacy` es expectativa derivada de fuente, no recibo de ejecución Python.
- `templates.json`: condiciones, orden de acciones y Params de las cinco
  plantillas. Prefijo wf→tpl, CRITICO→CRÍTICO y copy editorial honesto.
  La primera sigue siendo notify+message, no lock. El mensaje de desvío conserva
  literalmente `> 500 m` del legacy, no la paráfrasis del borrador.
  AND permite ordenar known antes de match sin cambiar el predicado.

## Decisiones 2.0 explícitas

D04-D01: se consume `risk.Severities` real, sin nuevas constantes en T03.
D04-D02: true==1 de Python NO se reproduce; no se declara paridad total.
D04-D03: turno exige known=true Y match=false explícitos; nil, ausencia, strings
  y números no son evidencia, tanto nativos como tras JSON.
D04-D04: MatchAll copia Params mediante JSON con UseNumber, incluidos todos los
  mapas/listas anidados. No se prometen tipos concretos Go: []string se convierte
  a []any y los números a json.Number; no se pierde el decimal de Params.
  Templates construye todos sus mapas/listas de nuevo; FindByID es una búsqueda
  simple (sin promesa de copia), mientras TemplateByID busca en catálogo fresco.
D04-D05: comparaciones numéricas solo en [-9007199254740991,9007199254740991],
  todas las familias int/uint (no uintptr), float32/64 y json.Number. Fuera del
  intervalo la validación de Value rechaza y el matching devuelve false,
  también ne. Enteros se comprueban antes de convertir a float64; json.Number
  se comprueba contra su decimal original. Fracciones se comparan en binary64:
  no se promete exactitud decimal arbitraria. Float32 se normaliza por su decimal
  corto JSON para conservar matching al rehidratar. Score T03 no se recalcula.
  Este límite no restringe Params: sus enteros grandes se copian con UseNumber.
D04-D06: cobertura y gates son mediciones del autor/CI, no Expected del borrador.

Otros endurecimientos: op ausente/vacío no significa gte; severidad vacía no
significa medium; Field pertenece al catálogo explícito o al prefijo signal;
retire no existe en action.All. Null no es una lista de políticas: ValidateAll
rechaza nil, acepta [] vacío; encoding/json rechaza documentos escalares/objeto.
Valores JSON objeto/lista pueden almacenarse en Value sin cambiar de familia,
pero eq/ne solo comparan escalares compatibles; no hay igualdad estructural
arbitraria. In admite []any/[]string, contains texto. False y 0 son explícitos.
La etiqueta fence_state="unknown" es un estado explícito de ubicación y permite
la plantilla de localización; no es lo mismo que un campo ausente/nil.

Condition.Match rechaza condiciones inválidas. Policy.Matches evalúa solo AND y
Enabled, MatchAll además valida la política completa antes de emitir candidatos;
Validate/ValidateAll proporcionan el error español accionable al consumidor.
Params son valores JSON (no funciones, canales, ciclos, NaN/Inf ni objetos Go
con comportamiento); no hay restricción a escalares ni mapas exteriores.

Sin store/API/UI/OpenAPI, planPolicies/T14, T06, replay/T17, ejecución UEM,
recalcular riesgo, reloj global, I/O, enforcement, releases o deploy. T02/T03 y
los pesos/redondeo permanecen intactos. La única fila fuera de este paquete es
su responsabilidad en ARCHITECTURE.md, bajo autorización protegida existente.
