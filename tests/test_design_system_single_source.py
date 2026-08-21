"""El sistema de diseño no se puede volver a fragmentar.

Contexto: hasta esta PR, cada superficie estática llevaba su propio bloque
`:root` y su propia familia tipográfica. El producto se servía con CUATRO
identidades a la vez -- verde valla en el dashboard, índigo en la landing y en
cloud/whitelabel, violeta en la PWA -- y tres familias distintas (Geist, Inter,
Roboto). No era una decisión: era deriva. Un cliente que entraba por la landing
y luego abría el Command Center veía dos productos.

Este guard convierte esa decisión en un invariante comprobable. Cubre:
  1. Una sola fuente de tokens: todas las superficies enlazan design.css y
     ninguna redeclara la paleta.
  2. Una sola familia, autoalojada: cero CDN de fuentes (la CSP es
     default-src 'self'; un @import externo ni siquiera cargaría).
  3. La rampa tipográfica tiene suelo (11px) y recorrido real.
  4. CONTRASTE AA CALCULADO, no estimado a ojo: cada color de texto contra
     cada superficie sobre la que se dibuja, en tema claro y oscuro.
  5. Los anti-patrones que esta PR eliminó no vuelven a entrar.

Ejecuta: python3 tests/run_tests.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
DESIGN = STATIC / "design.css"

# Las seis superficies HTML que sirve el producto.
SURFACES = ["dashboard.html", "index.html", "cloud.html",
            "manual.html", "web.html", "whitelabel.html"]

# Tokens de color que SOLO pueden declararse en design.css. Si una superficie
# redeclara cualquiera de estos, ha empezado a fabricarse su propia paleta.
PALETTE_TOKENS = ("--bg", "--panel", "--border", "--fg", "--muted",
                  "--accent", "--green", "--amber", "--red", "--blue")


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def _css() -> str:
    return DESIGN.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 1. Una sola fuente de tokens
# --------------------------------------------------------------------------
def test_every_surface_links_the_design_system():
    for name in SURFACES:
        html = _read(name)
        assert '/static/design.css' in html, (
            f"{name} no enlaza el sistema de diseño: se pintará con lo que "
            f"tenga a mano y volverá a divergir")


def test_no_surface_redeclares_the_palette():
    for name in SURFACES:
        html = _read(name)
        style = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
        for token in PALETTE_TOKENS:
            # `--bg:` declarado, no `var(--bg)` consumido.
            declared = re.search(rf"{re.escape(token)}\s*:", style)
            assert not declared, (
                f"{name} redeclara {token}: la paleta vuelve a vivir en dos "
                f"sitios y una de las dos copias envejecerá mal")


def test_design_system_is_the_only_place_that_defines_the_palette():
    css = _css()
    for token in PALETTE_TOKENS:
        assert re.search(rf"{re.escape(token)}\s*:", css), \
            f"design.css no define {token}"


# --------------------------------------------------------------------------
# 2. Una sola familia, autoalojada
# --------------------------------------------------------------------------
def test_typeface_is_self_hosted_and_never_a_cdn():
    css = _css()
    assert "@font-face" in css and "IBM Plex Sans" in css
    for url in re.findall(r"url\(['\"]?([^'\")]+)", css):
        assert url.startswith("/static/fonts/"), \
            f"la tipografía sale del origen propio: {url}"
        assert (ROOT / url.lstrip("/")).exists(), f"falta el binario {url}"
    # Y ninguna superficie se cuela por su cuenta a un CDN de fuentes.
    for name in SURFACES + ["design.css"]:
        text = _read(name)
        for host in ("fonts.googleapis.com", "fonts.gstatic.com",
                     "use.typekit", "cdn.jsdelivr"):
            assert host not in text, f"{name} pide fuentes a {host}"


def _strip_comments(text: str) -> str:
    """Los comentarios NOMBRAN las caras descartadas para explicar por qué lo
    están; solo interesan las declaraciones reales."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def test_the_overused_ai_faces_are_gone():
    """Inter, Geist, Roboto y compañía: las caras que convergen en cada ola de
    UI generada. El producto usa una cara de infraestructura."""
    for name in SURFACES + ["design.css"]:
        code = _strip_comments(_read(name)).lower()
        # Solo lo que declara una familia: font-family, el atajo `font:` y los
        # propios tokens --font/--mono.
        decls = re.findall(r"(?:font-family|--font[a-z-]*|--mono)\s*:\s*([^;{}]+)", code)
        decls += re.findall(r"\bfont\s*:\s*([^;{}]+)", code)
        for decl in decls:
            for face in ("inter", "geist", "roboto",
                         "plus jakarta", "space grotesk"):
                assert face not in decl, \
                    f"{name} vuelve a declarar {face}: {decl.strip()[:70]}"


def test_monospace_is_reserved_for_code_not_used_as_a_costume():
    """--mono existe para código, identificadores y hashes. Usarla como
    disfraz de 'técnico' en etiquetas de UI es un tic, no una decisión."""
    css = _css()
    assert "--mono:" in css
    # La familia por defecto de la interfaz NO es monoespaciada.
    font_decl = re.search(r"--font\s*:\s*([^;]+)", css).group(1)
    assert "mono" not in font_decl.lower()


