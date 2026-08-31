# POLICY_DSL Reference — LucidFence

La Policy DSL (Domain-Specific Language) de LucidFence define cómo se expresan las políticas de geofencing y riesgo del sistema.

## Tipos de política

### 1. Geofencing Policy

```yaml
policy:
  name: "oficina-cerca"
  type: geofence
  trigger:
    event: location_update
  condition:
    within:
      lat: 40.4168
      lon: -3.7038
      radius_m: 200
  action:
    - notify: "device_in_office_zone"
    - log: true
```

### 2. Risk Policy

```yaml
policy:
  name: "alto-riesgo-conexion--publica"
  type: risk
  condition:
    risk_score:
      gte: 75
    signals:
      - network_public
      - jailbroken
  action:
    - lock: true
    - notify_admin: true
    - escalate: P1
```

## Operadores disponibles

| Operador | Descripción | Ejemplo |
|----------|-------------|---------|
| `eq` | Igual que | `os == "ios"` |
| `neq` | No igual | `status != "compliant"` |
| `gte` | Mayor o igual | `risk_score >= 50` |
| `gt` | Mayor que | `risk_score > 75` |
| `lte` | Menor o igual | `battery <= 15` |
| `lt` | Menor que | `battery < 10` |
| `in` | Pertenece a lista | `platform in ["ios", "macos"]` |
| `notin` | No pertenece | `state notin ["lost", "stolen"]` |
| `within` | Dentro de geocerca | `within: {lat, lon, radius_m}` |

## Señales disponibles

- `location_update` — Actualización de ubicación
- `compliance_change` — Cambio de estado de cumplimiento
- `risk_score_change` — Actualización del score de riesgo
- `device_compromised` — Dispositivo marcado como comprometido
- `network_public` — Conectado a red pública
- `jailbroken` / `rooted` — Dispositivo jailbroken/rooteado
- `encryption_disabled` — Cifrado desactivado
- `os_outdated` — Sistema operativo desactualizado

## Estructuras de datos

### LocationEvidence

```python
@dataclass
class LocationEvidence:
    lat: float
    lon: float
    accuracy_m: float
    source: str  # "gps", "wifi", "cell"
    timestamp: str  # ISO 8601
```

### NormalizedDevice

```python
@dataclass
class NormalizedDevice:
    canonical_id: str
    provider: str
    provider_device_id: str
    name: str
    platform: str
    serial_number: str | None = None
    compliant: bool | None = None
    status: str = "unknown"
    # ... más campos
```

## Ejemplos completos

### Ejemplo 1: Política de geocerca con acciones múltiples

```yaml
policies:
  - name: "zona-segura-oficina"
    type: geofence
    enabled: true
    trigger:
      event: location_update
    condition:
      within:
        lat: 40.4168
        lon: -3.7038
        radius_m: 150
      platform: ios
    actions:
      - notify_user: "Has entrado en la zona segura"
      - log_event: true
      - update_compliance: compliant
```

### Ejemplo 2: Política de riesgo con umbral dinámico

```yaml
policies:
  - name: "riesgo-medio-alto"
    type: risk
    enabled: true
    condition:
      risk_score:
        gte: 50
      AND:
        - network_public: true
        - not: jailbreak_checked
    actions:
      - notify: admin
      - require_auth: true
      - log: true
```

### Ejemplo 3: Política compuesta con OR

```yaml
policies:
  - name: "dispositivo-peligroso"
    type: risk
    enabled: true
    condition:
      OR:
        - risk_score >= 80
        - jailbroken: true
        - encryption_disabled: true
        - os_outdated: true
          AND:
            - os_version < "16.0"
    actions:
      - lock_device: false  # Solo advertencia
      - notify_admin: true
      - create_ticket: true
```

## Validación

Las políticas se validan al aplicar:

```bash
lucidfence apply policy.yaml --dry-run
```

El comando muestra qué haría la política sin ejecutar acciones reales.

## Integración con UEM

Cada política puede tener adaptadores específicos:

```yaml
policy:
  name: "intune-only-policy"
  adapters:
    - intune
  condition:
    # ...
```

Véase también [Operaciones en producción](../operations/PRODUCTION.md) para configuración en producción.
