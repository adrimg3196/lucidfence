# PRODUCT_ROADMAP — LucidFence (vivo)

> **Canónico y vivo.** Mantenido por el loop Roadmap (`docs/internal/roadmap/README.md`),
> dueño `product-roadmap-strategist`. Horizonte deslizante: **Ahora / Próximo /
> Después**. Cada ítem cita su origen — sin señal real no entra.
>
> Estado: v1.5.0 en producción · main verde · última pasada 2026-08-16 (ciclo 1).
> Los roadmaps `ROADMAP_Q3*.md`, `ROADMAP_2026-2027.md` y `roadmap.json` son
> **históricos/archivados** (ver más abajo).

## Principios de priorización (no negociables)

Local-first & soberano · $0 por defecto (solo free tiers) · datos del tenant en
su máquina · verificar en runtime, no solo "compila" · sin telemetría ·
**complemento, no UEM** (decisión del propietario 2026-08-18: LucidFence nunca
enrola, empuja perfiles ni gestiona apps/parches — lee del UEM existente,
correlaciona, explica, y actúa solo a través del UEM cuando el admin decide).

## Ahora (en vuelo)

La flota mantiene v1.5.x. No hay épica de producto abierta esta semana: las
mejoras entran de una en una por el loop **Admin-value** (sábados), que toma su
siguiente ítem del bloque "Próximo" de abajo. Salud operativa la cubren
Guardián (main), Centinela (seguridad) y Deps-sweeper (dependencias).

**Lo más caliente del horizonte es seguridad** (ítem 1 de "Próximo"): hay 8
hallazgos de la auditoría Strix sin verificar desde julio.

## Próximo (candidatos priorizados — origen citado)

| # | Ítem | Impacto | Esfuerzo | Loop dueño | Origen (señal real) |
|---|------|---------|----------|-----------|---------------------|
| 1 | **Verificar y cerrar los 8 hallazgos Strix abiertos** (4 altos: `POST /api/settings/*` sin auth; `settings/test` reenvía `api_key` a Applivery sin auth; SSRF por header `Link` del MDM con robo de token Bearer; SSRF a `webhook_url` interno. + 4 medios/bajos: TLS ctx, `device_id` sin validar, lat/lng sin acotar) | **p0** | Centinela | `docs/internal/security/findings.md` — sembrados de PR #45, estado `open (verificar)`, ningún ciclo los ha cerrado aún |
| 2 | **Onboarding externo** (README npm-style para terceros: qué necesita, cómo instala, cómo comprueba que funciona, FAQ mínima) | p1 | small | Admin-value | README §"No está terminado" (único gap de producto que queda tras cerrar pricing/release/adapters/soporte/seguridad) |
| 3 | **Refrescar `docs/internal/STATE.md`** (sección "Stabilization QA 2026-07-20" declara base v1.2.0 / próximo v1.3.0; hoy v1.5.0) | p2 | small | Admin-value | Housekeeper `deferred-candidates.md` (diferido al loop de producto) |

## Después (horizonte, sin fecha)

| # | Ítem | Impacto | Origen |
|---|------|---------|--------|
| 5 | **Aclarar el estatus de `loop_improve.py` (raíz)**: legacy vs vivo (referenciado por `saas_server.py`, `roadmap_tooling.py`, tests y `roadmap.json`, pero excluido del tarball) — consolidar o retirar con evidencia | p2 | Housekeeper `deferred-candidates.md` |
| 6 | **Retirar `ZERO-BACKLOG.md` (raíz)** si el análisis confirma que es rancio (solo referenciado por el exclude de `build.sh`) | p2 | Housekeeper `deferred-candidates.md` |
| 7 | **Ampliar cobertura de adaptadores UEM** más allá de Applivery/Intune/Jamf/Fleet según demanda inbound real | p2 | README §"Lo que sí funciona" + inbound de Growth |

> Los ítems de "Después" suben a "Próximo" cuando un ciclo aporta señal fresca
> (demanda inbound, finding de seguridad, decisión del propietario). Los findings
> de Centinela con severidad entran directos en "Próximo" del ciclo siguiente.

## EXPLORE (Horizonte NOVA / Visión Soñadora para Hermes)

Propuestas de descubrimiento de producto para que el agente de ingeniería (Hermes) evalúe e implemente en futuros ciclos. Documentación completa en `docs/product/NOVA_VISIONARY_ROADMAP_HERMES.md`.

