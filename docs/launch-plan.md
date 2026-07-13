# Geofence UEM — Plan de Lanzamiento (GTM open-source / multi-MDM)

*Generado con skill `launch` (ORB + 5 fases) + dictamen Growth del tribunal.*
*Modelo: Apache-2.0 core + Enterprise on-prem (SSO/SOAR/Risk Engine premium). Land via MSPs.*

---

## Framework ORB

### Owned (controlamos, compuesto)
- **GitHub repo** (fuente de verdad: código + docs + Discussions)
- **README + docs/** (copy de `marketing-copy.md`)
- **Newsletter MSP** (LinkedIn → captura)
- **Discord dev** (adapters, debugging)

### Rented (visibilidad, no control)
- LinkedIn (posts MSP, Hall of Fame)
- r/selfhosted, Jamf Nation, foros Intune
- Show HN / Hacker News

### Borrowed (audiencia de otros)
- Podcasts de UEM/MDM
- Co-marketing con MSPs piloto
- Influencers self-hosted (estilo TRMNL: manda el demo a un YouTuber UEM)

---

## 5 Fases

### F1 · Internal (ahora)
- Recruir 3-5 MSPs piloto 1:1 para testear `./start_all.sh` + adapter Applivery.
- Validar que el claim "local-first, 0 exfil" es real (auditoría).
- Congelar interfaz `MDMAdapter` (DevRel: congelar o rompe el core).

### F2 · Alpha
- Landing page (GitHub README ya sirve) + sección "Cómo escribir un adapter".
- Anunciar que existe en LinkedIn (teaser: "control plane local agnóstico a MDM").
- Adapter Bounty Sprint abierto: primeros adapters Intune/Jamf verificados → Hall of Fame.

### F3 · Beta
- Trabajar lista de MSPs (demo 1:1 estilo Superhuman).
- Sticker "beta" en dashboard.
- Teasers de problemas resueltos (sin features vacuas).

### F4 · Early Access
- Leak: screenshots del Risk Engine (score 0-100 + razón), GIF de comando remoto.
- Medición: forks, stars, adapters contribuidos.
- Encuesta PMF a MSPs piloto para refinar mensaje.

### F5 · Full Launch
- Self-serve: `git clone` + `./start_all.sh`.
- Show HN + post r/selfhosted + Jamf Nation + foros Intune.
- Blog post: "Por qué tu MDM nativo no explica el riesgo".
- Adapter Bounty Sprint results → Hall of Fame público.

---

## Evento de apertura: Adapter Bounty Sprint
- 2 semanas al entrar en Beta.
- Recompensa: Hall of Fame + shoutout LinkedIn + co-maintainership.
- Plantilla `ADAPTER.md` + starter mock (barrera = PR de fin de semana).
- CI obligatorio contra mock + lint → badge "verified".

---

## Checklist de lanzamiento
- [ ] Interfaz `MDMAdapter` congelada + `ADAPTER.md` + starter mock
- [ ] ≥2 adapters reales: Applivery (live) + Intune/Jamf (mock incluidos, listos para live) — ya cumplido; el claim es "multi-MDM ready por framework de adapters"
- [ ] README con copy de `marketing-copy.md` (tagline, hero, objection handling)
- [ ] `.agents/product-marketing.md` en repo
- [ ] LICENSE Apache-2.0 + módulo Enterprise on-prem documentado
- [ ] Discord + GitHub Discussions abiertos
- [ ] Demo GIF de Risk Engine + comando remoto
- [ ] Landing MSP con CTA "Agenda demo"

---

## OKR Q1 (Growth)
- 2.000 stars · 200 forks · 5 adapters MDM · 10 demos MSP
- Canal primario: GitHub-first → Show HN, r/selfhosted, Jamf Nation, foros Intune, LinkedIn MSP.

---
*Monetización (skill `pricing`): Apache-2.0 core gratis; Enterprise on-prem (SSO/SAML, SOAR, Risk Engine premium) por licencia anual + retainer MSP. El OSS genera inbound; el servicio gestionado + inteligencia de amenazas recurrente es la captura.*
