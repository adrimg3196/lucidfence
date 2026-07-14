#!/usr/bin/env bash
# Seed de GROWTH (modo empresa free-first): tareas de adquisición, activación y
# retención en vez de ventas. El norte es la tracción, no el revenue.
set -u
export HERMES_KANBAN_BOARD=lucidfence
cd /Users/adri/geofence-uem

create() {
  local title="$1" assignee="$2" body="$3"
  HERMES_KANBAN_BOARD=lucidfence hermes kanban create "$title" --assignee "$assignee" --body "$body" 2>/dev/null \
    | grep -oE 't_[a-f0-9]+' | head -1
}

echo "Acquisicion:";   create "Growth: canal de adquisición para equipos UEM/MDM (donde hay dolor de coste)" "integrations-specialist" "Identifica 2-3 canales donde equipos UEM/MDM sientan el coste de SaaS tradicional (Reddit r/Intune, comunidades MDM, LinkedIn). Un post por semana mostrando el self-service gratis."
echo "Activacion:";    create "Growth: reducir fricción del signup (menos campos, mejor UX)" "integrations-specialist" "El self-service debe ser 1-click. Menos campos, validación clara, feedback inmediato de que el tenant está vivo en <=15 min."
echo "Retencion:";     create "Growth: email de bienvenida + tips de activación a nuevos tenants" "vault-curator" "Al registrarse un tenant, enviar (vía Atomic Mail) un email de bienvenida con 3 pasos para activar valor: arrancar, geocercas, leer incidencias."
echo "SocialProof:";   create "Growth: badge de tracción en landing ('X empresas usan LucidFence gratis')" "competitive-intel-specialist" "La landing debe mostrar tracción real del board (nº tenants vivos). Social proof de que es gratis Y usado."
echo "ProductoFit:";   create "Producto: vitrina muestra plan de cada tenant (Freemium) y uso" "oem-frontline-specialist" "En cloud.html, cada tenant muestra 'Freemium · N dev · M geocercas' para reforzar el modelo gratis y la activación visible."
echo "DONE growth-seed"
