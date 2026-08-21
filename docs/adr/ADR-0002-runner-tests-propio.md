# ADR-0002 — Runner de tests propio, sin pytest/fixtures

**Estado:** Accepted — ~2026-07 (fundacional; coherente con Constitución §V).

## Contexto

La suite necesita un tally **honesto**: el verde es el número real de tests que
pasan, no una cifra fijada a mano en un doc. pytest y su ecosistema de plugins y
fixtures son una dependencia de peso con magia de descubrimiento e inyección que
puede ocultar tests que no corren, y contradice el reflejo stdlib-first del
resto del runtime. El proyecto prefiere un runner transparente cuyo output *es*
la verdad.

## Decisión

Los tests corren con un runner propio en `tests/run_tests.py`: descubre los
`test_*.py`, los ejecuta e imprime el tally real (`N PASS / M FAIL`). Sin pytest,
sin fixtures mágicas. El verde es lo que el runner imprime, no un número escrito
en la spec.

## Consecuencias

- **A favor:** cero dependencia de test en el runtime path; el tally es
  auditable y honesto; un test que no corre se ve.
- **En contra:** sin el azúcar de pytest (parametrize, fixtures, plugins);
  disciplina de escritura obligatoria — un `test_*.py` que hace `raise
  SystemExit` en el import mata la discovery de los ficheros siguientes (ver
  CONTRIBUTING); baseline tolerada única: `test_oidc_sso.py` en contenedores con
  `cryptography` roto (verde en CI).
- **Regla de la casa:** no se hackea el runner para maquillar el verde.

## Dónde vive hoy

`tests/run_tests.py`; integrado en el gate `scripts/verify.py` y en
`.github/workflows/ci.yml`; nota de honestidad en
[CONTRIBUTING.md](../../CONTRIBUTING.md) y [SPEC.md §2](../architecture/SPEC.md).
