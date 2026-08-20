# Mini-spec de función — plantilla (SDD, adaptada de github/spec-kit)

> El loop PM (y cualquier loop que añada función nueva) rellena esto ANTES de
> escribir código, en el cuerpo de la PR o como fichero junto a la feature.
> Recortada a nuestro tamaño: si una sección no aplica, se borra, no se
> rellena por rellenar. La spec manda; el código la implementa.

## [Nombre de la función]

**Estado**: borrador | en implementación | entregada (#PR)
**Origen de la señal**: (ítem del BACKLOG.md / roadmap / tendencia con fuente / fricción de dogfooding — sin señal real no hay feature)

### Historia de usuario (priorizada, testeable por sí sola)

Como **[admin de Intune/Jamf/Applivery/Fleet]**, quiero **[capacidad]** para
**[valor operativo real]**. (P1; si hay más de una historia, cada una debe ser
un incremento entregable por sí solo.)

### Criterios de aceptación (medibles, sin ambigüedad)

1. DADO [estado inicial], CUANDO [acción], ENTONCES [resultado observable].
2. …

### Claim runtime (obligatorio — Constitución IV)

La línea exacta que `scripts/runtime_validation.py` probará en vivo. Si no se
puede formular, la función no se puede anunciar y no se construye.

### Check constitucional (art. I–VII)

- [ ] Local-first: ningún dato del tenant sale de su máquina.
- [ ] Complemento, no UEM: lee/correlaciona/explica; actúa solo vía UEM.
- [ ] $0 y stdlib-first: sin dependencia nueva de runtime.
- [ ] Desconocido nunca penaliza (si toca señales/riesgo).
- [ ] Frontera de autonomía: nada actúa sobre dispositivos sin el admin.
- [ ] Fleet primera clase y mock offline preservado (si toca adapters).

### Fuera de alcance

Lo que esta función NO hace (y quién lo hará, si alguien: backlog/diferido).
