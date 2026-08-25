# Flota federada multi-UEM: un panel, N consolas, el mismo veredicto

Una organización real corre 2+ UEMs a la vez (Intune para Windows, Jamf para
Mac, Fleet para Linux) y cada consola enseña solo su parcela con su propia
noción de "riesgo". `GET /api/fleet/federated` federa los inventarios del
tenant en UNA lista viva: cada dispositivo con su UEM de origen trazado (y el
segmento de flota que el admin le puso al registrarlo), el veredicto de riesgo
del engine — el mismo para todos, en la misma escala — y las razones top del
explain. Calculado en local sobre estado ya existente (nada sale de la
máquina). Requiere sesión con `device:read` y responde solo sobre la
organización activa.

**Parámetro:** `GET /api/fleet/federated?provider=jamf` filtra por UEM de
origen (nombre de provider: minúsculas/dígitos/`_`; inválido → 400, nunca un
filtro ignorado en silencio).

## Qué enseña

| Campo | Qué significa |
|---|---|
| `fleet[].providers` | Origen trazado: TODOS los UEMs que reportaron el dispositivo (uno consolidado puede venir de varios), cada uno con su `segment`. `[]` = origen desconocido, jamás atribuido por conjetura. |
| `fleet[].risk` | El veredicto que el Risk Engine ya produjo (`score` 0-100 + `level`). El panel NO recalcula: sin veredicto → `null`, nunca un 0 inventado. |
| `fleet[].top_reasons` | Las 2-3 razones top del explain-risk, tal cual las produjo el engine. El drill-down completo vive en el detalle del dispositivo. |
| `providers` | Resumen por UEM registrado (nombre, segmento, dispositivos), contado sobre la flota completa aunque haya filtro activo. |
| `sin_origen` | Dispositivos sin origen trazable. Se listan igual (existen), con `provider: null`. |

Readback-honesto: un campo que el provider no reporta llega como `null` — no
se inventa ni se penaliza al dispositivo por lo desconocido, y lo desconocido
no compite con señal real en el ranking (va al final).

## Por qué solo el overlay neutral puede

Microsoft no va a federar a Jamf ni viceversa: cada UEM vende su panel como el
único y puntúa su propio riesgo con su propia vara. LucidFence no compite por
la gestión — lee de los UEMs que ya tienes (`multiuem.py` normaliza los
modelos), correlaciona y aplica UN motor de riesgo explicable a toda la flota.
Sin incentivo de lock-in, el veredicto es comparable entre plataformas: un
Mac de Jamf y un portátil de Intune se miden con la misma regla.

## Ejemplo de respuesta

```json
{
  "fleet": [
    {"device_id": "win-042", "name": "Portátil Ventas 7", "platform": "windows",
     "providers": [{"name": "intune", "segment": "portátiles"}],
     "provider": "intune", "segment": "portátiles",
     "risk": {"score": 60.0, "level": "high"},
     "top_reasons": ["dispositivo no conforme", "fuera de geocerca permitida"],
     "compliant": false, "fence_state": "outside",
     "last_seen": "2026-08-25T09:41:00+00:00"},
    {"device_id": "mac-011", "name": "MacBook Diseño 2", "platform": "macos",
     "providers": [{"name": "jamf", "segment": "móviles"}],
     "provider": "jamf", "segment": "móviles",
     "risk": {"score": 5.0, "level": "low"},
     "top_reasons": [],
     "compliant": true, "fence_state": "inside",
     "last_seen": "2026-08-25T09:40:12+00:00"}
  ],
  "total": 2, "fleet_total": 2,
  "providers": [
    {"name": "intune", "segment": "portátiles", "devices": 1},
    {"name": "jamf", "segment": "móviles", "devices": 1}
  ],
  "sin_origen": 0,
  "filter": {"provider": null}
}
```

En el dashboard, la vista **Flota federada** pinta esta respuesta tal cual:
tabla con chip de origen por UEM, riesgo coloreado por nivel, filtro por
provider y clic en la fila → el explain-risk existente del dispositivo.

## Límites

- La vista refleja lo que el ciclo del engine ya ingirió: el origen se traza
  desde `provider_refs` (lo puebla el orquestador multi-UEM al reportar). Un
  dispositivo ingerido por una fuente sin trazabilidad de provider aparece con
  origen `null` — visible, nunca maquillado.
- Solo lectura. Actuar sobre un dispositivo sigue el camino de siempre
  (comandos con sus guardarraíles: `dry_run` por defecto, wipe con doble
  llave); la federación no añade ninguna vía de acción nueva.
- El registro de providers aporta nombre + segmento a la vista; las
  credenciales viven en `integration.json` (0600) y jamás viajan en esta
  respuesta.
