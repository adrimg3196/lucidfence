# ADR-0009 — Validación runtime como gate de merge, no solo unit tests

**Estado:** Accepted — 2026-08-15 (regla permanente del propietario; Constitución §IV, NO NEGOCIABLE).

## Contexto

Los unit tests verdes prueban que el código compila y que sus unidades se
comportan en aislamiento, pero no que un claim anunciado **funcione en vivo**: un
endpoint puede pasar sus tests y no arrancar, un webhook puede validar su firma
en un mock y fallar por stdio real. En un producto que promete honestidad
verificable, un claim que no arranca es una mentira aunque la suite esté verde.

## Decisión

Todo claim anunciado se valida **en vivo** además de en la suite honesta. La
batería `scripts/runtime_validation.py` arranca el `saas_server` real, el webhook
real y el MCP por stdio, y ejercita cada claim → `RUNTIME: N/N claims`. Un claim
que compila pero no arranca **bloquea el merge** aunque los unit tests estén
verdes. Corolarios: desconocido nunca penaliza (señal ausente/None no inventa
riesgo ni cobertura); evidencia, no certificación; un umbral de rendimiento es
guard de regresión, no SLA.

## Consecuencias

- **A favor:** el verde significa "funciona de verdad"; cero teatro de features;
  las demos no se caen; la honestidad es estructural, no una promesa.
- **En contra:** el gate es más lento y más caro que unit tests solos; cada
  claim nuevo debe traer su verificación runtime; cambiar una interfaz pública
  obliga a tocar la batería (`scripts/runtime_validation.py`).

## Dónde vive hoy

`scripts/runtime_validation.py`, integrado en `scripts/verify.py`
(`VERIFY: APTO (4/4)`); principio en
[CONSTITUTION.md §IV](../architecture/CONSTITUTION.md) y
[SPEC.md §2/§5](../architecture/SPEC.md).
