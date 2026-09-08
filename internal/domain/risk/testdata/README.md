# Veredicto puro D03

`verdicts.json` conserva los diez casos íntegros de Product (adjunto 178,
paquete 177 de t_7cb70a33, `golden-verdicts-upstream.json`). La prueba compara
el `device.Verdict` entero mediante go-cmp, incluida la distinción []/null.

`inputs.jsonl.gz` y `python-results.jsonl.gz` son compresiones sin modificar
los bytes descomprimidos del corpus CTO t_5b0520db (paquete 212). Los hashes,
tamaños y recuentos están en `rounding-provenance.json`. No son datos reales
de dispositivos. Se conservan las 43.347 filas, incluidos controles fuera
del dominio de Evaluate. El contrato numérico procede del delta Product
261 de t_84c807b9, sobre T02 aceptado en main f7691bafe641712ea3d5d25a5c3a2e67502cceb7.

## Semántica numérica

El producto acumula pesos en orden, aplica crédito de ruta y suelo cero,
acota a [0,100], redondea y solo entonces deriva Severity. `roundTenth`
usa la representación racional exacta del float64, cociente/resto enteros,
desempate al par y una única conversión de q/10 a binary64. No escala el
float antes de redondear ni usa tolerancias. Los tests verifican los bits
contra CPython 3.11.15 y ejercitan los 78 casos de zona del corpus mediante
el acumulador real y Evaluate, comprobando también razones y severidad.

El corpus no demuestra paridad universal entre versiones/arquitecturas.
Los controles negativos conservan las discrepancias de `Round(v*10)/10`
y `RoundToEven(v*10)/10`; ninguno es implementación de producción.

Divergencia explícita: legacy derivaba Severity antes de redondear. D03
sigue el brief y el delta, no afirma paridad integral de veredictos:
35 + 0.9975*20 = 54.95 acaba en 55/high (legacy medium); con base 60 acaba
en 80/critical (legacy high).

Las métricas int/float64 ausentes, inválidas o no finitas se neutralizan;
un peso finito de zona que desborda a +Inf termina acotado a 100. MaxScore
ignora solo nil/NaN, no infinitos. Failed conserva null/unknown. Un check
de velocidad sin métrica conserva texto 0 km/h por compatibilidad, no
como velocidad observada. Defaults neutros no demuestran salud.

## Límites

Solo cálculo puro: no ejecuta Compute/Assess, no hay I/O ni reloj global.
MatchedPolicies queda vacío hasta T04. No conecta motor/enforcement (T13/
T14), CVE (M3), UI, release ni producción. `device.go` no cambia. go-cmp
se permite solo en tests, con depguard y guardián AST de imports de
producción; las guardas existentes y allowlists siguen vigentes.
