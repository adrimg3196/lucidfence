# ADAPTER.md — Cómo escribir un conector MDM para Geofence UEM

El producto es **agnóstico al MDM**. La única superficie que tocas para soportar
un nuevo UEM (Intune, Jamf, Fleet, Workspace ONE...) es la interfaz `MDMAdapter`.

## El contrato (congelado)

```python
from core.adapters.base import MDMAdapter

class MiMdmAdapter(MDMAdapter):
    name = "mimdm"  # identificador estable, minúsculas

    def execute(self, device, action: str, params: dict, dry_run: bool = False) -> dict:
        device_id = self._dev_id(device)   # helper heredado
        # ... llama a la API de tu MDM ...
        return {
            "adapter": self.name,
            "ok": True,               # o False con "error": "..."
            "device_id": device_id,
            "action": action,
            # ...detalles (status_code, url, response, delegated, etc.)...
        }
```

**Reglas duras:**
1. `execute` **NUNCA debe hacer `raise`**. Ante fallo devuelve `{"ok": False, "error": "..."}`.
   El dashboard no debe 500ear por un MDM caído.
2. `name` debe ser estable y único (se usa para auditoría y routing).
3. Acciones válidas (`VALID_ACTIONS`): `lock, wipe, message, locate, reboot,
   clear_passcode, custom`. Si tu MDM no soporta una, devuelve `ok: False` con
   una nota, no crashees.
4. `dry_run=True` debe construir la petición pero no enviarla.

## Cómo registrarlo

En `core/adapters/__init__.py`:

```python
from core.adapters.mimdm import MiMdmAdapter
ADAPTER_REGISTRY["mimdm"] = MiMdmAdapter
```

El engine selecciona el adapter por el campo `uem.adapter` del `config.json`
del tenant (default `applivery`). El `mode: simulation` siempre usa
`SimulationAdapter` (demo 100% local).

## Tests contra mock (obligatorio para el PR)

Crea `tests/test_adapter_mimdm.py` que:
- Instancia `MiMdmAdapter` sin credenciales y verifica que `execute` devuelve
  `ok: True` en modo mock (no toca red).
- Para el path live, usa `monkeypatch`/`unittest.mock` sobre `requests.post`
  y verifica el mapeo de acción → endpoint de tu MDM.
- NUNCA hagas llamadas reales a la API de tu MDM en los tests del repo.

CI (`.github/workflows/ci.yml`) corre `tests/run_tests.py`; tu PR debe pasarlo
en verde para recibir el badge **verified**.

## Adapter Bounty Sprint & Hall of Fame

Lanzamos un sprint de 2 semanas por release donde los primeros adapters
verificados de los MDMs más pedidos (Intune, Jamf hoy stub; luego Fleet...)
entran al **Hall of Fame** del README y su autor se vuelve *Adapter Maintainer*
(con co-maintainership y voz en el roadmap de la interfaz).

¿Tu MDM no está? Ábrelo. Es un PR de fin de semana.
