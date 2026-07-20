# ROADMAP_TOOLING.md — Estructura de mejora a nivel de herramienta (LucidFence)

Este documento define **la estructura de mejora a nivel de herramienta** de
LucidFence (la herramienta de geofencing UEM) y su plan de 12 meses. No es un
PDF olvidado: es la fuente de verdad de `roadmap.json`, se auto-reporta con
`python3 roadmap_tooling.py`, se expone en `GET /api/roadmap` (cuando el
dashboard lo sirve) y se mejora en bucle con `python3 loop_improve.py` (el
`/loop` de Mixture-of-Agents).

> Estado base (20-jul-2026): LucidFence v1.2.0 — adapters Applivery/Intune/Jamf
> vivos, engine con risk explicable + CVE (NVD) + SOAR + incidents + workflows,
> loop de mejora en fase temprana (L1, report-only).

## Estructura de mejora a nivel de herramienta

La mejora continua es ciudadano de primera clase. Se sostiene en 6 capas:

| # | Capa | Qué es | Dónde vive |
|---|------|--------|-----------|
| 1 | **Persistencia** | `roadmap.json` con schema estricto (fases → features → subtasks, cada una con impacto/esfuerzo/criterios) | `roadmap.json` |
| 2 | **Motor** | `roadmap_tooling.py`: load/save/validate/format/update; el schema es la ley | `roadmap_tooling.py` |
| 3 | **CLI** | `python3 roadmap_tooling.py [--validate/--status/--phase/--mark/--export]` | `roadmap_tooling.py` |
| 4 | **API** | `GET /api/roadmap` (read + progress) + `PATCH /api/roadmap` (update) | `saas_server.py` |
| 5 | **Dashboard** | Pestaña Roadmap: fases, features con badge de estado, barra de progreso global | `static/dashboard.html` + `app.js` |
| 6 | **Loop** | `/loop` (Mixture-of-Agents): proposers gratis + Opus 4.8 como agregador, con verify | `loop_improve.py` |
| 7 | **QA** | `tests/roadmap_tooling_test.py` valida schema + CLI + API; no rompe el runner honesto | `tests/` |

Principios que gobiernan toda feature del roadmap:

1. **Local-first & soberano** — los datos del tenant nunca salen de su máquina.
2. **$0 por defecto** — solo free tiers; cualquier dependencia de pago se pregunta.
3. **Verificar en runtime** — no basta con "compila"; se valida producto vivo y QA.
4. **Runner honesto** — la suite no oculta fallos; el número verde es real.
5. **Sin secretos** — nada de tokens en el cliente Pages ni en el repo.
6. **Mejora continua como ciudadano de primera clase** — roadmap vivo + `/loop`.

### Taxonomía de campos (el "schema es la ley")

- `impact`: `p0_must` (imprescindible) · `p1_should` (debería) · `p2_nice` (opcional)
- `effort`: `small` · `medium` · `large` · `epic`
- `status` de feature: `proposed` · `planned` · `in_progress` · `done` · `deployed` · `blocked`
- `status` de fase: `pending` · `on_track` · `at_risk` · `complete`
- `capability`: `cli` · `api` · `dashboard` · `engine` · `config` · `observability` · `security` · `docs` · `devops` · `plugin` · `loop`

## Inventario de modelos (los que pide el usuario)

El `/loop` usa **Mixture-of-Agents**:

- **Proposers (paralelos, todos gratis):** Nous (vía OpenRouter), Groq, NVIDIA,
  Together, Fireworks, DeepInfra, GitHub Models, OpenAI. Cada uno se invoca solo
  si su API key está presente en `.env` / `LF_PROVIDER_*`. Sin clave, el proposer
  degrada a **análisis local determinístico** para que el loop sea demostrable
  sin secretos.
- **Agregador (merge final):** **Claude Opus 4.8**. Se invoca vía `claude` CLI
  (Claude Code, en `/Users/adri/.local/bin/claude`) si está disponible; si no,
  merge heurístico local.

