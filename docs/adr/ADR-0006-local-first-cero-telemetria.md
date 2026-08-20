# ADR-0006 — Local-first: cero telemetría, cero exfiltración de ubicación

**Estado:** Accepted — identidad fundacional; reafirmado 2026-08-15 (Constitución §I).

## Contexto

LucidFence maneja el dato más sensible de una flota: **dónde están los
dispositivos**. Un producto de geofencing que envíe ubicación a una nube ajena
es exactamente el riesgo que sus compradores quieren evitar. La confianza del
comprador UEM depende de una promesa fuerte y verificable: "nada sale de tu
máquina".

## Decisión

Arquitectura **local-first y soberana**: el dato del tenant vive en la máquina
del tenant. Cero telemetría, cero exfiltración de ubicación (el dato geoespacial
no sale del equipo), cero dependencia de una nube nuestra. La única publicación a
la nube es un snapshot **demo** (`data/cloud_state.json`, engine en simulación)
para la vitrina de Pages — jamás datos reales de tenant. Heurísticas
anti-spoofing y de integridad de ubicación son 100% locales.

## Consecuencias

- **A favor:** la promesa de privacidad es estructural, no una política; sin
  OIDC/IA configurados hay cero llamadas de red; el comprador puede auditar que
  nada sale.
- **En contra:** sin telemetría no hay analítica de uso remota ni crash-reporting
  automático; el soporte se apoya en lo que el cliente comparte a mano; features
  cloud-nativas quedan fuera por diseño.
- **Denylist:** `data/cloud_state.json` con datos reales de tenant está prohibido
  ni con gate verde.

## Dónde vive hoy

`lucidfence/core/location_source.py`, `location_integrity.py`,
`network_location.py`, `cloud_publisher.py` (demo-only); principio en
[CONSTITUTION.md §I](../architecture/CONSTITUTION.md) y
[SPEC.md §1](../architecture/SPEC.md).
