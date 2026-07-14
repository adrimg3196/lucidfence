# Coverage Analysis — LucidFence Cloud (multi-tenant)

**Scope:** `cloud_publisher.py`, `scripts/saas_api_op.py`, `static/cloud.html`, `engine-cron.yml`
**Runner:** `tests/run_tests.py` — HONESTO para tests estilo `test_*()` (99 pass / 6 fail, exit=1; fallos no ocultos). Gap residual: `test_it_admin_features.py` corre suite inline a nivel módulo y no hace `raise SystemExit`, así que sus `check()` fallidos NO entran en el tally ni en `sys.exit(1)`. No afecta a las 4 áreas de abajo (0 tests las cubren).

## Veredicto: **NEEDS_TESTS**

Cero tests cubren las 4 áreas nuevas (grep de `cloud_publisher|saas_api_op|build_demo_engine|create_tenant|add_fence|remove_tenant|cloud_tenants|serialize` → 0 matches).

### 🔴 BLOCKING (gaps de correctitud/seguridad)
- **saas_api_op — auth 401 / tenant_id raro:** `_tenant_dir` valida alfanumérico/-/_, pero `main()` no valida `ACTION` ni firma; cualquiera con dispatch puede `remove_tenant`. Falta test de `create_tenant` con `TENANT_ID="a/b;rm"` → `ValueError`, y `add_fence` a tenant inexistente → `ValueError`.
- **saas_api_op — input inválido:** `create_tenant` hace `d["lat"]`/`d["lng"]` sin `.get()` → `KeyError` silencioso si falta lat/lng; ningún test de payload con device sin lat/lng.
- **cloud_publisher — tenant con 0 devices / fence radio 0:** `serialize` divide por `total` (protegido con `if total else 0`), pero `compliance_rate_pct` y mapa con 0 devices no están testeados; `radius_m=0` → `Math.max(8,...)` oculta; `proj` con lat/lng null ya salta en JS.

### 🟡 RECOMMENDED (edge cases / error paths)
- **cloud.html render por tenant:** `renderTenant` con `s.devices` vacío, `totals` ausente, `cve_summary`/ `soar` nulos — sin test de contrato (test_frontend_contract.py no toca cloud.html).
- **saas_api_op PAYLOAD no-JSON:** `main()` hace `sys.exit(1)` pero no hay test que confirme el exit code.
- **engine-cron.yml concurrencia:** `cloud_publisher` itera tenants con `run_once` secuencial; `cycle_in_progress` solo testeado en server, no en publisher multi-tenant.

### 🟢 ADEQUATE (cubierto por otras suites)
- **run_once / cycle_in_progress:** cubierto en `test_engine_routes.py`, `test_cooldown.py`, `test_qa_e2e.py` (single-tenant).
- **Auth 401 en API server:** `test_run_once_requiere_auth` (patrón en testing-patterns).

## Siguiente paso sugerido
Añadir `tests/test_cloud_publisher.py` + `tests/test_saas_api_op.py` con patrones AAA del marco: `test_create_tenant_rechaza_tenant_id_raro`, `test_add_fence_tenant_inexistente_ValueError`, `test_serialize_tenant_0_devices_compliance_0`, `test_publisher_omite_tenant_sin_seed`. Mock de FS/HTTP en límites, no en lógica.