> **Nota de honestidad (verificada 2026-07-20):** `opencode` NO está instalado en
> este entorno, y no hay API keys de LLM en `config.json`/`.env`. Por tanto el
> `/loop` aquí corre en **modo local determinístico** (proposers + agregador
> heurístico) salvo que se provean claves. La arquitectura ya está cableada para
> usar los free tiers reales en cuanto existan las claves. El agregador Opus 4.8
> se prueba de verdad vía `claude` CLI cuando responde.

## El /loop (cómo "mejorar aún más todo")

`python3 loop_improve.py` ejecuta el ciclo MoA sobre la próxima feature pendiente
(o una concreta con `--feature Fx.y`):

```
Prompt inicial → Proposers paralelos (gratis) → Opus 4.8 merge
   → ¿calidad >= 7/10? ── No ─→ repite (temp -0.1, max 3)
        │ Sí
        ▼
Implementar (marcar subtasks/feature) → Verificar (tests/run_tests.py)
   → QA PASS → feature DONE + persistir en roadmap.json
```

- Máximo **3 iteraciones** por feature (sin loops infinitos).
- Temperatura decae **0.1** por iteración para converger.
- Cada iteración queda en `data/loop_history.jsonl` (ts, feature, temp, providers,
  agregador, score, longitud).
- Si QA no pasa, la feature queda `in_progress` (no se marca `done` falsamente).

## Plan de 12 meses (4 fases trimestrales)

### Q3-2026 — Fundación de mejora tooling + Loop
Roadmap vivo, `/loop` operativo, dashboard de mejora.
- F1.1 Roadmap Tooling (CLI + API + Dashboard) · P0/small
- F1.2 `/loop` de mejora (MoA: proposers gratis + Opus 4.8) · P0/medium
- F1.3 Dashboard de mejora (pestaña Roadmap en dashboard local) · P0/medium
- F1.4 QA extendido con tests de roadmap + loop + providers · P0/medium
- F1.5 Documentación de arquitectura MoA + loop + roadmap · P1/small

### Q4-2026 — Automatización y Resiliencia
- F2.1 Auto-priorización de features vía `/loop`
- F2.2 Alertas inteligentes (cruce de geocerca por LLM)
- F2.3 Análisis predictivo de movimiento
- F2.4 Simulador de flota multi-tenant
- F2.5 Observabilidad del `/loop` (métricas de calidad)

### Q1-2027 — Ecosistema y DX
- F3.1 SDK Python (`pip install lucidfence`)
- F3.2 Plugins de proveedores LLM (arquitectura extensible)
- F3.3 Integración con UEM (Intune + Workspace ONE)
- F3.4 CLI interactiva / REPL (`lf shell`)
- F3.5 Dashboard multi-tenant con autenticación

### Q2-2027 — Producción y Gobernanza
- F4.1 Containerización (Docker multi-stage + compose)
- F4.2 Observabilidad con Prometheus + logs estructurados
- F4.3 Gobernanza / Compliance (audit trail + API keys)
- F4.4 Release comunitario (CI/CD + changelog + issues)
- F4.5 Caso de éxito público + landing page

## Cómo usarlo (evidencia real, no afirmaciones)

```bash
cd ~/geofence-uem
python3 roadmap_tooling.py --validate     # valida el schema (debe decir "valido")
python3 roadmap_tooling.py                # muestra el plan + barra de progreso
python3 roadmap_tooling.py --phase Q3-2026
python3 roadmap_tooling.py --mark F1.1 status done   # marca y persiste
python3 loop_improve.py                   # /loop sobre la proxima feature
python3 loop_improve.py --feature F1.2 --dry-run
python3 tests/run_tests.py                # suite honesta (debe seguir verde)
```

## Métrica de éxito

- Progreso global = features `done`+`deployed` / total (se muestra en CLI/dashboard).
- Meta por fase: Q3-2026 ≥ 20% · Q4-2026 ≥ 45% · Q1-2027 ≥ 70% · Q2-2027 ≥ 90%.
- Calidad del `/loop`: score promedio por iteración en `data/loop_history.jsonl`.
- Cualquier feature se marca `done` solo cuando sus `subtasks` están `done` y QA
  pasa. El progreso de una feature es el % de subtasks completadas.
