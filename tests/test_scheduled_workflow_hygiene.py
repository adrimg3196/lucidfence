"""Higiene de los workflows programados: los únicos que escriben al propietario.

GitHub manda un correo al dueño del repo cuando falla un workflow disparado por
`schedule`. Los demás fallan en una PR y se ven en la PR. Por eso los crons son
la superficie que hay que cuidar: cada defecto suyo se convierte en correo.

Este guard fija lo mínimo comprobable, con la causa real detrás de cada regla:

  1. `concurrency` — un cron sin él puede solaparse consigo mismo. `engine-cron`
     corre cada 15 min: dos ciclos a la vez se pelean por la misma rama de datos
     y ambos fallan. Un fallo se convierte en dos.
  2. `timeout-minutes` — sin él, un cuelgue ocupa un runner hasta el límite de
     6 h de GitHub, y el siguiente ciclo se apila detrás.
  3. Ningún `|| true` sobre `git fetch`/`git ls-remote` — el patrón que motivó
     este fichero: `engine-cron` hacía `git fetch ... || true` y, si el fetch
     fallaba por red, tomaba la rama del `else` y creaba una rama HUÉRFANA cuyo
     push se rechazaba por non-fast-forward. Un parpadeo de red acababa
     disfrazado de problema de historia de git, con un mensaje que no apuntaba
     a la causa. Tragarse el error de una consulta remota y seguir como si nada
     es falso verde con otro nombre.

Lo que este guard NO hace: no opina sobre qué debe comprobar cada cron ni
prohíbe que fallen. Un cron que detecta un problema real DEBE fallar; el correo
entonces está ganado.

Ejecuta: python3 tests/run_tests.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WORKFLOWS = ROOT / ".github" / "workflows"


def _programados() -> list[tuple[str, str]]:
    """[(nombre, texto)] de los workflows con disparador `schedule:`."""
    out = []
    for p in sorted(WORKFLOWS.glob("*.yml")):
        texto = p.read_text(encoding="utf-8")
        if re.search(r"^\s*schedule:\s*$", texto, re.M):
            out.append((p.name, texto))
    return out


def test_hay_workflows_programados_que_auditar():
    """Si esto falla, el guard esta mirando al sitio equivocado."""
    assert _programados(), "no se encontro ningun workflow con `schedule:`"


def test_cada_cron_declara_concurrency():
    for nombre, texto in _programados():
        assert re.search(r"^concurrency:", texto, re.M), (
            f"{nombre} es un cron sin `concurrency`: dos ejecuciones pueden "
            f"solaparse y multiplicar el mismo fallo en correos.")


def test_cada_cron_declara_timeout():
    for nombre, texto in _programados():
        assert "timeout-minutes:" in texto, (
            f"{nombre} es un cron sin `timeout-minutes`: un cuelgue ocupa un "
            f"runner hasta el limite de 6 h y apila los ciclos siguientes.")


def test_ningun_cron_se_traga_el_error_de_una_consulta_remota():
    """`git fetch ... || true` fue el origen de un fallo que mentía sobre su causa."""
    patron = re.compile(r"git\s+(fetch|ls-remote)[^\n|]*\|\|\s*true")
    for nombre, texto in _programados():
        m = patron.search(texto)
        assert not m, (
            f"{nombre}: `{m.group(0).strip()}` se traga el fallo de una consulta "
            f"remota. Distingue 'la rama no existe' de 'no he podido preguntar' "
            f"(git ls-remote --exit-code: RC=2 vs otro) y aborta en el segundo caso.")


def test_los_scripts_que_publican_ramas_de_datos_tampoco_lo_hacen():
    """El mismo patrón vivía duplicado en el script que usa recon-social-cron."""
    patron = re.compile(r"git\s+(fetch|ls-remote)[^\n|]*\|\|\s*true")
    for p in sorted((ROOT / "scripts").glob("*.sh")):
        m = patron.search(p.read_text(encoding="utf-8"))
        assert not m, (
            f"scripts/{p.name}: `{m.group(0).strip()}` se traga el fallo de una "
            f"consulta remota y puede acabar creando una rama huerfana.")
