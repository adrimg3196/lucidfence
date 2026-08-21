# ADR-0003 — Estado en JSON en disco, sin base de datos

**Estado:** Accepted — ~2026-07 (deriva de local-first; reafirmado 2026-08-15).

## Contexto

El estado del producto (estados de dispositivo, transiciones, log de acciones,
incidentes, config de tenant, snapshot de vitrina) vive en la máquina del
cliente. Introducir un motor de BD (SQLite incluido) o un ORM añade esquema,
migraciones y una dependencia de acceso a datos para volúmenes que son de flota,
no de big data. La promesa local-first se cumple mejor con ficheros que el
cliente puede leer, versionar y borrar sin herramientas.

## Decisión

La persistencia es JSON (y JSONL para logs append-only) en disco, gestionada por
la stdlib. `state_store.py` custodia estados/transiciones/acciones; la config es
`config.json` + `.env`; la vitrina demo es `data/cloud_state.json`. Sin BD, sin
ORM, sin servidor de datos.

## Consecuencias

- **A favor:** cero dependencia de datos; el estado es inspeccionable con `cat`;
  backup y borrado triviales; coherente con "el dato del tenant vive en su
  máquina".
- **En contra:** sin consultas relacionales ni transacciones ACID reales;
  concurrencia y HA se resuelven a mano (lease de `cluster.py` para activo/pasivo);
  escrituras cuidadas (merge-no-reemplazo) para no perder campos; ficheros de
  estado versionados generan conflictos si se commitean (por eso CI rechaza
  `data/cloud_state.json` en rama).
- **Denylist:** jamás secretos en `config.json`/`data/`/`.env`; jamás datos
  reales de tenant en `data/cloud_state.json`.

## Dónde vive hoy

`lucidfence/core/state_store.py`, `incidents.py`, `config_loader.py`,
`data/*.json(l)`; contrato del snapshot en [SPEC.md §4](../architecture/SPEC.md);
principio en [CONSTITUTION.md §I](../architecture/CONSTITUTION.md).
