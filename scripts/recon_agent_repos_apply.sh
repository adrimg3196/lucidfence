#!/usr/bin/env bash
# Cron wrapper: recon de agent-repos CON aplicacion automatica (impacto real).
# Anade repos nuevos a la skill agent-upgrade y pushea a main.
cd /Users/adri/.hermes/scripts && python3 recon_agent_repos.py --apply