# --------------------------------------------------------------------------
# 3. La rampa tipográfica
# --------------------------------------------------------------------------
def _ramp() -> dict:
    css = _css()
    return {m.group(1): float(m.group(2))
            for m in re.finditer(r"(--t-[a-z0-9]+)\s*:\s*(\d+(?:\.\d+)?)px", css)}


def test_type_ramp_has_a_floor_and_real_range():
    ramp = _ramp()
    assert ramp, "no hay rampa tipográfica"
    smallest = min(ramp.values())
    largest = max(ramp.values())
    assert smallest >= 11, (
        f"el escalón más pequeño es {smallest}px; por debajo de 11px el texto "
        f"funcional deja de leerse en pantallas densas")
    assert largest / smallest >= 2.0, (
        f"la rampa va de {smallest}px a {largest}px (x{largest/smallest:.1f}): "
        f"sin recorrido no hay jerarquía, solo tamaños parecidos")


def test_no_surface_hardcodes_text_below_the_floor():
    """Un px suelto por debajo del suelo salta la rampa entera."""
    for name in SURFACES:
        for raw in re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", _read(name)):
            assert float(raw) >= 11, \
                f"{name} fija texto a {raw}px, por debajo del suelo de 11px"


# --------------------------------------------------------------------------
# 4. Contraste AA CALCULADO (el punto de este fichero)
# --------------------------------------------------------------------------
def _srgb(channel: float) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _srgb(r) + 0.7152 * _srgb(g) + 0.0722 * _srgb(b)


def _ratio(fg: str, bg: str) -> float:
    a, b = _luminance(fg), _luminance(bg)
    if a < b:
        a, b = b, a
    return (a + 0.05) / (b + 0.05)


def _tokens(scope: str) -> dict:
    """Extrae los tokens hex de un bloque (`:root` o `html[data-theme=dark]`)."""
    css = _css()
    start = css.index(scope)
    block = css[start:css.index("\n}", start)]
    return {m.group(1): m.group(2)
            for m in re.finditer(r"(--[a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{3,6})\b", block)}


# Cada color de texto con las superficies sobre las que REALMENTE se dibuja.
TEXT_ON_SURFACES = {
    "--fg":      ("--bg", "--bg-2", "--panel", "--panel-2", "--panel-3"),
    "--fg-2":    ("--bg", "--bg-2", "--panel", "--panel-2", "--panel-3"),
    "--muted":   ("--bg", "--bg-2", "--panel", "--panel-2", "--panel-3"),
    "--muted-2": ("--bg", "--bg-2", "--panel", "--panel-2", "--panel-3"),
}
# Colores de estado sobre su propia superficie tenida.
STATE_PAIRS = (("--green", "--green-soft"), ("--blue", "--blue-soft"),
               ("--amber", "--amber-soft"), ("--red", "--red-soft"),
               ("--violet", "--violet-soft"))


def _assert_aa(scope_name: str, tokens: dict):
    for fg, surfaces in TEXT_ON_SURFACES.items():
        for bg in surfaces:
            if fg not in tokens or bg not in tokens:
                continue
            r = _ratio(tokens[fg], tokens[bg])
            assert r >= 4.5, (
                f"[{scope_name}] {fg} ({tokens[fg]}) sobre {bg} ({tokens[bg]}) "
                f"= {r:.2f}:1, por debajo de AA 4.5:1")
    # El texto sobre el acento usa el color de contraste declarado del acento,
    # no blanco fijo: en tema oscuro el verde es claro y el blanco se cae.
    if "--accent" in tokens and "--accent-fg" in tokens:
        r = _ratio(tokens["--accent-fg"], tokens["--accent"])
        assert r >= 4.5, (
            f"[{scope_name}] --accent-fg sobre --accent = {r:.2f}:1; el texto "
            f"de los botones primarios no llega a AA")


def test_light_theme_text_meets_aa_on_every_surface_it_lands_on():
    _assert_aa("claro", _tokens(":root{"))


def test_dark_theme_text_meets_aa_on_every_surface_it_lands_on():
    _assert_aa("oscuro", _tokens('html[data-theme="dark"]{'))


def test_state_colors_meet_aa_on_their_own_tinted_surface():
    """Las etiquetas de estado (dentro/fuera/aviso/incumple) se dibujan con el
    color de estado sobre su versión tenida; ahí también hay que leer."""
    tokens = _tokens(":root{")
    for fg, bg in STATE_PAIRS:
        if fg not in tokens or bg not in tokens:
            continue
        r = _ratio(tokens[fg], tokens[bg])
        assert r >= 4.5, \
            f"{fg} sobre {bg} = {r:.2f}:1: la etiqueta de estado no se lee"


