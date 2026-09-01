# Investigación: Las acciones DDM en modo mock devuelven un mock genérico sin datos

**Issue:** #71

## Contexto

`JamfAdapter` con `live=False` (el default, y el modo en que corre la demo) enruta cualquier acción a `_execute_mock`, que devuelve `{"ok": True, "mock": True, "command_id": ..., "jamf_verb": None}`. Para las acciones DDM nuevas (`ddm_status`, `ddm_sync`) eso es engañoso:

- `ddm_status` responde `ok=True` **sin** `device_state` ni `status_items`, así que un consumidor que lea `res["device_state"]` recibe un `KeyError` en mock y un dict en live.
- `jamf_verb: None` sugiere que exist

---

*developer_agent el 2026-09-01*
