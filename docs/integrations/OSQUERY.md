# osquery como fuente de postura

LucidFence integra [osquery](https://github.com/osquery/osquery) como una fuente
opcional de evidencia del endpoint. La responsabilidad queda separada:

- **osquery observa** versión de SO, almacenamiento, cifrado, batería e
  integridad de su propia configuración.
- **LucidFence correlaciona** esa postura con ubicación, geocerca, ruta, horario
  y conformidad.
- **El UEM ejecuta** la remediación cuando una política compuesta lo exige.

osquery no sustituye al MDM ni recibe comandos arbitrarios desde LucidFence.
La integración no añade telemetría ni servicio cloud y permanece desactivada
por defecto.

## Opción A: consumir el results log

Instala osquery siguiendo su documentación oficial y añade el pack incluido:

```text
deploy/osquery/lucidfence.pack.json
```

El pack usa consultas `snapshot` de solo lectura con intervalos de 5 o 15
minutos. LucidFence ignora eventos diferenciales porque una fila aislada no
representa la postura completa de un disco. Configura LucidFence:

```json
{
  "osquery": {
    "enabled": true,
    "mode": "results_log",
    "results_path": "/var/log/osquery/osqueryd.results.log",
    "max_age_seconds": 1800,
    "host_map": {
      "macbook-ventas.example.com": "device-id-en-el-uem"
    }
  }
}
```

En Windows, el directorio de log predeterminado de osquery es
`C:\Program Files\osquery\log`. Usa la ruta efectiva de tu logger. Para una
flota remota, el archivo puede ser el destino local de un forwarder ya
administrado por el cliente; LucidFence no obliga a usar un backend concreto.

`host_map` evita uniones ambiguas: relaciona `hostIdentifier`, hostname, UUID o
serial reportado por osquery con el `device_id` del UEM. Si ambos identificadores
ya coinciden, puede omitirse. Los aliases repetidos entre dos hosts se descartan
de forma segura; en ese caso debe mapearse cada `hostIdentifier` único.

## Opción B: consultar el host local

Para el dispositivo que ejecuta LucidFence:

```json
{
  "osquery": {
    "enabled": true,
    "mode": "local",
    "device_id": "device-id-en-el-uem",
    "binary": "osqueryi",
    "timeout_seconds": 5,
    "total_timeout_seconds": 15
  }
}
```

LucidFence ejecuta únicamente una lista inmutable de consultas de lectura
incluida en el código. No acepta SQL por configuración, API o políticas. Cada
consulta y el lote completo tienen límites de tiempo para no bloquear un ciclo
de geofencing.

## Evidencia incorporada

| Plataforma | Evidencia |
| --- | --- |
| macOS | SO, volumen raíz, FileVault/cifrado, batería, hardware |
| Linux | SO, volumen raíz, cifrado disponible en `disk_encryption`, hardware |
| Windows | SO, unidad de arranque, BitLocker, batería, hardware |

Los campos normalizados (`storage_free_gb`, `encryption_enabled`,
`battery_level`, `os_version`) alimentan el Risk Engine existente. La
procedencia se conserva en `posture_source`, `posture_collected_at`,
`osquery_version` y `osquery_config_valid`.

Si el log está ausente, desactualizado o corrupto, LucidFence no inventa
postura: continúa el ciclo de geofencing sin esa evidencia y expone el estado
del proveedor en `osquery_posture` dentro de las estadísticas del ciclo.

## Seguridad y licencia

- No se vendoriza ni modifica osquery.
- No se ejecuta código procedente de resultados o configuración.
- La lectura del log está acotada a los últimos 4 MiB y 10.000 eventos.
- Las llamadas locales usan `subprocess` sin shell, timeout y SQL fijo.
- LucidFence conserva su licencia Apache-2.0. osquery se instala por separado y
  mantiene su licencia upstream (`Apache-2.0 OR GPL-2.0-only`).