def test_no_surface_hardcodes_white_text_on_the_accent():
    """`color:#fff` sobre var(--accent) funciona en claro y falla en oscuro,
    donde el acento es un verde claro. El token --accent-fg existe para eso."""
    for name in SURFACES:
        html = _read(name)
        for m in re.finditer(r"background:\s*var\(--accent\)\s*;\s*color:\s*(#fff\b|#ffffff\b|white\b)", html):
            raise AssertionError(
                f"{name}: texto blanco fijo sobre --accent ({m.group(0)}); "
                f"usa var(--accent-fg)")


# --------------------------------------------------------------------------
# 5. Los anti-patrones eliminados no vuelven
# --------------------------------------------------------------------------
def test_no_thick_coloured_side_stripe_on_cards_or_alerts():
    """La franja de color al costado es el tic más reconocible de una UI
    generada. La severidad se lee en un punto guía + la superficie tenida."""
    for name in SURFACES:
        for m in re.finditer(r"border-(?:left|right):\s*(\d+(?:\.\d+)?)px", _read(name)):
            assert float(m.group(1)) <= 2, \
                f"{name}: vuelve la franja lateral de {m.group(1)}px"


def test_no_kicker_label_above_a_heading():
    """Una micro-etiqueta en versal espaciada encima de un encabezado nunca se
    gana el sitio: el encabezado ya dice lo que ella repite."""
    for name in SURFACES + ["app.js"]:
        text = _read(name)
        assert 'class="eyebrow"' not in text, f"{name}: vuelve el kicker"
        assert 'class="company-eyebrow"' not in text, f"{name}: vuelve el kicker"


def test_no_zero_offset_coloured_halo_as_decoration():
    """Una sombra sin desplazamiento es un halo, no profundidad. Se permite el
    aro fino alrededor de un punto de estado (<=3px), que es un contorno."""
    for name in SURFACES:
        for m in re.finditer(r"box-shadow:\s*0\s+0\s+0\s+(\d+)px", _read(name)):
            assert int(m.group(1)) <= 3, \
                f"{name}: halo decorativo de {m.group(1)}px sin desplazamiento"


def test_elevation_is_declared_once_border_or_shadow():
    """Un borde fino bajo una sombra ancha es el 'ghost card'. Las sombras del
    sistema llevan desplazamiento y desenfoque; las tarjetas en reposo, borde."""
    css = _css()
    for name in ("--sh-pop", "--sh-modal"):
        decl = re.search(rf"{name}\s*:\s*([^;]+)", css)
        assert decl, f"falta {name}"
        # Primer valor de la primera capa = desplazamiento X, segundo = Y.
        first = decl.group(1).split(",")[0].split()
        offsets = [p for p in first if p.endswith("px")]
        assert len(offsets) >= 3, f"{name} no declara desplazamiento + desenfoque"
        assert any(float(o[:-2]) != 0 for o in offsets[:2]), \
            f"{name} es un halo a offset cero, no una elevación"


def test_browser_surfaces_are_themed():
    """Selección, cursor, barra de scroll y anillo de foco vienen por defecto
    de un sistema de diseño que no es el nuestro. Se tiñen de la paleta."""
    css = _css()
    for surface in ("::selection", "caret-color", "::-webkit-scrollbar-thumb",
                    ":focus-visible", "::placeholder"):
        assert surface in css, f"design.css no viste {surface}"


# --------------------------------------------------------------------------
# Desviaciones conocidas del detector Impeccable, con su razón.
# --------------------------------------------------------------------------
def test_known_detector_deviations_are_documented():
    """El detector deja 5 hallazgos vivos. Ninguno es deuda silenciosa: cada
    uno está escrito aquí con el porqué, y este test falla si alguien borra la
    explicación sin borrar la causa.

      - flat-type-hierarchy en dashboard/manual: el detector mide el HTML
        estático, y en una SPA el título de vista (24px) y la cifra de KPI
        (30px) los pinta el JS. La rampa REAL va de 11px a 30px (x2.7), lo
        que este mismo fichero comprueba en test_type_ramp_has_a_floor.
      - flat-type-hierarchy en index: el h1 y los h2 usan clamp(), que el
        detector no resuelve. El h1 real llega a 54px.
      - pulsing-dot en dashboard: es el indicador de escritura del chat, atado
        a una petición realmente en curso; aparece y desaparece con ella. La
        regla exceptúa justo ese caso, pero no puede ver el ciclo de vida.
      - codex-grid-background en web: la retícula está bajo el MAPA. La propia
        regla la permite sobre lienzos, mapas y planos.
    """
    doc = test_known_detector_deviations_are_documented.__doc__
    for reason in ("flat-type-hierarchy", "pulsing-dot", "codex-grid-background"):
        assert reason in doc
    # La causa del segundo punto sigue siendo real: el h1 de la landing es fluido.
    assert "clamp(" in _read("index.html")
    # Y la retícula sigue siendo la del mapa, no un fondo decorativo suelto.
    web = _read("web.html")
    grid_at = web.index("background-image:linear-gradient")
    assert ".map{" in web[max(0, grid_at - 400):grid_at]
