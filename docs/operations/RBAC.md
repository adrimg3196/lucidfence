# RBAC: roles, permisos y cómo asignarlos

LucidFence controla qué puede hacer cada persona con **roles por organización**.
El rol vive en el perfil del usuario (`org_id → rol`) y toda mutación de la API
comprueba una *capability* antes de tocar nada. Nada de esto sale de tu tenant:
un propietario solo ve y gestiona **su** organización.

## Los roles

| Rol | Etiqueta | Para quién |
| --- | --- | --- |
| `owner` | Propietario | Dueño del despliegue: facturación, usuarios, todo. |
| `admin` | Administrador | Gestiona flota, cercas, políticas y usuarios; no toca roles ni borra la org. |
| `operator` | Operador | Ejecuta ciclos y acciones sobre dispositivos; no configura el engine. |
| `viewer` | Solo lectura | Ve dashboards y reportes; no cambia nada. |
| `auditor` | Auditor | Visibilidad de auditoría/compliance + export; sin acciones. |

La matriz exacta de capabilities está en
[`../../lucidfence/saas/auth.py`](../../lucidfence/saas/auth.py) (`ROLE_CAPS`),
que es la única fuente de verdad. El dashboard la muestra tal cual en
**Ajustes → Equipo · Roles**, así que la guía nunca se desincroniza del código.

Diferencias que importan:

- Solo `owner` tiene `user:role`: **solo un propietario reasigna roles**.
- `owner` y `admin` tienen `user:invite`: ambos crean miembros y ven el equipo,
  pero un admin no puede crear ni ascender a `owner`/`admin`.
- `engine:config` (owner/admin) controla enforcement y conectores; ver
  [ENFORCEMENT.md](ENFORCEMENT.md).
- `device:action` (owner/admin/operator) es el permiso para ejecutar comandos;
  cada uno queda en el action log con el email del operador — ver
  [TEAM_ACCESS.md](TEAM_ACCESS.md).

## Ver y cambiar roles desde el dashboard

1. Entra como propietario y abre **Ajustes**.
2. La tarjeta **Equipo · Roles** lista cada miembro con su rol actual. Solo el
   propietario ve esta tarjeta.
3. Cambia el selector de rol de un miembro. El cambio se aplica al instante,
   sale un toast de confirmación y la lista se refresca.

Bajo el capó el navegador llama a la API local:

- `GET /api/members` — miembros de la org activa con su rol y su etiqueta
  (nunca hashes de contraseña ni secretos).
- `POST /api/members/role` con `{"user_id" | "email", "role"}` — valida el rol,
  aplica el guardarraíl del último propietario y deja rastro
  `member.role.changed` en el audit log hash-chained (`GET /api/audit`).

Por API directa (misma sesión de propietario):

```bash
curl -X POST http://127.0.0.1:8765/api/members/role \
  -H 'Content-Type: application/json' \
  --cookie 'gf_session=<tu-sesión>' \
  -d '{"email":"ops@acme.test","role":"operator"}'
```

## Guardarraíles

- **Último propietario:** no puedes degradar al único `owner` que le queda a la
  org. Deja el sistema sin nadie que gestione usuarios y facturación; la API
  responde `400` y no cambia nada. Asciende primero a otra persona a `owner`.
- **Aislamiento por tenant:** el endpoint solo opera sobre la org activa. Un
  usuario que no pertenece a tu org devuelve `404`, no se filtra su existencia.
- **Sin escalada por API key:** las claves de automatización no pueden reasignar
  roles (`user:role` exige una sesión de propietario en el navegador).

## Principio de mínimo privilegio

Asigna el rol **más bajo** que deje a la persona hacer su trabajo:

- ¿Solo mira paneles y saca reportes? `viewer`.
- ¿Audita compliance sin operar? `auditor`.
- ¿Ejecuta acciones sobre la flota pero no configura integraciones? `operator`.
- ¿Gestiona conectores, políticas y da de alta gente? `admin`.
- Reserva `owner` para las pocas personas que responden por la facturación y la
  cuenta. Cuantos menos propietarios, menor la superficie de un abuso o un robo
  de credencial — pero siempre **al menos uno**.

Rol + fase de enforcement + credencial UEM de mínimo privilegio son tres líneas
de defensa independientes; combínalas.
