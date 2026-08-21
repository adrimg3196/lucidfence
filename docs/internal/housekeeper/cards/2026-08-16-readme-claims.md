---
type: open
pr: 138
date: 2026-08-16
title: "README: licencia contradictoria (MIT vs Apache-2.0) y tally de tests rancio"
---

# README: claims rancios corregidos

**Qué**: la línea 97 del README decía `License: MIT` mientras `LICENSE`,
`pyproject.toml`, la fórmula Homebrew y la línea 105 del propio README dicen
Apache-2.0 (deuda legal-facing, autocontradicción en el mismo fichero). La
línea 95 decía "105 tests = verde" con una suite real de 477+.

**Evidencia de bajo riesgo**: cambio solo de prosa en README; `LICENSE`
contiene el texto Apache 2.0 verbatim; `pyproject.toml` declara
`license = Apache-2.0`; el tally real lo imprime `tests/run_tests.py` en CI.
El fix quita el número hardcodeado en vez de actualizarlo (los números en
prosa caducan — esa es la lección del hallazgo).

**Verificación**: suite completa + batería runtime verdes en el worktree
antes de abrir la PR (números reales en el cuerpo de la PR).
