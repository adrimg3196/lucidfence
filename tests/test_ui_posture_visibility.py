"""La UI cumple lo que el manual promete: postura DDM visible en la ficha de
dispositivo y puntos ciegos (GET /api/coverage) visibles en el Resumen.

Dos capas, sin navegador:
  - contrato estático sobre static/app.js — la ficha renderiza los campos de
    postura reales del payload y el render de null es NEUTRO (nunca alarma);
  - propagación funcional real: semilla demo → SimulationLocationSource →
    LocationReport con la postura sembrada (no un grep del JSON de la seed).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lucidfence.core.location_source import SimulationLocationSource  # noqa: E402
from lucidfence.core.policies import _hardware_degraded_components  # noqa: E402


def _js() -> str:
    return (ROOT / "static" / "app.js").read_text(encoding="utf-8")


def test_device_modal_renders_posture_fields():
    js = _js()
    # Las tres señales DDM + cifrado, con sus etiquetas visibles.
    for label in ("Lockdown Mode", "Supervisión", "Salud de hardware", "Cifrado"):
        assert label in js, f"la ficha no renderiza {label!r}"
    # Y leen los campos REALES de DeviceState.to_dict() (no nombres inventados).
    for field in ("d.lockdown_mode", "d.supervised", "d.hardware_health",
                  "d.encryption_enabled"):
        assert field in js, f"la ficha no lee el campo real {field}"
    assert "function postureBadge" in js
    assert "function hardwareHealthBadge" in js


def test_null_posture_renders_neutral_never_alarm():
    js = _js()
    # null/ausente → texto neutro, y SIEMPRE con clase .sub (muted): lo
    # desconocido nunca penaliza, tampoco visualmente.
    hits = re.findall(r'<span class="([^"]+)">— \(el UEM no lo reporta\)</span>', js)
    assert hits, "falta el render neutro para postura no reportada"
    assert all(cls == "sub" for cls in hits), \
        f"el render de null usa estilo de alarma: {hits}"


def test_hardware_health_render_matches_policies_semantics():
    js = _js()
    # Misma semántica que policies._HW_DEGRADED_WORDS: False o degraded/failed/
    # error = degradado; lo desconocido no cuenta.
    for word in ("degraded", "failed", "error"):
        assert f'"{word}"' in js
    assert "v===false" in js.replace(" ", "")
    assert "Todos los componentes OK" in js


def test_overview_has_coverage_card_wired():
    js = _js()
    assert '"/api/coverage"' in js, "la tarjeta no consume GET /api/coverage"
    assert "function renderCoverageCard" in js
    assert "Puntos ciegos" in js
    # Los 3 contadores del informe + el estado vacío positivo.
    for text in ("sin señal", "sin reportar", "cercas vacías",
                 "Cobertura completa: sin puntos ciegos", "coverage_percent"):
        assert text in js, f"tarjeta de puntos ciegos sin {text!r}"
    # Si /api/coverage falla (rol sin device:read), la tarjeta queda oculta en
    # silencio: el catch devuelve sin tocar el DOM del Resumen.
    body = js.split("async function renderCoverageCard")[1][:400]
    assert re.search(r'catch\(e\)\{\s*return;?\s*\}', body)
    # El estilo warn que usan los contadores existe de verdad en el CSS.
    html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")
    assert ".tag.warn{" in html.replace(" ", "")


def test_demo_seed_posture_propagates_via_simulation_source():
    """Funcional real: la semilla demo produce LocationReports CON la postura
    sembrada — el mismo camino que alimenta /api/status en el tenant demo."""
    src = SimulationLocationSource(sim_seed_path=str(ROOT / "data" / "fleet_seed.json"))
    reports = {r.device_id: r for r in src.fetch()}
    assert reports, "la semilla demo no produce dispositivos"

    # Una de cada señal, con la misma semántica que usará el motor de riesgo.
    assert any(r.supervised is False for r in reports.values()), \
        "ningún dispositivo demo enseña supervised=false"
    assert any(r.lockdown_mode is True for r in reports.values()), \
        "ningún dispositivo demo enseña lockdown_mode=true"
    degraded = [r for r in reports.values()
                if _hardware_degraded_components(r.hardware_health)]
    assert degraded, "ningún dispositivo demo enseña hardware degradado"
    # El dict llega verbatim (componente degradado + componente sano intacto).
    hh = degraded[0].hardware_health
    assert _hardware_degraded_components(hh) == ["camera"]
    assert hh.get("baseband") is True

    # Honestidad: el resto de la flota sigue en None (desconocido), jamás
    # defaulted — sembrar postura en 3 dispositivos no la inventa en los demás.
    assert any(r.supervised is None for r in reports.values())
    assert any(r.lockdown_mode is None for r in reports.values())
    assert any(r.hardware_health is None for r in reports.values())
