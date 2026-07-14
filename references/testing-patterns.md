# Testing Patterns — LucidFence (Python)

Referencia rápida de patrones de test para el stack de LucidFence. Usar junto
con el ciclo test-driven-development del marco agent-skills.

## Estructura (Arrange-Act-Assert)

```python
def test_geocerca_fuera_cuando_dispositivo_lejos():
    # Arrange
    fence = {"kind": "circle", "center": {"lat": 40.42, "lng": -3.70}, "radius_m": 500}
    dev = DeviceReport(device_id="d1", lat=40.50, lng=-3.70, ...)
    # Act
    state = evaluate_fence_state(dev, fence)
    # Assert
    assert state == "outside"
```

## Nomenclatura

```python
# Patrón: [unidad] [comportamiento esperado] [condición]
def test_evaluate_fence_state_dentro_cuando_cerca():
def test_evaluate_fence_state_fuera_cuando_lejos():
def test_risk_score_alto_cuando_rooted():
def test_cve_summary_vacio_cuando_sin_apps():
```

## Aserciones comunes

```python
assert result == expected                      # igualdad
assert result["compliant"] is False            # identidad
assert 0 <= score <= 100                       # rangos
assert "outside" in states                      # pertenencia
assertRaises(ValueError, fn, bad_arg)           # errores
with pytest.raises(ValueError): fn(bad_arg)     # (si hay pytest)
```

## Mocking en límites (no en lógica interna)

```
Mockear:                No mockear:
├── HTTP / requests     ├── Lógica de riesgo
├── Llamadas a APIs    ├── Validación de geocerca
├── Sistema de archivos├── Transformaciones de datos
├── Time/date          ├── Funciones puras
```

Ejemplo con `unittest.mock`:

```python
from unittest.mock import patch, MagicMock
with patch("core.adapters.applivery.requests.post") as mock_post:
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = "ok"
    out = delegate_webhook(...)
assert mock_post.called
```

## Tests de integración (HTTP local)

El runner `tests/run_tests.py` arranca `saas_server.py` en `:8765` de forma
hermética para los tests que lo requieren. Los tests usan `http.client`:

```python
def _login(email, pw):
    status, body, cookie = req("POST", "/api/auth/login", {"email": email, "password": pw})
    assert status == 200
    return cookie

def test_run_once_requiere_auth():
    status, _, _ = req("POST", "/api/run-once")   # sin cookie
    assert status == 401
```

## Anti-patrones

| Anti-patrón | Problema | Mejor |
|---|---|---|
| Testear detalles de implementación | Rompe al refactor | Testear inputs/outputs |
| Snapshot de todo | Nadie revisa diffs | Asertar valores específicos |
| Estado mutable compartido | Tests se contaminan | Setup/teardown por test |
| `test.skip` permanente | Código muerto | Arreglar o borrar |
| Aserciones muy amplias | No caza regresiones | Ser específico |
| Sin manejo de error async | Falsos pass | `try/except` en tests async |
