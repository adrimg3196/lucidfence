# Roadmap Q3 2026 — LucidFence

> PM: priorización del backlog del board `lucidfence`.
> Principios que rigen el orden (de `SPEC.md`): **local-first & soberano**, **$0**
> (solo free tiers), **datos del tenant en máquina del cliente**, y **verificar en
> runtime, no solo "compila"**.

## Resumen ejecutivo

El backlog se agrupa en 5 temas del negocio + 4 pistas de soporte. El orden Q3
prioriza **refuerzo del producto real** (instalación siempre-on + vitrina de
captación que convierte) por delante de la expansión de plataformas MDM, y encadena
**seguridad → self-service** porque la vitrina serverless no debe quedar expuesta
sin los gates M1–M4 cerrados.

**No se toca la nube del proveedor (Fly) sin el token del cliente** — es un bloqueo,
no una tarea del agente (ver Sprint 4).

## Temas del backlog → orden

| # | Tema (card) | Asignee | Dónde vive | Rol en Q3 |
|---|-------------|---------|-----------|-----------|
| 1 | Vitrina cloud (mapa de calor + filtro tenant) `t_e3c83b92` | oem-frontline-specialist | captación serverless | Conversión |
| 2 | Installer cliente (systemd always-on) `t_784df03f` | windows-mdm-specialist | producto real | Retención/operación |
| 3 | Self-service (issue→tenant→vitrina E2E) `t_314a3b3a` | integrations-specialist | captación | Automatización ventas |
| 4 | Seguridad (gates M1/M2 antes de Fly) `t_9bd39f56` | vault-curator | ambos | Pre-condición |
| 5 | CVE feed (NVD real en vitrina) `t_782e9002` | applivery-api-specialist | vitrina demo | Diferenciador |

Pistas de soporte: Landing `t_36295dfc`, Doc cliente/runbook `t_70bc3604`,
Monitor `t_e52d5ab0`, Adapter iOS `t_27cf3c3a`, ChromeOS `t_2855cbf2`,
Windows conformidad `t_4447cbfb`, Competitive intel `t_fb08c63c`.

## Secuencia sugerida (Sprints Q3)

### Sprint 1 — Ancla el producto real (Julio)
1. **Installer cliente (systemd)** — el producto real es la app local always-on.
   Sin systemd, el cliente reinicia y la vitrina/server caen. Dependen de esto las
   demos de conformidad en vivo que el usuario exige ver.
2. **Vitrina cloud (mapa de calor + filtro tenant)** — mejora la captación serverless
   (siempre-on, $0) que alimenta el embudo comercial. No bloquea al producto local.
3. **Landing (testimonios + pricing + FAQ)** — conversión de la vitrina a instalación.

*Por qué este orden:* el cliente que instala y ve su flota viva es la unidad de valor;
la vitrina y landing son la puerta de entrada.

### Sprint 2 — Confianza y diferenciadores (Julio–Agosto)
4. **CVE feed (NVD real)** — sustituye el demo por datos reales cuando hay red;
   mantiene fallback demo. Es el diferenciador técnico vs Jamf/Intune en el benchmark.
5. **Doc cliente (runbook Obsidian)** — reduce soporte: arrancar, añadir geocercas,
   leer incidencias. Necesario antes de escalar instalaciones.
6. **Monitor (health-check que crea tareas)** — protege el SLA vitrina/tests<110;
   cierra el bucle de operación.

### Sprint 3 — Seguridad pre-exposición (Agosto)
7. **Seguridad M1/M2 (+ M3/M4 de hardening local)** — gates de
   `security-audit-2026-07-14.md` **antes** de cualquier despliegue internet-facing.
   Incluye el hardening local (M3 rate-limit, M4 error genérico, L1/L2 headers) que
   beneficia también al server del cliente, no solo a Fly.

*Por qué aquí:* la vitrina serverless ya está viva y hay intención de self-service
internet-facing; los gates son pre-condición, no post-condición.

### Sprint 4 — Self-service y expansión (Agosto–Septiembre)
8. **Self-service E2E (issue→tenant→vitrina)** — **BLOQUEADO por token del cliente**
   (Fly/HF). El backend always-on no debe exponer nuestro token ni el de Pages.
   Cuando el cliente aporte `FLY_API_TOKEN`/`HF_TOKEN`: desplegar y validar signup E2E ≤15 min.
9. **Adapters MDM (iOS → ChromeOS → Windows conformidad)** — amplían la cobertura de
   flotas en la vitrina; secuencia iOS primero (mayor demanda), luego ChromeOS,
   Windows conformidad cierra el riesgo por plataforma.
10. **Competitive intel (benchmark)** — alimenta el copy de ventas; puede correr en
    paralelo desde Sprint 1 (no bloquea nada).

## Decisiones de priorización (criterios)
- **Valor para el cliente > amplitud de plataforma.** Installer y Vitrina primero.
- **Seguridad es pre-condición de exposición**, no trabajo de "después".
- **CVE y Competitive intel son diferenciadores de ventas** → Sprint 2/4, en paralelo.
- **Self-service depende de credencial externa** → se marca como bloqueo explícito,
  no se ejecuta en falso.
- **Monitor y Doc son habilitadores de escala**, no features de cara al cliente → S2.

## Riesgos / bloqueos
- **Fly/HF token del cliente** para self-service internet-facing (Sprint 4). Sin él,
  la vitrina serverless (GitHub Pages) cubre la captación y el Installer cubre el
  producto real. No se usa `flyctl auth login` headless (falla silenciosamente).
- **macOS sin Docker** en el entorno de build: el Installer (Docker) se valida por
  sintaxis (`docker compose config`), no por runtime aquí.
- **Tests <110**: el Monitor debe crear tarea de fix si la suite baja de 110 o la
  vitrina cae.
