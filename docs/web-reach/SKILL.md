---
name: web-reach
description: Busqueda web/YouTube sin API usando agent-reach.
category: integrations
---

# Web Reach — búsqueda sin API ni login

Fuente oficial de búsqueda del agente en este host:
**https://github.com/Panniantong/agent-reach** (instalado en `~/.agent-reach-venv`).

## Cuándo usar
Siempre que necesites buscar/leer en internet: YouTube, cualquier web, GitHub,
RSS, V2EX, B站. NO uses `curl` crudo (HTML sucio) ni yt-dlp suelto.

## Canales activos (sin login)
- **YouTube**: subtítulos + búsqueda → `~/.agent-reach-venv/bin/python -m yt_dlp "ytsearchN:<q>"`
- **Web**: markdown limpio → `curl -s https://r.jina.ai/<url>`
- **GitHub**: `gh` (ya con auth)
- **RSS / V2EX / B站**: vía agent-reach

## Canales que requieren cookies del usuario (pendientes)
Twitter/X y Reddit: `agent-reach install --channels=twitter,reddit` (necesita
sesión del usuario). No se usan solos.

## Scripts del repo que ya lo usan
- `scripts/recon_web.py` — recon de competidores (cron `recon-web-agent-reach`, 9AM).
- `scripts/recon_repos.py` / `recon_agent_repos.py` — recon de repos GitHub.

## Ejemplo (verification-before-completion)
```bash
~/.agent-reach-venv/bin/python -m yt_dlp --no-warnings --print "%(id)s | %(title)s" "ytsearch2:Applivery UEM"
curl -s --max-time 15 "https://r.jina.ai/https://github.com/Panniantong/agent-reach" | head -5
```
