"""Silenciar un test es una decisión con fecha de caducidad, no un borrado.

Por qué existe este guard. El 2026-08-24 dos agentes de la flota trabajaban a la
vez sobre el mismo sintoma y en direcciones opuestas:

  - una PR arreglaba el bug REAL (los componentes P-256 del JWK se serializaban
    con longitud minima en vez de los 32 bytes fijos que exige RFC 7518; el
    1,10% de las claves generadas salia invalida);
  - otra PR metia ese mismo test en una lista de "conocidos-flaky" para que el
    monitor horario **ignorara sus fallos**.

Si la segunda hubiera entrado sola, el repo habria dejado de ver un defecto real
en produccion y el correo de fallos habria callado sin que nada estuviera
arreglado. Eso es exactamente el falso verde que este repo no admite.

Una lista de cuarentena es una herramienta legitima —aisla un test de
infraestructura genuinamente inestable mientras aterriza su arreglo— pero solo
si NO PUEDE PUDRIRSE. Este fichero le pone los tres frenos que le faltaban:

  1. cada entrada dice QUIEN la puso, POR QUE y HASTA CUANDO;
  2. una entrada caducada rompe la suite (el silencio no se hereda);
  3. un test en cuarentena que vuelve a pasar rompe la suite (se sale solo).

El guard es inerte mientras no exista `tests/QUARANTINE.txt`: no obliga a
adoptar el mecanismo, solo impide usarlo a ciegas.

Ejecuta: python3 tests/run_tests.py
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

QUARANTINE = ROOT / "tests" / "QUARANTINE.txt"

# entrada valida:  test_x.py  # owner=@quien motivo=... caduca=YYYY-MM-DD issue=#123
_OWNER = re.compile(r"owner=(\S+)")
_CADUCA = re.compile(r"caduca=(\d{4}-\d{2}-\d{2})")
_ISSUE = re.compile(r"issue=#?(\d+)")
_MAX_DIAS = 30


def _entradas() -> list[tuple[int, str, str]]:
    """[(nlinea, fichero_de_test, comentario)] de QUARANTINE.txt."""
    if not QUARANTINE.exists():
        return []
    out = []
    for n, linea in enumerate(QUARANTINE.read_text(encoding="utf-8").splitlines(), 1):
        s = linea.strip()
        if not s or s.startswith("#"):
            continue
        fichero, _, comentario = s.partition("#")
        out.append((n, fichero.strip(), comentario.strip()))
    return out


def test_cada_entrada_declara_duenno_motivo_caducidad_e_issue():
    """Sin dueño ni fecha, 'temporal' significa 'para siempre'."""
    for n, fichero, comentario in _entradas():
        falta = []
        if not _OWNER.search(comentario):
            falta.append("owner=@usuario")
        if not _CADUCA.search(comentario):
            falta.append("caduca=YYYY-MM-DD")
        if not _ISSUE.search(comentario):
            falta.append("issue=#N")
        assert not falta, (
            f"QUARANTINE.txt:{n} ({fichero}) silencia un test sin {', '.join(falta)}. "
            f"Formato: '{fichero}  # owner=@quien motivo=... caduca=YYYY-MM-DD issue=#N'")


def test_ninguna_cuarentena_esta_caducada():
    """El silencio no se hereda: pasada la fecha, la suite vuelve a romper."""
    hoy = datetime.date.today()
    for n, fichero, comentario in _entradas():
        m = _CADUCA.search(comentario)
        if not m:
            continue  # ya lo cubre el test anterior
        caduca = datetime.date.fromisoformat(m.group(1))
        assert caduca >= hoy, (
            f"QUARANTINE.txt:{n}: la cuarentena de {fichero} caduco el {caduca}. "
            f"O se arregla el test, o se renueva la entrada explicando por que "
            f"sigue rota — pero no se queda callada sola.")
        assert (caduca - hoy).days <= _MAX_DIAS, (
            f"QUARANTINE.txt:{n}: {fichero} silenciado hasta {caduca}, mas de "
            f"{_MAX_DIAS} dias. Una cuarentena larga es un borrado con otro nombre.")


def test_el_fichero_en_cuarentena_existe():
    """Una entrada que no apunta a nada real solo estorba."""
    for n, fichero, _ in _entradas():
        candidatos = [ROOT / "tests" / fichero, ROOT / fichero]
        assert any(c.exists() for c in candidatos), (
            f"QUARANTINE.txt:{n}: {fichero} no existe; borra la entrada.")


def test_un_test_en_cuarentena_que_ya_pasa_sale_de_la_lista():
    """El caso que motivo este guard.

    Si el test silenciado vuelve a pasar de forma estable, seguir ignorandolo
    deja al repo ciego ante la proxima regresion DE VERDAD en esa zona. Se sale
    solo de la cuarentena: la suite obliga.
    """
    import importlib.util

    for n, fichero, _ in _entradas():
        ruta = next((c for c in (ROOT / "tests" / fichero, ROOT / fichero) if c.exists()), None)
        if ruta is None:
            continue  # lo cubre test_el_fichero_en_cuarentena_existe
        spec = importlib.util.spec_from_file_location(f"_q_{ruta.stem}", ruta)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            continue  # no importa ni en local: la cuarentena esta justificada

        fallo = False
        for nombre in dir(mod):
            if not nombre.startswith("test_"):
                continue
            try:
                getattr(mod, nombre)()
            except Exception:
                fallo = True
                break
        assert fallo, (
            f"QUARANTINE.txt:{n}: {fichero} PASA entero en este entorno. Un test "
            f"que ya funciona no puede seguir silenciado: sacalo de la lista o "
            f"documenta en el issue por que solo falla en CI.")
