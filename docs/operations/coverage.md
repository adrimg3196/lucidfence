# Informe de puntos ciegos: lo que tu configuración NO cubre

Los paneles del sector enseñan lo que SÍ cubren. El gap de cobertura — el
hueco por el que entran los incidentes — queda invisible. `GET /api/coverage`
enseña el negativo de la configuración actual del tenant, calculado en local
sobre estado ya existente (nada sale de la máquina). Requiere sesión con
`device:read` y responde solo sobre la organización activa.

## Qué enseña

| Lista | Punto ciego | Qué significa |
|---|---|---|
| `devices_sin_senal` | Sin ubicación utilizable | El dispositivo existe en el inventario pero no trae coordenadas válidas ni casa con ninguna firma de red declarada: no se puede evaluar contra ninguna geocerca. |
| `devices_sin_reportar` | "Lost sheep" | El `last_seen` supera el umbral (`stale_after_s`, 24 h por defecto), o directamente no existe (`last_seen: null`, motivo `"sin last_seen"`). |
| `fences_vacias` | Geocerca sin flota | La cerca está configurada pero ningún dispositivo evaluable está dentro: o sobra, o falta flota que debería estar ahí. |

El bloque `resumen` incluye `coverage_percent` (dispositivos evaluables /
total; `100.0` con inventario vacío) y los contadores de cada lista.

Readback-honesto: un dato ausente jamás inventa cobertura ni penaliza más
allá de listar el punto ciego con su motivo.

## Por qué solo lo enseña (complemento, no UEM)

LucidFence lee del UEM que ya tienes, correlaciona y **hace visible** el
hueco. Qué hacer con un dispositivo que dejó de reportar — reinstalar el
agente, darlo de baja, ir a buscarlo — lo decide el admin en su UEM. Nunca
hay acción automática sobre un punto ciego: es la frontera del producto.

## Ejemplo de respuesta

```json
{
  "devices_sin_senal": [
    {"device_id": "dev-007", "name": "Terminal Almacen D2",
     "location_source": "unknown",
     "reason": "sin coordenadas válidas ni match de red"}
  ],
  "devices_sin_reportar": [
    {"device_id": "dev-003", "name": "iPad Showroom C3",
     "last_seen": "2026-08-16T09:12:44Z", "age_s": 269000,
     "reason": "sin reportar desde hace 74h"},
    {"device_id": "dev-007", "name": "Terminal Almacen D2",
     "last_seen": null, "age_s": null, "reason": "sin last_seen"}
  ],
  "fences_vacias": [
    {"fence_id": "almacen-norte", "name": "Almacén Norte", "type": "polygon"}
  ],
  "resumen": {
    "devices_total": 6, "devices_evaluables": 5,
    "devices_sin_senal": 1, "devices_sin_reportar": 2,
    "fences_total": 3, "fences_vacias": 1,
    "stale_after_s": 86400, "coverage_percent": 83.3
  }
}
```

Un dispositivo puede aparecer en las dos listas de dispositivos a la vez
(sin señal Y sin reportar): son puntos ciegos independientes.
