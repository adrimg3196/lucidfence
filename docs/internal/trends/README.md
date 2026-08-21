# Loop Tendencias → Producto (investigación aplicada)

Vigila el ecosistema como lo haría un desarrollador senior: mira hacia dónde va
el sector MDM/UEM, la seguridad de endpoints y la regulación, y **convierte esa
señal en mejoras concretas del producto LucidFence** — sin autorización humana.
Es el brazo de I+D aplicada de la flota.

No confundir con el **Radar UEM/MDM** (`cron` de preventa del propietario, escribe
informes fuera del repo): aquel informa a una persona; este **entrega producto**.

## Norte

Traduce tendencia en valor para el admin IT. Toda señal que se registre o se
implemente cita su fuente (URL). Jamás una feature inventada ni "porque suena
moderno": la pregunta es siempre *¿esto hace LucidFence mejor para un admin real
de Intune/Jamf/Applivery/Fleet, respetando los invariantes?*

## Qué vigilar (fuentes reales, citadas)

- **Plataforma Apple:** protocolo MDM y **DDM** (Declarative Device Management),
  novedades de gestión en betas de iOS/iPadOS/macOS, `github.com/apple/device-management`.
- **Android Enterprise / AMAPI:** cambios en Android Management API, políticas,
  OEMConfig (Knox, Zebra), boletines de seguridad.
- **Windows:** CSPs nuevos/deprecados, DSC, Autopilot en lo que toque a gestión.
- **osquery / Fleet:** tablas nuevas, capacidades de postura y de ubicación lógica.
- **Seguridad:** CVEs y avisos que afecten a la stack (stdlib de Python, patrones
  de auth/SSRF/geofencing), OWASP, técnicas nuevas de spoofing de ubicación.
- **Regulación con impacto en gestión de flota:** NIS2, GDPR, CRA, ENS/CCN —
  cuando implican un requisito verificable de producto (retención de auditoría,
  minimización de datos, cifrado).
- **Competencia (para detectar gaps, no para copiar humo):** capacidades que un
  admin espera y LucidFence aún no da.

## Ciclo (semanal)

1. Lee `docs/internal/LOOP.md` (§Norte de la flota, §Coordinación, §Entrega por
   el raíl) y `docs/internal/STATE.md`.
2. Investiga con WebSearch/WebFetch (solo lectura; nunca ataca ni toca hosts de
   terceros). Reúne 3-6 señales reales de las últimas semanas, cada una con
   fuente y etiqueta de confianza ([Oficial]/[Prensa]/[Rumor]).
3. Prioriza **una** por impacto × esfuerzo × principios (local-first, $0,
   runtime-first, Fleet primera clase). Decide:
   - **Implementable en un diff pequeño** → delega en el especialista del bench
     adecuado (`engineering-senior-developer`, `engineering-iot-fleet-engineer`,
     `security-architect`…): código + tests + check runtime si añade un claim.
   - **Demasiado grande** → item de backlog en la sección "Loop admin-value" de
     `STATE.md` con la evidencia citada (no lo implementes a medias).
4. Verifica: `python3 scripts/verify.py` → `APTO (4/4)`. Registra la señal y la
   decisión en `docs/internal/trends/signals.md` (append-only, con fuentes).
5. **Entrega por el raíl:** `git push` a `claude/trends-loop`; `agent-pr.yml`
   abre la PR y `agent-automerge.yml` la mergea en verde. Sin autorización
   humana. Una entrega por ciclo (WIP=1, título `trends: …`).
6. Línea en `docs/internal/loop-run-log.md`.

## Invariantes

- Local-first, stdlib-first, 100% gratis, sin telemetría, sin exfiltración de
  ubicación. `base.py` y la doble llave del wipe, intactos.
- Nada anunciado sin validación en runtime (regla permanente del propietario).
- Solo señales reales y citadas. "No encontré nada accionable esta semana" es un
  resultado válido: refresco de `signals.md` y una línea, sin PR.
- Autonomía total para el trabajo de producto; el único gate humano que queda en
  la flota es `outreach:` (publicación externa), y no es de este loop.
