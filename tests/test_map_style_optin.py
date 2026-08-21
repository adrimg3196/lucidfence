"""El mapa detallado (teselas OSM) es OPT-IN; el defecto es el vector local.

Guard de la Constitución art. I: el dashboard jamás pide teselas a un tercero
sin decisión explícita del admin. Tests de contrato sobre las superficies
estáticas (sin navegador): el JS solo activa OSM vía localStorage tras un
confirm con el aviso de privacidad, y la CSP solo abre img-src al host de
teselas (nunca script/connect).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_JS = open(os.path.join(ROOT, "static", "app.js"), encoding="utf-8").read()
SERVER = open(os.path.join(ROOT, "saas_server.py"), encoding="utf-8").read()


def test_default_basemap_is_local_and_osm_requires_optin():
    # El único camino a las teselas pasa por el flag de localStorage...
    assert 'localStorage.getItem("lf_map_style")==="osm"' in APP_JS
    # ...y por un confirm() con el aviso de privacidad antes de activarlo:
    # el mensaje termina en la pregunta y se pasa entero a confirm(msg).
    idx_confirm = APP_JS.index("¿Activar el mapa detallado?")
    assert "if(!confirm(msg)) return;" in APP_JS[idx_confirm:idx_confirm + 400]
    assert "revela a ese servicio la zona" in APP_JS
    # El fallback/defecto sigue siendo el SVG vendorizado sin red.
    assert "/static/vendor/offline-map.svg" in APP_JS
    # Nadie añade el tileLayer incondicionalmente: solo dentro de basemapLayer().
    assert APP_JS.count("tile.openstreetmap.org") == 1


def test_csp_only_opens_img_src_to_tile_host():
    for m in re.finditer(r"img-src [^;]+", SERVER):
        assert "https://tile.openstreetmap.org" in m.group(0)
    # El host de teselas jamás aparece en script-src ni connect-src.
    for directive in re.findall(r"(?:script|connect)-src [^;\"]+", SERVER):
        assert "openstreetmap" not in directive
