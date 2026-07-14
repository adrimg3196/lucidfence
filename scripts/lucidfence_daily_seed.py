#!/usr/bin/env python3
"""lucidfence_daily_seed.py — siembra tareas de mejora diaria en el board.

Se ejecuta como cron 1x/día. Genera 1-2 tarjetas nuevas de mejora (features,
hardening, docs) asignadas al especialista adecuado, rotando por un pool.
Usa idempotency-key con la fecha para no duplicar si el cron corre 2x.
"""
import datetime
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD = "lucidfence"
os.environ["HERMES_KANBAN_BOARD"] = BOARD

# Pool de ideas de mejora (titulo, assignee, body) rotando por día.
POOL = [
    ("Feature: exportar reporte de compliance a PDF", "integrations-specialist",
     "Añade botón en dashboard/vitrina para descargar el reporte de conformidad en PDF."),
    ("Hardening: rate-limit en endpoints del saas_server", "vault-curator",
     "Aplica rate-limit por IP/sesión en saas_server.py para el despliegue always-on."),
    ("Doc: video de 60s de la vitrina para comercial", "competitive-intel-specialist",
     "Crea guion + asset de un video corto mostrando la vitrina multi-tenant en vivo."),
    ("Feature: alertas por email en incidencias de geocerca", "applivery-api-specialist",
     "Integra Atomic Mail para notificar salidas de geocerca en tiempo real."),
    ("QA: tests E2E de self-service con Playwright", "android-enterprise-specialist",
     "Crea test que simule el flujo issue->tenant->vitrina en un navegador headless."),
    ("Feature: dashboard de tendencia de compliance por semana", "oem-frontline-specialist",
     "Añade gráfica de evolución de conformidad en la vitrina."),
    ("Hardening: firma de webhooks SOAR entrantes", "windows-mdm-specialist",
     "Valida HMAC de los webhooks SOAR para evitar spoofing."),
    ("Doc: README de arquitectura serverless para clientes", "vault-curator",
     "Explica en CLIENTE.md la arquitectura GitHub-only ($0) para que el cliente entienda."),
    ("Feature: soporte de geocercas poligonales (no solo círculos)", "apple-mdm-specialist",
     "Extiende el engine para geocercas de polígono y la vitrina SVG."),
    ("Competitive: one-pager 'por qué local-first' para clientes", "competitive-intel-specialist",
     "Documento comercial sobre soberanía de datos y $0 vs SaaS tradicional."),
]


def kanban_create(title, assignee, body, key):
    try:
        subprocess.run(
            ["hermes", "kanban", "create", title, "--assignee", assignee,
             "--body", body, "--idempotency-key", key],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
        )
        print(f"[seed] creada: {title}")
    except Exception as e:
        print(f"[seed] error creando {title}: {e}")


def main():
    today = datetime.date.today()
    # 2 tareas diarias rotando por el día del año.
    n = today.timetuple().tm_yday
    picks = [POOL[n % len(POOL)], POOL[(n + 3) % len(POOL)]]
    for i, (title, assignee, body) in enumerate(picks):
        key = f"daily-{today.isoformat()}-{i}"
        kanban_create(title, assignee, body, key)
    print(f"[seed] {len(picks)} tareas diarias sembradas ({today.isoformat()})")


if __name__ == "__main__":
    main()
