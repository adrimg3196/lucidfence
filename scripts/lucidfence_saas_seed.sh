#!/usr/bin/env bash
# Seed del "modo empresa SaaS" de LucidFence: tareas de negocio además de dev.
set -u
export HERMES_KANBAN_BOARD=lucidfence
cd /Users/adri/geofence-uem

create() {
  local title="$1" assignee="$2" body="$3"
  HERMES_KANBAN_BOARD=lucidfence hermes kanban create "$title" --assignee "$assignee" --body "$body" 2>/dev/null \
    | grep -oE 't_[a-f0-9]+' | head -1
}

echo "Pricing:";       create "GTM: define pricing SaaS (Freemium $0 / Pro gestionado / Enterprise on-prem)" "default" "Modelo: Freemium self-hosted $0 (el producto actual). Pro = hosting gestionado por nosotros en la nube del cliente (suscripcion mensual). Enterprise = on-prem + soporte prioritario + SSO. Definir precios y mostrar en landing."
echo "Commercial:";    create "Commercial: landing con pricing tiers + 3 testimonios + CTA de registro" "integrations-specialist" "Completa la landing comercial: 3 tiers visibles (Freemium/Pro/Enterprise), 3 testimonios de clientes ficticios pero realistas, y CTA que lleve al self-service. Desbloquea la conversion."
echo "Growth:";       create "Growth: self-service captura email del lead y crea oportunidad CRM en board" "integrations-specialist" "El formulario de signup debe pedir email de contacto; al crear el issue, el ingest lo vuelca a una tarjeta de tipo 'Opportunidad' en el board asignada a Commercial."
echo "Marketing:";    create "Marketing: campaña comparativa LucidFence vs Jamf/Intune/Applivery" "competitive-intel-specialist" "Crea 1 pieza (LinkedIn post / one-pager) que posicione local-first y $0 vs SaaS tradicional caro. Enfocate en soberania de datos y coste."
echo "CS:";           create "CS: playbook de bienvenida automatica para nuevos tenants" "vault-curator" "Al registrarse un tenant, crear tarjeta de onboarding con checklist: arrancar, añadir geocercas, leer incidencias, contacto de soporte."
echo "Soporte:";      create "Soporte: SLA — crear ticket por cada incidencia de la vitrina" "android-enterprise-specialist" "El monitor de incidencias debe crear tarjetas de soporte (no solo fix tecnico) asignadas a CS cuando un tenant reporta fallo."
echo "Revenue:";      create "Revenue: modelo de ingresos Pro gestionado (hosting) + Enterprise on-prem" "default" "Documenta el flujo de cobro: Pro = suscripcion recurrente por dispositivo/gestionado; Enterprise = contrato on-prem + SLA. El self-hosted $0 es el iman (freemium)."
echo "Producto-Vitrina:"; create "Producto: vitrina con tier de cada tenant (Freemium/Pro) visible" "oem-frontline-specialist" "Muestra en cloud.html el plan de cada tenant (Freemium/Pro/Enterprise) y limites usados (dispositivos, geocercas)."
echo "Producto-Security:"; create "Producto: cerrar M1/M2 para ofrecer Pro gestionado seguro" "vault-curator" "Para vender Pro gestionado en la nube, aplicar TLS + verificacion de deps + rate-limit (audit 2026-07-14). Requerido para revenue."
echo "DONE saas-seed"