| # | Propuesta Visionaria | Impacto | Esfuerzo | Fichero de Especificación |
|---|----------------------|---------|----------|---------------------------|
| E1 | **Dynamic Swarm & Moving-Anchor Geofencing** (Geocercas móviles relativas para convoyes y escoltas) | Visionario (P1) | M-L | `docs/product/NOVA_VISIONARY_ROADMAP_HERMES.md` |
| E2 | **Peer-Assisted Zero-Cloud Mesh Consensus** (Atestiguamiento P2P BLE/mDNS para ubicación soberana sin GPS/nube) | Visionario (P1) | L | `docs/product/NOVA_VISIONARY_ROADMAP_HERMES.md` |
| E3 | **Local Edge Spatial-Drift Intelligence** (Predicción cinemática on-device de desvío espacial cero-telemetría) | Visionario (P2) | M | `docs/product/NOVA_VISIONARY_ROADMAP_HERMES.md` |
| E4 | **Immutable Black-Box Flight Recorder** (Registro forense inmutable hash-chained firmado por TPM/Enclave) | Visionario (P1) | M | `docs/product/NOVA_VISIONARY_ROADMAP_HERMES.md` |
| E5 | **Universal Declarative UEM Compiler (`lucidfence compile`)** (Compilador universal de políticas a Intune/Jamf/Fleet/AMAPI) | Visionario (P1) | L | `docs/product/NOVA_VISIONARY_ROADMAP_HERMES.md` |

## Bitácora de reconciliación

- **2026-08-18 (decisión del propietario).** Posicionamiento fijado: **"nunca
  seremos un UEM, somos el complemento"** — sube a principio no negociable.
  El loop PM lo aterrizó en `docs/internal/product/BACKLOG.md` (§Posicionamiento
  + 6 ítems nuevos de capa-complemento, #12–#17: panel multi-UEM, segunda
  opinión UEM vs observado, políticas portables, puntos ciegos, auditor de
  mínimo privilegio, eventos OCSF). Pendiente de reconciliar por el loop
  Roadmap en su próximo ciclo.
- **2026-08-16 (ciclo 2, decisión del propietario).** El propietario declaró el
  modelo: **LucidFence es 100% free open-source (Apache-2.0), sin pricing, sin
  enterprise, sin funciones de pago.** Cierra el gap "Pricing / modelo de
  negocio" (era el #3): declarado en `README.md` §Modelo. En la misma PR se
  corrigió la tabla "No está terminado" del README (el antiguo #2): las 4
  entregas ya hechas (release v1.5.0, guía de adaptadores, CONTRIBUTING,
  SECURITY.md) marcadas como completas. Queda como único gap de producto el
  onboarding externo (ahora #2).
- **2026-08-16 (ciclo 1, pasada manual).** Reconciliado contra la realidad de
  `main`:
  - **Bajan (entregado):** README externo/onboarding parcial, guía de
    adaptadores, CONTRIBUTING, SECURITY.md y la publicación de releases ya
    existen → dejan de ser gaps abiertos. El "Próximo" del ciclo 0 (pricing +
    README + STATE) se conserva, pero **repriorizado por debajo de seguridad**.
  - **Sube al #1:** los 8 hallazgos Strix sin verificar (leídos de
    `security/findings.md`) — no estaban en el ciclo 0. Es ahora lo más
    prioritario; su dueño es Centinela (jueves 22:07 UTC).
  - **Nuevo ítem #2:** la tabla "No está terminado" del README desinforma
    (4 entregas marcadas como pendientes) → derivado a Admin-value.
- **2026-08-16 (ciclo 0).** Roadmap canónico resuelto: los dos `ROADMAP_Q3` en
  conflicto (candidato diferido del Housekeeper) → este `PRODUCT_ROADMAP.md` es
  el único vivo; ambos Q3 archivados con banner. `roadmap.json` archivado.

## Archivo histórico (no editar; contexto, no plan)

- `roadmap.json` + `lucidfence/core/roadmap_tooling.py` — roadmap del *tooling de
  auto-mejora* (`/loop` MoA), 18/18 `complete`. Congelado 2026-08-01.
- `docs/roadmap/ROADMAP_2026-2027.md`, `ROADMAP_Q3.md`, `ROADMAP_Q3_2026.md`,
  `ROADMAP_TOOLING.md` — snapshots de planificación previos.
