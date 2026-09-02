# Privacidad: inventario de datos y geofencing derivado (#257 + #258)

Este documento cubre los dos módulos de privacidad por diseño entregados por
Hermes para LucidFence. Ambos son **read-only metadata / modelo determinista**
(stdlib-only, testeable offline) y respetan el contrato del charter: el runtime
real permanece bajo control del administrador.

## 1. Inventario de datos — transparencia, retención, minimización (#257)

Módulo: `lucidfence/core/data_inventory.py`. Responde "qué sabe LucidFence"
por dispositivo y tenant.

### Metadatos por campo (obligatorios para persistir)
Cada campo declarado lleva: `purpose`, `source`, `collected_at`,
`retention_class`, `visibility` y (resuelto en ingest) `retention_seconds` /
`purge_at`.

### Clases de retención
| Clase | Ventana | Uso típico |
|---|---|---|
| `ephemeral` | ≤ 1h | señales live CoT |
| `short` | ≤ 7d | estado geo derivado |
| `standard` | ≤ 90d | postura / identidad |
| `long` | ≤ 365d | vulnerabilidad / auditoría |
| `forever` | sin purge | archivo de cumplimiento |
| `undeclared` | — | **rechazado** en ingest |

### Garantías (criterios de aceptación de #257)
- Campos sin `purpose`/`source`/`collected_at` o con retención `undeclared`
  **se rechazan en `ingest`** (nunca persistidos) — es la garantía de minimización.
- `purge()` elimina exactamente los campos con `now >= purge_at` (en el límite
  configurado, no antes). El informe `PurgeReport` trae **conteos, por-categoría
  y un hash sha256** de la operación, **nunca los valores borrados**.
- RBAC: solo roles con `report:export` o `audit:read` (owner/admin/auditor)
  consultan el inventario; `viewer`/`operator` reciben `denied`. Se reusa la
  matriz `ROLE_CAPS` de `saas/auth.py` (no se inventa capacidad nueva).
- `inventory_export()` nunca expone campos con marcadores secretos
  (`private_key`, `secret`, `token`, `password`, `key_material`, `api_key`,
  `bearer`) aunque el rol esté autorizado.

## 2. Geofencing por estado derivado, sin coordenadas (#258)

Módulo: `lucidfence/core/derived_geo.py`. Muchas políticas solo necesitan
inside/outside/unknown; conservar lat/lng aumenta riesgo sin valor operativo.

### Señal derivada
`DerivedGeoSignal`: `fence_id`, `device_id`, `tenant_id`, `state`
(inside/outside/unknown), `observed_at`, `policy_hash`, `source`, `confidence`,
y opcionalmente `lat`/`lng` (solo para probar la ruta de venom).

### Modo por tenant `DERIVED_ONLY` (opt-in)
- Al activarse, `ingest()` **elimina `lat`/`lng`** del regististro — no se
  persisten en storage, logs, exports ni `cloud_state`.
- La activación reporta los trade-offs vía `activation_tradeoffs()`:
  sin seguimiento histórico de movimiento, sin auditoría forense de coordenadas
  pasadas, sin recomputar la decisión contra otra geometría de geocerca.
- `FULL` (default) conserva coordenadas; es la opción del administrador.

### Garantías (criterios de aceptación de #258)
- **Test de veneno**: coordenadas envenenadas (`lat=99.999,lng=999.999`) en
  `DERIVED_ONLY` no llegan a `to_cloud_state()` ni a `export_evidence()`.
- inside/outside/unknown se evalúan con `policy_hash` + frescura.
- Cambio de `policy_hash` **invalida** la señal previa → `unknown`.
- Replay (nonce repetido) o timestamp futuro **bajan la confianza a `low`** y
  quedan **visibles** (`replay_detected` / `future_timestamp`), no ocultos.
- `export_evidence()` prueba la decisión (cerca, política, cuándo, fuente,
  confianza, hash) **sin reconstruir una ruta personal**.

## Integración
- `data_inventory` se alimenta desde `state_store` / engine declarando los
  metadatos de cada campo persistido; `purge()` corre como job periódico.
- `derived_geo` se apoya en el cliente on-device existente y en
  `location_integrity` (anti-spoofing); el engine evalúa la política y guarda
  solo el estado derivado cuando el tenant está en `DERIVED_ONLY`.

## Referencia primaria
- [NIST Privacy Framework](https://www.nist.gov/privacy-framework)
