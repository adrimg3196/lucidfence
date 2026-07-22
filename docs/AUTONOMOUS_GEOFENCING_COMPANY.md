# LucidFence Autonomous Geofencing Company

## Objetivo

Convertir LucidFence en un sistema que avance de manera continua sobre objetivos de geofencing/UEM, sin convertir autonomía en acceso irrestricto a dispositivos.

La unidad de trabajo ya no es un prompt libre: es un objetivo medible que produce decisiones, tareas, evidencia, criterios de aceptación y un handoff humano cuando existe riesgo operativo.

## Referencia evaluada

Referencia conceptual: `MaxMiksa/Auto-Company`, commit `ebfab9b4bd5f0ab5ad452a1ff85285b3c141acdd`, inspeccionado el 21-jul-2026.

No se copió código, prompts ni perfiles. El repositorio no contiene un archivo `LICENSE` aunque su README muestre una insignia MIT. La implementación de LucidFence es limpia y original.

### Qué aprendimos y qué cambiamos

| Auto-Company observado | Riesgo para UEM/geofencing | Implementación LucidFence |
|---|---|---|
| Loop continuo con sesión nueva y un `consensus.md` | Estado global mutable, no tenant-scoped | JSON estructurado y atómico dentro del directorio de cada tenant |
| Personas históricas como agentes | Roles vistosos pero poco ligados a controles UEM | 9 roles funcionales: Mission Control, Field Intelligence, Geo Policy, UEM Operations, Risk & Compliance, Product Value, ROI & Finance, Independent Critic y QA & SRE |
| `Ship > Plan > Discuss` | Puede empujar acciones antes de demostrar seguridad | `Evidence > Simulate > Approve > Handoff`; sin evidencia no hay tarea válida |
| `bypassPermissions` y `danger-full-access` por defecto | Inaceptable para equipos, secretos y comandos remotos | RBAC, sesión obligatoria, API keys limitadas, policy engine y estado fail-closed |
| Ejecutar sin aprobación humana | Puede bloquear, borrar o aislar equipos reales | Solo análisis/simulaciones LOW son autónomas; MEDIUM requiere una aprobación; HIGH dos; FORBIDDEN nunca se aprueba |
| Dashboard con POST start/stop sin autenticación | Control local vulnerable si se expone el puerto | Endpoints autenticados y tenant-scoped, auditados mediante cadena hash |
| Progreso validado por actualización del consenso | Un texto puede afirmar éxito sin artefactos | Cada tarea exige evidencia y criterios de aceptación; el resultado indica explícitamente si hubo side effects |
| Circuit breaker por errores consecutivos | Útil, pero no cubre riesgo de negocio | Pausa persistente, bloqueo por clase de acción, handoff separado y kill switch existente del loop |
| Un equipo grande de agentes | Coste y coordinación innecesarios | Squad dinámico mínimo según señales reales del ciclo |

## Modelo operativo

```text
Objetivo medible
      │
      ▼
Snapshot tenant (flota, geovalla, riesgo, CVE, incidentes, compliance)
      │
      ▼
Mission Control selecciona objetivo P0→P2 y forma squad
      │
      ├── Geo Policy            → simulación de geovalla
      ├── Field Intelligence    → calidad/anomalías de ubicación
      ├── Risk & Compliance     → CVE, SOAR, CIS/ISO
      ├── UEM Operations        → incidentes y handoff reversible
      └── QA & SRE              → evidencia, criterios, rollback
      │
      ▼
Policy gate: LOW / MEDIUM / HIGH / FORBIDDEN
      │
      ├── LOW + simulate/execute_safe → resultado local sin side effects
      ├── MEDIUM                    → 1 aprobación → ready_for_handoff
      ├── HIGH                      → 2 aprobadores distintos
      └── FORBIDDEN                 → blocked permanente
```

## Contrato de seguridad

Acciones autónomas permitidas:

- `simulate_geofence`
- `analyze_location_quality`
- `assess_compliance`
- `analyze_incidents`
- `optimize_routes`

