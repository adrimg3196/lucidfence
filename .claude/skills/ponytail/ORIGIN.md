# Origen

Skills `ponytail*` adoptadas de
[DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail)
(MIT, ver `LICENSE` en este directorio) a petición del propietario
(2026-08-19). Sin modificar: la escalera de pereza (YAGNI → reuso → stdlib →
nativo → una línea) encaja con el invariante stdlib-first de LucidFence.

Uso en la flota: el Housekeeper (`engineering-minimal-change-engineer`) corre
`ponytail-audit`/`ponytail-review` en sus ciclos; cualquier loop puede invocar
`ponytail` al escribir código. La deuda deliberada se marca con comentarios
`# ponytail:` y se cosecha con `ponytail-debt`.
