# Documentación de LucidFence

Índice de la documentación del repositorio. El [`README.md`](../README.md) de la
raíz es la puerta de entrada para usuarios; aquí vive todo lo demás.

## Para el usuario y el cliente

| Documento | Contenido |
| --- | --- |
| [`README.en.md`](README.en.md) | README en inglés |
| [`product/CLIENTE.md`](product/CLIENTE.md) | Guía de entrega al cliente |
| [`product/README_CLIENTE.md`](product/README_CLIENTE.md) | Manual de la instalación de cliente |
| [`product/README_SAAS.md`](product/README_SAAS.md) | Manual del modo SaaS multi-tenant |

## Arquitectura

| Documento | Contenido |
| --- | --- |
| [`architecture/SPEC.md`](architecture/SPEC.md) | Especificación del repositorio y sus contratos |
| [`architecture/PRODUCT_SPEC.md`](architecture/PRODUCT_SPEC.md) | Especificación de producto |
| [`architecture/AI_AND_MCP.md`](architecture/AI_AND_MCP.md) | Proveedor AI opcional y servidor MCP |
| [`architecture/AUTONOMOUS_GEOFENCING_COMPANY.md`](architecture/AUTONOMOUS_GEOFENCING_COMPANY.md) | Modelo de compañía autónoma gobernada |
| [`architecture/THREAT_MODEL.md`](architecture/THREAT_MODEL.md) | Modelo de amenazas |
| [`architecture/openapi.json`](architecture/openapi.json) | Esquema OpenAPI 3.1 servido en `/api/openapi.json` |

## Operación

| Documento | Contenido |
| --- | --- |
| [`operations/RUNBOOK.md`](operations/RUNBOOK.md) | Playbook del operador |
| [`operations/PILOT_RUNBOOK.md`](operations/PILOT_RUNBOOK.md) | Runbook de piloto |
| [`operations/DEPLOY_FREE.md`](operations/DEPLOY_FREE.md) | Despliegue always-on a coste cero |
| [`operations/DESKTOP_APP.md`](operations/DESKTOP_APP.md) | App de escritorio macOS |
| [`operations/FREEDOMAIN_WHITELABEL.md`](operations/FREEDOMAIN_WHITELABEL.md) | Dominio propio y whitelabel |
| [`operations/health-monitor.md`](operations/health-monitor.md) | Monitor de salud |
| [`operations/OSQUERY.md`](operations/OSQUERY.md) | Posture real del endpoint vía osquery |
| [`operations/self-service-sla-2026-07-14.md`](operations/self-service-sla-2026-07-14.md) | SLA de self-service |

## Roadmap

`roadmap/` contiene el roadmap anual, el trimestral y el del tooling del loop.

## Interno

`internal/` (kanban, estado, loop, plan y revisiones) y `gtm/` (go-to-market)
son material de trabajo del equipo: se excluyen del tarball de release vía
`.gitattributes`.

## Contratos para agentes

- [`../AGENTS.md`](../AGENTS.md) — contrato raíz que leen los agentes. **No se mueve**: la ruta es parte de la convención.
- [`agents/`](agents/) — prompts de rol (code-reviewer, security-auditor, test-engineer) que invocan `/ship` y equivalentes.
- [`references/`](references/) — definition of done, patrones de test y checklist de seguridad.
- [`superpowers/`](superpowers/) — planes y especificaciones generados por el marco de skills.
