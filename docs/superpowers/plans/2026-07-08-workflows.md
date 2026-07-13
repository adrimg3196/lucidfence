# Plan: Módulo de Workflows Integrados (Applivery) — lucidfence

## Objetivo (pedido del usuario)
> "quiero que tenga un apartado de lógica de workflows integrados ya hechos de uso
> sencillos comunes para usar con applivery y si no de creación por el admin it
> pero poniéndoselo fácil"

El motor de políticas YA soporta trigger (`when`) + acciones Applivery
(`lock`, `wipe`, `message`, `locate`, `reboot`, `clear_passcode`, `custom`)
vía `LiveAdapter`. Lo que falta es la CAPA DE PRESENTACIÓN:
  1. **Workflows ya hechos** (plantillas comunes) listaos en el dashboard,
     un click para activar, pensados para Applivery.
  2. **Creación fácil por admin IT**: asistente que construye la política desde
     campos simples (disparador + condición + acción) SIN tocar JSON.

## Diseño
- `core/workflows.py` (nuevo):
  - `APPLIVERY_ACTIONS`: catálogo de acciones con label ES + params por defecto.
  - `TEMPLATES`: workflows comunes listos (Bloqueo al salir de ruta,
    Wipe si rooteado fuera de geocerca, Notificar CISO si desviación > 500m,
    Aislar fuera de turno, etc.) — cada uno = trigger + condiciones + acciones.
  - `build_policy_from_template(tpl_id, device_ids=None)` -> dict Policy.
  - `build_custom_policy(form)` -> dict Policy desde campos simples del admin
    (valida y normaliza trigger/condición/acción a la sintaxis `when`+`actions`).
  - `list_active(engine)` -> políticas que vienen de plantillas/custom (de policies.json).
- API `saas_server.py` (nuevo, con RBAC `workflow:*`):
  - `GET  /api/workflows`       -> {templates, active, actions_catalog}
  - `POST /api/workflows/apply`  -> aplica plantilla (añade a policies.json)
  - `POST /api/workflows/custom` -> crea workflow custom fácil
  - `DELETE /api/workflows/<id>` -> desactiva/borra
- `saas/auth.py`: caps `workflow:read`/`workflow:write` para los 4 roles.
- UI `static/saas_views4.js` (nuevo) + nav "Workflows":
  - Tarjetas de plantillas con botón "Activar".
  - Formulario sencillo de creación custom (selects, no JSON).
- Tests: `tests/test_workflows.py` (unit) + `tests/test_qa_workflows.py` (e2e HTTP).

## Tasks (TDD)
1. [TEST] unit `test_workflows.py`: TEMPLATES válidas, build_policy_from_template
   genera `when`+`actions` correctos, build_custom_policy normaliza y valida,
   catálogo de acciones completo.
2. [TEST] e2e `test_qa_workflows.py`: GET /api/workflows 200, apply plantilla
   200 y aparece en active, custom 200, RBAC (viewer 403 en write).
3. [CODE] `saas/auth.py` caps workflow:*; `core/workflows.py`; endpoints en
   `saas_server.py`; vista UI + nav.
4. [DEBUG] systematic-debugging si algún test falla.
5. [REVIEW] subagente reviewer senior sobre workflows.py + endpoints + auth caps.
6. [VERIFY] correr toda la suite (workflows + rutas + e2e) green antes de entregar.
7. [DOC] README sección Workflows.

## Criterio de "perfecto"
- 100% de tests green (unit + e2e).
- Todo vía HTTP directo (sin depender del browser sandbox).
- RBAC correcto (operator puede escribir workflows; viewer solo lee).
- Plantillas aplican políticas reales que el engine ejecuta contra Applivery
  (en sim/dry_run se registra la acción; en live hace POST real a Applivery).
- Sin secretos hardcodeados; sin deps nuevas.
