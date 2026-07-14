# Plan — LucidFence (lifecycle tasks)

Generado por `/plan` sobre `SPEC.md`. Ordenado por dependencia. Cada tarea tiene
verificación runtime. La barra de calidad es `references/definition-of-done.md`.

## T1 — Vitrina multi-tenant serverless ✅ DONE
- Obj: engine-cron publica estado de N tenants a `data/cloud_state.json`; cloud.html lo consume.
- Verif: `gh workflow run engine-cron.yml` → cloud.html muestra selector de tenant.
- Estado: COMPLETADO. 2 tenants (demo, acme-logistics), 7 devices, 57% compliance.

## T2 — CVE/SOAR demo en vitrina ✅ DONE
- Obj: inyectar resumen CVE/SOAR determinista en el payload de simulación.
- Verif: cloud.html renderiza "Apps escaneadas: 15 · Vulnerables: 2 · CVE-2024-1234".
- Estado: COMPLETADO.

## T3 — Installer para clientes ✅ DONE
- Obj: docker-compose.yml + install.sh + CLIENTE.md para que el cliente despliegue always-on en su infra.
- Verif: `docker compose config` válido; CLIENTE.md sirve en Pages (HTTP 200).
- Estado: COMPLETADO (Docker no disponible en este entorno para runtime, pero sintaxis validada).

## T4 — Definition of Done + agent-skills framework ✅ DONE (este plan)
- Obj: aplicar el marco agent-skills (addyosmani/agent-skills) a LucidFence.
- Entregables: SPEC.md, references/*, .claude/.gemini commands, agents/*, AGENTS.md, tasks/plan.md.
- Verif: `/review` y `/ship` corren sobre el estado actual (abajo).

## T5 — CI honesto + test runner (anteriores, consolidado)
- Obj: runner que no oculte fallos; 105 tests pasan.
- Verif: `python3 tests/run_tests.py` → 105 passed, 0 failed, exit 0.
- Estado: COMPLETADO y verificado.

## T6 — Always-on backend multi-tenant self-service (PENDIENTE, requiere credencial del cliente)
- Obj: backend always-on con sesiones reales para signup de tenants desde el navegador.
- Por qué pendiente: exponer un token en el cliente de Pages es inaceptable; necesita
  Fly/HF con el token del CLIENTE (no nuestro). `deploy-fly.yml` ya listo.
- Cuando el cliente aporte FLY_API_TOKEN o HF_TOKEN: ejecutar deploy y validar signup E2E.

## Orden de ejecución futura (greenfield para nuevas features)
/spec → /plan → /build (TDD, incremental) → /review → /ship
Legado en `core/`: characterization tests antes de cambiar (brownfield rule).