Acciones de riesgo medio —recomendación o handoff únicamente—:

- `recommend_soar_playbook`
- `notify_owner`
- `request_device_lock`

Acciones siempre prohibidas desde el control plane:

- `wipe`
- `factory_reset`
- `delete_device`
- `delete_tenant`
- `disable_audit`

Una aprobación no ejecuta el comando UEM. Cambia la tarea a `ready_for_handoff`; la ejecución sigue ocurriendo en el flujo UEM existente, con identidad del operador, dry-run/cooldown y auditoría.

## API

- `GET /api/company`
- `POST /api/company/goals`
- `POST /api/company/cycle`
- `POST /api/company/pause`
- `POST /api/company/resume`
- `POST /api/company/tasks/{task_id}/approve`
- `POST /api/company/tasks/{task_id}/reject`

Roles:

- owner/admin: lectura, objetivos, ciclos, pausa y aprobación;
- operator: lectura y ciclos seguros;
- viewer/auditor: solo lectura;
- API key: nunca crea objetivos, pausa ni aprueba handoffs.

## Modo principal: PWA 100% web y gratuita

`static/web.html` es una aplicación operativa independiente del backend Python. Se empaqueta como un bundle estático owner-neutral y cada organización lo publica en su propia infraestructura: GitHub Pages, Cloudflare Pages, S3, Nginx, Caddy o intranet. No requiere cuenta, instalación, tarjeta, Docker ni API de pago.

- `web-core.js`: objetivos, policy gate y ciclos deterministas;
- `web-worker.js`: ejecuta el ciclo fuera del hilo de interfaz;
- `web-store.js`: persistencia local en IndexedDB, con fallback localStorage;
- `sw.js`: caché offline e instalación PWA;
- importación/exportación JSON para portabilidad del workspace;
- CSP cerrada y rechazo de campos `token`, `secret`, `password`, `authorization` y `api_key`;
- sin dominio canónico, autenticación central, actualización forzada ni telemetría del autor;
- `scripts/build_web_bundle.py` genera ZIP determinista, `SHA256SUMS` y plantillas self-host.

El modo web ejecuta únicamente simulaciones sin efectos externos. La API Python anterior permanece como opción avanzada para despliegues soberanos y conectores UEM autenticados, pero deja de ser un requisito para usar el producto.

### Conectores live

Un navegador no puede almacenar de forma segura una API key UEM en JavaScript, y muchos proveedores bloquean CORS. Por ello:

1. la demo y todas las simulaciones funcionan sin backend;
2. OAuth con PKCE puede conectarse directamente cuando el proveedor lo permita;
3. conectores basados en secretos requieren un gateway opcional del cliente, compatible con un free tier como Cloudflare Workers;
4. GitHub Pages nunca recibe ni almacena credenciales.

“Gratis” significa software, hosting estático y modo operativo de simulación sin coste obligatorio. Los free tiers externos tienen cuotas y no equivalen a hosting live ilimitado garantizado.

## Persistencia y límites

Cada tenant guarda `autonomous_company.json` con permisos `0600`. La escritura usa un temporal y `os.replace`; se conservan hasta 500 tareas y 200 decisiones. Ninguna credencial se copia al contexto de un ciclo.

El sistema implementado es determinista y local. Todavía no invoca un LLM por sí mismo ni ejecuta un daemon 24/7: el loop externo puede proponer trabajo, pero este control plane es la autoridad que valida el objetivo, la evidencia, la clase de riesgo y el handoff. Esta separación evita que un proveedor/modelo se convierta en autoridad UEM.

## Criterio de éxito

Un ciclo es exitoso solo si:

1. existe un objetivo activo con al menos una métrica;
2. el snapshot pertenece al tenant actual;
3. cada tarea tiene fuente de evidencia y criterio de aceptación;
4. la policy asigna riesgo y número de aprobaciones;
5. cualquier resultado autónomo declara `side_effects: false`;
6. se registra un evento en la auditoría encadenada;
7. la compañía puede pausarse y falla cerrada mientras está pausada.
