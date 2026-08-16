# PRODUCT_ROADMAP — LucidFence (vivo)

> **Canónico y vivo.** Mantenido por el loop Roadmap (`docs/internal/roadmap/README.md`),
> dueño `product-roadmap-strategist`. Horizonte deslizante: **Ahora / Próximo /
> Después**. Cada ítem cita su origen — sin señal real no entra.
>
> Estado: v1.5.0 en producción · main verde · actualizado 2026-08-16 (ciclo 0).
> Los roadmaps `ROADMAP_Q3*.md`, `ROADMAP_2026-2027.md` y `roadmap.json` son
> **históricos/archivados** (ver más abajo).

## Principios de priorización (no negociables)

Local-first & soberano · $0 por defecto (solo free tiers) · datos del tenant en
su máquina · verificar en runtime, no solo "compila" · sin telemetría.

## Ahora (en vuelo)

La flota mantiene v1.5.x. No hay épica de producto abierta esta semana: las
mejoras entran de una en una por el loop **Admin-value** (sábados), que toma su
siguiente ítem del bloque "Próximo" de abajo. Salud operativa la cubren
Guardián (main), Centinela (seguridad) y Deps-sweeper (dependencias).

## Próximo (candidatos priorizados — origen citado)

| # | Ítem | Impacto | Esfuerzo | Loop dueño | Origen (señal real) |
|---|------|---------|----------|-----------|---------------------|
| 1 | **Declarar pricing / modelo de negocio** (qué es OSS puro, qué sería enterprise, si acaso) | p1 | small | Admin-value | README §"No está terminado": *"Pricing / modelo de negocio declarado — No existe"* |
| 2 | **Pulir README externo / onboarding de terceros** (qué necesita, cómo instala, cómo comprueba que funciona, FAQ mínima, cómo reporta bugs) | p1 | small | Admin-value / Growth | README §"No está terminado": *"README público / onboarding — Estado inicial"* |
| 3 | **Refrescar `docs/internal/STATE.md`** (sección "Stabilization QA 2026-07-20" declara base v1.2.0 / próximo v1.3.0; hoy v1.5.0 publicada) | p2 | small | Admin-value | Housekeeper `deferred-candidates.md` (diferido al loop de producto) |

## Después (horizonte, sin fecha)

| # | Ítem | Impacto | Origen |
|---|------|---------|--------|
| 4 | **Aclarar el estatus de `loop_improve.py` (raíz)**: legacy vs vivo (referenciado por `saas_server.py`, `roadmap_tooling.py`, tests y `roadmap.json`, pero excluido del tarball) — decidir consolidar o retirar con evidencia | p2 | Housekeeper `deferred-candidates.md` |
| 5 | **Retirar `ZERO-BACKLOG.md` (raíz)** si el análisis confirma que es rancio (solo referenciado por el exclude de `build.sh`) | p2 | Housekeeper `deferred-candidates.md` |
| 6 | **Ampliar cobertura de adaptadores UEM** más allá de Applivery/Intune/Jamf/Fleet según demanda inbound real | p2 | README §"Lo que sí funciona" + inbound de Growth |

> Los ítems de "Después" suben a "Próximo" cuando un ciclo aporta señal fresca
> (demanda inbound, finding de seguridad, decisión del propietario). Los findings
> de Centinela con severidad entran directos en "Próximo" del ciclo siguiente.

## Decisión de producto de este ciclo (ciclo 0)

**Roadmap canónico resuelto.** Existían dos `ROADMAP_Q3` en conflicto que el
Housekeeper difirió como *"decisión de producto, no de limpieza"*:
- `ROADMAP_Q3_2026.md` (board `lucidfence`, con "Estado operativo revalidado
  2026-08-14") y `ROADMAP_Q3.md` (board `uem-ops`, referenciado por el CEO
  review de julio) → **ambos archivados como snapshots históricos**; este
  `PRODUCT_ROADMAP.md` es el único canónico vivo. Q3-2026 termina; el horizonte
  real es Q4-2026 en adelante, capturado arriba.

## Archivo histórico (no editar; contexto, no plan)

- `roadmap.json` + `lucidfence/core/roadmap_tooling.py` — roadmap del *tooling de
  auto-mejora* (`/loop` MoA), 18/18 `complete`. Congelado 2026-08-01.
- `docs/roadmap/ROADMAP_2026-2027.md`, `ROADMAP_Q3.md`, `ROADMAP_Q3_2026.md`,
  `ROADMAP_TOOLING.md` — snapshots de planificación previos.
