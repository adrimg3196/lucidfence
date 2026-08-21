# Generic HTTP location source (bring-your-own UEM/MDM)

LucidFence puede leer dispositivos de **cualquier API JSON** de cualquier
fabricante de UEM/MDM sin escribir código. Declaras endpoint, auth y mapeo de
campos en `config.json`; un solo conector configurable (`GenericHTTPLocationSource`)
hace el resto. No necesitas un adapter por vendor.

## Configuración

En `config.json`, añade un bloque `location_source` con `url`:

```json
{
  "mode": "generic",
  "location_source": {
    "url": "https://mdm.tu-vendor.com/api/v1/devices",
    "method": "GET",
    "headers": { "Authorization": "Bearer ${VENDOR_API_TOKEN}" },
    "items_path": "data.items",
    "fields": {
      "device_id": "id",
      "name":      "displayName",
      "platform":  "os",
      "lat":       "location.lat",
      "lng":       "location.lng",
      "compliant": "compliance.ok",
      "status":    "state"
    }
  }
}
```

- `headers` soporta `${VAR}` → se expande desde el entorno (el secreto nunca
  va en el repo).
- `items_path`: ruta punteada hasta la lista de dispositivos dentro del JSON.
  Vacío o `"."` = la raíz (o una lista directa).
- `fields`: cada clave es un campo de `LocationReport`; el valor es la ruta
  punteada dentro de cada dispositivo. Campos ausentes → `None` (el engine los
  trata como desconocidos, no crashea).

## Reglas

- Sin `url` → el source devuelve error grabado en `last_error`, sin romper el ciclo.
- Dispositivo sin `lat`/`lng` → se omite (no entra en geovallas).
- Cualquier fallo HTTP se captura (nunca 500): aparece como `integration_error`
  en el dashboard.

## Ejemplo: Microsoft Graph (Intune)

```json
{
  "location_source": {
    "url": "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices",
    "headers": { "Authorization": "Bearer ${GRAPH_TOKEN}" },
    "items_path": "value",
    "fields": {
      "device_id": "id", "name": "deviceName", "platform": "operatingSystem",
      "lat": "lastKnownGateway.latitude", "lng": "lastKnownGateway.longitude",
      "compliant": "complianceState", "status": "managementState"
    }
  }
}
```

Esto es equivalente a un adapter Intune de ubicación, pero sin código: solo
mapeo. Lo mismo sirve para Jamf, Fleet (osquery), Workspace ONE, Mosyle,
Kandji, o tu propio endpoint interno.

## Tests

`tests/test_generic_location_source.py` cubre mapeo, expansión de env,
`items_path` y errores — con `urllib` mockeado (sin red).
