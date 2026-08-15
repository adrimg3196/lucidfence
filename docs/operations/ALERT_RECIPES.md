# Recetas de alertas: incidentes donde ya miras

Los incidentes (apertura, acknowledge, resolución) salen por los canales de
`incident_webhooks`. Todos son locales, best-effort y con fan-out: un canal
caído no bloquea a los demás. Config de referencia:

```yaml
incident_webhooks:
  - {type: "slack",   url: "https://hooks.slack.com/services/T000/B000/XXXX"}
  - {type: "generic", url: "https://automation.tu-org.com/hook", secret: "s3cr3t"}
  - {type: "ntfy",    url: "https://ntfy.sh/tu-topic-privado", token: "tk_..."}
```

(`incident_webhook_url` a secas sigue funcionando como canal único legacy.)

## Slack

1. Crea una app → **Incoming Webhooks** → añade el webhook a tu canal.
2. Pega la URL con `type: slack`. El payload es el formato clásico de Slack
   (`text` + `attachments` con color por severidad y campos ID/dispositivo/
   geocerca): no hay nada más que configurar.

## Microsoft Teams

Teams (workflows de Power Automate) no entiende el formato Slack; usa el
canal `generic` con un flujo intermedio:

1. Teams → canal → **Workflows → "Post to a channel when a webhook request
   is received"** → copia la URL.
2. En LucidFence: `{type: "generic", url: "<url del flujo>", secret: "..."}`.
3. En el flujo, mapea el JSON del incidente (`transition`, `incident.title`,
   `incident.severity`, `incident.device_id`) a la tarjeta.

## Webhook firmado (SOAR / automatización propia)

El canal `generic` firma cada entrega con HMAC-SHA256 en la cabecera
`X-LucidFence-Signature` (`sha256=<hex>`). Verificación en el receptor:

```python
import hashlib, hmac

def verify(secret: str, body: bytes, header: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header or "")
```

Rechaza todo lo que no verifique: cualquiera puede descubrir la URL de un
endpoint; la firma es lo que prueba que el incidente lo emitió tu LucidFence.

## ntfy (push a móvil sin cuentas)

1. Elige un topic difícil de adivinar (es la única "auth" en ntfy.sh
   público) o usa un servidor ntfy propio con `token`.
2. `{type: "ntfy", url: "https://ntfy.sh/<topic>", token: "tk_..."}`.
3. Instala la app ntfy y suscríbete al topic: alertas en el móvil del
   on-call en 2 minutos, gratis.

## Email

El canal de email es Atomic Mail (opt-in por tenant, config `atomicmail` en
la integración): incidentes + digest diario al buzón que configures. Si tu
org exige SMTP corporativo, la vía soportada hoy es el webhook `generic`
hacia tu pasarela (que ya habla con tu SMTP); no hay cliente SMTP embebido.

## Prueba de fuego

Con el canal configurado, fuerza un incidente de prueba: mueve un
dispositivo simulado fuera de una geocerca (`POST /api/run-once` en modo
simulación) o usa un dispositivo de staging. La entrega queda registrada en
el propio incidente (`deliveries`), así que "¿llegó o no?" tiene respuesta
en la API, no en la fe.
