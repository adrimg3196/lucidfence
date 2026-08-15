# LucidFence — Guía para contribuir un adaptador UEM nuevo

Un adaptador UEM (Universal Endpoint Management) le permite a LucidFence hablar con tu proveedor MDM/UEM existente (Applivery, Intune, Jamf, Fleet, y otros). Cada adaptador es un plugin Python que implementa una interfaz mínima.

## Qué necesitas antes de empezar

- Python 3.11+
- Conocimiento de la API de tu proveedor UEM (endpoints, auth, rate limits)
- Un entorno de test local (puedes correr contra mock primero)

## Contrato mínimo del adaptador

El engine espera que cada adaptador implemente la clase `MDMAdapter` con estos métodos:

```python
class MDMAdapter(ABC):
    # Autenticación y gestión de credenciales
    def authenticate(self, credentials: dict) -> bool
    def refresh_credentials(self) -> bool

    # Dispositivos
    def get_devices(self) -> list[Device]
    def get_device_location(self, device_id: str) -> Location | None

    # Comandos (opcionales, implementa solo los que tu UEM soporta)
    def lock(self, device_id: str) -> bool
    def wipe(self, device_id: str) -> bool
    def message(self, device_id: str, text: str) -> bool
    def locate(self, device_id: str) -> bool
    def reboot(self, device_id: str) -> bool
```

Ver `lucidfence/core/adapters/base.py` para la interfaz completa y los tipos `Device`, `Location`, etc.

## Pasos para agregar un adaptador nuevo

### 1. Crear el archivo del adaptador

```bash
touch lucidfence/core/adapters/<nombre>.py
```

Donde `<nombre>` es el slug en minúscula del proveedor (ej: `applivery.py`, `intune.py`, `jamf.py`).

### 2. Implementar la clase

```python
# lucidfence/core/adapters/<nombre>.py
from lucidfence.core.adapters.base import MDMAdapter, Device, Location

class <Nombre>Adapter(MDMAdapter):
    name = "<Nombre>"
    slug = "<nombre>"

    def authenticate(self, credentials: dict) -> bool:
        # TODO: implementar auth contra la API de <nombre>
        ...

    def get_devices(self) -> list[Device]:
        # TODO: listar dispositivos de la flota
        ...

    def get_device_location(self, device_id: str) -> Location | None:
        # TODO: obtener ubicación del dispositivo
        ...
```

### 3. Registrar el adaptador

El descubrimiento del core lee los adaptadores registrados. Verifica que tu adaptador aparece en el dashboard después de implementarlo.

### 4. Escribir tests contra mock

Crea `tests/test_adapter_<nombre>.py` con:
- Happy path: autenticación exitosa, listado de dispositivos, ubicación
- Casos de error: credenciales inválidas, dispositivo no encontrado, rate limit

El PR template exige: `tests/test_adapter_<mdm>.py` cubre happy path + al menos un caso de error.

### 5. Actualizar el índice de adaptadores

Si el core usa un índice explícito (ver `lucidfence/plugins/`), agrega tu adaptador al índice con el hash verificado.

### 6. Hacer PR

Usa el PR template (`.github/PULL_REQUEST_TEMPLATE.md`). Marca los checkboxes del checklist de adaptador MDM.

## Ejemplos existentes

Revisa los adaptadores existentes para ver el patrón:

```bash
ls lucidfence/core/adapters/
# → applivery.py, intune.py, jamf.py, ...
```

Cada uno implementa el contrato mínimo con código real contra la API del proveedor.

## Testing local sin credenciales

Puedes probar tu adaptador contra mock sin credenciales reales del UEM:

```bash
# Mock del adaptador
python3 -c "
from unittest.mock import MagicMock
from lucidfence.core.adapters.<nombre> import <Nombre>Adapter

adapter = <Nombre>Adapter()
adapter.authenticate = MagicMock(return_value=True)
adapter.get_devices = MagicMock(return_value=[Device(id='test', name='test')])
print(adapter.get_devices())
"
```

## Sobre credenciales y seguridad

- **Nunca hardcodees credenciales en el adaptador.**
- El engine espera que las credenciales lleguen vía el mecanismo de config del cliente (env vars, vault, etc.).
- El adaptador debe validar que las credenciales son suficientes antes de hacer requests.
- Los logs del engine sanitizan datos sensibles — no logs credenciales.

## Checklist antes de abrir PR

- [ ] `authenticate()` funciona con credenciales válidas e inválidas
- [ ] `get_devices()` retorna lista de `Device` con los campos esperados
- [ ] `get_device_location()` retorna `Location` o `None` si no hay ubicación
- [ ] Comandos opcionales implementados si el UEM los soporta
- [ ] Tests contra mock cubren happy path + al menos un caso de error
- [ ] El adaptador no hardcodea credenciales ni endpoints sensibles
- [ ] El adaptador se registra y aparece en el dashboard
- [ ] PR usa el template `.github/PULL_REQUEST_TEMPLATE.md`

## Preguntas

Abre un issue etiquetado `enhancement` describiendo el adaptador que quieres agregar, el proveedor UEM, y qué endpoints necesitas. Si el proveedor es nuevo, discutimos primero si cabe en el core o va a un repo separado.

---

*El contrato de adaptador es mínimo a propósito: si tu UEM no soporta algún comando, no lo implementes. El engine lo sabe y no lo pide.*
