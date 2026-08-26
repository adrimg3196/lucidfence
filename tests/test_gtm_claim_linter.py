"""Regression tests for scripts/gtm_claim_linter.py (messaging gate, riesgo #110).

Covers:
  - t_bdc60b29: POS-LAYER-CLOSED / POS-BUYS-UEM honour the same negative-context
    exemption as the other positioning rules (red line #110).
  - t_565b1493: --scope outbox MUST include the canonical co-sign files
    (docs/gtm/CTO_CHANNEL.md and .cto_input_188.md), so technical co-signatures
    over them cannot evade the lint. --no-canonical opts out.

Run:  python3.11 tests/run_tests.py   (discovered automatically)
"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINTER = ROOT / "scripts" / "gtm_claim_linter.py"


def _load():
    spec = importlib.util.spec_from_file_location("gtm_claim_linter", LINTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_linter = _load()


def _scan_pos(text: str) -> list[dict]:
    rules = _linter.compile_rules(_linter.POSITIONING_RULES)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return _linter.scan_file(Path(path), rules, "POSITIONING")
    finally:
        Path(path).unlink(missing_ok=True)


def _scan_tec(text: str) -> list[dict]:
    rules = _linter.compile_rules(_linter.TECHNICAL_RULES)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return _linter.scan_file(Path(path), rules, "TECHNICAL")
    finally:
        Path(path).unlink(missing_ok=True)


def test_all_positioning_rules_are_negation_exempt():
    """Guard: la asimetría t_bdc60b29 nunca puede volver. Todas las reglas de
    posicionamiento deben ser negation_exempt=True de forma explícita."""
    for rid, _desc, _pat, exempt in _linter.POSITIONING_RULES:
        assert exempt is True, f"{rid} debe ser negation_exempt=True"


def test_negated_layer_closed_gives_info_not_block():
    """Aceptancia #2: 'NUNCA \"capa cerrada\"' -> 0 BLOCK."""
    findings = _scan_pos('# SOP\n- NUNCA menciones "capa cerrada" como parte del producto.\n')
    blocks = [x for x in findings if x["severity"] == "BLOCK"]
    assert not blocks, f"capa cerrada bajo negación no debe bloquear: {blocks}"
    assert any(x["rule"] == "POS-LAYER-CLOSED" for x in findings), "debe detectarse como INFO"


def test_negated_buys_uem_gives_info_not_block():
    """Aceptancia #2: 'NUNCA ... nos compra un UEM' -> 0 BLOCK."""
    findings = _scan_pos('# SOP\n- NUNCA digas que "nos compra un UEM" gestionado.\n')
    blocks = [x for x in findings if x["severity"] == "BLOCK"]
    assert not blocks, f"nos compra un UEM bajo negación no debe bloquear: {blocks}"
    assert any(x["rule"] == "POS-BUYS-UEM" for x in findings), "debe detectarse como INFO"


def test_negated_other_forms_still_exempt():
    """Equivalentes de negación seguros (sin / prohibido) también eximen.
    Nota: 'ni ...' NO se incluye a propósito — 'ni bien'/'ni siquiera' son
    conectores, no negación; añadir 'ni ' debilitaría la red line #110."""
    for line in [
        "El producto es 100% free, sin capa cerrada enterprise.",
        "Prohibido: nos compra un uem gestionado.",
        "El modelo no incluye capa cerrada ni nos compra un uem (negación 'no ').",
    ]:
        findings = _scan_pos(f"# SOP\n{line}\n")
        blocks = [x for x in findings if x["severity"] == "BLOCK"]
        assert not blocks, f"línea negada bloqueó: {line} -> {blocks}"


def test_affirmative_layer_closed_blocks():
    """El downgrade solo aplica bajo negación: copy vivo 'capa cerrada' BLOQUEA."""
    findings = _scan_pos("# Copy\nEl producto incluye una capa cerrada para enterprise.\n")
    blocks = [x for x in findings if x["rule"] == "POS-LAYER-CLOSED" and x["severity"] == "BLOCK"]
    assert blocks, "capa cerrada afirmativa debe bloquear"


def test_affirmative_buys_uem_blocks():
    findings = _scan_pos("# Copy\nEl cliente nos compra un UEM gestionado.\n")
    blocks = [x for x in findings if x["rule"] == "POS-BUYS-UEM" and x["severity"] == "BLOCK"]
    assert blocks, "nos compra un uem afirmativo debe bloquear"


def test_redline_ssrf_affirmative_blocks():
    """Aceptancia #3 (control #110): claim afirmativo 'egress RFC1918 bloqueado
    por defecto' del webhook SOAR BLOQUEA bajo --technical."""
    findings = _scan_tec(
        "# Copy\nEl webhook SOAR es SSRF-hardened: egress RFC1918 bloqueado por defecto.\n"
    )
    blocks = [x for x in findings if x["rule"] == "TEC-WEBHOOK-SSRF" and x["severity"] == "BLOCK"]
    assert blocks, "claim afirmativo de egress RFC1918 debe bloquear (red line #110)"


def test_redline_ssrf_negated_exempt():
    """El mismo claim dentro de negación/no-reclamo NO bloquea (es el wording honesto)."""
    findings = _scan_tec(
        '# SOP\n- El webhook SOAR NO se vende como "egress RFC1918 bloqueado por defecto".\n'
    )
    blocks = [x for x in findings if x["severity"] == "BLOCK"]
    assert not blocks, f"claim de webhook bajo negación no debe bloquear: {blocks}"


