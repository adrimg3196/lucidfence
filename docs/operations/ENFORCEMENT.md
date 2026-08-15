# Runbook de enforcement: de observación a producción

El error clásico de un piloto de geofencing es conectar el tenant real con
las acciones armadas. LucidFence lo hace imposible por defecto: sin config
explícita, **nada sale al UEM**. Este runbook es el camino inverso, por
fases, con marcha atrás en cada una.

## Fase 0 — Por defecto: observe

```yaml
enforcement:
  mode: observe
```

(Es también el comportamiento sin bloque `enforcement`.) Todo el pipeline
corre completo — ubicación, geocercas, riesgo, políticas, incidentes,
auditoría — pero cada acción se ejecuta como dry-run: queda registrado *qué
habría pasado* (`would_send` incluido en adapters live), no pasa. El chip
del dashboard dice `live · observación` y `/api/status` expone
`"enforcement": {"mode": "observe", ...}`.

**Sal de esta fase solo cuando**: llevas ≥2 semanas, has revisado los
incidentes y el action log, y los falsos positivos (GPS con mala precisión,
spoofing, dispositivos `unknown`) están entendidos y acotados por políticas.

## Fase 1 — Enforce con acciones reversibles

```yaml
enforcement:
  mode: enforce
  live_actions: ["message", "set_compliance"]
```

Solo las acciones listadas salen en vivo; **cualquier otra sigue en
dry-run** y auditada. `message` avisa al usuario; `set_compliance` corta
acceso vía Conditional Access sin tocar el dispositivo (Intune). Ambas se
deshacen en segundos.

## Fase 2 — Lock

```yaml
enforcement:
  mode: enforce
  live_actions: ["message", "set_compliance", "lock"]
```

`lock` es recuperable pero molesto: hazlo después de validar la fase 1 y
con el cooldown por defecto (`action_cooldown_seconds: 3600`) que impide
que una violación sostenida re-dispare el comando cada ciclo.

## Fase 3 — Wipe (doble llave, nunca por defecto)

```yaml
enforcement:
  mode: enforce
  live_actions: ["lock", "wipe"]
  allow_wipe: true                      # llave 1: opt-in explícito
  wipe_allowlist: ["dev-4711", "dev-4712"]   # llave 2 (opcional): blast radius acotado
```

Sin `allow_wipe: true`, un `wipe` en vivo — de policy **o manual de un
operador** — se bloquea con `blocked: true` + `error_type: wipe_not_allowed`,
queda en el action log y no arma cooldown (al habilitar la llave puedes
reintentar al momento). Con `wipe_allowlist`, solo esos `device_id`
pueden recibirlo. Recomendación: usa la allowlist siempre; un wipe de flota
entera no es una política, es un incidente.

## Defensa en profundidad

El gating de LucidFence es la primera línea, no la única. Alinea las
credenciales del UEM con la fase:

| Fase | Intune (Graph) | Jamf (API role) | Fleet (role) |
|---|---|---|---|
| observe | `...Read.All` | Read only | observer |
| enforce | + `PrivilegedOperations.All` | + comandos concretos | maintainer |

Si la credencial no puede ejecutar la acción, la fase es imposible aunque
la config diga otra cosa. Detalle por UEM en `docs/integrations/`.

## Verificación en cada cambio de fase

```bash
curl -s localhost:8765/api/status | python3 -c "import sys,json; print(json.load(sys.stdin)['enforcement'])"
```

y dispara una acción de prueba desde el dashboard contra un dispositivo de
staging: en observe debe volver `dry_run: true`; en enforce, solo las
`live_actions` deben ejecutar de verdad. La batería
`scripts/runtime_validation.py` cubre exactamente esto en CI.
