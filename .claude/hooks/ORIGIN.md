# Origen

`quality_gate.sh` está adaptado de
[alexfazio/plankton](https://github.com/alexfazio/plankton) (MIT) a petición
del propietario (2026-08-20): enforcement de calidad en el momento de
escribir, no en CI horas después. La adaptación es deliberadamente mínima
(escalera ponytail): solo Python, solo sintaxis + ruff F/E9 (`.ruff.toml` en
la raíz define el contrato: el estilo compacto de la casa NO se lintea),
stdlib en vez de jaq, y fail-open si falta ruff. La batería runtime y
`verify.py` siguen siendo el gate de verdad; esto atrapa lo obvio N pasos
antes.
