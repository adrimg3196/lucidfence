# Changelog

Formato Keep a Changelog; versionado semántico.

## [2.0.0-dev] - en construcción

### Añadido
- Pre-release `2.0.0-alpha.2` (hito M2, riesgo y acciones): motor de riesgo
  explicable con siete señales y veredicto 0-100 con razones; integridad de
  ubicación, permanencia y violación sostenida; acciones de ruta; políticas con
  gramática `field / op / value`, plantillas y simulador what-if; guardarraíles
  completos (deduplicación, cooldown persistido, observe/enforce, allowlist de
  acciones en vivo, doble llave de wipe); incidentes con ciclo de vida y
  analítica; reglas de alerta; playbooks SOAR con handoffs humanos para lo
  destructivo; webhook HMAC-SHA256 compatible con 1.x, OCSF 2004 sin
  coordenadas, ntfy y cola de entregas tras una allowlist de egress con DNS y
  rechazo de IP privadas; ajustes editables (enforcement, webhooks, ntfy,
  egress, riesgo); eventos y acciones paginados con cursor; vistas de
  políticas, incidentes, alertas, playbooks y handoffs, eventos, acciones,
  ajustes y detalle de dispositivo con riesgo explicado; batería 22/22 y
  Playwright con what-if y aprobación de handoff.
- Pre-release `2.0.0-alpha.1` (hito M1, núcleo demo): binario único `lucidfence` con
  `serve`, `doctor`, `open` y `version`, apagado ordenado con SIGINT/SIGTERM.
- Dominio geoespacial en Go: geocercas circulares y poligonales, rutas, POIs,
  dispositivos y transiciones con histéresis.
- Almacenamiento JSON/JSONL por organización con escritura atómica.
- Motor de evaluación con ciclo periódico, `run-once`, estadísticas por ciclo y
  guardrails en modo observe (acciones simuladas y registradas, nunca ejecutadas).
- Conector de simulación con flota demo de seis dispositivos en Madrid.
- Autenticación mínima: asistente inicial, login con argon2id, sesión por cookie
  con CSRF, token local para la CLI, roles y capacidades.
- API `/api/v1` documentada en `docs/openapi.yaml` (`x-capability` por ruta) con
  test de paridad contra el registro de rutas.
- Dashboard React embebido: asistente inicial, login, visión general, mapa
  MapLibre, dispositivos y editor de geocercas; español por defecto, inglés
  disponible, tema claro y oscuro.
- Batería en vivo (`make battery`), recorrido e2e con Playwright (`make e2e`) y
  seis checks obligatorios en CI.

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
