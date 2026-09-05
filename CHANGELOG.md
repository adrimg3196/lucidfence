# Changelog

Formato Keep a Changelog; versionado semántico.

## [2.0.0-dev] - en construcción

### Cambiado
- Reescritura completa en Go con un único binario y dashboard React embebido.
  El código 1.x queda en la rama `legacy/python` y el tag `v1.6.1-python-final`.
- La oficina de agentes (loops, GTM, recon, brand, merge-train) sale del
  repositorio. Quedan solo `ci.yml`, `agent-pr.yml` y `agent-automerge.yml`.

### Eliminado
- Empresa autónoma, atomicmail, whitelabel/FreeDomain, chat de IA, DDM/DSC,
  SSF/CAEP, predicción, HA por lease, app macOS Swift, worker Cloudflare,
  deploy Fly.io y publicación en PyPI (spec §4.2).

## [1.6.1] - 2026-09-04

Última release de la línea Python. Historial completo en
`legacy/python:CHANGELOG.md`.
