# Growth — vigilar la adopción y empujarla (un experimento por semana)

Loop semanal de crecimiento. Dirección *mide* la tracción; este loop la
*empuja*: cada ciclo formula UNA hipótesis, ejecuta UN experimento, y el
resultado (con números) aparece en el digest del lunes. Growth engineering
honesto: sin humo, sin spam, sin métricas inventadas.

## Qué vigila (cada ciclo)

1. **Inbound sin atender** — issues nuevas o preguntas sin respuesta.
   Regla: ninguna issue de un usuario real pasa >1 ciclo sin una respuesta
   útil (primera impresión = adopción). Spam/duplicados: política de
   `LOOP.md`.
2. **Menciones y llegada** — búsqueda de menciones de LucidFence
   (GitHub code/repo search; web search si está disponible). Nuevas
   menciones → se registran en `mentions.md` con enlace y contexto.
3. **Superficie pública** — Pages vivo y sin strings prohibidos, README con
   quickstart arriba, description y topics del repo alineados con lo que un
   admin buscaría (los topics son el SEO de GitHub), release notes de la
   última release legibles.
4. **La serie de tracción** (`docs/internal/exec/traction.jsonl`, escrita
   por Dirección) — para leer si el experimento anterior movió algo.

## Qué ejecuta (UN experimento por ciclo, de este menú o similar)

- Mejoras de discoverability del repo: topics, description, README
  (quickstart primero, GIF/captura del dashboard, badges honestos).
- Páginas de caso de uso en la vitrina ("geofencing para flotas Intune sin
  exfiltrar ubicación", por vertical) — siempre con claims validados.
- Contenido técnico publicable EN el repo/Pages: comparativas honestas,
  guías que respondan a búsquedas reales de admins.
- **Workflows SEO** (metodología de [open-seo](https://github.com/every-app/open-seo):
  workflows enfocados, no suite inflada):
  - *Auditoría on-page de Pages*: title/meta description únicos por página,
    un solo H1, jerarquía de headings, Open Graph, `sitemap.xml` +
    `robots.txt`, enlaces internos entre landing/casos de uso/docs. Se
    audita con fetch real de las páginas publicadas, no de memoria.
  - *Visibilidad ante IAs* (AI visibility): `llms.txt` en Pages con el
    resumen canónico del producto, claims verificables enlazados y docs
    estructuradas — los asistentes que recomiendan herramientas a admins
    son un canal de descubrimiento real.
  - *Contenido orientado a keyword*: cada página de caso de uso apunta a
    UNA búsqueda concreta de admin (p.ej. "intune geofence compliance
    open source") formulada como la haría el admin; la hipótesis del
    experimento nombra la búsqueda objetivo.
  - *Escalado opt-in*: si el propietario despliega OpenSEO o aporta
    credenciales DataForSEO, el loop puede usar keyword research y rank
    tracking reales; sin credenciales se usan solo señales gratuitas
    (GitHub search, autocompletar público) y se dice así en la hipótesis.
- **Borradores de outreach** en `docs/gtm/outbox/` (Show HN, r/selfhosted,
  r/sysadmin, LinkedIn, listas awesome-*): redactados, listos para que EL
  PROPIETARIO los publique con un copy/paste. El material previo de
  `docs/gtm/` (community-strategy, launch-copy) es la base — operarlo, no
  reinventarlo.
- Mejoras de first-run (si son de producto → derivación al Admin-value).

## Registro de experimentos (`experiments.md`)

Una entrada por experimento: fecha, hipótesis, acción, métrica esperada,
y (rellenado en ciclos posteriores) resultado real leído de la serie de
tracción. Los experimentos sin resultado a 3 semanas se cierran como
"sin señal". Append-only.

## Límites duros (los que protegen al propietario)

- **Publicar requiere aprobación previa del propietario, siempre.** El
  flujo: el loop propone la publicación en una PR `outreach:` con el
  contenido EXACTO y el destino; el merge del propietario es el sí; el
  siguiente run la ejecuta y registra el enlace en `mentions.md` y el
  resultado en `experiments.md`. Sin merge no se publica nada, nunca.
- Ámbito de lo ejecutable por el loop: solo la cuenta de GitHub
  (submission a listas awesome-*, discussions, UNA respuesta útil y no
  promocional en un repo relacionado). Plataformas donde el agente no
  tiene cuenta (HN, Reddit, LinkedIn, X, email): borrador en
  `docs/gtm/outbox/`, lo publica el propietario.
- Sin spam: máximo UNA publicación externa por ciclo, siempre con valor
  genuino para quien la recibe; a un mismo destino no se vuelve en <30
  días.
- Sin testimonios, métricas o social proof inventados (la vitrina ya se
  limpió de eso una vez, #119; el guard de Pages lo vigila).
- Sin telemetría en el producto: la adopción se mide solo con señales
  públicas (stars, forks, descargas, issues, menciones).
- Todo cambio va por PR con el gate QA; cambios de superficie pública
  (Pages/README/topics) son mergeables por el loop; outreach es SIEMPRE
  del propietario.
