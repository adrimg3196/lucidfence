"""Guardarrail issue #110: integridad pública de la vitrina.

Detecta la reintroducción de testimonios atribuidos, métricas de tracción sin
fuente y prueba social en el contenido estático servido, y verifica que la
banda de datos demo y el CTA de descarga en primer viewport siguen presentes.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "static")

# Cadenas prohibidas del criterio de aceptación del issue #110. Cualquier
# aparición en contenido servido es una regresión: la opción por defecto es
# retirar el claim, no re-redactarlo.
BANNED = [
    "Marina Gómez",
    "Álvaro Rivas",
    "Lucía Castro",
    "10 descargas",
    "166 clones",
    "4 descargas",
    "5 clones",
    "100% gratis",
    "★★★★★",           # testimonios con estrellas
    "tractionCopy",     # IDs/JS de métricas retiradas: ocultarlas no basta
    "releaseDownloads",
    "repoClones",
    "traction_badge",
]

# Palabras de tracción: no deben aparecer como sustantivo de métrica en el
# contenido servido ("descargas del release", "clones únicos"). "Descargar"/
# "Descarga" como CTA sí está permitido.
BANNED_TRACTION_WORDS = ["clones", "descargas"]


def _served_files() -> list[str]:
    out = []
    for base, _dirs, files in os.walk(STATIC):
        for name in files:
            if name.endswith((".html", ".js", ".json")):
                out.append(os.path.join(base, name))
    return out


def test_no_fabricated_social_proof_or_traction_metrics() -> None:
    offenders: list[str] = []
    for path in _served_files():
        content = open(path, encoding="utf-8", errors="replace").read()
        rel = os.path.relpath(path, ROOT)
        for banned in BANNED:
            if banned in content:
                offenders.append(f"{rel}: contiene {banned!r}")
        lowered = content.lower()
        for word in BANNED_TRACTION_WORDS:
            if word in lowered:
                offenders.append(f"{rel}: contiene la palabra de tracción {word!r}")
    assert not offenders, (
        "Regresión del issue #110 — prueba social/tracción sin fuente en contenido servido:\n"
        + "\n".join(offenders)
    )


def test_dashboard_demo_banner_present() -> None:
    html = open(os.path.join(STATIC, "dashboard.html"), encoding="utf-8").read()
    assert 'id="demoBanner"' in html and 'role="status"' in html
    assert "Estás viendo datos de ejemplo; no pertenecen a tu organización." in html
    assert 'href="#connectors"' in html and "Conecta tu UEM" in html
    # No descartable: la banda no lleva botón de cierre.
    banner = html.split('id="demoBanner"', 1)[1].split("</div>", 1)[0]
    assert "<button" not in banner
    js = open(os.path.join(STATIC, "app.js"), encoding="utf-8").read()
    assert "demoBanner" in js and '"simulation"' in js


def test_cloud_download_cta_precedes_tenant_selector_and_pdf() -> None:
    html = open(os.path.join(STATIC, "cloud.html"), encoding="utf-8").read()
    cta = html.index("Descargar LucidFence")
    assert cta < html.index('id="tenantSel"'), "el CTA de descarga debe preceder al selector de tenant"
    assert cta < html.index("Descargar reporte PDF"), "el CTA de descarga debe preceder al PDF"
    assert "Gratis y on-premise." in html
