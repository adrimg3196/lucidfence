# Auditor de mínimo privilegio: qué puede de verdad tu token del UEM

Nadie del sector audita los privilegios de sus propias integraciones. Un
complemento que lee del UEM se conecta con el token que el admin tenía a mano
—muchas veces uno que puede borrar dispositivos— y ahí se queda para siempre.

LucidFence debe ser el eslabón **menos** peligroso de la cadena: si el tenant
está en modo `observe`, donde el producto no ejecuta ni una sola acción en
vivo, un token capaz de wipear no aporta absolutamente nada y sí añade
superficie de ataque. `GET /api/least-privilege` compara, por proveedor
conectado, lo que la credencial **declara** poder hacer contra lo que el modo
de enforcement actual **necesita**, y nombra el exceso.

Cálculo 100% local sobre estado ya existente (cero llamadas de red, cero
escritura). Requiere sesión con `engine:config` y responde solo sobre la
organización activa. El gating es más estricto que el de `/api/coverage` a
propósito: el informe dice en voz alta qué credenciales del tenant pueden
wipear, y quien puede recortar el token es exactamente quien tiene esa
capability. **La credencial nunca viaja**: del registro solo salen el nombre
del proveedor, los scopes declarados y el veredicto.

## De dónde salen los scopes (y por qué no hay tabla)

LucidFence **no** trae una tabla de scopes de Intune/Jamf/Fleet. Inventarla
sería afirmar permisos que nadie ha verificado — justo el pecado que este
auditor existe para denunciar. Qué scopes tiene el token y qué concede cada uno
es **dato de entrada**: se declara al conectar el adapter.

```json
POST /api/providers
{"name": "intune", "segment": "portátiles", "client_secret": "…",
 "scopes": [{"id": "DeviceManagementManagedDevices.Read.All", "grants": ["read"]},
            {"id": "DeviceManagementManagedDevices.PrivilegedOperations.All",
             "grants": ["wipe", "lock", "reboot"]}]}
```

`id` es el nombre del scope tal cual lo llama tu UEM (viaja literal al
informe). `grants` lo traduce al vocabulario que el producto ya entiende: las
acciones del contrato `MDMAdapter` (`lock`, `wipe`, `message`, `locate`,
`reboot`, `clear_passcode`, `set_compliance`, `apply_ddm`…) más `read` para la
lectura del inventario. `read` no es exceso nunca: leer del UEM **es** el
producto.

Un scope sin `grants` se guarda igual, pero **no se interpreta**: el proveedor
queda *no auditable*, que es la verdad, en vez de darse por correcto.

## Contra qué se mide

El listón sale del enforcement vivo del tenant (`Engine.enforcement_status()`),
no de una preferencia del auditor:

| Modo del tenant | Acciones que LucidFence ejecuta en vivo | Consecuencia |
|---|---|---|
| `observe` | ninguna (el engine fuerza `dry_run`) | **todo** permiso de escritura sobra |
| `enforce` | las de `live_actions` que el adapter sabe ejecutar | sobra lo que quede fuera |
| `enforce` + `wipe` | solo con `allow_wipe: true` (doble llave) | sin la doble llave, el permiso de wipe sobra |

Además se cruza con la matriz de capacidades del adapter
(`core/adapters/capabilities.py`): si el UEM ni siquiera expone esa acción en
LucidFence (ChromeOS, por ejemplo, es solo inventario), el permiso sobra
aunque el tenant esté en `enforce`.

## Tres veredictos, nunca dos

| Veredicto | Significa |
|---|---|
| `correcto` | **auditado**: sus scopes son los que el modo necesita. |
| `exceso` | **auditado**: sobra permiso; se lista qué scope, qué concede de más y por qué es peligroso en el modo actual. |
| `no_auditable` | **no sabemos** qué puede el token: el UEM no expone sus scopes, nadie los declaró, o el scope no dice qué concede. Nunca se presenta como correcto ni como excesivo. |

`resumen.providers_auditables` publica el denominador honesto: **"0 excesos"
sobre 0 auditables no es "todo bien"**, es ausencia de señal. Es el mismo
razonamiento que `devices_verifiable` en
[`second_opinion.md`](second_opinion.md).

## Ejemplo de respuesta

```json
{
  "enforcement": {"mode": "observe", "live_actions": "all", "allow_wipe": false},
  "providers": [
    {
      "provider": "intune",
      "veredicto": "exceso",
      "scopes_declarados": ["DeviceManagementManagedDevices.Read.All",
                            "DeviceManagementManagedDevices.PrivilegedOperations.All"],
      "exceso": [
        {"scope": "DeviceManagementManagedDevices.PrivilegedOperations.All",
         "grants": ["lock", "reboot", "wipe"],
         "severity": "critical",
         "why": "El token puede BORRAR el dispositivo (wipe: irreversible) (lock, reboot, wipe) y el tenant está en modo observe: LucidFence no ejecuta NINGUNA acción en vivo en este modo, así que ese permiso solo añade superficie de ataque. Recórtalo a solo lectura."}
      ],
      "scopes_recomendados": ["DeviceManagementManagedDevices.Read.All"],
      "scopes_sin_clasificar": [],
      "min_permission_documentada": "App de Entra con permiso de aplicación DeviceManagementManagedDevices.Read.All"
    },
    {
      "provider": "jamf",
      "veredicto": "no_auditable",
      "motivo": "el UEM no expone los scopes de su credencial y nadie los ha declarado al conectar el adapter",
      "scopes_declarados": [], "exceso": [], "scopes_recomendados": [],
      "scopes_sin_clasificar": [],
      "min_permission_documentada": "API role de solo lectura (Read Computers, Read Mobile Devices)"
    }
  ],
  "resumen": {
    "providers_total": 2, "providers_auditables": 1,
    "providers_no_auditables": 1, "providers_con_exceso": 1,
    "providers_correctos": 0, "scopes_excesivos": 1
  }
}
```

`min_permission_documentada` es el mínimo que el catálogo de conectores del
repo ya exige para ese UEM (`lucidfence/saas/providers.py`), servido tal cual
para que el admin sepa a qué recortar.

## Límites honestos

- **Ningún UEM soportado hoy publica por API los scopes efectivos de su
  credencial de forma uniforme.** El adapter no los descubre solo: los declara
  el operador al conectar. Un token real puede tener más permisos de los que
  su dueño declaró — el informe audita lo declarado y lo dice con esas
  palabras, nunca promete haber interrogado al UEM.
- Sin declaración, el proveedor es `no_auditable`. El auditor no rellena el
  hueco por inferencia ni castiga por él.
- El informe **solo enseña**: nunca revoca, rota ni recorta un token. Eso se
  hace en la consola del UEM, y lo decide el admin (frontera del producto:
  LucidFence es el complemento, no el UEM).
- El contrato de mínimo privilegio que este auditor hace verificable está
  escrito en [`ADAPTER.md`](../../lucidfence/core/adapters/ADAPTER.md).
