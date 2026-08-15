# Applivery — onboarding para administradores

Applivery es hoy el UEM con la integración más completa en LucidFence: es la
única fuente **live de ubicación** verificada contra la API real
(`api.applivery.io/v1`), además de destino de acciones. Tiempo estimado:
10 minutos.

## 1. Credenciales

1. En Applivery, crea un **service account / API key** con acceso de lectura
   a MDM devices (y de escritura solo cuando pases a enforce).
2. Anota el **org id** de tu organización.

```bash
export APPLIVERY_API_KEY="<bearer token>"
```

Alternativa sin variables de entorno: pega la key en
**Dashboard → Ajustes → Credenciales** (queda cifrada en el data dir del
tenant, nunca en el YAML) y usa el botón de test de token.

## 2. Configuración

```yaml
mode: live
enforcement:
  mode: observe
applivery:
  org_id: "<tu-org-id>"
```

Verifica:

```bash
lucidfence validate-config   # llama a /organizations/{org}/mdm/devices real
```

`validate-config` existe precisamente para esto: valida el mapeo de
`location_source` contra la respuesta real de tu tenant (paginación
incluida) y te dice qué campos de ubicación llegan.

## 3. Qué obtienes

- **Ubicación por dispositivo** (lat/lng/accuracy + last seen) en cada ciclo
  del engine — la base del geofencing, las rutas y el anti-spoofing.
- **Conformidad y postura** del MDM.
- **Acciones**: vía el endpoint de comandos MDM o delegadas a tu webhook de
  remediación (`uem.remediation_webhook_url`) si prefieres que las ejecute
  tu SOAR.

La cadencia de ubicación depende del check-in del MDM, no de LucidFence:
ver [matriz de ubicación](LOCATION_MATRIX.md).

## 4. Rollout

Igual que el resto de UEMs: [ENFORCEMENT.md](../operations/ENFORCEMENT.md).
Arranca en `observe`, revisa incidentes un par de semanas, y habilita
`live_actions` de menos a más. `wipe` exige doble llave siempre.

## Problemas típicos

- `401` → el Bearer no es válido o el service account no tiene scope MDM.
- Flota vacía → `org_id` incorrecto (es el de la organización, no el del
  workspace de apps).
- Dispositivos sin lat/lng → ese dispositivo no reporta ubicación al MDM
  (permiso de localización revocado en el dispositivo, o plataforma sin
  soporte); LucidFence los trata como `unknown`, no los inventa.
