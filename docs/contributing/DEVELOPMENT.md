# Development Guide — LucidFence

Cómo trabajar en el código de LucidFence: correr tests, añadir adaptadores, respetar la convención stdlib-first.

## Prerequisites

- **Python 3.11+** (el proyecto usa `tomllib`, stdlib desde 3.11; en 3.9 instalar `tomli`)
- **pip** para instalar dependencias
- ** playwirght** (opcional) para tests de dashboard

```bash
# Activar el venv del proyecto (Python 3.11)
cd /Users/adri/lucidfence
source .venv/bin/activate

# O con el python directo del venv
.venv/bin/python scripts/verify.py
```

## Correr los tests

```bash
# Runner honesto (el gate de calidad usa esto)
.venv/bin/python tests/run_tests.py

# Ver todos los resultados
.venv/bin/python tests/run_tests.py 2>&1 | tail -5
```

Salida esperada: `===\s*555 passed, 0 failed ===`

## El gate de calidad: verify.py

```bash
# Todo el gate (4 checks)
.venv/bin/python scripts/verify.py

# Solo versión + enlaces docs (rápido, útil en CI)
.venv/bin/python scripts/verify.py --docs-only

# Omite runtime battery (para desarrollo rápido)
.venv/bin/python scripts/verify.py --fast

# Resumen final solo
.venv/bin/python scripts/verify.py --quiet
```

Los 4 checks:

1. **Coherencia de versión** — `cli.VERSION == pyproject.toml == .release-version`
3. **Batería runtime** — `scripts/runtime_validation.py` da N/N con claims validados
4. **Suite honesta** — `tests/run_tests.py` pasa todas (tolerando solo la baseline OIDC)

## Añadir un adaptador UEM nuevo

```bash
# Genera el esqueleto del adaptador
.venv/bin/python lucidfence/cli.py adapter new nombre-adapter

# Esto crea:
#   lucidfence/core/adapters/nombre_adapter.py
#   tests/test_adapter_nombre_adapter.py

# Implementar el adaptador siguiendo el contrato SDK
# Ver: lucidfence/core/adapters/__init__.py para el registro

# Probar que el contrato se cumple
.venv/bin/python tests/run_tests.py
```

El contrato SDK exige:

- `execute(self, device_id, action, config)` → dict con resultado
- `dry_run(self, device_id, action, config)` → sin efectos laterales
- `supported_actions(self)` → lista de acciones que soporta
- `supports_device(self, device)` → bool

Véase [`new-adapter-guide.md`](new-adapter-guide.md) para el proceso completo.

## Convenciones de código

### Stdlib-first

El proyecto prioriza la stdlib de Python antes que dependencias externas. Solo añadir dependencias de terceros si:
- La stdlib no puede hacerlo (ej: requests para HTTP, PyJWT para JWT)
- Hay una razón de seguridad/correctness clara

### Estructura del paquete

```
lucidfence/
├── cli.py              # CLI de ciclo de vida
├── shell.py            # Shell interactiva
├── core/               # Motor, políticas, estado
│   ├── actions.py      # Catálogo de acciones
│   ├── alerts.py       # Sistema de alertas
│   ├── config_validator.py
│   ├── declarative.py  # Gate declarativo vs imperativo
│   ├── ddm.py          # Apple DDM
│   ├── engine.py       # Motor de geofencing
│   ├── export.py       # Exportación de evidencias
│   ├── locations.py    # Fuentes de ubicación
│   ├── oidc.py         # Auth OIDC
│   ├── policy.py       # DSL de políticas
106|│   ├── policies.py    # Evaluación de riesgo + RiskEngine
│   ├── saas.py         # Multi-tenant SaaS
│   ├── sentinels.py    # Sentinelas de alertas
│   ├── unique.py       # Identidad única de dispositivos
│   ├── windows.py      # PowerShell DSC
│   └── multiuem.py     # Normalización multi-UEM
├── adapters/           # Conectores UEM
│   ├── __init__.py     # Registro de adaptadores
│   ├── applivery.py
│   ├── intune.py
│   ├── jamf.py
│   └── scaffold.py     # Generador de esqueletos
├── saas/               # Capas SaaS/multi-tenant
│   ├── api.py
│   ├── auth.py
│   └── tenant.py
└── plugins/            # Índice verificado de plugins
    └── index.py
```

### Testing

- Todos los tests son funciones `test_*` en archivos `test_*.py`
- Tests que necesitan credenciales reales usan mocks (véase `test_adapter_applivery.py` como ejemplo)
- Tests de contratación SDK en `tests/test_sdk_contract.py`
- Tests que requieren playwright están marcados con `SKIP` si no está instalado

### Commits

Los commits siguen [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(scope): descripción
fix(scope): descripción
docs(scope): descripción
test(scope): descripción
chore(scope): descripción
```

Los scopes comunes: `core`, `adapters`, `cli`, `docs`, `ci`, `sdk`, `risk`, `policy`.

## Reviewer checklist

Antes de mergear un PR:

1. **verify.py pasa** — todos los 4 checks OK
2. **Tests nuevos cubren el cambio** — si añades funcionalidad, añades tests
3. **No secrets en el código** — usar variables de entorno o vault
4. **Compatibilidad con Python 3.11+** — sin dependencias solo stdlib
5. **Docs actualizados** — si cambias la API o añades features, actualiza la doc

## Debugging

```bash
# Modo debug del servidor
LUCIDFENCE_LOG_LEVEL=DEBUG .venv/bin/python lucidfence/cli.py start

# Ver logs
tail -f /Users/adri/lucidfence/logs/*.log

# Ver estado del servidor
.venv/bin/python lucidfence/cli.py status

# Comprobar health
curl http://localhost:8765/api/health
```

## Rendimiento

El sistema está diseñado para funcionar en máquinas con recursos limitados. Los tests de rendimiento se corren en CI y los resultados se documentan en `docs/operations/coverage`.

## Seguridad

- **Nunca hardcodear secrets** — usar `LUCIDFENCE_*` env vars o vault
- **Validar todas las entradas** — el validador de config está en `core/config_validator.py`
- **RBAC** — los permisos se gestionan en `saas/auth.py`
- **Auditoría** — todas las acciones se loguan en `core/audit.py`

Véase [`docs/internal/security/`](../internal/security/) para el modelo de seguridad completo.
