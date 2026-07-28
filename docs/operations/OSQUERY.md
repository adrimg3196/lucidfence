# Posture real con osquery

LucidFence puede alimentar su Risk Engine con la postura REAL del endpoint vía
[osquery](https://github.com/osquery/osquery) (Apache-2.0/GPL-2.0). No se
vendoriza nada: LucidFence solo lee la salida de osquery. Cero dependencias
nuevas, $0, y todo se queda en la máquina del cliente.

## Qué aporta

Los campos que ya consume el Risk Engine (`sig_device_posture` /
`sig_device_health`) dejan de venir solo del UEM o de la simulación y pasan a
ser verdad del endpoint:

| Query | Tabla osquery | Campo del device |
|---|---|---|
| `lf_os_version` | `os_version` | `os_version` |
| `lf_disk_encryption` | `disk_encryption` | `encryption_enabled` |
| `lf_storage` | `mounts` (path `/`) | `storage_free_gb`, `storage_total_gb` |
| `lf_battery` | `battery` (macOS/Windows) | `battery_level` |
| `lf_agent_health` | `osquery_info` | `osquery_version` |

Señales con más de `max_age_min` minutos se DESCARTAN (evidence gate: mejor
sin señal que con señal caducada). Los campos frescos de osquery pisan lo que
dijera el adapter/simulación, con `posture_source: "osquery"` como provenance.

## Modo flota (osqueryd + results log)

1. Despliega el pack `deploy/osquery/lucidfence.conf` en tus endpoints
   (osquery standalone o gestionado con Fleet — si ya tienes Fleet, añade las
   5 queries como scheduled queries y apunta LucidFence al log del host).
2. osqueryd con filesystem logger escribe `osqueryd.results.log` (JSON-lines).
3. En `config.json`:

```json
"posture": {
  "source": "osquery",
  "results_log": "/var/log/osquery/osqueryd.results.log",
  "max_age_min": 30
}
```

El match device ↔ host usa `hostIdentifier` de osquery contra `device_id`,
`name` o `serial` (case-insensitive).

## Modo una máquina (osqueryi)

Sin demonio: si `osqueryi` está en el PATH, LucidFence puede consultar la
propia máquina (útil para el modo local/desktop):

```json
"posture": {
  "source": "osquery",
  "local_device_id": "mi-mac"
}
```

## Garantías

- Nunca rompe el engine: log ausente, JSON corrupto o binario inexistente →
  posture vacía y el ciclo sigue (misma regla dura que los adapters).
- Solo se leen las queries `lf_*` conocidas; el resto del log se ignora.
- Cola máxima leída del log: 8 MB (rotación de osquery recomendada aparte).
- Tests: `tests/test_posture_osquery.py`.
