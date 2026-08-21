# ADR-0011 · Los datos generados viven en ramas de datos, nunca en main

**Estado:** Accepted · 2026-08-20

## Contexto

`data/cloud_state.json` (snapshot demo de la vitrina) se regeneraba y
commiteaba a `main` cada 15 minutos por `engine-cron`. Consecuencias medidas:
~100 commits/día de ruido que hacían ilegible `git log`, conflicto garantizado
con CUALQUIER PR que tocara `data/` (el deadlock del issue #74 y el bloqueo de
la PR #195 durante 17 h), y una familia entera de fallos de CI cuando los
consumidores (vitrina, health-checks, monitor) derivaron entre la URL vieja y
la nueva durante la migración.

## Decisión

1. **Ningún artefacto generado por workflow se commitea a `main`.** Los datos
   vivos van a una **rama de datos** dedicada (patrón `gh-pages`): hoy,
   `cloud-state` para el snapshot de la vitrina. Su historial no se lee; es un
   buffer de publicación.
2. **Una sola fuente de verdad por artefacto publicado**: URL canónica y
   esquema viven en UN sitio (`scripts/check_vitrina.py`, que importa
   `PUBLISHED_REQUIRED_KEYS` del publisher). Los workflows DELEGAN en ese
   checker; prohibidas las copias inline de URL o esquema.
3. **Enforcement por máquina, no por memoria**:
   - `tests/test_single_source_cloud_state.py` — toda referencia a la URL del
     snapshot debe ser la canónica; los workflows de salud deben delegar en el
     checker; el esquema del checker ES el del publisher (mismo objeto).
   - El guard `runtime-artifacts` de `ci.yml` rechaza reintroducir
     `data/cloud_state.json` en una PR (`--diff-filter=AM`).
   - El job `workflows-lint` (actionlint pinned, con shellcheck) valida todo
     cambio de workflow en la PR, antes de que corra en producción.

## Consecuencias

- `main` queda limpio para siempre; los PRs no vuelven a conflictar con datos.
- Añadir un artefacto generado nuevo = crear/reutilizar una rama de datos y su
  checker de fuente única; nunca un commit a main. Si un loop futuro intenta
  el patrón viejo, lo paran el guard de CI y este ADR.
- El purgado del historial ya acumulado en main sigue siendo decisión del
  propietario (destructivo; ver TECH_DEBT_STRUCTURAL.md §HP-1).
