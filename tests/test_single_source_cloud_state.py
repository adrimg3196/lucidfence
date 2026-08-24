"""Fuente única de la vitrina: la URL y el esquema no pueden derivar.

La familia de fallos de 2026-08-20 (monitor con URL vieja, health-check con
esquema viejo) ocurrió porque cada superficie llevaba su copia. Este test la
cierra estructuralmente: (a) TODA referencia a la URL del snapshot en el repo
debe ser LA canónica de scripts/check_vitrina.py; (b) los workflows de salud
no llevan checks inline de la vitrina — llaman al checker; (c) el esquema del
checker ES el del publisher (importado, no copiado).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from scripts.check_vitrina import CANONICAL_URL  # noqa: E402
from lucidfence.core.cloud_publisher import PUBLISHED_REQUIRED_KEYS  # noqa: E402

_SURFACES = (".github/workflows", "scripts", "static", "lucidfence", "tests")
_URL_RE = re.compile(r"https://raw\.githubusercontent\.com/[^\s\"')]+cloud_state\.json")


def _walk_files():
    for base in _SURFACES:
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, base)):
            for f in files:
                if f.endswith((".py", ".js", ".html", ".yml", ".yaml", ".sh")):
                    yield os.path.join(dirpath, f)


def test_every_cloud_state_url_is_the_canonical_one():
    offenders = []
    for path in _walk_files():
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for url in _URL_RE.findall(fh.read()):
                if url != CANONICAL_URL:
                    offenders.append(f"{os.path.relpath(path, ROOT)} -> {url}")
    assert not offenders, "URLs de vitrina fuera de la canónica: " + "; ".join(offenders)


def test_cloud_html_uses_canonical_url():
    # The vitrina state URL now lives in static/cloud.js (the inline script was
    # externalized so cloud.html can be served with a strict CSP, no 'unsafe-inline').
    js = open(os.path.join(ROOT, "static", "cloud.js"), encoding="utf-8").read()
    m = re.search(r'const STATE_URL = "([^"]+)"', js)
    assert m and m.group(1) == CANONICAL_URL


def test_health_workflows_delegate_to_single_checker():
    for wf in ("nightly-health-check.yml", "monitor-hourly.yml"):
        text = open(os.path.join(ROOT, ".github", "workflows", wf), encoding="utf-8").read()
        assert "scripts/check_vitrina.py" in text, f"{wf} no usa el checker único"
        # sin copias inline del check de esquema
        assert "json.load(sys.stdin)" not in text, f"{wf} lleva un check inline duplicado"


def test_checker_schema_is_publisher_contract():
    # el checker importa las claves del publisher: mismo objeto, no copia
    import scripts.check_vitrina as cv
    assert cv.PUBLISHED_REQUIRED_KEYS is PUBLISHED_REQUIRED_KEYS
    assert set(PUBLISHED_REQUIRED_KEYS) >= {"devices", "fences", "generated_at", "service"}