# ---------------------------------------------------------------------------
# t_565b1493 — --scope outbox debe incluir los archivos canónicos de co-firma.
# ---------------------------------------------------------------------------

def test_canonical_files_are_declared():
    """La fuente de verdad de la co-firma debe estar declarada en CANONICAL_COSIGN_FILES."""
    names = {p.name for p in _linter.CANONICAL_COSIGN_FILES}
    assert "CTO_CHANNEL.md" in names, "falta docs/gtm/CTO_CHANNEL.md"
    assert ".cto_input_188.md" in names, "falta .cto_input_188.md"


def test_scope_outbox_includes_canonical(tmp_path):
    """--scope outbox incluye los archivos canónicos aunque vivan fuera de outbox/.

    HERMÉTICO: sobreescribe CANONICAL_COSIGN_FILES con archivos sintéticos en
    tmp_path (no depende de la rama marketing-outbox, que es float y no está en
    origin/main). El canónico lleva un claim afirmativo de red line #110 que SÓLO
    vive ahí: si --scope outbox lo omitiera, el lint pasaría (falso verde) y la
    co-firma técnica evadiría el gate. El test afirma que el claim BLOQUEA.
    """
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "draft.md").write_text(
        "# Copy\nLucidFence protege tu flota.\n", encoding="utf-8"
    )
    canonical = tmp_path / "CTO_CHANNEL.md"
    # Claim afirmativo de red line #110 que SÓLO vive en el archivo canónico.
    canonical.write_text(
        "# Canal CTO\nEl webhook SOAR es SSRF-hardened: egress RFC1918 bloqueado por defecto.\n",
        encoding="utf-8",
    )
    cto_input = tmp_path / ".cto_input_188.md"
    cto_input.write_text(
        "# Input 188\nIntune live incondicional sin token del cliente.\n", encoding="utf-8"
    )

    # Sobrescribe la fuente de verdad del scope para apuntar a los sintéticos.
    saved = _linter.CANONICAL_COSIGN_FILES
    _linter.CANONICAL_COSIGN_FILES = [canonical, cto_input]
    try:
        targets = _linter.resolve_targets(
            [str(outbox)],
            list(_linter.DEFAULT_SKIP_GLOBS),
            include_canonical=True,
        )
        found = {t.name for t in targets}
        assert "CTO_CHANNEL.md" in found, "--scope outbox omitió el canónico CTO_CHANNEL.md"
        assert ".cto_input_188.md" in found, "--scope outbox omitió el canónico .cto_input_188.md"
        assert "draft.md" in found, "--scope outbox debe seguir escaneando el outbox"

        # El claim afirmativo en el canónico debe BLOQUEAR bajo --technical.
        all_findings = []
        tech_rules = _linter.compile_rules(_linter.TECHNICAL_RULES)
        for t in targets:
            all_findings.extend(_linter.scan_file(t, tech_rules, "TECHNICAL"))
        blocks = [x for x in all_findings if x["severity"] == "BLOCK"]
        assert blocks, "el claim afirmativo en el canónico debió bloquear vía --scope outbox"
        assert any(str(canonical) == x["file"] for x in blocks), \
            "el BLOCK debe provenir del archivo canónico recién incluido"
    finally:
        _linter.CANONICAL_COSIGN_FILES = saved


def test_no_canonical_excludes_canonical(tmp_path):
    """--no-canonical excluye los archivos canónicos del target set."""
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "draft.md").write_text("# Copy\nLucidFence protege tu flota.\n", encoding="utf-8")
    canonical = tmp_path / "CTO_CHANNEL.md"
    canonical.write_text("# Canal CTO\nEl webhook SOAR es seguro.\n", encoding="utf-8")
    cto_input = tmp_path / ".cto_input_188.md"
    cto_input.write_text("# Input 188\nIntune live.\n", encoding="utf-8")

    targets = _linter.resolve_targets(
        [str(outbox)],
        list(_linter.DEFAULT_SKIP_GLOBS),
        include_canonical=False,
    )
    found = {t.name for t in targets}
    assert "CTO_CHANNEL.md" not in found, "--no-canonical no excluyó CTO_CHANNEL.md"
    assert ".cto_input_188.md" not in found, "--no-canonical no excluyó .cto_input_188.md"


def test_explicit_paths_scan_canonical_independently_of_scope():
    """Pasar rutas explícitas de los canónicos siempre las escanea (comportamiento
    heredado del canal de co-firma, reforzado por t_565b1493)."""
    with tempfile.TemporaryDirectory() as d:
        canonical = Path(d) / "CTO_CHANNEL.md"
        canonical.write_text(
            "# Canal CTO\nwebhook SOAR egress RFC1918 bloqueado por defecto.\n", encoding="utf-8"
        )
        targets = _linter.resolve_targets(
            [str(canonical)],
            list(_linter.DEFAULT_SKIP_GLOBS),
            include_canonical=False,  # ni siquiera pidieron canonical
        )
        assert any(t.name == "CTO_CHANNEL.md" for t in targets), \
            "ruta explícita de canónico debe escanearse aunque include_canonical=False"
