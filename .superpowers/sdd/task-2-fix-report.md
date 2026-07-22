# Task 2 fix report

## Alcance

Se corrigieron únicamente `core/multiuem.py` y sus pruebas focales. No se modificaron providers, engine, auth, frontend ni documentación de producto.

## Evidencia TDD (RED → GREEN)

RED observados antes de cada cambio de producción:

1. Routing de dispositivo `dict`: `AssertionError` en `calls == ["b-7"]`; no se invocaba Intune.
2. Frontera de respuesta: `AssertionError` al esperar que `request_id` arbitrario fuese descartado.
3. Validación de bindings: `AssertionError: ValueError not raised` para nombre inválido.
4. Cero bindings/estado: `AssertionError` al esperar `status == "error"`.

GREEN focal final:

```text
FOCAL: 18 passed
```

## Cambios verificados

- Routing equivalente para `NormalizedDevice` y `dict`, seleccionando por `provider_refs` + capability y usando siempre el ID de la referencia del proveedor objetivo.
- Respuestas de callback requieren `ok: bool`, validan tipos permitidos, fijan `adapter` al binding y se reducen a la allowlist: `ok`, `adapter`, `action`, `mode`, `dry_run`, `delegated`, `error_type`, `http_status`.
- Respuestas inválidas devuelven `invalid_response`; secretos/cuerpos/headers/request/message y otros campos se descartan.
- Constructor fail-fast con `ValueError` determinista para binding, nombre, duplicados, capabilities y callbacks inválidos.
- `params` y respuesta del callback se desacoplan mediante copia profunda.
- `sync()`/`health()` usan `RLock`; health interno, `SyncResult.health` y `health()` no comparten diccionario mutable; los sync concurrentes quedan serializados.
- Política explícita de cero bindings: `SyncResult.status == "error"`.

## Gates ejecutados

```text
FOCAL: 18 passed
DOMAIN: 15 passed
SDK CONTRACT: 7 passed
Honest runner (primer intento): 281 passed, 4 failed
  Causa: dependencia Playwright ausente, no regresión del cambio.
Honest runner (tras instalar Playwright/Chromium en .venv ignorado): 287 passed, 0 failed
python py_compile: PASS
git diff --check: PASS
static secret/dangerous-code scan: sin hallazgos
browser gates incluidos en runner: cloud install smoke, self-service Playwright,
cloud page smoke y dashboard de 19 vistas, todos PASS.
```

Los archivos de telemetría generados por el runner (`data/device_states.json`, `data/dwell.json`, `data/stats_history.jsonl`, `data/trails.jsonl`) fueron restaurados. También se eliminaron `uv.lock` y `lucidfence_local.egg-info/` generados al preparar el entorno.

## Concerns

Ninguno bloqueante. El constructor vacío se conserva por compatibilidad para permitir respuestas `unknown_provider`; la política de error se aplica al ejecutar `sync()`.
