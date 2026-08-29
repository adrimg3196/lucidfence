# Eventos OCSF: la señal en el idioma que tu SOC ya habla

Tu organización ya tiene su herramienta: Splunk, Sentinel, Chronicle, o el SIEM
que sea. LucidFence es el **complemento**, no otro panel que mirar: en vez de
pedirte que vigiles una pantalla más, escribe sus veredictos en
[OCSF](https://schema.ocsf.io/) (Open Cybersecurity Schema Framework), el
esquema abierto que esas herramientas ingieren **sin parser a medida**.

El evento se genera en local, por el webhook que ya tenías configurado. A dónde
va lo decides tú: LucidFence no publica nada a ningún sitio por su cuenta.

## Cómo se activa

Es **opt-in por canal**. En el webhook genérico de tu `config.json` (o de la
configuración del tenant) añade `"format": "ocsf"`:

```json
"incident_webhooks": [
  {"type": "generic", "url": "https://mi-siem.interno/hec", "format": "ocsf",
   "secret": "s3cr3t"},
  {"type": "slack", "url": "https://hooks.slack.com/services/T/B/X"}
]
```

Sin `format`, o con cualquier otro valor, el canal sigue enviando el payload
nativo de siempre: **quien no lo active no nota ningún cambio**. La firma
`X-LucidFence-Signature` (HMAC-SHA256 sobre los bytes exactos del cuerpo) y la
política de egress del tenant funcionan igual en los dos formatos.

Solo el canal `generic` admite OCSF. Slack y ntfy son canales para personas: un
JSON OCSF ahí no aporta nada.

## Qué llega al SIEM

Un evento de la clase **Detection Finding** (`class_uid` 2004, `category_uid` 2
*Findings*), uno por transición del incidente (`open`, `acknowledged`,
`resolved`), sin sobre ni envoltorio: el cuerpo HTTP **es** el evento OCSF.

```json
{
  "activity_id": 1,
  "activity_name": "Create",
  "category_uid": 2,
  "category_name": "Findings",
  "class_uid": 2004,
  "class_name": "Detection Finding",
  "type_uid": 200401,
  "type_name": "Detection Finding: Create",
  "severity_id": 4,
  "severity": "High",
  "status_id": 1,
  "status": "New",
  "time": 1787045400000,
  "message": "Tablet almacén está fuera de geovalla",
  "count": 3,
  "metadata": {
    "version": "1.3.0",
    "product": {"vendor_name": "LucidFence", "name": "LucidFence"}
  },
  "finding_info": {
    "uid": "inc-outside-dev-7",
    "title": "Tablet almacén está fuera de geovalla",
    "desc": "Validar ubicación reciente y ejecutar acción UEM si procede.",
    "types": ["geofence_exit"],
    "first_seen_time": 1787043600000,
    "last_seen_time": 1787045400000
  },
  "resources": [{"uid": "dev-7", "name": "Tablet almacén", "type": "device"}],
  "unmapped": {"type": "geofence_exit", "fence_id": "hq"}
}
```

### El mapeo, campo a campo

| LucidFence | OCSF | Nota |
|---|---|---|
| transición `open` / `acknowledged` / `resolved` | `activity_id` 1 *Create* / 2 *Update* / 3 *Close* | cualquier otra transición → `99 Other`, con el nombre literal en `activity_name` |
| — | `status_id` 1 *New* / 2 *In Progress* / 4 *Resolved* | derivado de la misma transición |
| `severity` | `severity_id` | `info`→1, `low`→2, `medium`→3, `high`→4, `critical`→5 |
| `id` | `finding_info.uid` | |
| `title` | `finding_info.title` y `message` | |
| `recommendation` | `finding_info.desc` | |
| `type` | `finding_info.types` | |
| `first_seen` / `last_seen` | `finding_info.first_seen_time` / `last_seen_time` | epoch en **milisegundos**, como exige OCSF |
| `last_seen` | `time` | la marca de cuándo pasó, no de cuándo se reenvió |
| `device_id` / `device_name` | `resources[0].uid` / `.name` | identidad del dispositivo, **nunca** su ubicación |
| `count` | `count` | |
| `type`, `fence_id`, `route_state`, `risk_score`, `assignee` | `unmapped` | lo específico del producto, en el sitio que OCSF reserva para ello |

**La severidad no se estira.** OCSF tiene un `6 Fatal` por encima de
`5 Critical`; LucidFence no tiene nada por encima de `critical`, así que ese
valor no se usa: exagerar el veredicto en el panel del SOC sería mentir con
formato válido. Y una severidad que no reconocemos —incluido el `unknown` que
emite el evaluador de riesgo cuando falla— va a `0 Unknown`, **nunca** a
`1 Informational`: presentar lo que no se sabe como benigno es el falso verde
que este repo prohíbe (misma regla que
[`second_opinion.md`](second_opinion.md) y
[`least_privilege.md`](least_privilege.md)).

## La coordenada no viaja

El evento se construye con **lista blanca**: se nombra campo por campo lo que
sale. No hay ninguna copia del incidente completo. El webhook nativo de hoy no
publica coordenadas y OCSF **no amplía esa superficie** — aunque un incidente
llevase `lat`/`lng` dentro, el serializador no los emite porque no los nombra.
Hay un test con coordenadas envenenadas y un check de la batería runtime que lo
fijan: si alguien lo rompe, el gate no pasa.

Lo que sale del perímetro es: qué incidente, de qué dispositivo, con qué
severidad y cuándo. Ni dónde.

## Límites honestos

- **Cubrimos una sola clase OCSF: Detection Finding (2004).** No emitimos
  `Compliance Finding` (2003), `Vulnerability Finding` (2002), `Incident
  Finding` (2005) ni ninguna clase de las categorías *System Activity*,
  *Network Activity* o *Identity & Access Management*. Emitir una clase que no
  mapeamos de verdad rompería la ingesta del cliente, que es exactamente lo
  contrario de para lo que existe esto.
- **El mapeo se declara contra OCSF 1.3.0** (`metadata.version`). La clase 2004
  existe desde 1.1.0; si tu SIEM valida contra otra versión, revisa esa
  declaración antes de dar por buena la ingesta.
- **Los veredictos de riesgo llegan como incidentes**, que es como viajan hoy
  por el webhook: el `high_risk_device` que deriva el motor, con su
  `risk_score` en `unmapped`. No hay un canal aparte que publique la
  puntuación de cada dispositivo en cada ciclo.
- **No hay transporte propio**: no hablamos HEC de Splunk, ni la Data Collector
  API de Sentinel, ni la de Chronicle. Es un POST HTTP con el evento en el
  cuerpo. Si tu SIEM necesita una cabecera o un sobre concretos, ponlos con el
  colector que ya uses delante.
- **Ni telemetría ni destino por defecto.** Sin `incident_webhooks`
  configurado, aquí no sale nada a ningún sitio.
