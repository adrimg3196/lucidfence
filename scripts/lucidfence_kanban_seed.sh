#!/usr/bin/env bash
# Seed del backlog de la "empresa autónoma LucidFence" en el board kanban.
# Fija el board con HERMES_KANBAN_BOARD para que cada `hermes kanban create`
# (proceso independiente) cree en lucidfence, no en el board por defecto.
set -u
export HERMES_KANBAN_BOARD=lucidfence
cd /Users/adri/geofence-uem

create() {
  # $1 title, $2 assignee, $3 body
  local title="$1" assignee="$2" body="$3"
  HERMES_KANBAN_BOARD=lucidfence hermes kanban create "$title" --assignee "$assignee" --body "$body" 2>/dev/null \
    | grep -oE 't_[a-f0-9]+' | head -1
}

echo "PM:";            create "PM: define roadmap Q3 y prioriza backlog LucidFence" "default" "Prioriza el backlog del board: vitrina, installer, self-service, seguridad, CVE. Decide orden y crea subtareas si hace falta."
echo "Landing:";      create "Landing: testimonios + pricing tiers + FAQ instalación" "integrations-specialist" "Mejora static/index.html para conversión: 2-3 testimonios, tiers de precio claros, FAQ de instalación local."
echo "Vitrina:";      create "Vitrina cloud: mapa de calor por departamento + filtro tenant" "oem-frontline-specialist" "En static/cloud.html añade densidad de dispositivos por departamento y filtro en el selector de tenant."
echo "Installer:";    create "Installer cliente: soporte systemd para auto-arranque always-on" "windows-mdm-specialist" "Añade unit systemd a install.sh/docker-compose para arranque tras reboot en el servidor del cliente."
echo "Self-service:"; create "Self-service: validar flujo end-to-end issue→tenant→vitrina con tenant real" "integrations-specialist" "Verifica saas-signup.yml: crear issue con flota real, confirmar que el tenant aparece en cloud.html en <=15min. Documenta el SLA."
echo "Security:";     create "Security: cerrar gaps M1/M2 (TLS + verify deps) antes de Fly deploy" "vault-curator" "Aplica gates de security-audit-2026-07-14.md: TLS en docker-compose, verificación de deps en install.sh, rate-limit. Solo para despliegue internet-facing."
echo "CVE:";          create "CVE feed: integrar feed real NVD en vitrina demo" "applivery-api-specialist" "Sustituye cve_summary demo por datos reales de cve_feed_nvd.py cuando el engine tenga red; mantén fallback demo."
echo "Doc cliente:";  create "Doc cliente: guía de operación en Obsidian (runbook)" "vault-curator" "Genera runbook de operación del cliente en el vault: arrancar, añadir geocercas, leer incidencias."
echo "Monitor:";      create "Monitor: health-check que crea tareas si tests<110 o vitrina caída" "android-enterprise-specialist" "Crea script lucidfence_monitor.py que chequea suite de tests y HTTP de vitrina; si falla, crea tarjeta de fix en el board automáticamente."
echo "Apple MDM:";    create "Apple MDM: adaptar adapter para geocercas en dispositivos iOS" "apple-mdm-specialist" "Extiende core/adapters para que la vitrina muestre cumplimiento de geocercas en flotas iOS (simulado)."
echo "ChromeOS:";     create "ChromeOS MDM: soporte de plataforma en vitrina multi-tenant" "chromeos-mdm-specialist" "Añade ChromeOS como platform en el seed y la vitrina."
echo "Windows:";      create "Windows MDM: política de conformidad para geocercas en Windows" "windows-mdm-specialist" "Define política de risk para dispositivos Windows en el engine."
echo "Competitive:";  create "Competitive intel: benchmark LucidFence vs Jamf/Intune/Applivery" "competitive-intel-specialist" "Documenta diferenciadores de LucidFence (local-first, $0) vs competidores para ventas."
echo "DONE seeding"
