"""La landing no puede vender como incluida una IA que vive fuera del repo.

``lucidfence/core/ai.py`` solo habla con un servidor MoA local externo
(127.0.0.1:8085) que no forma parte de LucidFence; el motor de riesgo no lo
necesita. Un claim "IA local (MoA)" como feature del producto es un falso verde
de marketing (riesgo #110): la portada debe decir que la IA es opcional.
"""
import os
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INDEX = ROOT / "static" / "index.html"


def test_landing_does_not_claim_bundled_moa_ai():
    text = INDEX.read_text(encoding="utf-8")
    for forbidden in ("Mixture-of-Agents", "IA local (MoA)", "MoA, modo libre"):
        assert forbidden not in text, f"claim no honesto en la landing: {forbidden!r}"


def test_landing_states_ai_is_optional():
    text = INDEX.read_text(encoding="utf-8")
    assert "Sin IA obligatoria" in text
    assert "/api/ai/support" in text
    assert "sin IA ni API externa" in text
