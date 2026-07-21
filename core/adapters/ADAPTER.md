# ADAPTER.md — Cómo escribir un conector MDM para LucidFence

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

## Live IntuneAdapter (Microsoft Graph) — issue #1

`IntuneAdapter` puede ahora operar en modo *live* contra Microsoft Graph
(`/deviceManagement/managedDevices`), además del modo *mock* por defecto.

### Cómo activarlo

1. Registra una app en Azure AD (Microsoft Entra ID) con `Application` permissions
   `DeviceManagementConfiguration.ReadWrite.All` (rol de aplicación, NO delegated).
2. Crea un client secret. Configura:
   ```
   INTUNE_TENANT_ID=<tu-tenant-guid>
   INTUNE_CLIENT_ID=<app-client-guid>
   INTUNE_CLIENT_SECRET=<secret-valor>
   ```
   (o pasa `tenant_id` / `client_id` / `client_secret` al constructor).
3. Construye el adapter en modo live:
   ```python
   from core.adapters.intune import IntuneAdapter
   adapter = IntuneAdapter(live=True, org_id="contoso")  # creds desde env
   r = adapter.execute({"device_id": "abc-123"}, "lock", {})
   # r["mode"] == "live", r["graph_status"] == 204 si OK
   ```
4. El endpoint por defecto es `https://graph.microsoft.com/v1.0`. Si tu tenant
   tiene un endpoint regional (ej. US Gov), sobrescribe `endpoint_template`.

### Errores mapeados (no rompen el dashboard)

| `error_type`         | Cuándo                                              |
|----------------------|-----------------------------------------------------|
| `auth_error`         | 401/403 de Graph; o falta tenant_id/client_*.        |
| `transport_error`    | 5xx de Graph; timeout; respuesta no JSON.          |
| `missing_device_id`  | `device` no trae `device_id` / `id`.                |
| `unsupported_action` | Acción no está en GRAPH_ACTION (lock/wipe/...).     |
| `graph_rejected`     | 4xx distinto (rate-limit, validation).              |
| `device_not_found`   | 404 sobre managed device.                           |

El contrato del dashboard (`MDMAdapter.execute`) garantiza que **nunca se
lanza excepción** — siempre devuelve `{"ok": False, "error": ..., "error_type": ...}`.

### Pruebas

* Mock path: igual que el adapter pre-live (`test_adapters_contrib.py` sigue verde).
* Live path: `tests/test_adapters_intune_live.py` cubre URL shape, error mapping,
  falta de credenciales y dry_run — sin tocar la red real.

`build_intune_adapter_from_config(cfg)` está disponible para wiring desde
`config.json` (ver `mdm.intune.tenant_id` / `client_id` / `client_secret`).

## Live JamfAdapter (Jamf Pro API) — issue #2

`JamfAdapter` puede ahora operar en modo *live* contra la Jamf Pro API
(`/api/v1/mobile-devices`), además del modo *mock* por defecto. Sigue el
mismo patrón que Intune: `live=True` activa llamadas reales; sin credenciales
opera en mock.

### Cómo activarlo

1. Crea un *API Role* en Jamf Pro con permisos de `Send Mobile Device Remote
   Commands` (lock/wipe/restart/clear-passcode/locate/message).
2. Genera un *API Client* (client_id + client_secret, Basic auth).
3. Configura:
   ```
   JAMF_BASE_URL=https://<tu-tenant>.jamfcloud.com
   JAMF_CLIENT_ID=<api-client-id>
   JAMF_CLIENT_SECRET=<api-client-secret>
   ```
   (o pasa `base_url` / `client_id` / `client_secret` al constructor).
4. Construye el adapter en modo live:
   ```python
   from core.adapters.jamf import JamfAdapter
   adapter = JamfAdapter(live=True)  # creds desde env
   r = adapter.execute({"device_id": "abc-123"}, "lock", {})
   # r["mode"] == "live", r["jamf_status"] == 204 si OK
   ```

### Errores mapeados (no rompen el dashboard)

| `error_type`         | Cuándo                                              |
|----------------------|-----------------------------------------------------|
| `auth_error`         | 401/403 de Jamf; o falta base_url/client_*.         |
| `transport_error`    | 5xx de Jamf; timeout; respuesta no JSON.            |
| `missing_device_id`  | `device` no trae `device_id` / `id`.                |
| `unsupported_action` | Acción no está en JAMF_VERB (lock/wipe/...).        |
| `jamf_rejected`      | 4xx distinto (rate-limit, validation).              |
| `device_not_found`   | 404 sobre mobile device.                            |

El token de sesión se obtiene vía `POST /api/v1/auth/token` (Basic auth) y se
cachea hasta ~50 min. El contrato `MDMAdapter.execute` garantiza que **nunca se
lanza excepción** — siempre devuelve `{"ok": False, "error": ..., "error_type": ...}`.

### Pruebas

* Mock path: igual que el adapter pre-live (`test_adapters_contrib.py` sigue verde).
* Live path: `tests/test_adapters_jamf_live.py` cubre URL shape, error mapping,
  falta de credenciales y dry_run — sin tocar la red real.

`build_jamf_adapter_from_config(cfg)` está disponible para wiring desde
`config.json` (ver `mdm.jamf.base_url` / `client_id` / `client_secret`).


## SDK contract tests (issue #14)

`tests/test_sdk_contract.py` provides reusable contract assertions that
every community adapter must pass. The contract is:

* Subclass `MDMAdapter` (ABC).
* Set a stable lowercase `name` (regex `^[a-z][a-z0-9_]*$`).
* Implement `execute(device, action, params, dry_run=False) -> dict`.
* **Never raise** — return `{"ok": False, "error_type": "...", "error": "..."}`.
* Always include keys: `adapter`, `ok` (bool), `device_id`, `action`.

The contract runner is reusable from any adapter's own test file:

```python
from tests.test_sdk_contract import assert_valid_name, assert_response_shape

def test_my_adapter_contract():
    a = MyAdapter()
    assert_valid_name(a.name)
    r = a.execute({"device_id": "abc"}, "lock", {})
    assert_response_shape(r, a.name)
```

## SDK template — `core/adapters/_template_adapter.py`

Drop-in starter for a new community adapter. The template runs in mock
mode out of the box (returns `ok: True`, `mock: True`) so the new adapter
registers cleanly without a live MDM endpoint. Replace `_build_request`
and uncomment the live-path branch to wire up your MDM.

Reference implementations in this repo:
* `IntuneAdapter` — Microsoft Graph OAuth client_credentials + REST (merged in #13).
* `JamfAdapter` — Jamf Pro API Basic auth + REST (merged in #21).
* `TemplateMdmAdapter` — the SDK template itself; community adapters
  start by copying this file and renaming.

The SDK template is verified by `test_sdk_template_helper` in the SDK
contract suite — if you break it, the CI badge turns red.
